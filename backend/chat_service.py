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
from langchain_core.messages import HumanMessage, AIMessage

def _patch_langchain_google_genai_finish_reason() -> None:
    """
    Patch langchain-google-genai to handle newer/unknown finish_reason values.

    Some versions of google generativeai return finish_reason as an int for unknown enums,
    but langchain-google-genai expects an enum with a .name attribute.

    This patch is compatible with both langchain-google-genai 1.x and 2.x.
    """
    import warnings

    # Suppress the proto-plus enum warning
    warnings.filterwarnings("ignore", message="Unrecognized FinishReason enum value")

    try:
        import langchain_google_genai.chat_models as genai_chat_models  # type: ignore
    except ImportError:
        return

    if getattr(genai_chat_models, "_novamind_finish_reason_patch", False):
        return

    # Check if this is langchain-google-genai 2.x (uses google-genai SDK)
    # vs 1.x (uses google-generativeai SDK)
    original = getattr(genai_chat_models, "_response_to_result", None)
    if not callable(original):
        # In 2.x, the structure is different - the patch may not be needed
        # as the new SDK handles unknown enums better
        genai_chat_models._novamind_finish_reason_patch = True
        return

    def _safe_finish_reason(fr) -> str:
        name = getattr(fr, "name", None)
        if name is not None:
            return str(name)
        return str(fr)

    def patched(response, stream: bool = False):  # type: ignore[no-untyped-def]
        try:
            llm_output = {
                "prompt_feedback": genai_chat_models.proto.Message.to_dict(response.prompt_feedback)
            }
        except Exception:
            llm_output = {}

        try:
            input_tokens = response.usage_metadata.prompt_token_count
            output_tokens = response.usage_metadata.candidates_token_count
            total_tokens = response.usage_metadata.total_token_count
            if input_tokens + output_tokens + total_tokens > 0:
                lc_usage = genai_chat_models.UsageMetadata(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                )
            else:
                lc_usage = None
        except (AttributeError, Exception):
            lc_usage = None

        generations = []
        for candidate in response.candidates:
            generation_info = {}
            finish_reason = getattr(candidate, "finish_reason", None)
            if finish_reason:
                generation_info["finish_reason"] = _safe_finish_reason(finish_reason)
            try:
                generation_info["safety_ratings"] = [
                    genai_chat_models.proto.Message.to_dict(
                        safety_rating, use_integers_for_enums=False
                    )
                    for safety_rating in candidate.safety_ratings
                ]
            except Exception:
                generation_info["safety_ratings"] = []

            message = genai_chat_models._parse_response_candidate(candidate, streaming=stream)
            message.usage_metadata = lc_usage
            generations.append(
                (genai_chat_models.ChatGenerationChunk if stream else genai_chat_models.ChatGeneration)(
                    message=message,
                    generation_info=generation_info,
                )
            )

        if not response.candidates:
            genai_chat_models.logger.warning(
                "Gemini produced an empty response. Continuing with empty message\n"
                f"Feedback: {response.prompt_feedback}"
            )
            generations = [
                (genai_chat_models.ChatGenerationChunk if stream else genai_chat_models.ChatGeneration)(
                    message=(
                        genai_chat_models.AIMessageChunk if stream else genai_chat_models.AIMessage
                    )(content=""),
                    generation_info={},
                )
            ]

        return genai_chat_models.ChatResult(generations=generations, llm_output=llm_output)

    genai_chat_models._response_to_result = patched  # type: ignore[assignment]
    genai_chat_models._novamind_finish_reason_patch = True


_patch_langchain_google_genai_finish_reason()

