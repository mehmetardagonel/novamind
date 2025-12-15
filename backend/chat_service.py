# Set protobuf to use pure Python implementation for Python 3.14 compatibility
# This MUST be done before any protobuf-using modules are imported
import os

os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

import json
import logging
from datetime import datetime

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import Tool
from langchain_google_genai import ChatGoogleGenerativeAI

from email_tools import (
    delete_all_spam,
    delete_draft,
    draft_email,
    fetch_mails,
    get_draft_by_id,
    get_drafts,
    get_drafts_for_recipient,
    move_mails_by_sender,
    send_draft,
    send_email,
    update_draft,
)
from ml_service import get_classifier


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class ChatService:
    _AGENT_EARLY_STOP_OUTPUT = "Agent stopped due to iteration limit or time limit."

    def __init__(self, user_id: str = None):
        """
        Initialize ChatService with user context.

        Args:
            user_id: User ID for multi-account support.
                     If None, falls back to legacy token.json.
        """
        self.user_id = user_id

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found! Check your .env file.")

        masked_key = f"{api_key[:10]}...{api_key[-4:]}" if len(api_key) > 14 else "***"
        logger.info(f"🔑 Using GEMINI_API_KEY: {masked_key}")

        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.7,
        )

        # Draft selection state - track pending draft selections
        # Example: {"drafts": [...], "operation": "send", "to_email": "..."}
        self.pending_selection = None

        self.tools = [
            Tool(
                name="fetch_mails",
                func=self._format_fetch_mails_response,
                description=(
                    "Advanced email fetching with multiple filter options. Provide filters as JSON.\n"
                    "Available filters: label, sender, importance (true/false), subject_keyword, folder, max_results (int, default 25)\n\n"
                    "For dates, use ONE of:\n"
                    "1. time_period: 'today', 'yesterday', 'last_week', 'last_month', 'last_3_months'\n"
                    "2. since_date and/or until_date: ISO format (YYYY-MM-DD)\n\n"
                    "All filters are optional and can be combined.\n"
                    "IMPORTANT:\n"
                    "- For a SINGLE specific day, use BOTH since_date AND until_date with the SAME date\n"
                    "- For a date range, use different since_date and until_date\n"
                    '- For "from X onwards", use only since_date\n'
                    "Examples:\n"
                    '- {"sender": "boss", "time_period": "today"}\n'
                    '- {"since_date": "2025-11-01"}\n'
                    '- {"since_date": "2025-11-01", "until_date": "2025-11-30"}\n'
                    '- {"label": "Work", "importance": true}\n'
                    '- {"sender": "team", "since_date": "2025-11-20"}\n'
                ),
            ),
            Tool(
                name="delete_all_spam",
                func=lambda _: json.dumps(delete_all_spam(user_id=self.user_id), indent=2),
                description="Delete all spam emails from the inbox. No input needed.",
            ),
            Tool(
                name="move_mails_by_sender",
                func=lambda x: json.dumps(self._parse_move_mails_by_sender(x), indent=2),
                description=(
                    "Move multiple emails from a specific sender to a target folder.\n"
                    'Input format: "sender|target_folder"\n\n'
                    "- sender: Sender name or email (partial match, case-insensitive)\n"
                    "- target_folder: Target label/folder (will be created if it doesn't exist)\n\n"
                    "Examples:\n"
                    '- "playstation|game"\n'
                    '- "amazon|shopping"\n'
                    '- "john|personal"\n'
                ),
            ),
            Tool(
                name="send_email",
                func=lambda x: json.dumps(self._parse_send_email(x), indent=2),
                description=(
                    "Send an email immediately.\n"
                    "Input format: 'to_email|subject|body'\n"
                    "Example: 'john@company.com|Tomorrow's Meeting|Hi John,...'\n"
                ),
            ),
            Tool(
                name="draft_email",
                func=lambda x: json.dumps(self._parse_draft_email(x), indent=2),
                description=(
                    "Create a draft email without sending it. You MUST ALWAYS provide the recipient email address.\n"
                    "Input format: 'to_email|subject|body' where:\n"
                    "- to_email: recipient's email address (REQUIRED - cannot be empty)\n"
                    "- subject: a clear, concise subject line (optional, can be empty)\n"
                    "- body: a well-written, professional email body that addresses the user's intent\n\n"
                    "CRITICAL RULES:\n"
                    "1. The recipient email address is MANDATORY - drafts cannot be created without it\n"
                    "2. If user provides only a name (e.g., \"John\"), ask for their full email address\n"
                    "3. If user does not provide a recipient, you MUST ASK for it before creating the draft\n"
                    "4. If the system returns \"requires_recipient\": true, prompt user for the email address\n"
                ),
            ),
            Tool(
                name="get_drafts",
                func=lambda _: json.dumps(get_drafts(user_id=self.user_id), indent=2),
                description="Get all draft emails. No input needed.",
            ),
            Tool(
                name="delete_draft_for_recipient",
                func=lambda x: self._delete_draft_for_recipient(x.strip()),
                description=(
                    "Delete a draft email for a specific recipient.\n"
                    "Input: recipient email address (e.g., 'alice@example.com')\n"
                    "If multiple drafts exist, you will be asked to choose which one."
                ),
            ),
            Tool(
                name="send_draft_for_recipient",
                func=lambda x: self._send_draft_for_recipient(x.strip()),
                description=(
                    "Send a draft email for a specific recipient.\n"
                    "Input: recipient email address (e.g., 'alice@example.com')\n"
                    "If multiple drafts exist, you will be asked to choose which one."
                ),
            ),
            Tool(
                name="get_drafts_for_recipient",
                func=lambda x: self._get_drafts_for_recipient_display(x.strip()),
                description=(
                    "Get all draft emails for a specific recipient.\n"
                    "Input: recipient email address (e.g., 'alice@example.com')"
                ),
            ),
            Tool(
                name="update_draft_for_recipient",
                func=lambda x: json.dumps(self._parse_update_draft_for_recipient(x), indent=2),
                description=(
                    "Update draft email body for a specific recipient with instructions.\n"
                    "Input format: 'email@example.com|update_instruction'\n"
                    "Example: 'alice@example.com|Make it more formal'\n"
                    "If multiple drafts exist, you will be asked to choose which one."
                ),
            ),
        ]

        try:
            self.ml_classifier = get_classifier()
            if self.ml_classifier:
                logger.info(" ML Classifier integrated into ChatService")
                self.tools.append(
                    Tool(
                        name="classify_emails_ml",
                        func=self._classify_emails_with_ml,
                        description="Classify emails using ML model (spam/ham/important). Input: JSON filters or empty string",
                    )
                )
        except Exception as e:
            logger.error(f" Could not load ML classifier: {str(e)}")
            self.ml_classifier = None

        system_prompt = """You are an AI email assistant. Your job is to help users manage their emails efficiently.

When users ask you to draft, send, or reply to emails:
1. Understand their intent and context
2. Compose professional, well-written emails with proper greetings and closings
3. Use appropriate tone (formal/informal) based on the context
4. Include relevant details from the user's request
5. For drafts, create complete emails that users can review before sending

MANDATORY REQUIREMENT FOR DRAFTS:
- Recipient email address is REQUIRED for all drafts
- You MUST NOT generate or assume email addresses
- You MUST ALWAYS ask user for email if not provided
- If user doesn't provide a recipient email, you MUST:
  1. Compose the email content based on their request
  2. Use the draft_email tool (which will return requires_recipient: true)
  3. When the system indicates recipient is needed, ASK THE USER for the recipient email
  4. Wait for user to provide the email address
  5. Then retry draft creation with the provided email
- If user provides only a name (e.g., "John"), politely ask for the full email address
- Never create "body-only" drafts

CRITICAL RULE FOR DRAFT OPERATIONS (UPDATE, SEND, DELETE):
When user asks about draft operations (update draft, send draft, delete draft), you MUST:
1. Identify the recipient email address
2. Identify the operation type (update/send/delete)
3. CALL the appropriate tool IMMEDIATELY - do NOT explain first or try to answer yourself
4. Wait for the tool result (which may ask user to select from multiple drafts)
5. Report the tool's result to user exactly as returned

IMPORTANT: Do NOT try to answer draft-related questions yourself.
ALWAYS use the draft_related tools first (update_draft_for_recipient, send_draft_for_recipient, delete_draft_for_recipient).
User may need to select a draft (1, 2, 3...) - show that selection list clearly.

CRITICAL RULE FOR FETCHING EMAILS:
When using the 'fetch_mails' tool, the tool will return a response containing both text and a JSON block.
You MUST include that raw JSON block in your 'Final Answer' exactly as it appears.
The frontend relies on this JSON to render the UI cards.
NEVER remove, summarize, or alter the JSON data returned by fetch_mails.
"""

        from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        agent = create_tool_calling_agent(llm=self.llm, tools=self.tools, prompt=prompt)

        max_iterations = 30
        max_execution_time = 180.0
        try:
            max_iterations = int(os.getenv("LANGCHAIN_AGENT_MAX_ITERATIONS", str(max_iterations)))
        except ValueError:
            pass
        try:
            max_execution_time = float(
                os.getenv("LANGCHAIN_AGENT_MAX_EXECUTION_TIME", str(max_execution_time))
            )
        except ValueError:
            pass

        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=False,
            handle_parsing_errors=True,
            return_intermediate_steps=True,
            max_iterations=max_iterations,
            max_execution_time=max_execution_time,
            early_stopping_method="force",
        )

    def _parse_fetch_mails(self, input_str: str) -> dict:
        try:
            if input_str.strip().startswith("{"):
                filters = json.loads(input_str)
                max_results_raw = filters.get("max_results", 25)
                try:
                    max_results = int(max_results_raw)
                except (TypeError, ValueError):
                    max_results = 25
                max_results = max(1, min(max_results, 50))
                return fetch_mails(
                    label=filters.get("label"),
                    sender=filters.get("sender"),
                    importance=filters.get("importance"),
                    time_period=filters.get("time_period"),
                    since_date=filters.get("since_date"),
                    until_date=filters.get("until_date"),
                    subject_keyword=filters.get("subject_keyword"),
                    folder=filters.get("folder"),
                    max_results=max_results,
                    user_id=self.user_id,
                )
            return fetch_mails(max_results=25, user_id=self.user_id)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON format for fetch_mails"}
        except Exception as e:
            return {"error": f"Fetch failed: {str(e)}"}

    def _format_fetch_mails_response(self, input_str: str) -> str:
        """Format fetch_mails response as clean email blocks and LIGHTWEIGHT JSON."""
        emails = self._parse_fetch_mails(input_str)

        if isinstance(emails, dict) and "error" in emails:
            return json.dumps(emails, indent=2, cls=DateTimeEncoder)

        if isinstance(emails, list):
            emails_for_json = []
            for email in emails:
                try:
                    e_copy = email.copy() if isinstance(email, dict) else email.model_dump()
                    if "body" in e_copy and e_copy["body"] and len(e_copy["body"]) > 200:
                        e_copy["body"] = e_copy["body"][:200] + "..."
                    emails_for_json.append(e_copy)
                except Exception:
                    emails_for_json.append(email)

            json_str = json.dumps(emails_for_json, indent=2, cls=DateTimeEncoder)
            return f"```json\n{json_str}\n```"

        return json.dumps(emails, indent=2, cls=DateTimeEncoder)

    def _parse_move_mails_by_sender(self, input_str: str) -> dict:
        try:
            parts = input_str.split("|", 1)
            if len(parts) < 2:
                return {"success": False, "message": "Invalid format. Use: 'sender|target_folder'"}

            sender = parts[0].strip()
            target_folder = parts[1].strip()

            if not sender or not target_folder:
                return {"success": False, "message": "Both sender and target_folder are required"}

            return move_mails_by_sender(sender, target_folder, user_id=self.user_id)
        except Exception as e:
            return {"success": False, "message": f"Failed to move emails: {str(e)}"}

    def _parse_send_email(self, input_str: str) -> dict:
        try:
            parts = input_str.split("|", 2)
            if len(parts) < 3:
                return {"success": False, "message": "Invalid input format. Use: 'to|subject|body'"}

            to = parts[0].strip()
            subject = parts[1].strip()
            body = parts[2].strip()
            return send_email(to, subject, body, user_id=self.user_id)
        except (ValueError, IndexError, AttributeError) as e:
            logger.warning(f"Error parsing send_email input: {str(e)}")
            return {"success": False, "message": "Invalid input format. Use: 'to|subject|body'"}

    def _parse_draft_email(self, input_str: str) -> dict:
        try:
            parts = input_str.split("|", 2)
            if len(parts) == 3:
                to = parts[0].strip()
                subject = parts[1].strip()
                body = parts[2].strip()
            elif len(parts) == 2:
                to = parts[0].strip()
                subject = parts[1].strip()
                body = ""
            elif len(parts) == 1:
                to = parts[0].strip()
                subject = ""
                body = ""
            else:
                to, subject, body = "", "", ""

            result = draft_email(to, subject, body, user_id=self.user_id)

            if result.get("requires_recipient"):
                self.pending_selection = {
                    "action": "draft_awaiting_recipient",
                    "composed_subject": subject,
                    "composed_body": body,
                }
                return {
                    "success": False,
                    "action_required": "ask_recipient",
                    "message": result.get("message"),
                    "hint": result.get("hint", ""),
                    "system_message": "Ask for the recipient email address. Wait for user response.",
                }

            return result

        except Exception as e:
            logger.error(f"Error parsing draft_email input: {str(e)}")
            return {"success": False, "message": f"Draft oluşturmada hata: {str(e)}"}

    def _parse_update_draft_for_recipient(self, input_str: str) -> dict:
        try:
            parts = input_str.split("|", 1)
            if len(parts) < 2:
                return {"error": "Invalid input format. Use: 'recipient_email|update_instruction'"}

            to_email = parts[0].strip()
            update_instruction = parts[1].strip()

            if not to_email or not update_instruction:
                return {"error": "Both recipient email and update instruction are required"}

            result_text = self._update_draft_for_recipient(to_email, update_instruction)
            return {"message": result_text}

        except Exception as e:
            logger.error(f"Error parsing update_draft_for_recipient input: {str(e)}")
            return {"error": f"Failed to update draft: {str(e)}"}

    def _smart_enhance_body_with_instruction(self, draft_id: str, instruction: str) -> str:
        """Use Gemini to intelligently update draft body based on user instruction."""
        try:
            draft = get_draft_by_id(draft_id, user_id=self.user_id)
            if not draft:
                logger.warning(f"Draft {draft_id} not found for body enhancement")
                return instruction

            current_body = ""
            if isinstance(draft, dict):
                msg = draft.get("message", {})
                if isinstance(msg, dict):
                    msg_id = msg.get("id")
                    if msg_id:
                        from gmail_service import _decode_body, get_gmail_service, get_primary_account_service
                        import asyncio

                        try:
                            if self.user_id:
                                service = asyncio.run(get_primary_account_service(self.user_id))
                            else:
                                service = get_gmail_service()

                            full_msg = (
                                service.users()
                                .messages()
                                .get(userId="me", id=msg_id, format="full")
                                .execute()
                            )
                            current_body = _decode_body(full_msg.get("payload", {}))
                        except Exception as e:
                            logger.warning(f"Could not fetch full message {msg_id}: {e}")
                            return instruction

            if not current_body:
                logger.warning(f"Draft {draft_id} has empty body")
                return instruction

            enhancement_prompt = f"""You are helping to update an email draft body.

Current draft body:
{current_body}

User instruction: {instruction}

Your task:
1. Read the current draft body carefully
2. Apply the user's instruction intelligently (they want you to {instruction})
3. Preserve the overall structure (greeting, main content, professional closing)
4. Maintain professional tone and context
5. Return the COMPLETE, UPDATED email body (not just the changed part)

IMPORTANT: Return the FULL email body (greeting + content + closing), not just the modified part."""

            response = self.llm.invoke(enhancement_prompt)
            enhanced_text = response.content.strip() if hasattr(response, "content") else str(response).strip()

            if not enhanced_text:
                logger.warning(f"Gemini returned empty response for draft {draft_id}")
                return instruction

            return enhanced_text

        except Exception as e:
            logger.warning(f"Gemini body enhancement failed for draft {draft_id}: {str(e)}")
            return instruction

    def _extract_json_from_response(self, response_text: str) -> str:
        import re

        code_block_match = re.search(
            r"```json\s*([\s\S]*?)\s*```", response_text, re.IGNORECASE
        )

        if code_block_match:
            json_str = (code_block_match.group(1) or "").strip()
            try:
                json.loads(json_str)
                code_block = response_text[code_block_match.start() : code_block_match.end()]
                intro_text = response_text[: code_block_match.start()].strip()
                if intro_text:
                    return f"{intro_text}\n\n{code_block}"
                return code_block
            except json.JSONDecodeError:
                pass

        json_match = re.search(r"\[[\s\S]*?\]", response_text)
        if json_match:
            json_str = json_match.group(0)
            try:
                json.loads(json_str)
                intro_text = response_text[: json_match.start()].strip()
                if intro_text:
                    return f"{intro_text}\n\n```json\n{json_str}\n```"
                return f"```json\n{json_str}\n```"
            except json.JSONDecodeError:
                return response_text

        return response_text

    def _get_last_tool_observation(
        self, intermediate_steps: list, tool_name: str
    ) -> str | None:
        for action, observation in reversed(intermediate_steps or []):
            try:
                if getattr(action, "tool", None) != tool_name:
                    continue
                if isinstance(observation, str) and observation.strip():
                    return observation
            except Exception:
                continue
        return None

    def _ensure_fetch_mails_json_block(self, output: str, intermediate_steps: list) -> str:
        fetch_obs = self._get_last_tool_observation(intermediate_steps, "fetch_mails")
        if not fetch_obs:
            return output

        # If the model already included a JSON fence, don't duplicate.
        if "```json" in (output or "").lower():
            return output

        if output and output.strip():
            return f"{output.strip()}\n\n{fetch_obs}"
        return fetch_obs

    def _handle_draft_selection(self, selection_idx: int) -> str:
        """Handle draft selection when user picks a number."""
        if not self.pending_selection:
            return "No draft selection pending. Please try your request again."

        drafts = self.pending_selection.get("drafts", [])
        operation = self.pending_selection.get("operation", "")

        if selection_idx < 1 or selection_idx > len(drafts):
            return f"❌ Invalid selection. Please choose 1-{len(drafts)}"

        selected_draft = drafts[selection_idx - 1]
        draft_id = selected_draft.get("id")
        subject = selected_draft.get("subject", "(No subject)")

        try:
            if operation == "send":
                self.pending_selection = {
                    "action": "send_draft_after_selection",
                    "draft_id": draft_id,
                    "subject": subject,
                }
                return f"Are you sure you want to send the draft '{subject}'?\n\nReply with 'Yes' or 'No'"

            if operation == "delete":
                delete_draft(draft_id, user_id=self.user_id)
                self.pending_selection = None
                return f"✅ Draft deleted: '{subject}'"

            if operation == "update":
                update_instruction = self.pending_selection.get("update_instruction", "")
                self.pending_selection = None

                if not update_instruction:
                    return f"No update instruction found. Selected draft: '{subject}'"

                new_body = self._smart_enhance_body_with_instruction(draft_id, update_instruction)
                result = update_draft(draft_id=draft_id, body=new_body, user_id=self.user_id)

                if result.get("success"):
                    return f"✅ Draft updated: '{subject} \n New body is: {new_body}'"
                return f"❌ Failed to update draft: {result.get('message', 'Unknown error')}"

            self.pending_selection = None
            return f"Unknown operation: {operation}"

        except Exception as e:
            logger.error(f"Error handling draft operation {operation} on {draft_id}: {str(e)}")
            self.pending_selection = None
            return f"❌ Error performing {operation}: {str(e)}"

    def _send_draft_for_recipient(self, to_email: str) -> str:
        try:
            drafts = get_drafts_for_recipient(to_email, user_id=self.user_id)
            if not drafts:
                return f"❌ No drafts found for {to_email}"

            if len(drafts) == 1:
                draft_id = drafts[0].get("id")
                subject = drafts[0].get("subject", "(No subject)")
                self.pending_selection = {
                    "action": "send_draft",
                    "draft_id": draft_id,
                    "to_email": to_email,
                    "subject": subject,
                }
                return f"Are you sure you want to send the draft '{subject}' to {to_email}?\n\nReply with 'Yes' or 'No'"

            draft_list = "\n".join(
                [
                    f"{i+1}️⃣ {d.get('subject', '(No subject)')[:40]}... ({d.get('date', 'Unknown')[:10]})"
                    for i, d in enumerate(drafts)
                ]
            )
            self.pending_selection = {"drafts": drafts, "operation": "send", "to_email": to_email}
            return (
                f"Found {len(drafts)} drafts for {to_email}:\n\n{draft_list}\n\n"
                "Which one would you like to send? (Reply with a number: 1, 2, 3...)"
            )

        except Exception as e:
            logger.error(f"Error sending draft for {to_email}: {str(e)}")
            return f"❌ Error: {str(e)}"

    def _delete_draft_for_recipient(self, to_email: str) -> str:
        try:
            drafts = get_drafts_for_recipient(to_email, user_id=self.user_id)
            if not drafts:
                return f"❌ No drafts found for {to_email}"

            if len(drafts) == 1:
                draft_id = drafts[0].get("id")
                subject = drafts[0].get("subject", "(No subject)")
                delete_draft(draft_id, user_id=self.user_id)
                return f"✅ Draft deleted: '{subject}'"

            draft_list = "\n".join(
                [
                    f"{i+1}️⃣ {d.get('subject', '(No subject)')[:40]}... ({d.get('date', 'Unknown')[:10]})"
                    for i, d in enumerate(drafts)
                ]
            )
            self.pending_selection = {"drafts": drafts, "operation": "delete", "to_email": to_email}
            return (
                f"Found {len(drafts)} drafts for {to_email}:\n\n{draft_list}\n\n"
                "Which one would you like to delete? (Reply with a number: 1, 2, 3...)"
            )

        except Exception as e:
            logger.error(f"Error deleting draft for {to_email}: {str(e)}")
            return f"❌ Error: {str(e)}"

    def _update_draft_for_recipient(self, to_email: str, update_instruction: str) -> str:
        try:
            drafts = get_drafts_for_recipient(to_email, user_id=self.user_id)
            if not drafts:
                return f"❌ No drafts found for {to_email}"

            if len(drafts) == 1:
                draft_id = drafts[0].get("id")
                subject = drafts[0].get("subject", "(No subject)")
                new_body = self._smart_enhance_body_with_instruction(draft_id, update_instruction)
                result = update_draft(draft_id=draft_id, body=new_body, user_id=self.user_id)
                if result.get("success"):
                    return f"✅ Draft updated: '{subject} \n New body is: {new_body}'"
                return f"❌ Failed to update draft: {result.get('message', 'Unknown error')}"

            draft_list = "\n".join(
                [
                    f"{i+1}️⃣ {d.get('subject', '(No subject)')[:40]}... ({d.get('date', 'Unknown')[:10]})"
                    for i, d in enumerate(drafts)
                ]
            )
            self.pending_selection = {
                "drafts": drafts,
                "operation": "update",
                "to_email": to_email,
                "update_instruction": update_instruction,
            }
            return (
                f"Found {len(drafts)} drafts for {to_email}:\n\n{draft_list}\n\n"
                "Which one would you like to update? (Reply with a number: 1, 2, 3...)"
            )

        except Exception as e:
            logger.error(f"Error updating draft for {to_email}: {str(e)}")
            return f"❌ Error: {str(e)}"

    def _get_drafts_for_recipient_display(self, to_email: str) -> str:
        try:
            drafts = get_drafts_for_recipient(to_email, user_id=self.user_id)
            if not drafts:
                return f"No drafts found for {to_email}"

            draft_list = "\n".join(
                [
                    f"📄 {i+1}. {d.get('subject', '(No subject)')} ({d.get('date', 'Unknown')[:10]})"
                    for i, d in enumerate(drafts)
                ]
            )
            return f"Found {len(drafts)} draft(s) for {to_email}:\n\n{draft_list}"

        except Exception as e:
            logger.error(f"Error getting drafts for {to_email}: {str(e)}")
            return f"❌ Error: {str(e)}"

    def _validate_email_format(self, email: str) -> bool:
        if not email or not isinstance(email, str):
            return False
        email = email.strip()
        if "@" not in email:
            return False
        parts = email.split("@")
        if len(parts) != 2:
            return False
        local, domain = parts
        if not local or not domain:
            return False
        if "." not in domain:
            return False
        return True

    def _handle_draft_recipient_input(self, user_input: str) -> str:
        if not self.pending_selection:
            return "Error: No pending draft. Please try again."

        email_input = user_input.strip()
        if not self._validate_email_format(email_input):
            return (
                f"'{email_input}' doesn't look like a valid email address.\n\n"
                "Please provide a valid email (e.g., john@example.com)"
            )

        composed_subject = self.pending_selection.get("composed_subject", "")
        composed_body = self.pending_selection.get("composed_body", "")

        try:
            result = draft_email(
                to=email_input,
                subject=composed_subject,
                body=composed_body,
                user_id=self.user_id,
            )
            self.pending_selection = None

            if result.get("success"):
                preview = result.get("draft", {})
                return (
                    "✅ Draft created successfully!\n\n"
                    f"Recipient: {email_input}\n"
                    f"Subject: {preview.get('subject', '(No subject)')}\n"
                    f"Preview: {preview.get('body', '')[:100]}..."
                )
            return f"❌ Error creating draft: {result.get('message', 'Unknown error')}"

        except Exception as e:
            logger.error(f"Error creating draft with recipient: {str(e)}")
            self.pending_selection = None
            return f"❌ Error: {str(e)}"

    def chat(self, user_message: str) -> str:
        try:
            if not user_message or not user_message.strip():
                return "Please provide a message to get started."

            message_stripped = user_message.strip()

            if self.pending_selection and "action" in self.pending_selection:
                action = self.pending_selection.get("action")

                if action == "draft_awaiting_recipient":
                    return self._handle_draft_recipient_input(message_stripped)

                if message_stripped.lower() in ["yes", "y"]:
                    if action == "send_draft":
                        draft_id = self.pending_selection["draft_id"]
                        to_email = self.pending_selection["to_email"]
                        result = send_draft(draft_id, user_id=self.user_id)
                        self.pending_selection = None
                        if result.get("success"):
                            return f"✅ Draft sent to {to_email}!"
                        return f"❌ Failed to send draft to {to_email}: {result.get('message', 'Unknown error')}"

                    if action == "send_draft_after_selection":
                        draft_id = self.pending_selection["draft_id"]
                        subject = self.pending_selection["subject"]
                        result = send_draft(draft_id, user_id=self.user_id)
                        self.pending_selection = None
                        if result.get("success"):
                            return f"✅ Draft sent: '{subject}'"
                        return f"❌ Failed to send draft '{subject}': {result.get('message', 'Unknown error')}"

                if message_stripped.lower() in ["no", "n"]:
                    self.pending_selection = None
                    return "❌ Draft not sent. Operation cancelled."

                return "Please reply with 'Yes' or 'No'"

            if self.pending_selection and message_stripped.isdigit():
                return self._handle_draft_selection(int(message_stripped))

            draft_keywords = [
                "update draft",
                "edit draft",
                "modify draft",
                "change draft",
                "send draft",
                "delete draft",
            ]
            is_draft_related = any(kw in message_stripped.lower() for kw in draft_keywords)

            logger.info("Sending request to Gemini Agent...")

            response = self.agent_executor.invoke({"input": user_message})
            output = response.get("output", "No response generated")
            intermediate_steps = response.get("intermediate_steps", [])

            if output and output.strip() == self._AGENT_EARLY_STOP_OUTPUT:
                logger.warning(
                    "Agent stopped early (steps=%s). Returning best-effort tool output.",
                    len(intermediate_steps) if isinstance(intermediate_steps, list) else "unknown",
                )
                best_effort = None
                if isinstance(intermediate_steps, list):
                    best_effort = self._get_last_tool_observation(intermediate_steps, "fetch_mails")
                    if not best_effort:
                        # If some other tool ran, return its last observation.
                        for _action, observation in reversed(intermediate_steps):
                            if isinstance(observation, str) and observation.strip():
                                best_effort = observation
                                break
                if best_effort:
                    return best_effort
                return (
                    "I couldn't finish that request in time. "
                    "Please try again with a shorter query (e.g., limit dates, sender, or max_results)."
                )

            if isinstance(intermediate_steps, list):
                output = self._ensure_fetch_mails_json_block(output, intermediate_steps)

            if is_draft_related and not self.pending_selection:
                import re

                email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", message_stripped)
                if email_match:
                    email = email_match.group()
                    instruction = message_stripped.split(email, 1)[1].strip()
                    if instruction:
                        if any(k in message_stripped.lower() for k in ["update", "edit", "modify"]):
                            logger.info(
                                f"[FALLBACK] Using direct invocation for update_draft_for_recipient: {email}"
                            )
                            fallback_result = self._parse_update_draft_for_recipient(f"{email}|{instruction}")
                            return json.dumps(fallback_result, indent=2, cls=DateTimeEncoder)
                        if "send" in message_stripped.lower():
                            logger.info(
                                f"[FALLBACK] Using direct invocation for send_draft_for_recipient: {email}"
                            )
                            return self._send_draft_for_recipient(email)
                        if "delete" in message_stripped.lower():
                            logger.info(
                                f"[FALLBACK] Using direct invocation for delete_draft_for_recipient: {email}"
                            )
                            return self._delete_draft_for_recipient(email)

            return self._extract_json_from_response(output)

        except ValueError as e:
            logger.warning(f"Input validation error: {str(e)}")
            return f"Invalid input: {str(e)}. Please try again with a valid message."
        except TimeoutError as e:
            logger.warning(f"Timeout error: {str(e)}")
            return "The request took too long. Please try again or check your connection."
        except KeyError as e:
            logger.error(f"Response structure error: {str(e)}")
            return "Unexpected response format. Please try again."
        except Exception as e:
            logger.error(f"Chat processing error: {str(e)}", exc_info=True)
            return "Sorry, I encountered an error processing your request. Please try again later."

    def _classify_emails_with_ml(self, input_str: str) -> str:
        if not self.ml_classifier:
            return " ML classifier not available"

        try:
            filters = json.loads(input_str) if input_str.strip().startswith("{") else {}
            emails = fetch_mails(**filters, max_results=50, user_id=self.user_id)

            if not emails:
                return "No emails found to classify."

            classified_emails = self.ml_classifier.classify_batch(emails)
            summary = self.ml_classifier.get_classification_summary(classified_emails)

            response = "📊 ML Classification Results\n\n"
            response += f"Total Emails: {summary['total']}\n\n"

            for pred, count in summary["by_prediction"].items():
                emoji = "🚫" if pred == "spam" else "⭐" if pred == "important" else "📧"
                response += f"{emoji} {pred.upper()}: {count} emails\n"

            return response

        except Exception as e:
            logger.error(f"ML classification error: {str(e)}")
            return f" Classification failed: {str(e)}"

    def clear_history(self):
        pass
