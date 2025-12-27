"""
LangGraph Supervisor for Email Agent.

This module implements the supervisor pattern that routes user requests to
specialized agents (Inbox, Draft, Send, Organization) based on intent.

Architecture:
- Supervisor: Analyzes user intent and routes to appropriate agent
- InboxAgent: Handles read operations (fetch, query, list)
- DraftAgent: Handles draft composition and management
- SendAgent: Handles immediate email sending
- OrganizationAgent: Handles inbox organization (move, delete spam)
"""

import os
import re
import json
import logging
from typing import Literal, Optional, Any
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from .state import EmailAgentState, create_initial_state, DraftPendingInfo
from .tools import (
    create_inbox_tools,
    create_draft_tools,
    create_send_tools,
    create_organization_tools,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Agent Prompts
# =============================================================================

SUPERVISOR_PROMPT = """You are a supervisor routing email requests to specialized agents.

Analyze the user's message and decide which agent should handle it:

AGENTS:
- "inbox": For reading/fetching/searching emails, listing accounts, viewing drafts
  Keywords: show, list, fetch, get, read, search, query, find, check, inbox, emails from

- "draft": For creating, editing, updating, or deleting email drafts
  Keywords: draft, compose, write, create email, edit draft, update draft, delete draft

- "send": For sending emails immediately (not drafts) or confirming draft sends
  Keywords: send, send email now, send immediately, confirm send

- "organization": For organizing inbox (moving emails, deleting spam)
  Keywords: move, organize, delete spam, clean up, label, folder

- "human": When you need clarification or the request is ambiguous

- "__end__": For greetings, general questions, or when you can answer directly

RULES:
1. Route to ONE agent only
2. If user is responding to a pending operation (yes/no, email address, number), check context
3. For draft creation, ALWAYS route to "draft" agent first
4. For "send the email" after draft creation, route to "send"

Respond with ONLY the agent name: inbox, draft, send, organization, human, or __end__
"""

DRAFT_AGENT_PROMPT = """You are a specialized email drafting assistant.

Your capabilities:
1. Create new email drafts
2. Update existing drafts with natural language instructions
3. Delete drafts
4. Help compose professional emails

CRITICAL RULES FOR DRAFT CREATION:
1. ALWAYS ask the user how they want to proceed before creating a draft
2. If user only provides recipient - ask what the email should be about
3. If user provides context but NO recipient - ask for recipient email address
4. If user says "generate it yourself" or "auto" - create subject and body from context
5. ALWAYS ask for user preference: auto-complete with AI or provide manually
6. ALWAYS confirm after creating: "Draft created to [email] with subject '[subject]'"

For updating drafts:
- Use the update_draft tool with the recipient email and instruction
- The tool will use AI to intelligently modify the draft

Always be professional and helpful.
"""

INBOX_AGENT_PROMPT = """You are a specialized email reading assistant.

Your capabilities:
1. Fetch emails with various filters (sender, date, label, importance)
2. Search emails with natural language queries
3. List connected email accounts
4. View all drafts or drafts for specific recipients
5. Summarize emails from specific time periods

RESPONSE FORMAT:
- For fetch_emails: Display emails in a structured card format (see below)
- For query_emails: Present results conversationally with key highlights
- For summarize_emails: Extract the summary text from JSON and present it conversationally
- Always mention the count of emails found
- Highlight important emails, meetings, and action items

CRITICAL: EMAIL DISPLAY FORMAT
When displaying a list of emails, use this exact structured format:

# Email #1

From: sender@example.com
Subject: Email subject here
Date: 2025-04-10T08:42:22Z
⭐ Important

Body:
Email content here...

---

# Email #2

From: another@example.com
Subject: Another subject
Date: 2025-04-10T09:15:30Z

Body:
Another email content...

---

Rules for email display:
1. Number each email (Email #1, Email #2, etc.)
2. Always include: From, Subject, Date, and Body sections
3. Add "⭐ Important" badge if the email has ml_prediction="important" or is_important=true
4. Separate each email with "---"
5. Keep body content concise (first 200-300 characters)

CRITICAL RULES FOR EMAIL SUMMARIES:
When user asks to "summarize my emails" or "create a summary":
1. Use the summarize_emails tool with appropriate time_period
2. Extract the summary text from JSON and present it conversationally
3. Present it conversationally to the user - DO NOT show raw JSON
4. Common time periods: "today", "yesterday", "last_week", "last_month"

5. If user mentions "important", set importance=True

Examples:
- "summarize my emails" → summarize_emails(time_period="today")
- "summary of important emails this week" → summarize_emails(time_period="last_week", importance=True)
- "what did I get yesterday" → summarize_emails(time_period="yesterday")

Be concise but informative.
"""

SEND_AGENT_PROMPT = """You are a specialized email sending assistant.

Your capabilities:
1. Send emails immediately (not as drafts)
2. Confirm and send existing drafts

CRITICAL RULES:
1. ALWAYS ask for confirmation before sending: "Are you sure you want to send this email?"
2. If user confirms with "yes" - proceed with sending
3. If user says "no" - cancel the operation
4. After sending, confirm success: "Email sent to [recipient]!"

Be careful - sending is irreversible!
"""


# =============================================================================
# LLM Initialization
# =============================================================================

def get_llm(model_name: Optional[str] = None, temperature: float = 0.3):
    """
    Get configured LLM instance with proper settings.

    Now supports Gemini 3 models with thought_signature handling via langchain-google-genai 2.x.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found!")

    # Use environment variable or default to gemini-2.5-flash
    # Gemini 3 models (gemini-3-pro-preview) are supported with the updated SDK
    model = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    logger.info(f"[LLM] Initializing model: {model}")

    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=temperature,
        convert_system_message_to_human=True,  # Required for some models
    )


# =============================================================================
# Node Functions
# =============================================================================

def supervisor_node(state: EmailAgentState) -> dict:
    """
    Supervisor node that analyzes intent and routes to appropriate agent.
    """
    logger.info(f"[SUPERVISOR] Processing: {state.get('current_input', '')[:100]}")

    current_input = state.get("current_input", "").strip()

    # Check for "reply N" pattern FIRST (before pending checks)
    reply_match = re.match(r'^reply\s*(?:to\s*)?(?:email\s*)?#?(\d+)$', current_input, re.IGNORECASE)
    if reply_match:
        email_number = int(reply_match.group(1))
        listed_emails = state.get("listed_emails")

        if not listed_emails or not listed_emails.get("emails"):
            return {
                "response": "No emails are currently listed. Please fetch your emails first (e.g., 'show my emails').",
                "next_agent": "__end__",
            }

        emails = listed_emails["emails"]
        if email_number < 1 or email_number > len(emails):
            return {
                "response": f"Invalid email number. Please choose between 1 and {len(emails)}.",
                "next_agent": "__end__",
            }

        email = emails[email_number - 1]
        body_preview = email.get('body', '')[:500]
        if len(email.get('body', '')) > 500:
            body_preview += '...'

        preview = f"""**Email #{email_number}:**
**From:** {email.get('sender', 'Unknown')}
**Subject:** {email.get('subject', '(No subject)')}
**Date:** {email.get('date', 'Unknown')}

{body_preview}

---
What would you like to reply?
*Type your message or say 'generate it for me' to have AI write a reply.*"""

        return {
            "response": preview,
            "next_agent": "__end__",
            "draft_pending": DraftPendingInfo(
                awaiting="reply_content",
                reply_to_email=email,
            ),
        }

    # Check for pending operations that need specific routing
    if state.get("draft_pending"):
        pending = state["draft_pending"]
        awaiting = pending.get("awaiting")

        # Handle pending draft operations
        if awaiting == "recipient":
            return {"next_agent": "draft"}
        elif awaiting == "ai_generation_choice":
            return {"next_agent": "draft"}
        elif awaiting == "subject_and_body":
            return {"next_agent": "draft"}
        elif awaiting == "update_instruction":
            return {"next_agent": "draft"}
        elif awaiting == "reply_content":
            return {"next_agent": "draft"}
        elif awaiting == "confirmation":
            user_input = state.get("current_input", "").lower().strip()
            if user_input in ["yes", "y"]:
                return {"next_agent": "send"}
            elif user_input in ["no", "n"]:
                return {
                    "next_agent": "__end__",
                    "response": "Operation cancelled.",
                    "draft_pending": None,
                }
        elif awaiting == "selection":
            return {"next_agent": "draft"}

    if state.get("account_selection"):
        return {"next_agent": "inbox"}

    # Use LLM to determine routing
    try:
        llm = get_llm(temperature=0.1)

        # Build context from recent messages
        recent_messages = state.get("messages", [])[-5:]
        context_str = ""
        if recent_messages:
            context_str = "\n".join([
                f"{m.get('role', 'user')}: {m.get('content', '')[:200]}"
                for m in recent_messages
            ])

        routing_prompt = f"""{SUPERVISOR_PROMPT}

Recent context:
{context_str}

Current message: {state.get('current_input', '')}

Route to:"""

        response = llm.invoke(routing_prompt)
        route = response.content.strip().lower().replace('"', '').replace("'", "")

        # Validate route
        valid_routes = ["inbox", "draft", "send", "organization", "human", "__end__"]
        if route not in valid_routes:
            # Default routing based on keywords
            current_input = state.get("current_input", "").lower()
            if any(kw in current_input for kw in ["draft", "compose", "write email", "create email"]):
                route = "draft"
            elif any(kw in current_input for kw in ["send", "mail now"]):
                route = "send"
            elif any(kw in current_input for kw in ["show", "list", "fetch", "get", "inbox", "email"]):
                route = "inbox"
            elif any(kw in current_input for kw in ["move", "spam", "organize"]):
                route = "organization"
            else:
                route = "__end__"

        logger.info(f"[SUPERVISOR] Routing to: {route}")
        return {"next_agent": route}

    except Exception as e:
        logger.error(f"[SUPERVISOR] Routing error: {e}")
        # Fallback to keyword-based routing
        current_input = state.get("current_input", "").lower()
        if "draft" in current_input:
            return {"next_agent": "draft"}
        elif "send" in current_input:
            return {"next_agent": "send"}
        elif any(kw in current_input for kw in ["show", "list", "fetch", "inbox"]):
            return {"next_agent": "inbox"}
        return {"next_agent": "__end__"}


def inbox_agent_node(state: EmailAgentState) -> dict:
    """
    Inbox Agent: Handles email reading/fetching operations.
    """
    logger.info("[INBOX_AGENT] Processing request")

    try:
        llm = get_llm()
        tools = create_inbox_tools(user_id=state.get("user_id"))
        llm_with_tools = llm.bind_tools(tools)

        messages = [
            SystemMessage(content=INBOX_AGENT_PROMPT),
            HumanMessage(content=state.get("current_input", "")),
        ]

        response = llm_with_tools.invoke(messages)

        # Handle tool calls
        if response.tool_calls:
            tool_results = []
            fetched_emails = None  # Track fetched emails for reply-by-number feature

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                logger.info(f"[INBOX_AGENT] Calling tool: {tool_name} with args: {tool_args}")

                # Find and execute the tool
                for tool in tools:
                    if tool.name == tool_name:
                        result = tool.invoke(tool_args)
                        tool_results.append(result)

                        # Extract emails from fetch_emails for reply-by-number feature
                        if tool_name == "fetch_emails":
                            try:
                                json_str = result
                                if "```json" in result:
                                    json_str = result.split("```json")[1].split("```")[0].strip()
                                parsed_emails = json.loads(json_str)
                                if isinstance(parsed_emails, list) and parsed_emails:
                                    fetched_emails = parsed_emails
                                    logger.info(f"[INBOX_AGENT] Stored {len(fetched_emails)} emails for reply-by-number")
                            except Exception as parse_err:
                                logger.warning(f"[INBOX_AGENT] Could not parse emails for storage: {parse_err}")
                        break

            # Generate response with tool results
            if tool_results:
                follow_up_messages = messages + [
                    AIMessage(content=response.content or "", tool_calls=response.tool_calls),
                    HumanMessage(content=f"Tool results: {tool_results[0]}")
                ]
                final_response = llm.invoke(follow_up_messages)

                # Ensure JSON blocks are preserved for fetch_emails
                response_content = final_response.content
                for result in tool_results:
                    if "```json" in result and "```json" not in response_content:
                        response_content = f"{response_content}\n\n{result}"

                # Add hint for reply-by-number if emails were fetched
                if fetched_emails:
                    response_content = f"{response_content}\n\n*Reply to any email by saying 'reply 1', 'reply 2', etc.*"

                result_dict = {
                    "response": response_content,
                    "next_agent": "__end__",
                    "last_tool_result": {"results": tool_results},
                }

                # Store listed emails for reply-by-number feature
                if fetched_emails:
                    result_dict["listed_emails"] = {
                        "emails": fetched_emails,
                        "listed_at": datetime.now().isoformat(),
                    }

                return result_dict

        return {
            "response": response.content or "I couldn't process that request.",
            "next_agent": "__end__",
        }

    except Exception as e:
        logger.error(f"[INBOX_AGENT] Error: {e}")
        return {
            "response": f"Error processing inbox request: {str(e)}",
            "next_agent": "__end__",
            "error": str(e),
        }


def draft_agent_node(state: EmailAgentState) -> dict:
    """
    Draft Agent: Handles draft creation and management.

    Implements interactive draft flow:
    - If recipient missing -> ask for it
    - If subject/body missing firstly -> ask for it and if the user wants to auto-generate create the subject and the body for the user 
    - Otherwise ask for missing info
    """
    logger.info("[DRAFT_AGENT] Processing request")

    try:
        llm = get_llm()
        tools = create_draft_tools(user_id=state.get("user_id"), llm=llm)
        llm_with_tools = llm.bind_tools(tools)

        current_input = state.get("current_input", "")
        pending = state.get("draft_pending")

        # Handle pending draft completion
        if pending:
            awaiting = pending.get("awaiting")

            if awaiting == "ai_generation_choice":
                user_input_lower = current_input.strip().lower()

                # Parse user choice
                choice = None
                if user_input_lower in ["1", "auto", "auto-complete", "auto-complete with ai", "ai", "generate"]:
                    choice = "auto"
                elif user_input_lower in ["2", "manual", "manually", "i'll provide", "provide manually", "i'll provide subject and body manually"]:
                    choice = "manual"
                elif user_input_lower in ["3", "cancel"]:
                    choice = "cancel"

                # Invalid choice - re-prompt
                if choice is None:
                    return {
                        "response": (
                            "I didn't understand that choice. Please reply with:\n"
                            "1 (or 'auto') - to auto-complete with AI\n"
                            "2 (or 'manual') - to provide subject and body manually\n"
                            "3 (or 'cancel') - to cancel"
                        ),
                        "next_agent": "__end__",
                    }

                # Handle CANCEL
                if choice == "cancel":
                    return {
                        "response": "Draft creation cancelled.",
                        "next_agent": "__end__",
                        "draft_pending": None,
                    }

                # Handle AUTO-COMPLETE
                if choice == "auto":
                    recipient = pending.get("recipient")
                    context_hint = pending.get("context_hint", "")

                    # Generate subject and body using LLM
                    generation_prompt = f"""Generate a professional email subject and body based on this context:
Context: {context_hint or 'General email'}

Recipient: {recipient}

Return ONLY a JSON object with this exact format:
{{"subject": "...", "body": "..."}}

Make it professional, clear, and appropriate. The body should include:
- Appropriate greeting
- Clear main content
- Professional closing"""

                    try:
                        gen_response = llm.invoke(generation_prompt)
                        import re
                        json_match = re.search(r'\{[^}]+\}', gen_response.content, re.DOTALL)
                        if json_match:
                            generated = json.loads(json_match.group())
                            subject = generated.get("subject", "")
                            body = generated.get("body", "")
                        else:
                            # Fallback
                            subject = f"Email regarding {context_hint[:50]}" if context_hint else "Email"
                            body = f"Dear recipient,\n\n{context_hint}\n\nBest regards"
                    except Exception as e:
                        logger.warning(f"Auto-generation failed: {e}")
                        subject = f"Email regarding {context_hint[:50]}" if context_hint else "Email"
                        body = f"Dear recipient,\n\n{context_hint}\n\nBest regards"

                    # Create the draft
                    for tool in tools:
                        if tool.name == "create_draft":
                            result = tool.invoke({
                                "recipient": recipient,
                                "subject": subject,
                                "body": body,
                            })
                            result_dict = json.loads(result)

                            if result_dict.get("success"):
                                return {
                                    "response": f"Draft created to {recipient} with subject '{subject}'",
                                    "next_agent": "__end__",
                                    "draft_pending": None,
                                }
                            else:
                                return {
                                    "response": f"Failed to create draft: {result_dict.get('message', 'Unknown error')}",
                                    "next_agent": "__end__",
                                    "draft_pending": None,
                                }

                # Handle MANUAL input request
                if choice == "manual":
                    return {
                        "response": (
                            "Please provide the subject and body for your email.\n\n"
                            "Format your response as:\n"
                            "Subject: [your subject line]\n"
                            "Body: [your email body]"
                        ),
                        "draft_pending": DraftPendingInfo(
                            awaiting="subject_and_body",
                            recipient=pending.get("recipient"),
                            context_hint=pending.get("context_hint"),
                            auto_generate=False,
                        ),
                        "next_agent": "__end__",
                    }

            elif awaiting == "subject_and_body":
                user_input = current_input.strip()

                # Parse subject and body from user input
                subject = ""
                body = ""

                # Try to extract using the format "Subject: ... Body: ..."
                import re
                subject_match = re.search(r'subject:\s*(.+?)(?=body:|$)', user_input, re.IGNORECASE | re.DOTALL)
                body_match = re.search(r'body:\s*(.+)', user_input, re.IGNORECASE | re.DOTALL)

                if subject_match:
                    subject = subject_match.group(1).strip()
                if body_match:
                    body = body_match.group(1).strip()

                # Validation: both must be provided
                if not subject or not body:
                    return {
                        "response": (
                            "I couldn't parse the subject and body. Please make sure to use this format:\n\n"
                            "Subject: Your subject line here\n"
                            "Body: Your email body here\n\n"
                            "Both subject and body are required."
                        ),
                        "next_agent": "__end__",
                    }

                # Create the draft with manual input
                recipient = pending.get("recipient")
                for tool in tools:
                    if tool.name == "create_draft":
                        result = tool.invoke({
                            "recipient": recipient,
                            "subject": subject,
                            "body": body,
                        })
                        result_dict = json.loads(result)

                        if result_dict.get("success"):
                            return {
                                "response": f"Draft created to {recipient} with subject '{subject}'",
                                "next_agent": "__end__",
                                "draft_pending": None,
                            }
                        else:
                            return {
                                "response": f"Failed to create draft: {result_dict.get('message', 'Unknown error')}",
                                "next_agent": "__end__",
                                "draft_pending": None,
                            }

            elif awaiting == "recipient":
                # User provided recipient email
                email_input = current_input.strip()
                if "@" not in email_input or "." not in email_input.split("@")[-1]:
                    return {
                        "response": f"'{email_input}' doesn't look like a valid email address.\nPlease provide a valid email (e.g., john@example.com)",
                        "next_agent": "__end__",
                    }

                # Create the draft with the provided email
                subject = pending.get("subject", "")
                body = pending.get("body", "")
                context_hint = pending.get("context_hint", "")

                # If subject/body empty but have context, auto-generate
                if (not subject or not body) and (context_hint or pending.get("auto_generate")):
                    generation_prompt = f"""Generate an email subject and body based on this context:
Context: {context_hint or 'General email'}

Recipient: {email_input}

Return JSON format:
{{"subject": "...", "body": "..."}}

Make it professional and appropriate."""
                    try:
                        gen_response = llm.invoke(generation_prompt)
                        import re
                        json_match = re.search(r'\{[^}]+\}', gen_response.content, re.DOTALL)
                        if json_match:
                            generated = json.loads(json_match.group())
                            subject = generated.get("subject", subject)
                            body = generated.get("body", body)
                    except Exception as e:
                        logger.warning(f"Auto-generation failed: {e}")

                # Call create_draft tool
                for tool in tools:
                    if tool.name == "create_draft":
                        result = tool.invoke({
                            "recipient": email_input,
                            "subject": subject,
                            "body": body,
                        })
                        result_dict = json.loads(result)

                        if result_dict.get("success"):
                            return {
                                "response": f"Draft created to {email_input} with subject '{subject}'",
                                "next_agent": "__end__",
                                "draft_pending": None,
                            }
                        else:
                            return {
                                "response": f"Failed to create draft: {result_dict.get('message', 'Unknown error')}",
                                "next_agent": "__end__",
                                "draft_pending": None,
                            }

            elif awaiting == "update_instruction":
                # User provided update instruction for a selected draft
                update_instruction = current_input.strip()
                drafts_list = pending.get("drafts_list", [])

                if not drafts_list:
                    return {
                        "response": "❌ No draft selected. Please try again.",
                        "next_agent": "__end__",
                        "draft_pending": None,
                    }

                selected = drafts_list[0]
                draft_id = selected.get("id")
                subject = selected.get("subject", "(No subject)")

                # Call update_draft tool
                for tool in tools:
                    if tool.name == "update_draft":
                        result = tool.invoke({
                            "draft_id": draft_id,
                            "instruction": update_instruction,
                        })
                        result_dict = json.loads(result)

                        if result_dict.get("success"):
                            new_body = result_dict.get("draft", {}).get("body", "")
                            return {
                                "response": f"✅ Draft updated: '{subject}'\n\nNew body:\n{new_body[:200]}...",
                                "next_agent": "__end__",
                                "draft_pending": None,
                            }
                        else:
                            return {
                                "response": f"❌ Failed to update draft: {result_dict.get('message', 'Unknown error')}",
                                "next_agent": "__end__",
                                "draft_pending": None,
                            }

            elif awaiting == "reply_content":
                # User provided reply content for a numbered email
                original_email = pending.get("reply_to_email", {})
                reply_content = current_input.strip()

                # Check if user wants AI to generate the reply
                auto_generate_keywords = ["generate", "write it", "auto", "yourself", "for me", "create it"]
                if any(kw in reply_content.lower() for kw in auto_generate_keywords):
                    # Use LLM to generate reply based on original email
                    generation_prompt = f"""Generate a professional reply to this email:

From: {original_email.get('sender', 'Unknown')}
Subject: {original_email.get('subject', '')}
Body: {original_email.get('body', '')[:1000]}

Write a brief, professional reply. Return ONLY the reply text, no subject line or greeting like 'Here is a reply'."""

                    try:
                        gen_response = llm.invoke(generation_prompt)
                        reply_content = gen_response.content.strip()
                        logger.info(f"[DRAFT_AGENT] AI generated reply: {reply_content[:100]}...")
                    except Exception as gen_err:
                        logger.error(f"[DRAFT_AGENT] Reply generation failed: {gen_err}")
                        return {
                            "response": "Failed to generate reply. Please type your message manually.",
                            "next_agent": "__end__",
                        }

                if not reply_content:
                    return {
                        "response": "What would you like to reply?\n\n*You can type your message or say 'generate it for me' to have AI write a reply.*",
                        "next_agent": "__end__",
                    }

                # Extract recipient email from sender
                sender = original_email.get("sender", "")
                recipient = sender
                if "<" in sender and ">" in sender:
                    recipient = sender.split("<")[1].split(">")[0].strip()

                # Create subject with Re: prefix (avoid duplicate)
                original_subject = original_email.get("subject", "")
                if original_subject.lower().startswith("re:"):
                    subject = original_subject
                else:
                    subject = f"Re: {original_subject}"

                # Create draft using existing tool
                for tool in tools:
                    if tool.name == "create_draft":
                        result = tool.invoke({
                            "recipient": recipient,
                            "subject": subject,
                            "body": reply_content,
                        })
                        result_dict = json.loads(result)

                        if result_dict.get("success"):
                            return {
                                "response": f"Reply draft created!\n\n**To:** {recipient}\n**Subject:** {subject}\n\n**Your reply:**\n{reply_content}\n\nWould you like to send it? (Yes/No)",
                                "next_agent": "__end__",
                                "draft_pending": DraftPendingInfo(
                                    awaiting="confirmation",
                                    recipient=recipient,
                                    drafts_list=[result_dict],
                                    operation="send",
                                ),
                            }
                        else:
                            return {
                                "response": f"Failed to create reply draft: {result_dict.get('message', 'Unknown error')}",
                                "next_agent": "__end__",
                                "draft_pending": None,
                            }

            elif awaiting == "selection":
                # User selected a draft number
                if current_input.strip().isdigit():
                    selection = int(current_input.strip())
                    drafts = pending.get("drafts_list", [])
                    if 1 <= selection <= len(drafts):
                        selected = drafts[selection - 1]
                        operation = pending.get("operation")

                        if operation == "send":
                            return {
                                "response": f"Are you sure you want to send '{selected.get('subject', '(No subject)')}'?\n\nReply with 'Yes' or 'No'",
                                "draft_pending": DraftPendingInfo(
                                    awaiting="confirmation",
                                    recipient=selected.get("recipient"),
                                    drafts_list=[selected],
                                    operation="send",
                                ),
                                "next_agent": "__end__",
                            }

                        # Handle DELETE operation
                        elif operation == "delete":
                            draft_id = selected.get("id")
                            subject = selected.get("subject", "(No subject)")

                            # Delete the draft
                            from email_tools import delete_draft
                            result = delete_draft(draft_id=draft_id, user_id=state.get("user_id"))

                            if result.get("success"):
                                return {
                                    "response": f"✅ Draft deleted: '{subject}'",
                                    "next_agent": "__end__",
                                    "draft_pending": None,
                                }
                            else:
                                return {
                                    "response": f"❌ Failed to delete draft: {result.get('message', 'Unknown error')}",
                                    "next_agent": "__end__",
                                    "draft_pending": None,
                                }

                        # Handle UPDATE operation
                        elif operation == "update":
                            draft_id = selected.get("id")
                            subject = selected.get("subject", "(No subject)")
                            update_instruction = pending.get("update_instruction", "")

                            if not update_instruction:
                                return {
                                    "response": f"Selected draft: '{subject}'\n\nWhat would you like to change?",
                                    "draft_pending": DraftPendingInfo(
                                        awaiting="update_instruction",
                                        drafts_list=[selected],
                                        operation="update",
                                    ),
                                    "next_agent": "__end__",
                                }

                            # Call update_draft tool
                            for tool in tools:
                                if tool.name == "update_draft":
                                    result = tool.invoke({
                                        "draft_id": draft_id,
                                        "instruction": update_instruction,
                                    })
                                    result_dict = json.loads(result)

                                    if result_dict.get("success"):
                                        new_body = result_dict.get("draft", {}).get("body", "")
                                        return {
                                            "response": f"✅ Draft updated: '{subject}'\n\nNew body:\n{new_body[:200]}...",
                                            "next_agent": "__end__",
                                            "draft_pending": None,
                                        }
                                    else:
                                        return {
                                            "response": f"❌ Failed to update draft: {result_dict.get('message', 'Unknown error')}",
                                            "next_agent": "__end__",
                                            "draft_pending": None,
                                        }

        # Regular draft request - use LLM with tools
        messages = [
            SystemMessage(content=DRAFT_AGENT_PROMPT),
            HumanMessage(content=current_input),
        ]

        response = llm_with_tools.invoke(messages)

        # Handle tool calls
        if response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                logger.info(f"[DRAFT_AGENT] Tool call: {tool_name} with {tool_args}")

                for tool in tools:
                    if tool.name == tool_name:
                        # NEW: For create_draft, ALWAYS ask for user preference before creating
                        if tool_name == "create_draft":
                            recipient = tool_args.get("recipient")
                            subject = tool_args.get("subject", "")
                            body = tool_args.get("body", "")

                            # Extract context hint for potential auto-generation
                            context_hint = ""
                            import re
                            context_patterns = [
                                r"about\s+(.+?)(?:\s+to|\s*$)",
                                r"regarding\s+(.+?)(?:\s+to|\s*$)",
                                r"for\s+(.+?)(?:\s+to|\s*$)",
                            ]
                            for pattern in context_patterns:
                                match = re.search(pattern, current_input.lower())
                                if match:
                                    context_hint = match.group(1)
                                    break

                            # If recipient missing, ask for that FIRST
                            if not recipient or not recipient.strip():
                                return {
                                    "response": "I'd be happy to create that draft! What email address should I send it to?",
                                    "draft_pending": DraftPendingInfo(
                                        awaiting="recipient",
                                        subject=subject,
                                        body=body,
                                        context_hint=context_hint or current_input,
                                        auto_generate=False,
                                    ),
                                    "next_agent": "__end__",
                                }

                            # ALWAYS present choice to user before creating draft
                            return {
                                "response": (
                                    "I can help you create this draft. How would you like to proceed?\n\n"
                                    "Please choose one option:\n"
                                    "1. Auto-complete with AI - I'll generate the subject and body based on context\n"
                                    "2. I'll provide subject and body manually\n"
                                    "3. Cancel\n\n"
                                    "Reply with the number (1, 2, or 3) or the option name."
                                ),
                                "draft_pending": DraftPendingInfo(
                                    awaiting="ai_generation_choice",
                                    recipient=recipient,
                                    subject=subject,
                                    body=body,
                                    context_hint=context_hint or current_input,
                                    auto_generate=False,
                                ),
                                "next_agent": "__end__",
                            }

                        result = tool.invoke(tool_args)
                        result_dict = json.loads(result)

                        # Check if we need more info
                        if result_dict.get("requires_recipient") or (
                            tool_name == "create_draft" and not tool_args.get("recipient")
                        ):
                            # Extract context for auto-generation
                            context_hint = ""
                            import re
                            context_patterns = [
                                r"about\s+(.+?)(?:\s+to|\s*$)",
                                r"regarding\s+(.+?)(?:\s+to|\s*$)",
                                r"for\s+(.+?)(?:\s+to|\s*$)",
                            ]
                            for pattern in context_patterns:
                                match = re.search(pattern, current_input.lower())
                                if match:
                                    context_hint = match.group(1)
                                    break

                            return {
                                "response": "I'd be happy to create that draft! What email address should I send it to?",
                                "draft_pending": DraftPendingInfo(
                                    awaiting="recipient",
                                    subject=tool_args.get("subject", ""),
                                    body=tool_args.get("body", ""),
                                    context_hint=context_hint or current_input,
                                    auto_generate=any(kw in current_input.lower() for kw in [
                                        "auto", "generate", "yourself", "create it"
                                    ]),
                                ),
                                "next_agent": "__end__",
                            }

                        if result_dict.get("requires_selection"):
                            return {
                                "response": result_dict.get("message", "Please select a draft."),
                                "draft_pending": DraftPendingInfo(
                                    awaiting="selection",
                                    drafts_list=result_dict.get("drafts", []),
                                    operation=result_dict.get("operation", "update"),
                                ),
                                "next_agent": "__end__",
                            }

                        if result_dict.get("requires_confirmation"):
                            return {
                                "response": result_dict.get("message", "Please confirm."),
                                "draft_pending": DraftPendingInfo(
                                    awaiting="confirmation",
                                    drafts_list=result_dict.get("drafts", [{"id": result_dict.get("draft_id")}]),
                                    operation="send",
                                    recipient=result_dict.get("recipient"),
                                ),
                                "next_agent": "__end__",
                            }

                        if result_dict.get("success"):
                            return {
                                "response": result_dict.get("message", "Operation completed."),
                                "next_agent": "__end__",
                                "draft_pending": None,
                            }

                        return {
                            "response": result_dict.get("message", result),
                            "next_agent": "__end__",
                        }

        # No tool call - return LLM response
        return {
            "response": response.content or "I couldn't process that draft request.",
            "next_agent": "__end__",
        }

    except Exception as e:
        logger.error(f"[DRAFT_AGENT] Error: {e}", exc_info=True)
        return {
            "response": f"Error processing draft request: {str(e)}",
            "next_agent": "__end__",
            "error": str(e),
            "draft_pending": None,
        }


def send_agent_node(state: EmailAgentState) -> dict:
    """
    Send Agent: Handles email sending operations.
    """
    logger.info("[SEND_AGENT] Processing request")

    try:
        llm = get_llm()
        tools = create_send_tools(user_id=state.get("user_id"))
        llm_with_tools = llm.bind_tools(tools)

        current_input = state.get("current_input", "").lower().strip()
        pending = state.get("draft_pending")

        # Handle confirmation for draft send
        if pending and pending.get("awaiting") == "confirmation":
            if current_input in ["yes", "y"]:
                drafts = pending.get("drafts_list", [])
                if drafts:
                    draft = drafts[0]
                    # Check both 'draft_id' (from draft_email) and 'id' (legacy) for compatibility
                    draft_id = draft.get("draft_id") or draft.get("id")

                    if not draft_id:
                        logger.error(f"[SEND_AGENT] No draft_id found in draft: {draft}")
                        return {
                            "response": "Error: Could not find draft ID. The draft may not have been created properly.",
                            "next_agent": "__end__",
                            "draft_pending": None,
                        }

                    for tool in tools:
                        if tool.name == "confirm_and_send_draft":
                            result = tool.invoke({"draft_id": draft_id})
                            result_dict = json.loads(result)

                            if result_dict.get("success"):
                                recipient = pending.get("recipient", "recipient")
                                return {
                                    "response": f"Email sent to {recipient}!",
                                    "next_agent": "__end__",
                                    "draft_pending": None,
                                }
                            else:
                                return {
                                    "response": f"Failed to send: {result_dict.get('message', 'Unknown error')}",
                                    "next_agent": "__end__",
                                    "draft_pending": None,
                                }

            elif current_input in ["no", "n"]:
                return {
                    "response": "Operation cancelled. Draft not sent.",
                    "next_agent": "__end__",
                    "draft_pending": None,
                }

        # Regular send request
        messages = [
            SystemMessage(content=SEND_AGENT_PROMPT),
            HumanMessage(content=state.get("current_input", "")),
        ]

        response = llm_with_tools.invoke(messages)

        if response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                for tool in tools:
                    if tool.name == tool_name:
                        result = tool.invoke(tool_args)
                        result_dict = json.loads(result)

                        if result_dict.get("success"):
                            return {
                                "response": f"Email sent to {tool_args.get('recipient', 'recipient')}!",
                                "next_agent": "__end__",
                            }
                        else:
                            return {
                                "response": f"Failed to send: {result_dict.get('message', 'Unknown error')}",
                                "next_agent": "__end__",
                            }

        return {
            "response": response.content or "I couldn't process that send request.",
            "next_agent": "__end__",
        }

    except Exception as e:
        logger.error(f"[SEND_AGENT] Error: {e}")
        return {
            "response": f"Error sending email: {str(e)}",
            "next_agent": "__end__",
            "error": str(e),
        }


def organization_agent_node(state: EmailAgentState) -> dict:
    """
    Organization Agent: Handles inbox organization operations.
    """
    logger.info("[ORGANIZATION_AGENT] Processing request")

    try:
        llm = get_llm()
        tools = create_organization_tools(user_id=state.get("user_id"))
        llm_with_tools = llm.bind_tools(tools)

        messages = [
            SystemMessage(content="You help organize emails. You can move emails by sender or delete spam."),
            HumanMessage(content=state.get("current_input", "")),
        ]

        response = llm_with_tools.invoke(messages)

        if response.tool_calls:
            for tool_call in response.tool_calls:
                for tool in tools:
                    if tool.name == tool_call["name"]:
                        result = tool.invoke(tool_call["args"])
                        return {
                            "response": result,
                            "next_agent": "__end__",
                        }

        return {
            "response": response.content or "I couldn't process that organization request.",
            "next_agent": "__end__",
        }

    except Exception as e:
        logger.error(f"[ORGANIZATION_AGENT] Error: {e}")
        return {
            "response": f"Error: {str(e)}",
            "next_agent": "__end__",
            "error": str(e),
        }


def human_node(state: EmailAgentState) -> dict:
    """
    Human node: Handles requests that need clarification.
    """
    return {
        "response": "I'm not sure what you'd like me to do. Could you please clarify your request?\n\nI can help you:\n- Read and search emails\n- Create and manage drafts\n- Send emails\n- Organize your inbox",
        "next_agent": "__end__",
        "requires_human_input": True,
    }


def end_node(state: EmailAgentState) -> dict:
    """
    End node: Generates final response for direct answers.
    """
    # If we already have a response, return it
    if state.get("response"):
        return state

    # Generate a greeting or direct answer
    try:
        llm = get_llm()
        response = llm.invoke([
            SystemMessage(content="You are a friendly email assistant. Respond helpfully to the user's message."),
            HumanMessage(content=state.get("current_input", "")),
        ])
        return {
            "response": response.content,
            "next_agent": "__end__",
        }
    except Exception as e:
        return {
            "response": "Hello! I'm your email assistant. How can I help you today?",
            "next_agent": "__end__",
        }


# =============================================================================
# Graph Builder
# =============================================================================

def route_from_supervisor(state: EmailAgentState) -> str:
    """Conditional edge: route based on supervisor decision."""
    next_agent = state.get("next_agent", "__end__")
    logger.info(f"[ROUTER] Routing to: {next_agent}")
    return next_agent


def create_email_assistant_graph(checkpointer=None):
    """
    Create the complete email assistant graph with all agents.

    Args:
        checkpointer: Optional memory saver for state persistence

    Returns:
        Compiled LangGraph
    """
    # Build the graph
    builder = StateGraph(EmailAgentState)

    # Add nodes
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("inbox", inbox_agent_node)
    builder.add_node("draft", draft_agent_node)
    builder.add_node("send", send_agent_node)
    builder.add_node("organization", organization_agent_node)
    builder.add_node("human", human_node)
    builder.add_node("end", end_node)

    # Set entry point
    builder.add_edge(START, "supervisor")

    # Add conditional edges from supervisor
    builder.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "inbox": "inbox",
            "draft": "draft",
            "send": "send",
            "organization": "organization",
            "human": "human",
            "__end__": "end",
        }
    )

    # All agents return to supervisor for multi-turn handling
    builder.add_edge("inbox", END)
    builder.add_edge("draft", END)
    builder.add_edge("send", END)
    builder.add_edge("organization", END)
    builder.add_edge("human", END)
    builder.add_edge("end", END)

    # Compile with optional checkpointer
    if checkpointer is None:
        checkpointer = MemorySaver()

    return builder.compile(checkpointer=checkpointer)


# =============================================================================
# High-Level Interface
# =============================================================================

class EmailAssistant:
    """
    High-level interface for the multi-agent email assistant.

    Usage:
        assistant = EmailAssistant(user_id="user123")
        response = assistant.chat("Show me my latest emails")
    """

    def __init__(self, user_id: Optional[str] = None):
        self.user_id = user_id
        self.graph = create_email_assistant_graph()
        self.thread_id = f"thread_{user_id or 'default'}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.conversation_history = []
        # State persistence for reply-by-number feature
        self.listed_emails = None
        self.draft_pending = None

    def chat(self, message: str, context: str = "") -> str:
        """
        Process a user message and return the assistant's response.

        Args:
            message: User's message
            context: Optional additional context

        Returns:
            Assistant's response string
        """
        if not message or not message.strip():
            return "Please provide a message to get started."

        try:
            # Create initial state with persisted data
            state = create_initial_state(
                user_message=message,
                user_id=self.user_id,
                context=context,
                existing_messages=self.conversation_history,
                listed_emails=self.listed_emails,
                draft_pending=self.draft_pending,
            )

            # Run the graph
            config = {"configurable": {"thread_id": self.thread_id}}
            result = self.graph.invoke(state, config)

            # Persist state for next turn (reply-by-number feature)
            self.listed_emails = result.get("listed_emails", self.listed_emails)
            self.draft_pending = result.get("draft_pending")

            # Extract response
            response = result.get("response", "I couldn't process that request.")

            # Update conversation history
            self.conversation_history.append({
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat(),
            })
            self.conversation_history.append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().isoformat(),
            })

            # Keep history manageable
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]

            return response

        except Exception as e:
            logger.error(f"Chat error: {e}", exc_info=True)
            return f"Sorry, I encountered an error: {str(e)}"

    def clear_history(self):
        """Clear conversation history and persisted state."""
        self.conversation_history = []
        self.thread_id = f"thread_{self.user_id or 'default'}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.listed_emails = None
        self.draft_pending = None