from email_tools import (
    delete_all_spam,
    delete_draft,
    draft_email,
    fetch_mails,
    get_draft_body,
    list_email_accounts,
    get_drafts,
    get_drafts_for_recipient,
    move_mails_by_sender,
    query_emails,
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

        # Use configured Gemini model (defaults to gemini-3-flash).
        # Note: Avoid 2.5 for now due to tool-calling instability with LangChain agents.
        self.llm = ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-3-flash"),
            google_api_key=api_key,
            temperature=0.7,
        )

        # Draft selection state - track pending draft selections
        # Example: {"drafts": [...], "operation": "send", "to_email": "..."}
        self.pending_selection = None
        self.chat_history: list = []
        self._max_history_messages = 12

        self.tools = [
            Tool(
                name="list_email_accounts",
                func=lambda _: json.dumps(list_email_accounts(user_id=self.user_id), indent=2),
                description=(
                    "List connected email accounts (Gmail + Outlook) for the current user.\n"
                    "Use this when you need to choose a specific provider/account.\n"
                    "No input needed."
                ),
            ),
            Tool(
                name="fetch_mails",
                func=self._format_fetch_mails_response,
                description=(
                    "Advanced email fetching with multiple filter options. Provide filters as JSON.\n"
                    "Available filters: label, sender, importance (true/false), subject_keyword, folder, max_results (int, default 25), provider ('gmail'|'outlook'), account_id\n\n"
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
                    "Create a draft email. Input must be a SINGLE STRING with pipe separators.\n\n"
                    "REQUIRED FORMAT: 'recipient@email.com|Subject Line|Email body text'\n\n"
                    "EXAMPLES:\n"
                    "- 'john@company.com|Meeting Tomorrow|Hi John, Let's discuss the project tomorrow at 2pm. Best regards'\n"
                    "- 'alice@example.com|Grocery List|Hi Alice, Here's the grocery list: milk, eggs, bread. Thanks!'\n"
                    "- 'bob@test.com|Quick Question|Hi Bob, Do you have time for a quick call? Let me know. Thanks'\n\n"
                    "CRITICAL RULES:\n"
                    "1. ALWAYS use pipe | character to separate the three parts: email|subject|body\n"
                    "2. Generate intelligent subject and body from user's context (e.g., 'about the grocery list' -> create subject: 'Grocery List' and body with grocery list content)\n"
                    "3. NEVER ask user for subject/body after they provide context - generate them automatically\n"
                    "4. If user doesn't provide recipient email, the tool will ask for it\n"
                    "5. If user says 'about X', create subject and body related to X\n\n"
                    "WRONG: calling this tool with 3 separate arguments\n"
                    "RIGHT: calling this tool with ONE string argument like 'email@test.com|Subject|Body'\n"
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
            Tool(
                name="query_emails",
                func=lambda x: json.dumps(query_emails(query=x, user_id=self.user_id), indent=2),
                description=(
                    "Query emails using natural language. This tool intelligently searches emails "
                    "and provides insights based on your query.\n\n"
                    "Use this when the user asks questions about their emails like:\n"
                    "- 'what did I receive from Google jobs'\n"
                    "- 'is there anything important from Google jobs'\n"
                    "- 'do I have any meetings tomorrow'\n"
                    "- 'show me emails about project updates from last week'\n"
                    "- 'what emails do I have about the budget'\n\n"
                    "Input: Natural language query string\n"
                    "Example: 'what did I receive from Google jobs'\n\n"
                    "The tool will:\n"
                    "1. Use semantic search if enabled for better results\n"
                    "2. Fall back to intelligent keyword filtering\n"
                    "3. Extract relevant filters (sender, time period, importance, subject)\n"
                    "4. Return matching emails with insights and summaries\n\n"
                    "Output includes:\n"
                    "- Count of matching emails\n"
                    "- Email details (sender, subject, date, body preview)\n"
                    "- Insights (top senders, important emails, meeting notifications)\n"
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
                        description=(
                            "Classify emails using ML model to identify spam, ham, and important emails. "
                            "Also provides a summary of email classifications.\n"
                            "Use this tool when the user asks for:\n"
                            "- Email classification or categorization\n"
                            "- Summary of emails (e.g., 'summarize my emails', 'give me a summary')\n"
                            "- Important emails (e.g., 'show important emails', 'what important things do I have')\n"
                            "- Email statistics or overview\n"
                            "Input: JSON filters (e.g., {\"since_date\": \"2025-01-10\"}) or empty string for all recent emails"
                        ),
                    )
                )
        except Exception as e:
            logger.error(f" Could not load ML classifier: {str(e)}")
            self.ml_classifier = None

        system_prompt = """You are an AI email assistant. Your job is to help users manage their emails efficiently.

CRITICAL COMMUNICATION RULES:
1. NEVER output raw JSON responses to the user (EXCEPTION: fetch_mails tool requires JSON for UI rendering)
2. ALWAYS respond in natural, conversational language
3. When users request features you don't have:
   - Politely acknowledge you can't do that specific thing
   - Immediately suggest similar features you CAN do
   - Ask if the alternative would work for them
   - Example: "I don't have a direct archive feature, but I can move emails to a specific label for you. Would that work?"
4. Be friendly, helpful, and solution-oriented
5. Present information in readable, formatted text - NOT as JSON objects

This system can access both Gmail and Outlook accounts.
- Use the tool `list_email_accounts` when you need to choose a specific account/provider.
- The tool `fetch_mails` can filter by `provider` ('gmail'|'outlook') and/or `account_id`.

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

CRITICAL RULE FOR AFTER CREATING DRAFTS:
- After successfully creating a draft, simply confirm it was created with the recipient and subject
- DO NOT ask if the user wants to send it immediately
- DO NOT suggest actions like "send this draft?" or "would you like to send it?"
- Let the user explicitly request to send the draft if they want to
- Example good response: "✅ Draft created to [email] with subject '[subject]'"
- Example bad response: "Draft created. Would you like to send it now?" (DO NOT DO THIS)

CRITICAL RULE FOR DRAFT OPERATIONS (UPDATE, SEND, DELETE):
When user asks about draft operations (update draft, send draft, delete draft), you MUST:
1. Identify the recipient email address
2. Identify the operation type (update/send/delete)
3. CALL the appropriate tool ONCE - do NOT call it multiple times
4. Return the tool's output DIRECTLY to the user WITHOUT any additional text or explanation
5. If the tool asks for confirmation or selection, pass that message to the user EXACTLY as it appears

CRITICAL: When the tool returns a confirmation request like "Are you sure you want to send...", you MUST return that exact message to the user.
DO NOT add your own commentary like "Okay, I'm ready to send..." or "I'll send the draft now...".
DO NOT call the same tool multiple times for the same request.
The tool's output IS your response - return it verbatim.

CRITICAL RULE FOR FETCHING EMAILS:
When using the 'fetch_mails' tool, the tool will return a JSON block fenced in ```json ...```.
You MUST include that raw JSON block in your final answer exactly as it appears.
The frontend relies on this JSON to render the UI cards.
NEVER remove, summarize, or alter the JSON data returned by fetch_mails.

CRITICAL RULE FOR QUERYING EMAILS:
When using the 'query_emails' tool, the tool will return a JSON response with:
- insights: A natural language summary of the results
- emails: List of matching emails with details
- count: Number of emails found
- filters_used: The filters extracted from the query

IMPORTANT: You MUST extract the information from this JSON and present it conversationally to the user.
DO NOT copy-paste the raw JSON. Transform it into friendly, readable text.

UNDERSTANDING USER QUERIES (Few-Shot Learning):
Here are examples of how to interpret different types of queries:

Example 1:
User: "what did I receive from Google jobs?"
Interpretation: User wants emails ABOUT Google jobs/careers, not necessarily FROM Google.
Look for: Emails with "Google", "jobs", "careers" in subject or body
Tool to use: query_emails

Example 2:
User: "is there anything important from Google jobs?"
Interpretation: Same as above, but filter for important emails
Look for: Important emails about Google jobs/careers
Tool to use: query_emails

Example 3:
User: "do I have any meetings tomorrow?"
Interpretation: User wants emails about meetings in the near future
Look for: Emails with "meeting", "invitation", "event" in subject
Tool to use: query_emails

Example 4:
User: "emails from John about the project"
Interpretation: Emails FROM a person named John, ABOUT the project
Look for: Sender contains "John" AND subject/body contains "project"
Tool to use: query_emails

RESPONSE FORMAT:
You MUST:
1. Present the insights in a conversational, friendly way
2. Show the most relevant emails first (especially those matching the query best)
3. For emails about jobs/careers, highlight the job title, company, and key details
4. For meeting invitations, highlight the date, time, and subject
5. If there are many results, summarize and show the top 3-5 most relevant ones
6. Always include the sender, subject, and date for each email shown

Example response format:
"I found [count] emails about [topic]. [insights]

The most relevant ones are:

1. **[Subject]** from [Sender]
   Date: [date]
   [Key details from preview]

2. **[Subject]** from [Sender]
   Date: [date]
   [Key details from preview]

Would you like me to show more details about any of these?"
"""

        from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt + "\n\n{context}"),
                MessagesPlaceholder(variable_name="chat_history"),
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

    def _append_to_history(self, user_text: str, assistant_text: str) -> None:
        try:
            if user_text and user_text.strip():
                self.chat_history.append(HumanMessage(content=user_text.strip()))

            assistant_clean = (assistant_text or "").strip()
            if assistant_clean:
                import re

                assistant_clean = re.sub(r"```[\s\S]*?```", "", assistant_clean).strip()
                self.chat_history.append(AIMessage(content=assistant_clean[:2000]))

            if len(self.chat_history) > self._max_history_messages:
                self.chat_history = self.chat_history[-self._max_history_messages :]
        except Exception:
            # History is best-effort; never break the chat flow.
            return

    def _extract_raw_user_message(self, user_message: str) -> str:
        """Extract the actual user text when RAG context is prepended by the API layer."""
        if not user_message:
            return ""

        marker = "User message:"
        if marker in user_message:
            return user_message.split(marker, 1)[1].strip()
        return user_message.strip()

    def _build_summary_from_emails(
        self,
        emails: list,
        time_period: str | None = None,
        importance: bool | None = None,
        provider: str | None = None,
        max_items: int = 5,
    ) -> str:
        if not emails:
            period_label = (time_period or "recent").replace("_", " ")
            provider_label = (
                "Outlook" if provider == "outlook" else "Gmail" if provider == "gmail" else ""
            )
            provider_prefix = f"{provider_label} " if provider_label else ""
            if importance:
                return (
                    "I checked your inbox and didn’t find any "
                    f"important {provider_prefix}emails for {period_label}."
                )
            return f"I checked your inbox and didn’t find any emails to summarize for {period_label}."

        total = len(emails)
        period_label = (time_period or "recent").replace("_", " ")
        provider_label = (
            "Outlook" if provider == "outlook" else "Gmail" if provider == "gmail" else ""
        )
        provider_prefix = f"{provider_label} " if provider_label else ""

        items = []
        for email in emails[:max_items]:
            if isinstance(email, dict):
                sender = (email.get("sender") or "Unknown sender").strip()
                subject = (email.get("subject") or "(No subject)").strip()
            else:
                sender = getattr(email, "sender", "Unknown sender")
                subject = getattr(email, "subject", "(No subject)")
            sender = sender.replace('"', "")
            items.append(f"{subject} from {sender}")

        highlights = "; ".join(items)
        if total > max_items:
            highlights = f"{highlights}, and {total - max_items} more"

        importance_label = "important " if importance else ""
        if time_period:
            if time_period in {"today", "yesterday"}:
                scope = f"from {period_label}"
            else:
                scope = f"from the {period_label}"
        else:
            scope = "recently"
        return f"Your {importance_label}{provider_prefix}emails {scope} ({total}) include {highlights}."

    def _summarize_emails_with_llm(
        self,
        emails: list,
        time_period: str | None = None,
        importance: bool | None = None,
        provider: str | None = None,
        max_items: int = 20,
    ) -> str | None:
        if not emails:
            return None

        period_label = (time_period or "recent").replace("_", " ")
        provider_label = (
            "Outlook" if provider == "outlook" else "Gmail" if provider == "gmail" else ""
        )
        provider_prefix = f"{provider_label} " if provider_label else ""
        importance_label = "important " if importance else ""

        items = []
        for email in emails[:max_items]:
            if isinstance(email, dict):
                sender = (email.get("sender") or "Unknown sender").strip()
                subject = (email.get("subject") or "(No subject)").strip()
                body = (email.get("body") or "").strip()
                date = email.get("date")
            else:
                sender = getattr(email, "sender", "Unknown sender")
                subject = getattr(email, "subject", "(No subject)")
                body = getattr(email, "body", "")
                date = getattr(email, "date", None)

            snippet = " ".join(body.split())
            if len(snippet) > 180:
                snippet = snippet[:180].rstrip() + "..."
            date_str = date.isoformat() if hasattr(date, "isoformat") else str(date or "")
            items.append(
                f"- Subject: {subject}\n  From: {sender}\n  Date: {date_str}\n  Snippet: {snippet}"
            )

        prompt = (
            "You are an email assistant. Write a concise, human-sounding paragraph summary "
            f"of the user's {importance_label}{provider_prefix}emails from {period_label}. "
            "Focus on the main topics and any action items. "
            "Use 2-4 sentences. Do NOT use bullet points, lists, JSON, or code fences.\n\n"
            "Emails:\n" + "\n".join(items)
        )

        try:
            response = self.llm.invoke(prompt)
            summary = response.content.strip() if hasattr(response, "content") else str(response).strip()
        except Exception as e:
            logger.warning(f"LLM summary failed: {e}")
            return None

        if not summary:
            return None

        import re

        summary = re.sub(r"```[\s\S]*?```", "", summary).strip()
        if not summary or summary.lower().startswith("```"):
            return None
        if any(token in summary for token in ["```json", "{", "[", "]"]):
            return None

        return summary

    def _get_provider_accounts(self, provider: str) -> list:
        try:
            accounts = list_email_accounts(user_id=self.user_id) or []
        except Exception:
            return []
        return [acc for acc in accounts if acc.get("provider") == provider]

    def _resolve_account_from_message(self, accounts: list, message: str) -> str | None:
        if not accounts:
            return None

        import re

        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", message or "")
        if email_match:
            email = email_match.group(0).lower()
            for acc in accounts:
                if (acc.get("email_address") or "").lower() == email:
                    return acc.get("id")

        return None

    def _prompt_for_account_choice(self, provider: str, accounts: list, payload: dict, mode: str) -> str:
        provider_label = "Gmail" if provider == "gmail" else "Outlook"
        lines = []
        for idx, acc in enumerate(accounts, start=1):
            email = acc.get("email_address", "Unknown")
            display = acc.get("display_name") or email
            lines.append(f"{idx}. {display} ({email})")

        self.pending_selection = {
            "action": "account_choice",
            "provider": provider,
            "accounts": accounts,
            "payload": payload,
            "mode": mode,
        }

        return (
            f"I see multiple {provider_label} accounts. Which one should I use?\n\n"
            + "\n".join(lines)
            + "\n\nReply with a number or the email address."
        )

    def _build_fetch_intro(self, payload: dict) -> str:
        provider = payload.get("provider")
        time_period = payload.get("time_period")
        importance = payload.get("importance")
        max_results = payload.get("max_results", 25)

        provider_label = "Outlook" if provider == "outlook" else "Gmail" if provider == "gmail" else ""
        provider_prefix = f"{provider_label} " if provider_label else ""

        if importance and time_period:
            period_label = str(time_period).replace("_", " ")
            return f"Here are your important {provider_prefix}emails from {period_label}:"
        if provider == "outlook" and int(max_results) == 1:
            return "Here’s your latest Outlook email:"
        if provider == "gmail" and int(max_results) == 1:
            return "Here’s your latest Gmail email:"
        if provider == "outlook":
            return "Here are your Outlook inbox emails:"
        if provider == "gmail":
            return "Here are your Gmail inbox emails:"
        return "Here are your inbox emails:"

    def _maybe_handle_summary_request(self, raw_user_message: str) -> str | None:
        """Handle summary-style inbox requests deterministically."""
        msg = (raw_user_message or "").strip()
        if not msg:
            return None

        msg_lower = msg.lower()

        if any(k in msg_lower for k in ["draft", "send", "reply", "forward"]):
            return None

        summary_keywords = [
            "summarize",
            "summarise",
            "summary",
            "recap",
            "overview",
            "highlight",
            "highlights",
            "brief",
            "news",
            "updates",
        ]
        significant_keywords = ["significant", "important", "priority", "high priority", "urgent"]
        email_keywords = ["email", "emails", "inbox", "message", "messages", "mail", "mails"]

        wants_summary = any(k in msg_lower for k in summary_keywords)
        wants_significant = any(k in msg_lower for k in significant_keywords)

        time_period = None
        if any(k in msg_lower for k in ["this week", "last week", "past week", "recent week"]):
            time_period = "last_week"
        elif any(k in msg_lower for k in ["this month", "last month", "past month"]):
            time_period = "last_month"
        elif any(k in msg_lower for k in ["last 3 months", "past 3 months", "three months"]):
            time_period = "last_3_months"
        elif "yesterday" in msg_lower:
            time_period = "yesterday"
        elif "today" in msg_lower:
            time_period = "today"

        if not wants_summary and not wants_significant:
            return None

        provider = None
        if "outlook" in msg_lower:
            provider = "outlook"
        elif "gmail" in msg_lower:
            provider = "gmail"

        is_emailish = any(k in msg_lower for k in email_keywords) or provider is not None
        if not is_emailish and not time_period and not wants_summary:
            return None

        list_keywords = ["show", "list", "display", "get", "fetch", "see"]
        if wants_significant and not wants_summary and any(k in msg_lower for k in list_keywords):
            return None

        importance = True if wants_significant else None
        if wants_significant and not time_period:
            time_period = "today"
        time_period = time_period or "today"

        payload = {"folder": "inbox", "max_results": 25, "time_period": time_period}
        if provider:
            payload["provider"] = provider
        if importance is not None:
            payload["importance"] = importance

        if provider:
            accounts = self._get_provider_accounts(provider)
            if len(accounts) > 1:
                matched_id = self._resolve_account_from_message(accounts, msg)
                if matched_id:
                    payload["account_id"] = matched_id
                else:
                    return self._prompt_for_account_choice(
                        provider=provider,
                        accounts=accounts,
                        payload=payload,
                        mode="summary",
                    )

        emails = self._parse_fetch_mails(json.dumps(payload))
        if isinstance(emails, dict) and "error" in emails:
            return json.dumps(emails, indent=2, cls=DateTimeEncoder)
        if not isinstance(emails, list):
            return "I couldn't fetch your emails right now. Please try again."

        llm_summary = self._summarize_emails_with_llm(
            emails=emails,
            time_period=time_period,
            importance=importance,
            provider=provider,
        )
        if llm_summary:
            return llm_summary

        return self._build_summary_from_emails(
            emails=emails,
            time_period=time_period,
            importance=importance,
            provider=provider,
        )

    def _maybe_handle_direct_inbox_fetch(self, raw_user_message: str) -> str | None:
        """Handle common inbox requests without the LLM.

        This acts as a safety net for cases where the LLM returns an empty response
        (Gemini occasionally produces empty candidates), and it also avoids
        unnecessary multi-turn clarification when the provider is explicit.
        """
        msg = (raw_user_message or "").strip()
        if not msg:
            return None

        msg_lower = msg.lower()

        provider = None
        if "outlook" in msg_lower:
            provider = "outlook"
        elif "gmail" in msg_lower:
            provider = "gmail"

        # For provider-agnostic requests we only auto-handle "important" time-bounded queries.
        importance = None
        if any(k in msg_lower for k in ["important", "priority", "high priority"]):
            # Note: we intentionally do not implement "not important" here; keep it conservative.
            importance = True

        time_period = None
        if any(k in msg_lower for k in ["this week", "last week", "past week", "recent week"]):
            time_period = "last_week"
        elif any(k in msg_lower for k in ["this month", "last month", "past month"]):
            time_period = "last_month"
        elif any(k in msg_lower for k in ["last 3 months", "past 3 months", "three months"]):
            time_period = "last_3_months"
        elif "yesterday" in msg_lower:
            time_period = "yesterday"
        elif "today" in msg_lower:
            time_period = "today"

        # Avoid hijacking non-inbox/connection troubleshooting.
        negative_keywords = [
            "connect",
            "connection",
            "integration",
            "oauth",
            "token",
            "login",
            "log in",
            "sign in",
            "signin",
            "authenticate",
            "auth",
        ]
        email_keywords = [
            "email",
            "emails",
            "inbox",
            "message",
            "messages",
            "mail",
            "mails",
        ]
        action_keywords = [
            "latest",
            "newest",
            "most recent",
            "recent",
            "last",
            "check",
            "show",
            "read",
            "fetch",
            "get",
            "receive",
            "received",
            "got",
        ]

        if any(k in msg_lower for k in ["draft", "send", "reply", "forward"]):
            return None

        if any(k in msg_lower for k in negative_keywords) and not any(
            k in msg_lower for k in email_keywords
        ):
            return None

        is_emailish = (
            any(k in msg_lower for k in email_keywords)
            or any(k in msg_lower for k in action_keywords)
            or provider is not None
        )
        if not is_emailish and importance and time_period:
            # Users often omit the word "email" in questions like:
            # "Do I have anything important this week?"
            is_emailish = True
        if not is_emailish:
            return None

        latest_keywords = [
            "latest",
            "newest",
            "most recent",
            "last message",
            "last email",
            "latest message",
            "latest email",
        ]
        max_results = 1 if any(k in msg_lower for k in latest_keywords) else 25

        # If the user asks for "latest" without specifying a provider, ask a deterministic clarifying question.
        if max_results == 1 and not provider:
            try:
                accounts = list_email_accounts(user_id=self.user_id) or []
                providers = {a.get("provider") for a in accounts if isinstance(a, dict)}
                providers = {p for p in providers if p}
                if len(providers) >= 2:
                    # Store a lightweight pending action so a follow-up like "Outlook" works reliably.
                    # (This mirrors the UI flow shown in the product screenshot.)
                    self.pending_selection = {
                        "action": "inbox_provider_choice",
                        "max_results": max_results,
                        "folder": "inbox",
                    }
                    return (
                        "I see you have both Gmail and Outlook accounts connected. "
                        "Which one should I check for the latest email?"
                    )
            except Exception:
                pass
        elif not provider and not (importance and time_period):
            # Only auto-handle provider-agnostic requests for:
            # - time-bounded importance queries ("important this week")
            # - latest email (handled above)
            return None

        if importance and not time_period:
            time_period = "today"

        payload = {"folder": "inbox", "max_results": max_results}
        if provider:
            payload["provider"] = provider
        if importance is not None:
            payload["importance"] = importance
        if time_period:
            payload["time_period"] = time_period

        if provider:
            accounts = self._get_provider_accounts(provider)
            if len(accounts) > 1:
                matched_id = self._resolve_account_from_message(accounts, msg)
                if matched_id:
                    payload["account_id"] = matched_id
                else:
                    return self._prompt_for_account_choice(
                        provider=provider,
                        accounts=accounts,
                        payload=payload,
                        mode="fetch",
                    )
        try:
            emails = self._parse_fetch_mails(json.dumps(payload))
        except Exception as e:
            logger.error(f"Direct inbox fetch failed: {e}")
            return None

        if isinstance(emails, dict) and "error" in emails:
            return json.dumps(emails, indent=2, cls=DateTimeEncoder)

        if not isinstance(emails, list):
            return "I couldn't fetch your emails right now. Please try again."

        if not emails:
            return self._build_summary_from_emails(
                emails=emails,
                time_period=time_period,
                importance=importance,
                provider=provider,
            )

        emails_block = self._format_email_list_json_block(emails)

        if importance and time_period:
            provider_label = "Outlook" if provider == "outlook" else "Gmail" if provider == "gmail" else ""
            provider_prefix = f"{provider_label} " if provider_label else ""
            period_label = time_period.replace("_", " ")
            if time_period in {"today", "yesterday"}:
                intro = f"Here are your important {provider_prefix}emails from {period_label}:"
            else:
                intro = f"Here are your important {provider_prefix}emails from the {period_label}:"
        elif provider == "outlook" and max_results == 1:
            intro = "Here’s your latest Outlook email:"
        elif provider == "outlook":
            intro = "Here are your Outlook inbox emails:"
        elif max_results == 1:
            intro = "Here’s your latest Gmail email:"
        else:
            intro = "Here are your Gmail inbox emails:"

        return f"{intro}\n\n{emails_block}"

    def _parse_fetch_mails(self, input_str) -> dict:
        # LangChain tool calling may pass non-string inputs (dict/float/etc).
        # Be defensive and normalize to a JSON string our parser can handle.
        if input_str is None:
            input_str = ""
        if isinstance(input_str, (int, float)):
            # Interpret a raw number as a "max_results" request.
            try:
                max_results = int(input_str)
            except (TypeError, ValueError):
                max_results = 25
            return fetch_mails(max_results=max(1, min(max_results, 50)), user_id=self.user_id)
        if isinstance(input_str, dict):
            try:
                input_str = json.dumps(input_str)
            except Exception:
                input_str = str(input_str)
        if not isinstance(input_str, str):
            input_str = str(input_str)

        try:
            if input_str.strip().startswith("{"):
                filters = json.loads(input_str)
                if not isinstance(filters, dict):
                    filters = {}

                def _coerce_str(val):
                    if val is None:
                        return None
                    if isinstance(val, str):
                        return val
                    return str(val)

                # Normalize filter types (LLMs sometimes send numbers/objects).
                sender = _coerce_str(filters.get("sender"))
                label = _coerce_str(filters.get("label"))
                subject_keyword = _coerce_str(filters.get("subject_keyword"))
                folder = _coerce_str(filters.get("folder"))
                provider = _coerce_str(filters.get("provider"))
                account_id = _coerce_str(filters.get("account_id"))
                time_period = _coerce_str(filters.get("time_period"))
                since_date = _coerce_str(filters.get("since_date"))
                until_date = _coerce_str(filters.get("until_date"))

                importance = filters.get("importance")
                if isinstance(importance, str):
                    if importance.strip().lower() in {"true", "1", "yes"}:
                        importance = True
                    elif importance.strip().lower() in {"false", "0", "no"}:
                        importance = False
                    else:
                        importance = None

                max_results_raw = filters.get("max_results", 25)
                try:
                    max_results = int(max_results_raw)
                except (TypeError, ValueError):
                    max_results = 25
                max_results = max(1, min(max_results, 50))
                return fetch_mails(
                    label=label,
                    sender=sender,
                    importance=importance,
                    time_period=time_period,
                    since_date=since_date,
                    until_date=until_date,
                    subject_keyword=subject_keyword,
                    folder=folder,
                    max_results=max_results,
                    provider=provider,
                    account_id=account_id,
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
            return self._format_email_list_json_block(emails)

        return json.dumps(emails, indent=2, cls=DateTimeEncoder)

    def _format_email_list_json_block(self, emails: list) -> str:
        """Return a JSON block for a list of emails, truncating long bodies."""
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
            current_body = get_draft_body(draft_id, user_id=self.user_id) or ""
            if not current_body.strip():
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

    def _detect_malformed_tool_output(self, response_text: str) -> dict | None:
        """
        Detect if the response is a malformed tool call output (Gemini sometimes outputs
        tool arguments as text instead of executing the tool).

        Returns parsed tool arguments if detected, None otherwise.
        """
        import re

        if not response_text:
            return None

        text = response_text.strip()
        fetch_keys = {"time_period", "sender", "label", "folder", "max_results",
                     "importance", "since_date", "until_date", "provider", "subject_keyword"}

        def _coerce_arg1(value: object) -> dict | None:
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    return None
            return None

        def _extract_from_parsed(parsed: object) -> dict | None:
            if not isinstance(parsed, dict):
                return None
            for key, value in parsed.items():
                if isinstance(key, str) and key.lstrip("_") == "arg1":
                    coerced = _coerce_arg1(value)
                    if coerced:
                        return coerced
            if any(k in parsed for k in fetch_keys):
                return parsed
            return None

        # Pattern 1: any JSON block that contains tool args (including _arg1 wrappers)
        code_block_match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.DOTALL)
        if code_block_match:
            json_str = (code_block_match.group(1) or "").strip()
            try:
                parsed = json.loads(json_str)
            except (json.JSONDecodeError, ValueError):
                parsed = None
            extracted = _extract_from_parsed(parsed)
            if extracted:
                return extracted

        # Pattern 2: {"_arg1": "{...}"} or {"__arg1": "{...}"}
        arg1_match = re.search(r'\{[^}]*["\']_+arg1["\']\s*:\s*["\'](.+?)["\']\s*\}', text, re.DOTALL)
        if arg1_match:
            try:
                inner_json = arg1_match.group(1)
                inner_json = inner_json.replace('\\"', '"').replace('\\\\', '\\')
                return json.loads(inner_json)
            except (json.JSONDecodeError, ValueError):
                pass

        # Pattern 3: ```json\n{...tool arguments directly...}\n```
        # This handles cases where Gemini outputs tool arguments directly in a code block
        # without the _arg1 wrapper
        direct_json_match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
        if direct_json_match:
            try:
                json_str = direct_json_match.group(1).strip()
                parsed = json.loads(json_str)

                extracted = _extract_from_parsed(parsed)
                if extracted:
                    logger.info(f"[MALFORMED_DETECTION] Found direct JSON tool args: {extracted}")
                    return extracted
            except (json.JSONDecodeError, ValueError) as e:
                logger.debug(f"Failed to parse direct JSON: {e}")
                pass

        return None

    def _handle_malformed_tool_output(self, parsed_args: dict) -> str | None:
        """
        Execute the appropriate tool based on detected malformed output.
        Returns tool result or None if cannot be handled.
        """
        try:
            # Check if this looks like a fetch_mails request
            fetch_keys = {"time_period", "sender", "label", "folder", "max_results",
                         "importance", "since_date", "until_date", "provider", "subject_keyword"}

            if any(k in parsed_args for k in fetch_keys):
                logger.info(f"[MALFORMED_OUTPUT_FIX] Detected fetch_mails args: {parsed_args}")
                result = self._format_fetch_mails_response(json.dumps(parsed_args))

                # Add a nice intro based on the filters
                intro = "Here are your emails"
                if parsed_args.get("time_period"):
                    period = parsed_args["time_period"].replace("_", " ")
                    intro = f"Here are your emails from {period}"
                elif parsed_args.get("sender"):
                    intro = f"Here are emails from {parsed_args['sender']}"

                return f"{intro}:\n\n{result}"

            return None

        except Exception as e:
            logger.error(f"Error handling malformed tool output: {e}")
            return None

    def _extract_json_from_response(self, response_text: str) -> str:
        import re

        # First, check for malformed tool output and handle it
        malformed_args = self._detect_malformed_tool_output(response_text)
        if malformed_args:
            handled_result = self._handle_malformed_tool_output(malformed_args)
            if handled_result:
                return handled_result

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

    def chat(self, user_message: str, context: str = "") -> str:
        try:
            if not user_message or not user_message.strip():
                return "Please provide a message to get started."

            raw_user_message = self._extract_raw_user_message(user_message)
            if not raw_user_message:
                return "Please provide a message to get started."

            message_stripped = raw_user_message.strip()

            if self.pending_selection and "action" in self.pending_selection:
                action = self.pending_selection.get("action")

                if action == "inbox_provider_choice":
                    choice_lower = message_stripped.lower()
                    provider = None
                    if "outlook" in choice_lower:
                        provider = "outlook"
                    elif "gmail" in choice_lower:
                        provider = "gmail"

                    if not provider:
                        return "Please reply with 'Outlook' or 'Gmail'."

                    max_results = self.pending_selection.get("max_results", 1)
                    folder = self.pending_selection.get("folder", "inbox")
                    self.pending_selection = None

                    try:
                        payload = {"folder": folder, "max_results": max_results, "provider": provider}
                        emails = self._parse_fetch_mails(json.dumps(payload))
                        if isinstance(emails, dict) and "error" in emails:
                            return json.dumps(emails, indent=2, cls=DateTimeEncoder)
                        if not isinstance(emails, list):
                            return "I couldn't fetch your emails right now. Please try again."
                        if not emails:
                            return self._build_summary_from_emails(
                                emails=emails,
                                time_period=payload.get("time_period"),
                                importance=payload.get("importance"),
                                provider=provider,
                            )
                        emails_block = self._format_email_list_json_block(emails)
                        if provider == "outlook" and int(max_results) == 1:
                            intro = "Here’s your latest Outlook email:"
                        elif provider == "outlook":
                            intro = "Here are your Outlook inbox emails:"
                        elif int(max_results) == 1:
                            intro = "Here’s your latest Gmail email:"
                        else:
                            intro = "Here are your Gmail inbox emails:"

                        response_text = f"{intro}\n\n{emails_block}"
                        self._append_to_history(message_stripped, response_text)
                        return response_text
                    except Exception as e:
                        logger.error(f"Provider choice fetch failed: {e}")
                        return "I couldn't fetch emails for that account. Please try again."

                if action == "account_choice":
                    accounts = self.pending_selection.get("accounts") or []
                    payload = self.pending_selection.get("payload") or {}
                    mode = self.pending_selection.get("mode") or "fetch"
                    selection = message_stripped.strip()

                    selected = None
                    if selection.isdigit():
                        idx = int(selection)
                        if 1 <= idx <= len(accounts):
                            selected = accounts[idx - 1]
                    else:
                        for acc in accounts:
                            email = (acc.get("email_address") or "").lower()
                            if email and email in selection.lower():
                                selected = acc
                                break

                    if not selected:
                        return "Please reply with a number or the email address of the account."

                    payload["account_id"] = selected.get("id")
                    self.pending_selection = None

                    if mode == "summary":
                        emails = self._parse_fetch_mails(json.dumps(payload))
                        if isinstance(emails, dict) and "error" in emails:
                            return json.dumps(emails, indent=2, cls=DateTimeEncoder)
                        if not isinstance(emails, list):
                            return "I couldn't fetch your emails right now. Please try again."

                        summary = self._summarize_emails_with_llm(
                            emails=emails,
                            time_period=payload.get("time_period"),
                            importance=payload.get("importance"),
                            provider=payload.get("provider"),
                        )
                        if summary:
                            self._append_to_history(message_stripped, summary)
                            return summary
                        fallback_summary = self._build_summary_from_emails(
                            emails=emails,
                            time_period=payload.get("time_period"),
                            importance=payload.get("importance"),
                            provider=payload.get("provider"),
                        )
                        self._append_to_history(message_stripped, fallback_summary)
                        return fallback_summary

                    emails = self._parse_fetch_mails(json.dumps(payload))
                    if isinstance(emails, dict) and "error" in emails:
                        return json.dumps(emails, indent=2, cls=DateTimeEncoder)
                    if not isinstance(emails, list):
                        return "I couldn't fetch your emails right now. Please try again."
                    if not emails:
                        summary = self._build_summary_from_emails(
                            emails=emails,
                            time_period=payload.get("time_period"),
                            importance=payload.get("importance"),
                            provider=payload.get("provider"),
                        )
                        self._append_to_history(message_stripped, summary)
                        return summary

                    emails_block = self._format_email_list_json_block(emails)
                    intro = self._build_fetch_intro(payload)
                    response_text = f"{intro}\n\n{emails_block}"
                    self._append_to_history(message_stripped, response_text)
                    return response_text

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

            summary_response = self._maybe_handle_summary_request(message_stripped)
            if summary_response:
                self._append_to_history(message_stripped, summary_response)
                return summary_response

            direct_fetch = self._maybe_handle_direct_inbox_fetch(message_stripped)
            if direct_fetch:
                self._append_to_history(message_stripped, direct_fetch)
                return direct_fetch

            logger.info("Sending request to Gemini Agent...")

            response = self.agent_executor.invoke(
                {
                    "input": raw_user_message,
                    "context": context or "",
                    "chat_history": self.chat_history,
                }
            )

            # Debug: Log full response structure
            logger.info(f"Agent response keys: {response.keys() if isinstance(response, dict) else type(response)}")

            output = response.get("output", "No response generated")
            intermediate_steps = response.get("intermediate_steps", [])

            # Debug: Log output and steps
            logger.info(f"Agent raw output (first 500 chars): {repr(output[:500]) if output else 'EMPTY'}")
            logger.info(f"Intermediate steps count: {len(intermediate_steps) if intermediate_steps else 0}")

            # If intermediate steps exist, log the tools that were called
            if intermediate_steps:
                for i, (action, observation) in enumerate(intermediate_steps):
                    tool_name = getattr(action, 'tool', 'unknown')
                    obs_preview = str(observation)[:200] if observation else 'None'
                    logger.info(f"  Step {i+1}: Tool={tool_name}, Observation preview={obs_preview}")

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
                    self._append_to_history(message_stripped, best_effort)
                    return best_effort
                timeout_msg = (
                    "I couldn't finish that request in time. "
                    "Please try again with a shorter query (e.g., limit dates, sender, or max_results)."
                )
                self._append_to_history(message_stripped, timeout_msg)
                return timeout_msg

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

            final_response = self._extract_json_from_response(output)
            logger.info(f"Final response length: {len(final_response) if final_response else 0}")
            logger.info(f"Final response preview: {final_response[:500] if final_response else 'EMPTY'}...")

            # Ensure we never return an empty response
            if not final_response or not final_response.strip():
                logger.warning("Final response is empty! Returning output directly.")
                if output and output.strip():
                    self._append_to_history(message_stripped, output)
                    return output

                # Agent/LLM returned nothing; try a deterministic fallback when possible.
                direct_fetch = self._maybe_handle_direct_inbox_fetch(message_stripped)
                if direct_fetch:
                    self._append_to_history(message_stripped, direct_fetch)
                    return direct_fetch
                return "I couldn't process that request. Please try again."

            self._append_to_history(message_stripped, final_response)
            return final_response

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
