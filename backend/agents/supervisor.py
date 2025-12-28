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
from langgraph.errors import GraphInterrupt
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
1. When the user asks to create/compose a draft, ALWAYS use the create_draft tool (even if subject/body are missing).
2. If user provides context but NO recipient - ask for recipient email address.
3. If subject/body are missing, ask if you should generate them. Use the user's last request as context.
4. If user says "yes", "auto", or "generate it", create subject and body from context.
5. If user says "no" or "manual", ask for subject and body in a clear format.
6. Do NOT ask for "the user's message" if they already described the email.
7. ALWAYS confirm after creating: "Draft created to [email] with subject '[subject]'"

For updating drafts:
- Use the update_draft tool with the recipient email and instruction
- The tool will use AI to intelligently modify the draft

Always be professional and helpful.
"""

INBOX_AGENT_PROMPT = """You are a specialized email reading assistant.

Your capabilities:
1. Fetch emails with various filters (sender, date, label, importance, provider)
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
- "summarize emails from last week" → summarize_emails(time_period="last_week")
- "what did I get yesterday" → summarize_emails(time_period="yesterday")
- "summarize last month's emails" → summarize_emails(time_period="last_month")

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

def _format_email_cards(emails: list) -> str:
    blocks = []
    for idx, email in enumerate(emails or [], 1):
        if not isinstance(email, dict):
            continue
        sender = email.get("sender") or email.get("from") or "Unknown"
        subject = email.get("subject") or "(No subject)"
        date = email.get("date") or "Unknown"
        body = email.get("body") or email.get("snippet") or ""
        body = " ".join(str(body).split())
        if len(body) > 300:
            body = body[:300] + "..."

        important = (
            email.get("ml_prediction") == "important"
            or email.get("is_important") is True
            or email.get("importance") is True
        )

        lines = [
            f"# Email #{idx}",
            "",
            f"From: {sender}",
            f"Subject: {subject}",
            f"Date: {date}",
        ]
        if important:
            lines.append("⭐ Important")
        lines.extend(["", "Body:", body])
        blocks.append("\n".join(lines))

    return "\n\n---\n\n".join(blocks).strip()


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

    show_match = re.search(r"\b(shows?|lists?|displays?|give)\b.*\b(those|these|them|that|emails?|mails?)\b", current_input, re.IGNORECASE)
    has_time_filter = re.search(r"\b(today|yesterday|last|week|month|from|since|until)\b", current_input, re.IGNORECASE)

    logger.info(f"[SHOW_CHECK] show_match={bool(show_match)}, has_time_filter={bool(has_time_filter)}")

    if show_match and not has_time_filter:
        logger.info(f"[SHOW_HANDLER] Triggered! User input: '{current_input}'")
        listed_emails = state.get("listed_emails")
        logger.info(f"[SHOW_HANDLER] listed_emails type: {type(listed_emails)}, has emails key: {listed_emails.get('emails') if isinstance(listed_emails, dict) else 'N/A'}")

        if not listed_emails or not listed_emails.get("emails"):
            logger.warning(f"[SHOW_HANDLER] No listed_emails in state")
            return {
                "response": "No emails are currently listed. Please ask for a summary or fetch emails first.",
                "next_agent": "__end__",
            }

        emails = listed_emails["emails"]
        list_type = listed_emails.get("list_type", "emails")
        logger.info(f"[SHOW_HANDLER] Retrieved {len(emails) if emails else 0} emails, list_type={list_type}")

        if not emails:
            logger.warning(f"[SHOW_HANDLER] Emails list is empty")
            return {
                "response": "I couldn't format those emails. Please try fetching them again.",
                "next_agent": "__end__",
            }

        if list_type == "drafts":
            logger.info(f"[SHOW_HANDLER] Returning {len(emails)} drafts with display_emails")
            return {
                "response": f"Found {len(emails)} drafts.",
                "next_agent": "__end__",
                "display_emails": emails,
            }

        logger.info(f"[SHOW_HANDLER] Returning {len(emails)} emails with display_emails. First email preview: {emails[0].get('subject', 'NO SUBJECT') if emails and isinstance(emails[0], dict) else 'INVALID FORMAT'}")
        result = {
            "response": f"Found {len(emails)} emails.\n\n*Reply to any email by saying 'reply 1', 'reply 2', etc.*",
            "next_agent": "__end__",
            "display_emails": emails,
        }
        logger.info(f"[SHOW_HANDLER] Result dict keys: {list(result.keys())}, display_emails type: {type(result['display_emails'])}, count: {len(result['display_emails'])}")
        return result

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
        if listed_emails.get("list_type") == "drafts":
            return {
                "response": "Those are drafts. Replying is only available for inbox emails. Please fetch emails to reply.",
                "next_agent": "__end__",
            }
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
            "display_emails": None,
            "draft_pending": DraftPendingInfo(
                awaiting="reply_content",
                reply_to_email=email,
            ),
        }

    # NEW: Detect update draft intent and route to draft agent with context preservation
    update_draft_match = re.search(r'\bupdate\b.*\b(draft|subject|body)\b', current_input, re.IGNORECASE)
    if update_draft_match:
        # Check if we have draft context from previous turn
        if state.get("draft_pending"):
            pending = state["draft_pending"]
            # Preserve recipient if we know it
            if pending.get("selected_draft_recipient") or pending.get("recipient"):
                logger.info("[SUPERVISOR] Routing update to draft agent with preserved context")
                return {"next_agent": "draft"}

        # Check if recipient is in current input
        import re as re_module
        email_match = re_module.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", current_input or "")
        if email_match:
            logger.info("[SUPERVISOR] Routing update to draft agent (recipient in message)")
            return {"next_agent": "draft"}

        # No recipient context - let draft agent handle it (will interrupt for recipient)
        logger.info("[SUPERVISOR] Routing update to draft agent (will request recipient)")
        return {"next_agent": "draft"}

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

    draft_list_match = re.search(r"\bdraft(s)?\b", current_input, re.IGNORECASE) and re.search(
        r"\b(show|list|display|get|fetch|view|see)\b", current_input, re.IGNORECASE
    )
    draft_action_match = re.search(
        r"\b(create|compose|write|make|update|delete|send)\b", current_input, re.IGNORECASE
    )
    if draft_list_match and not draft_action_match:
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

        current_input = state.get("current_input", "")
        current_lower = current_input.lower()

        def _parse_time_period(text: str) -> Optional[str]:
            if "yesterday" in text:
                return "yesterday"
            if "today" in text:
                return "today"
            if "last 3 months" in text or "last three months" in text:
                return "last_3_months"
            if "last week" in text or "this week" in text:
                return "last_week"
            if "last month" in text or "this month" in text:
                return "last_month"
            return None

        def _parse_provider(text: str) -> Optional[str]:
            if "gmail" in text:
                return "gmail"
            if "outlook" in text:
                return "outlook"
            return None

        def _is_draft_list_request(text: str) -> bool:
            if not re.search(r"\bdraft(s)?\b", text):
                return False
            if re.search(r"\b(create|compose|write|make|update|delete|send)\b", text):
                return False
            if re.search(r"\b(show|list|display|get|fetch|view|see)\b", text):
                return True
            return "my drafts" in text

        def _wants_show_emails(text: str) -> bool:
            return bool(
                re.search(r"\b(show|display|list|see|give)\b", text)
                and re.search(r"\b(email|emails|mail|mails)\b", text)
            )

        wants_show_emails = _wants_show_emails(current_lower)

        if _is_draft_list_request(current_lower):
            draft_tool = next((tool for tool in tools if tool.name == "get_all_drafts"), None)
            recipient_match = re.search(
                r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                current_input,
            )
            if recipient_match:
                draft_tool = next(
                    (tool for tool in tools if tool.name == "get_drafts_for_recipient"),
                    draft_tool,
                )
            if draft_tool:
                draft_args = {}
                if recipient_match and draft_tool.name == "get_drafts_for_recipient":
                    draft_args["recipient_email"] = recipient_match.group(0)
                result = draft_tool.invoke(draft_args)
                try:
                    parsed_drafts = json.loads(result)
                    if isinstance(parsed_drafts, list):
                        response_content = f"Found {len(parsed_drafts)} drafts."
                        return {
                            "response": response_content,
                            "next_agent": "__end__",
                            "last_tool_result": {"results": [result]},
                            "display_emails": parsed_drafts,
                            "listed_emails": {
                                "emails": parsed_drafts,
                                "listed_at": datetime.now().isoformat(),
                                "list_type": "drafts",
                            },
                        }
                except Exception as parse_err:
                    logger.warning(f"[INBOX_AGENT] Draft list parse failed: {parse_err}")

        def _is_list_request(text: str) -> bool:
            if "summary" in text or "summarize" in text:
                return False
            if re.search(r"\b(show|list|display|get|fetch|read)\b", text) and re.search(
                r"\b(email|emails|mail|mails)\b", text
            ):
                return True
            if "last" in text and re.search(r"\b(email|emails|mail|mails)\b", text):
                return True
            return False

        if _is_list_request(current_lower):
            fetch_tool = next((tool for tool in tools if tool.name == "fetch_emails"), None)
            if fetch_tool:
                fetch_args = {
                    "time_period": _parse_time_period(current_lower),
                    "importance": "important" in current_lower,
                    "provider": _parse_provider(current_lower),
                }
                fetch_args = {k: v for k, v in fetch_args.items() if v is not None}
                result = fetch_tool.invoke(fetch_args)
                try:
                    json_str = result
                    if "```json" in result:
                        json_str = result.split("```json")[1].split("```")[0].strip()
                    parsed_emails = json.loads(json_str)
                    if isinstance(parsed_emails, list):
                        response_content = f"Found {len(parsed_emails)} emails.\n\n*Reply to any email by saying 'reply 1', 'reply 2', etc.*"
                        return {
                            "response": response_content,
                            "next_agent": "__end__",
                            "last_tool_result": {"results": [result]},
                            "display_emails": parsed_emails,
                            "listed_emails": {
                                "emails": parsed_emails,
                                "listed_at": datetime.now().isoformat(),
                                "list_type": "emails",
                            },
                        }
                except Exception as parse_err:
                    logger.warning(f"[INBOX_AGENT] Direct fetch parse failed: {parse_err}")

        # Handle summary requests with pre-parsed parameters
        def _is_summary_request(text: str) -> bool:
            return bool(re.search(r"\b(summary|summarize)\b", text) and re.search(r"\b(email|emails|mail|mails)\b", text))

        if _is_summary_request(current_lower):
            summary_tool = next((tool for tool in tools if tool.name == "summarize_emails"), None)
            if summary_tool:
                # Parse parameters from user input
                time_period = _parse_time_period(current_lower)
                importance = "important" in current_lower
                provider = _parse_provider(current_lower)

                summary_args = {}
                if time_period:
                    summary_args["time_period"] = time_period
                if importance:
                    summary_args["importance"] = importance
                if provider:
                    summary_args["provider"] = provider

                logger.info(f"[INBOX_AGENT] Direct summarize with args: {summary_args}")
                result = summary_tool.invoke(summary_args)

                try:
                    parsed_summary = json.loads(result)

                    # Handle account selection if multiple accounts found
                    if parsed_summary.get("requires_account_selection"):
                        accounts = parsed_summary.get("accounts", [])
                        provider_name = parsed_summary.get("provider", "email")

                        account_list_str = "\n".join([
                            f"{i+1}. {acc.get('email_address', 'Unknown')} ({acc.get('display_name', 'No name')})"
                            for i, acc in enumerate(accounts)
                        ])
                        prompt = (
                            f"I found multiple {provider_name} accounts connected. Which one would you like to summarize for {time_period or 'today'}?\n\n"
                            f"{account_list_str}\n\n"
                            f"Please reply with the number or email address."
                        )

                        selection = interrupt(prompt)
                        logger.info(f"[INBOX_AGENT] User selected: {selection}")

                        # Process selection
                        selected_accounts = []
                        selection_str = str(selection).strip().lower()

                        if selection_str in ["all", "both", "all of them", "everything"]:
                            selected_accounts = accounts
                        elif selection_str.isdigit():
                            idx = int(selection_str) - 1
                            if 0 <= idx < len(accounts):
                                selected_accounts = [accounts[idx]]
                        else:
                            for acc in accounts:
                                if selection_str in acc.get("email_address", "").lower():
                                    selected_accounts.append(acc)

                        if not selected_accounts:
                            return {
                                "response": "I couldn't match your selection. Please try again.",
                                "next_agent": "__end__"
                            }

                        # Re-run for selected accounts
                        summaries = []
                        all_emails_data = []

                        for acc in selected_accounts:
                            acc_args = summary_args.copy()
                            acc_args["account_id"] = acc.get("id")
                            if "provider" in acc_args:
                                del acc_args["provider"]

                            logger.info(f"[INBOX_AGENT] Summarizing {acc.get('email_address')} with args: {acc_args}")
                            acc_result = summary_tool.invoke(acc_args)
                            acc_data = json.loads(acc_result)

                            if acc_data.get("success"):
                                summaries.append(f"**{acc.get('email_address')}**:\n{acc_data.get('summary')}")
                                if acc_data.get("emails"):
                                    all_emails_data.extend(acc_data.get("emails"))
                            else:
                                summaries.append(f"**{acc.get('email_address')}**: {acc_data.get('message', 'No summary available')}")

                        combined = "\n\n---\n\n".join(summaries)
                        result_dict = {
                            "response": combined,
                            "next_agent": "__end__",
                            "last_tool_result": {"results": [combined]}
                        }

                        if all_emails_data:
                            result_dict["display_emails"] = all_emails_data
                            result_dict["listed_emails"] = {
                                "emails": all_emails_data,
                                "listed_at": datetime.now().isoformat(),
                                "list_type": "emails"
                            }

                        return result_dict

                    # Single account summary - return result
                    summary_text = parsed_summary.get("summary") or parsed_summary.get("message")
                    summary_emails = parsed_summary.get("emails")

                    result_dict = {
                        "response": summary_text,
                        "next_agent": "__end__",
                        "last_tool_result": {"results": [result]}
                    }

                    if summary_emails and isinstance(summary_emails, list):
                        result_dict["listed_emails"] = {
                            "emails": summary_emails,
                            "listed_at": datetime.now().isoformat(),
                            "list_type": "emails"
                        }
                        if wants_show_emails:
                            result_dict["display_emails"] = summary_emails
                            result_dict["response"] = f"{summary_text}\n\nFound {len(summary_emails)} emails."
                        else:
                            result_dict["response"] = f"{summary_text}\n\n*Want to see the emails? Say 'show these emails'.*"

                    return result_dict

                except Exception as parse_err:
                    logger.warning(f"[INBOX_AGENT] Direct summary parse failed: {parse_err}")

        messages = [
            SystemMessage(content=INBOX_AGENT_PROMPT),
            HumanMessage(content=current_input),
        ]

        response = llm_with_tools.invoke(messages)

        # Handle tool calls
        if response.tool_calls:
            tool_results = []
            fetched_emails = None  # Track fetched emails for reply-by-number feature
            emails_visible = False
            fetch_emails_called = False
            summary_text = None
            summary_emails = None
            list_type = "emails"

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
                            fetch_emails_called = True
                            list_type = "emails"
                            try:
                                json_str = result
                                if "```json" in result:
                                    json_str = result.split("```json")[1].split("```")[0].strip()
                                parsed_emails = json.loads(json_str)
                                if isinstance(parsed_emails, list) and parsed_emails:
                                    fetched_emails = parsed_emails
                                    emails_visible = True
                                    logger.info(f"[INBOX_AGENT] Stored {len(fetched_emails)} emails for reply-by-number")
                            except Exception as parse_err:
                                logger.warning(f"[INBOX_AGENT] Could not parse emails for storage: {parse_err}")
                        elif tool_name in ("get_all_drafts", "get_drafts_for_recipient"):
                            fetch_emails_called = True
                            list_type = "drafts"
                            try:
                                parsed_emails = json.loads(result)
                                if isinstance(parsed_emails, list):
                                    fetched_emails = parsed_emails
                                    emails_visible = True
                                    logger.info(f"[INBOX_AGENT] Stored {len(fetched_emails)} drafts for display")
                            except Exception as parse_err:
                                logger.warning(f"[INBOX_AGENT] Could not parse drafts for storage: {parse_err}")
                        elif tool_name == "summarize_emails":
                            try:
                                parsed_summary = json.loads(result)
                                
                                # Handle account selection if multiple accounts found for provider
                                if parsed_summary.get("requires_account_selection"):
                                    accounts = parsed_summary.get("accounts", [])
                                    provider = parsed_summary.get("provider", "email")
                                    original_params = parsed_summary.get("original_params", {})
                                    
                                    # Format prompt for user
                                    account_list_str = "\n".join([
                                        f"{i+1}. {acc.get('email_address')} ({acc.get('display_name', 'No name')})" 
                                        for i, acc in enumerate(accounts)
                                    ])
                                    prompt = (
                                        f"I found multiple {provider} accounts. Which one would you like to summarize?\n\n"
                                        f"{account_list_str}\n\n"
                                        f"Please reply with the number, email, or 'all'."
                                    )
                                    
                                    # Interrupt workflow to get user selection
                                    selection = interrupt(prompt)
                                    logger.info(f"[INBOX_AGENT] Account selection: {selection}")
                                    
                                    # Process user selection
                                    selected_accounts = []
                                    selection_str = str(selection).strip().lower()
                                    
                                    if selection_str in ["all", "both", "all of them", "everything"]:
                                        selected_accounts = accounts
                                    elif selection_str.isdigit():
                                        idx = int(selection_str) - 1
                                        if 0 <= idx < len(accounts):
                                            selected_accounts = [accounts[idx]]
                                    else:
                                        # Try matching email address
                                        for acc in accounts:
                                            if selection_str in acc.get("email_address", "").lower():
                                                selected_accounts.append(acc)
                                    
                                    if not selected_accounts:
                                        return {
                                            "response": "I couldn't match your selection to an account. Please try asking again.",
                                            "next_agent": "__end__"
                                        }
                                    
                                    # Re-run summarization for selected account(s)
                                    summaries = []
                                    all_emails_data = []
                                    
                                    for acc in selected_accounts:
                                        # Prepare args for specific account using original tool_args
                                        new_args = tool_args.copy()
                                        new_args["account_id"] = acc.get("id")
                                        # Remove provider to avoid re-triggering selection logic
                                        if "provider" in new_args:
                                            del new_args["provider"]
                                            
                                        logger.info(f"[INBOX_AGENT] Re-running summary for account {acc.get('email_address')}")
                                        logger.info(f"[INBOX_AGENT] New args: {new_args}")
                                        res = tool.invoke(new_args)
                                        res_data = json.loads(res)
                                        
                                        if res_data.get("success"):
                                            acc_summary = res_data.get("summary")
                                            summaries.append(f"**{acc.get('email_address')}**:\n{acc_summary}")
                                            if res_data.get("emails"):
                                                all_emails_data.extend(res_data.get("emails"))
                                        else:
                                            summaries.append(f"**{acc.get('email_address')}**: {res_data.get('message', 'Failed to summarize')}")
                                    
                                    combined_summary = "\n\n---\n\n".join(summaries)
                                    
                                    # Return combined result
                                    result_dict = {
                                        "response": combined_summary,
                                        "next_agent": "__end__",
                                        "last_tool_result": {"results": [combined_summary]}
                                    }
                                    
                                    if all_emails_data:
                                        result_dict["display_emails"] = all_emails_data
                                        result_dict["listed_emails"] = {
                                            "emails": all_emails_data,
                                            "listed_at": datetime.now().isoformat(),
                                            "list_type": "emails",
                                        }
                                        
                                    return result_dict

                                summary_text = parsed_summary.get("summary") or parsed_summary.get("message")
                                summary_emails = parsed_summary.get("emails")
                                if isinstance(summary_emails, list) and summary_emails:
                                    fetched_emails = summary_emails
                                    list_type = "emails"
                                    logger.info(f"[INBOX_AGENT] Stored {len(fetched_emails)} emails from summary for follow-up")
                            except Exception as parse_err:
                                logger.warning(f"[INBOX_AGENT] Could not parse summary emails for storage: {parse_err}")
                        break

            # Generate response with tool results
            if tool_results:
                if summary_text:
                    response_content = summary_text
                    result_dict = {
                        "response": response_content,
                        "next_agent": "__end__",
                        "last_tool_result": {"results": tool_results},
                    }
                    if summary_emails:
                        result_dict["listed_emails"] = {
                            "emails": summary_emails,
                            "listed_at": datetime.now().isoformat(),
                            "list_type": "emails",
                        }
                        if wants_show_emails:
                            result_dict["display_emails"] = summary_emails
                            response_content = f"{summary_text}\n\nFound {len(summary_emails)} emails."
                        else:
                            response_content = f"{summary_text}\n\n*Want to see the emails? Say 'show these emails'.*"
                        result_dict["response"] = response_content
                    return result_dict

                if fetch_emails_called and fetched_emails:
                    if list_type == "drafts":
                        response_content = f"Found {len(fetched_emails)} drafts."
                    else:
                        response_content = f"Found {len(fetched_emails)} emails.\n\n*Reply to any email by saying 'reply 1', 'reply 2', etc.*"
                    result_dict = {
                        "response": response_content,
                        "next_agent": "__end__",
                        "last_tool_result": {"results": tool_results},
                    }
                    result_dict["listed_emails"] = {
                        "emails": fetched_emails,
                        "listed_at": datetime.now().isoformat(),
                        "list_type": list_type,
                    }
                    result_dict["display_emails"] = fetched_emails
                    return result_dict

                follow_up_messages = messages + [
                    AIMessage(content=response.content or "", tool_calls=response.tool_calls),
                    HumanMessage(content=f"Tool results: {tool_results[0]}")
                ]
                final_response = llm.invoke(follow_up_messages)

                response_content = final_response.content

                # Add hint if emails were fetched
                if fetched_emails:
                    if list_type == "drafts":
                        if not emails_visible:
                            response_content = f"{response_content}\n\n*Want to see the drafts? Say 'show these drafts'.*"
                    elif emails_visible:
                        response_content = f"{response_content}\n\n*Reply to any email by saying 'reply 1', 'reply 2', etc.*"
                    else:
                        response_content = f"{response_content}\n\n*Want to see the emails? Say 'show these emails'.*"

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
                        "list_type": list_type,
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


def parse_update_instruction(user_input: str) -> dict:
    """
    Parse user input to detect direct subject/body updates vs natural language instructions.

    Returns:
        {
            "mode": "direct" | "instruction",
            "subject": str | None,
            "body": str | None,
            "instruction": str | None
        }

    Examples:
        "subject: Meeting body: Let's meet tomorrow"
            -> mode=direct, subject="Meeting", body="Let's meet tomorrow"

        "update subject with: Final Exam Tomorrow and body: If you don't attend you fail"
            -> mode=direct, subject="Final Exam Tomorrow", body="If you don't attend you fail"

        "make it more formal"
            -> mode=instruction, instruction="make it more formal"
    """
    import re

    # Pattern 1: "subject: X body: Y" or "subject with: X and body: Y" or "subject: X and body with: Y"
    pattern1 = re.search(
        r'subject\s*(?:with)?\s*:\s*(.+?)\s+(?:and\s+)?body\s*(?:with)?\s*:\s*(.+)',
        user_input,
        re.IGNORECASE | re.DOTALL
    )

    # Pattern 2: Just "subject: X" or "subject with: X" (subject only)
    pattern2 = re.search(
        r'(?:update\s+)?subject\s*(?:with)?\s*:\s*(.+?)(?:\s+and\s+body|$)',
        user_input,
        re.IGNORECASE
    )

    # Pattern 3: Just "body: X" or "body with: X" (body only)
    pattern3 = re.search(
        r'(?:update\s+)?body\s*(?:with)?\s*:\s*(.+?)$',
        user_input,
        re.IGNORECASE
    )

    if pattern1:
        # Both subject and body
        subject = pattern1.group(1).strip()
        body = pattern1.group(2).strip()
        return {
            "mode": "direct",
            "subject": subject,
            "body": body,
            "instruction": None
        }
    elif pattern2:
        # Subject only
        subject = pattern2.group(1).strip()
        # Remove trailing "and body" if it exists without actual body content
        subject = re.sub(r'\s+and\s+body\s*$', '', subject, flags=re.IGNORECASE).strip()
        return {
            "mode": "direct",
            "subject": subject,
            "body": None,
            "instruction": None
        }
    elif pattern3:
        # Body only
        body = pattern3.group(1).strip()
        return {
            "mode": "direct",
            "subject": None,
            "body": body,
            "instruction": None
        }
    else:
        # Natural language instruction
        return {
            "mode": "instruction",
            "subject": None,
            "body": None,
            "instruction": user_input.strip()
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

        def _extract_first_email(text: str) -> Optional[str]:
            import re
            match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text or "")
            return match.group(0) if match else None

        def _extract_subject_body(text: str) -> tuple[str, str]:
            import re
            if not text:
                return "", ""
            subject = ""
            body = ""
            subject_match = re.search(
                r"\bsubject\b\s*[:=\-]\s*(.+?)(?=\bbody\b\s*[:=\-]|$)",
                text,
                re.IGNORECASE | re.DOTALL,
            )
            body_match = re.search(r"\bbody\b\s*[:=\-]\s*(.+)", text, re.IGNORECASE | re.DOTALL)
            if subject_match:
                subject = subject_match.group(1).strip().rstrip(" ,;")
            else:
                for line in text.splitlines():
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue
                    if line_stripped.lower().startswith("subject"):
                        subject = line_stripped[len("subject"):].lstrip(" \t:-=").rstrip(" ,;")
                        break
            if body_match:
                body = body_match.group(1).strip()
            else:
                for line in text.splitlines():
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue
                    if line_stripped.lower().startswith("body"):
                        body = line_stripped[len("body"):].lstrip(" \t:-=")
                        break
            return subject, body

        def _is_create_draft_intent(text: str) -> bool:
            import re
            lower = (text or "").lower()
            if any(kw in lower for kw in ["update", "edit", "delete", "remove", "send", "reply"]):
                return False
            if re.search(r"\b(create|compose|write|make)\b", lower) and re.search(r"\b(email|draft|mail)\b", lower):
                return True
            return re.search(r"\bdraft\s+(me\s+)?(an|a|to)\b", lower) is not None

        def _is_update_draft_intent(text: str) -> bool:
            lower = (text or "").lower()
            return "update" in lower and ("draft" in lower or "subject" in lower or "body" in lower)

        # ========================================================================
        # NEW: Update Draft Flow with interrupt()
        # ========================================================================
        if not pending and _is_update_draft_intent(current_input):
            logger.info("[DRAFT_AGENT] Detected update draft intent")

            # Parse the update instruction to extract direct subject/body
            parsed = parse_update_instruction(current_input)
            recipient = _extract_first_email(current_input)

            # Try to preserve recipient from previous context
            if not recipient and state.get("draft_pending"):
                prev_pending = state["draft_pending"]
                recipient = prev_pending.get("selected_draft_recipient") or prev_pending.get("recipient")

            if not recipient:
                # Need recipient to identify draft - interrupt
                recipient_response = interrupt("Which draft would you like to update? Please provide the recipient's email address.")

                # This code won't execute until resumed - validate email
                if "@" not in recipient_response or "." not in recipient_response.split("@")[-1]:
                    interrupt(f"'{recipient_response}' doesn't look like a valid email address. Please provide a valid email (e.g., john@example.com)")
                    return {}

                recipient = recipient_response.strip()

            # Now we have recipient - try to update the draft
            for tool in tools:
                if tool.name == "update_draft":
                    tool_args = {"recipient_email": recipient}

                    if parsed["mode"] == "direct":
                        # Direct subject/body update
                        if parsed["subject"] is not None:
                            tool_args["subject"] = parsed["subject"]
                        if parsed["body"] is not None:
                            tool_args["body"] = parsed["body"]
                    else:
                        # Natural language instruction
                        tool_args["instruction"] = parsed["instruction"]

                    logger.info(f"[DRAFT_AGENT] Calling update_draft with: {tool_args}")
                    result = tool.invoke(tool_args)
                    result_dict = json.loads(result)

                    if result_dict.get("requires_selection"):
                        # Multiple drafts - need selection
                        draft_list = result_dict.get("drafts", [])
                        message = result_dict.get("message", "Multiple drafts found")

                        selection_input = interrupt(f"{message}\n\nPlease enter the number of the draft to update:")

                        # Validate selection
                        if not selection_input.strip().isdigit():
                            interrupt(f"Invalid selection. Please enter a number between 1 and {len(draft_list)}.")
                            return {}

                        selection = int(selection_input.strip())
                        if selection < 1 or selection > len(draft_list):
                            interrupt(f"Invalid selection. Please enter a number between 1 and {len(draft_list)}.")
                            return {}

                        selected_draft = draft_list[selection - 1]
                        draft_id = selected_draft.get("id")

                        # Check if user provided meaningful update instructions
                        # Generic requests should trigger AI choice prompt
                        instruction = parsed.get("instruction", "")
                        
                        generic_keywords = [
                            "update draft", "edit draft", "modify draft", "change draft",
                            "update email", "edit email", "modify email", "change email"
                        ]
                        is_generic_update = (
                            not instruction 
                            or (any(k in instruction.lower() for k in generic_keywords) and len(instruction.split()) < 15)
                        )
                        
                        logger.info(f"[DRAFT_AGENT] Update instruction: '{instruction}', is_generic: {is_generic_update}")

                        if parsed["mode"] != "direct" and is_generic_update:
                            logger.info(f"[DRAFT_AGENT] No update details provided, asking user for choice")
                            ai_choice_prompt = "Would you like me to:\n1. Generate response with AI\n2. Let you provide the update yourself\n\nPlease enter 1 or 2:"

                            ai_choice = interrupt(ai_choice_prompt)
                            logger.info(f"[DRAFT_AGENT] User AI choice: {ai_choice}")

                            if ai_choice.strip() == "1":
                                # User wants AI to generate - ask for context first
                                context_prompt = "Please provide context for the AI to generate the update.\n\nExamples:\n- 'make the mail a bit formal'\n- 'replace the time of the meeting with 18:00 PM'\n- 'add more details about the project'\n\nYour context:"
                                context = interrupt(context_prompt)
                                logger.info(f"[DRAFT_AGENT] User provided context: {context}")
                                # Use the context to build instruction for AI
                                parsed["instruction"] = context.strip()
                            elif ai_choice.strip() == "2":
                                # User wants to provide content manually
                                update_content_prompt = "Please provide the updated subject and body.\nFormat: subject: <subject>\nbody: <body>"
                                update_content = interrupt(update_content_prompt)
                                logger.info(f"[DRAFT_AGENT] User provided update: {update_content[:100]}")

                                # Parse the user's update
                                manual_parsed = parse_update_instruction(update_content)
                                if manual_parsed["mode"] == "direct":
                                    parsed = manual_parsed  # Use the manually provided subject/body
                                else:
                                    # Treat as instruction if not in correct format
                                    parsed["instruction"] = update_content
                            else:
                                return {
                                    "response": "Invalid choice. Please say 'update draft' again and select 1 or 2.",
                                    "next_agent": "__end__",
                                    "draft_pending": None,
                                }

                        # Update with selected draft
                        update_args = {"draft_id": draft_id}
                        if parsed["mode"] == "direct":
                            if parsed["subject"] is not None:
                                update_args["subject"] = parsed["subject"]
                            if parsed["body"] is not None:
                                update_args["body"] = parsed["body"]
                        else:
                            update_args["instruction"] = parsed["instruction"]

                        logger.info(f"[DRAFT_AGENT] Updating selected draft with: {update_args}")
                        update_result = tool.invoke(update_args)
                        update_result_dict = json.loads(update_result)

                        if update_result_dict.get("success"):
                            return {
                                "response": update_result_dict.get("message", "Draft updated successfully"),
                                "next_agent": "__end__",
                                "draft_pending": None,
                            }
                        else:
                            return {
                                "response": update_result_dict.get("message", "Failed to update draft"),
                                "next_agent": "__end__",
                                "draft_pending": None,
                            }

                    elif result_dict.get("success"):
                        # Single draft updated successfully
                        return {
                            "response": result_dict.get("message", "Draft updated successfully"),
                            "next_agent": "__end__",
                            "draft_pending": None,
                        }
                    else:
                        # Error
                        return {
                            "response": result_dict.get("message", "Failed to update draft"),
                            "next_agent": "__end__",
                            "draft_pending": None,
                        }

        # ========================================================================
        # Create Draft Flow (existing logic)
        # ========================================================================
        if not pending and _is_create_draft_intent(current_input):
            recipient = _extract_first_email(current_input)
            subject, body = _extract_subject_body(current_input)
            context_hint = current_input

            if not recipient:
                return {
                    "response": "I'd be happy to create that draft! What email address should I send it to?",
                    "draft_pending": DraftPendingInfo(
                        awaiting="recipient",
                        subject=subject,
                        body=body,
                        context_hint=context_hint,
                        auto_generate=False,
                    ),
                    "next_agent": "__end__",
                }

            if subject and body:
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
                        return {
                            "response": f"Failed to create draft: {result_dict.get('message', 'Unknown error')}",
                            "next_agent": "__end__",
                            "draft_pending": None,
                        }

            return {
                "response": (
                    "I can generate the subject and body for you. Would you like me to do that?\n\n"
                    "Reply 'Yes' to auto-generate, or 'No' to provide them yourself."
                ),
                "draft_pending": DraftPendingInfo(
                    awaiting="ai_generation_choice",
                    recipient=recipient,
                    subject=subject,
                    body=body,
                    context_hint=context_hint,
                    auto_generate=False,
                ),
                "next_agent": "__end__",
            }

        # Handle pending draft completion
        if pending:
            awaiting = pending.get("awaiting")

            if awaiting == "ai_generation_choice":
                user_input_lower = current_input.strip().lower()

                # Parse user choice
                choice = None
                if user_input_lower.startswith("yes") or user_input_lower in [
                    "1",
                    "auto",
                    "auto-generate",
                    "auto generate",
                    "autogenerate",
                    "auto-complete",
                    "auto-complete with ai",
                    "ai",
                    "generate",
                    "go ahead",
                    "sure",
                    "ok",
                    "okay",
                ]:
                    choice = "auto"
                elif user_input_lower.startswith("no") or user_input_lower in [
                    "2",
                    "manual",
                    "manually",
                    "i'll provide",
                    "provide manually",
                    "i will provide",
                    "i want to write it",
                    "i'll write it",
                ]:
                    choice = "manual"
                elif user_input_lower in ["3", "cancel"]:
                    choice = "cancel"
                elif "auto" in user_input_lower or "generate" in user_input_lower:
                    choice = "auto"

                # Invalid choice - re-prompt
                if choice is None:
                    return {
                        "response": (
                            "I didn't understand that choice. Please reply with:\n"
                            "Yes - to auto-generate the subject and body\n"
                            "No - to provide them manually\n"
                            "Cancel - to cancel"
                        ),
                        "next_agent": "__end__",
                        "draft_pending": pending,
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
                subject, body = _extract_subject_body(user_input)
                if not subject:
                    subject = pending.get("subject", "")
                if not body:
                    body = pending.get("body", "")

                # Validation: both must be provided
                if not subject or not body:
                    updated_pending = dict(pending)
                    if subject:
                        updated_pending["subject"] = subject
                    if body:
                        updated_pending["body"] = body
                    if not subject and not body:
                        response = (
                            "I couldn't find a subject or body. Please use this format:\n\n"
                            "Subject: Your subject line here\n"
                            "Body: Your email body here"
                        )
                    elif not subject:
                        response = (
                            "I have the body. Please provide the subject using:\n"
                            "Subject: Your subject line here"
                        )
                    else:
                        response = (
                            "I have the subject. Please provide the body using:\n"
                            "Body: Your email body here"
                        )
                    return {
                        "response": response,
                        "next_agent": "__end__",
                        "draft_pending": updated_pending,
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
                        "draft_pending": pending,
                    }

                # Create the draft with the provided email
                subject = pending.get("subject", "")
                body = pending.get("body", "")
                context_hint = pending.get("context_hint", "")

                if not subject or not body:
                    if pending.get("auto_generate"):
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
                    else:
                        return {
                            "response": (
                                "I can generate the subject and body for you. Would you like me to do that?\n\n"
                                "Reply 'Yes' to auto-generate, or 'No' to provide them yourself."
                            ),
                            "draft_pending": DraftPendingInfo(
                                awaiting="ai_generation_choice",
                                recipient=email_input,
                                subject=subject,
                                body=body,
                                context_hint=context_hint,
                                auto_generate=False,
                            ),
                            "next_agent": "__end__",
                        }

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
                        "draft_pending": pending,
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
                                "display_emails": None,
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
                                "display_emails": None,
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
                        logger.info(f"[DRAFT_AGENT] Draft selection - operation={operation}, pending_keys={list(pending.keys())}")

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
                            # Get account_id from draft_pending to ensure deletion from correct account
                            account_id = pending.get("selected_account_id")

                            # Delete the draft
                            from email_tools import delete_draft
                            result = delete_draft(
                                draft_id=draft_id,
                                user_id=state.get("user_id"),
                                account_id=account_id
                            )

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
                                    "I can generate the subject and body for you. Would you like me to do that?\n\n"
                                    "Reply 'Yes' to auto-generate, or 'No' to provide them yourself."
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
                                    auto_generate=False,
                                ),
                                "next_agent": "__end__",
                            }

                        if result_dict.get("requires_selection"):
                            drafts = result_dict.get("drafts", [])
                            # Extract account_id from first draft for multi-account support
                            account_id = drafts[0].get("account_id") if drafts else None
                            operation_value = result_dict.get("operation", "update")
                            logger.info(f"[DRAFT_AGENT] Setting draft_pending with operation={operation_value}, result_dict_keys={list(result_dict.keys())}")
                            return {
                                "response": result_dict.get("message", "Please select a draft."),
                                "draft_pending": DraftPendingInfo(
                                    awaiting="selection",
                                    drafts_list=drafts,
                                    operation=operation_value,
                                    selected_account_id=account_id,
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

    except GraphInterrupt:
        # Re-raise GraphInterrupt - it needs to propagate for interrupt() to work properly
        raise
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
        # Preserve display_emails from state if it exists
        return {
            "response": state.get("response"),
            "next_agent": "__end__",
            "display_emails": state.get("display_emails"),  # Preserve instead of clearing
        }

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
            "display_emails": None,  # Clear for direct answers that don't have emails
        }
    except Exception as e:
        return {
            "response": "Hello! I'm your email assistant. How can I help you today?",
            "next_agent": "__end__",
            "display_emails": None,  # Clear for error cases
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
        self.last_result = None

    def chat(self, message: str, context: str = "") -> str:
        """
        Process a user message and return the assistant's response.

        Handles both normal messages and resuming from interrupts.

        Args:
            message: User's message
            context: Optional additional context

        Returns:
            Assistant's response string
        """
        if not message or not message.strip():
            return "Please provide a message to get started."

        try:
            # Create config with thread_id and user_id for checkpointer
            # user_id is critical for multi-user state isolation (LangGraph best practice)
            config = {
                "configurable": {
                    "thread_id": self.thread_id,
                    "user_id": self.user_id or "default"
                }
            }

            # Check if we should resume from an interrupted state
            try:
                state_snapshot = self.graph.get_state(config)
                has_next = state_snapshot and state_snapshot.next and len(state_snapshot.next) > 0
                
                has_interrupts = False
                if state_snapshot and hasattr(state_snapshot, 'tasks') and state_snapshot.tasks:
                    for task in state_snapshot.tasks:
                        if hasattr(task, 'interrupts') and task.interrupts:
                            has_interrupts = True
                            break
                            
                is_interrupted = has_next or has_interrupts
            except Exception:
                is_interrupted = False

            # If interrupted, use Command(resume=...) to continue the graph flow
            if is_interrupted:
                logger.info(f"[ASSISTANT] Resuming interrupted graph with: {message[:50]}")
                result = self.graph.invoke(Command(resume=message), config)
                # Continue to process the result below
            # DEPRECATED fallback: Check if we have a pending draft selection (when interrupt() doesn't work)
            elif self.draft_pending and self.draft_pending.get("interrupt_reason") == "need_draft_selection":
                logger.info(f"[ASSISTANT] Handling pending draft selection with input: {message}")
                drafts_list = self.draft_pending.get("drafts_list", [])

                # Validate the selection
                if message.strip().isdigit():
                    selection = int(message.strip())
                    if 1 <= selection <= len(drafts_list):
                        selected_draft = drafts_list[selection - 1]
                        draft_id = selected_draft.get("id") or selected_draft.get("message_id")
                        logger.info(f"[ASSISTANT] User selected draft {selection}, id={draft_id}")

                        # Now perform the update with the selected draft
                        from .tools import create_draft_tools
                        tools = create_draft_tools(user_id=self.user_id)

                        for tool in tools:
                            if tool.name == "update_draft":
                                update_args = {"draft_id": draft_id}

                                # Add subject/body if provided
                                if self.draft_pending.get("subject"):
                                    update_args["subject"] = self.draft_pending.get("subject")
                                if self.draft_pending.get("body"):
                                    update_args["body"] = self.draft_pending.get("body")
                                if self.draft_pending.get("update_instruction"):
                                    update_args["instruction"] = self.draft_pending.get("update_instruction")

                                logger.info(f"[ASSISTANT] Calling update_draft with: {update_args}")
                                try:
                                    result_str = tool.invoke(update_args)
                                    result_dict = json.loads(result_str)
                                    self.draft_pending = None  # Clear pending state

                                    if result_dict.get("success"):
                                        response = result_dict.get("message", "Draft updated successfully")
                                    else:
                                        response = result_dict.get("message", "Failed to update draft")

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
                                    return response

                                except Exception as e:
                                    self.draft_pending = None
                                    return f"Error updating draft: {str(e)}"

                    else:
                        return f"Invalid selection. Please enter a number between 1 and {len(drafts_list)}."
                else:
                    return f"Please enter a number between 1 and {len(drafts_list)} to select a draft."
            else:
                # Normal message flow
                state = create_initial_state(
                    user_message=message,
                    user_id=self.user_id,
                    context=context,
                    existing_messages=self.conversation_history,
                    listed_emails=self.listed_emails,
                    draft_pending=self.draft_pending,
                )

                result = self.graph.invoke(state, config)

            self.last_result = result
            logger.info(f"[ASSISTANT] Graph result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")

            # Debug display_emails extraction
            if isinstance(result, dict):
                display_emails = result.get("display_emails")
                logger.info(f"[ASSISTANT] display_emails in result: {display_emails is not None}")
                if display_emails is not None:
                    logger.info(f"[ASSISTANT] display_emails type: {type(display_emails)}, count: {len(display_emails) if isinstance(display_emails, list) else 'not a list'}")
                    if isinstance(display_emails, list) and display_emails:
                        logger.info(f"[ASSISTANT] First email in display_emails: {display_emails[0].get('subject', 'NO SUBJECT') if isinstance(display_emails[0], dict) else 'INVALID'}")
                else:
                    logger.warning(f"[ASSISTANT] display_emails is None or missing from result")

            # Check if the graph has pending interrupts via state snapshot
            # This is the proper way to detect interrupts in LangGraph
            try:
                state_snapshot = self.graph.get_state(config)
                logger.info(f"[ASSISTANT] State snapshot next: {state_snapshot.next if state_snapshot else 'None'}")
                # Log all available attributes on state snapshot for debugging
                if state_snapshot:
                    snapshot_attrs = [attr for attr in dir(state_snapshot) if not attr.startswith('_')]
                    logger.info(f"[ASSISTANT] State snapshot attrs: {snapshot_attrs}")
                    logger.info(f"[ASSISTANT] has interrupts attr: {hasattr(state_snapshot, 'interrupts')}")
                    if hasattr(state_snapshot, 'interrupts'):
                        logger.info(f"[ASSISTANT] interrupts value: {state_snapshot.interrupts}")
                    if hasattr(state_snapshot, 'tasks'):
                        logger.info(f"[ASSISTANT] tasks value: {state_snapshot.tasks}")

                # Check for interrupts in state snapshot (LangGraph stores them in tasks)
                if state_snapshot and hasattr(state_snapshot, 'tasks') and state_snapshot.tasks:
                    # Interrupts are stored in tasks, not directly on state_snapshot
                    for task in state_snapshot.tasks:
                        if hasattr(task, 'interrupts') and task.interrupts:
                            interrupts = task.interrupts
                            logger.info(f"[ASSISTANT] Found {len(interrupts)} interrupt(s) in task {task.name}")

                            if len(interrupts) > 0:
                                # Extract the interrupt message from the first interrupt
                                first_interrupt = interrupts[0]
                                interrupt_msg = first_interrupt.value if hasattr(first_interrupt, 'value') else str(first_interrupt)
                                logger.info(f"[ASSISTANT] Interrupt message: {str(interrupt_msg)[:200]}")

                                # Update conversation history with the interrupt prompt
                                self.conversation_history.append({
                                    "role": "user",
                                    "content": message,
                                    "timestamp": datetime.now().isoformat(),
                                })
                                self.conversation_history.append({
                                    "role": "assistant",
                                    "content": interrupt_msg,
                                    "timestamp": datetime.now().isoformat(),
                                })

                                return interrupt_msg

            except Exception as snap_err:
                logger.info(f"[ASSISTANT] Could not get state snapshot: {snap_err}")

            # Also check for __interrupt__ in result (older LangGraph pattern)
            if isinstance(result, dict) and "__interrupt__" in result:
                interrupts = result["__interrupt__"]
                if interrupts and len(interrupts) > 0:
                    # Extract the interrupt message
                    interrupt_msg = interrupts[0].value if hasattr(interrupts[0], 'value') else str(interrupts[0])
                    logger.info(f"[ASSISTANT] Graph interrupted (from result): {interrupt_msg[:100]}")

                    # Update conversation history with the interrupt prompt
                    self.conversation_history.append({
                        "role": "user",
                        "content": message,
                        "timestamp": datetime.now().isoformat(),
                    })
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": interrupt_msg,
                        "timestamp": datetime.now().isoformat(),
                    })

                    return interrupt_msg

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

        except GraphInterrupt as gi:
            # Handle GraphInterrupt exception - extract the interrupt message
            # The interrupt contains the prompt we want to show the user
            logger.info(f"[ASSISTANT] GraphInterrupt caught: {gi}")

            # Extract the message from the interrupt
            interrupt_msg = "Please provide more information to continue."
            if gi.args and len(gi.args) > 0:
                interrupts = gi.args[0]
                # Interrupts can be a single object or a collection (list/tuple)
                first_interrupt = None
                if isinstance(interrupts, (list, tuple)) and len(interrupts) > 0:
                    first_interrupt = interrupts[0]
                else:
                    first_interrupt = interrupts

                # Extract value from the interrupt object
                if hasattr(first_interrupt, 'value'):
                    interrupt_msg = first_interrupt.value
                else:
                    interrupt_msg = str(first_interrupt)

            # Update conversation history
            self.conversation_history.append({
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat(),
            })
            self.conversation_history.append({
                "role": "assistant",
                "content": interrupt_msg,
                "timestamp": datetime.now().isoformat(),
            })

            return interrupt_msg

        except Exception as e:
            logger.error(f"Chat error: {e}", exc_info=True)
            return f"Sorry, I encountered an error: {str(e)}"

    def clear_history(self):
        """Clear conversation history and persisted state."""
        self.conversation_history = []
        self.thread_id = f"thread_{self.user_id or 'default'}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.listed_emails = None
        self.draft_pending = None
