# Set protobuf to use pure Python implementation for Python 3.14 compatibility
# This MUST be done before any protobuf-using modules are imported
import os
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

import json
import logging
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import Tool
from langchain.agents import create_react_agent, AgentExecutor
from ml_service import get_classifier


# Setup logging for error tracking
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Custom JSON encoder for datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

from email_tools import (
    fetch_mails,
    delete_all_spam,
    move_mails_by_sender,
    send_email,
    draft_email,
    get_drafts,
    get_draft_by_id,
    delete_draft,
    send_draft,
    update_draft,
    get_drafts_for_recipient
)

class ChatService:
    def __init__(self):
        # Gemini API key'i al
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY not found! Check your .env file.")

        # Gemini modeli oluştur
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-lite",
            google_api_key=api_key,
            temperature=0.7,
        )

        # Draft selection state - track pending draft selections
        self.pending_selection = None  # {"drafts": [...], "operation": "send", "to_email": "..."}
        
        # Tools tanımlama
        self.tools = [
            Tool(
                name="fetch_mails",
                func=self._format_fetch_mails_response,
                description="""Advanced email fetching with multiple filter options. Provide filters as JSON.
                Available filters: label, sender, importance (true/false), subject_keyword, folder

                For dates, use ONE of:
                1. time_period: 'today', 'yesterday', 'last_week', 'last_month', 'last_3_months'
                2. since_date and/or until_date: ISO format (YYYY-MM-DD)

                All filters are optional and can be combined.
                Examples:
                - {"sender": "boss", "time_period": "today"} for emails from boss today
                - {"since_date": "2025-11-01"} for emails from November 1st onwards
                - {"since_date": "2025-11-01", "until_date": "2025-11-30"} for November emails
                - {"label": "Work", "importance": true} for important work emails
                - {"sender": "team", "since_date": "2025-11-20"} for team emails since Nov 20
                """
            ),
            Tool(
                name="delete_all_spam",
                func=lambda _: json.dumps(delete_all_spam(), indent=2),
                description="Delete all spam emails from the inbox. No input needed."
            ),
            Tool(
                name="move_mails_by_sender",
                func=lambda x: json.dumps(self._parse_move_mails_by_sender(x), indent=2),
                description="""Move multiple emails from a specific sender to a target folder.
                Input format: "sender|target_folder"

                - sender: Sender name or email (partial match, case-insensitive)
                  Examples: 'playstation', 'amazon', 'john', 'team@company.com'
                - target_folder: Target label/folder (will be created if it doesn't exist)
                  Examples: 'game', 'shopping', 'work'

                Examples:
                - "playstation|game" - Move all PlayStation emails to game folder
                - "amazon|shopping" - Move Amazon emails to shopping folder
                - "john|personal" - Move emails from John to personal folder
                """
            ),
            Tool(
                name="send_email",
                func=lambda x: json.dumps(self._parse_send_email(x), indent=2),
                description="""Send an email immediately. You should compose a professional email based on the user's request.
                Input format: 'to_email|subject|body' where:
                - to_email: recipient's email address
                - subject: a clear, concise subject line
                - body: a well-written, professional email body
                Example: 'john@company.com|Tomorrow's Meeting|Hi John,\n\nLet's meet tomorrow at 10 AM to discuss the project.\n\nBest regards'
                """
            ),
            Tool(
                name="draft_email",
                func=lambda x: json.dumps(self._parse_draft_email(x), indent=2),
                description="""Create a draft email without sending it. You should compose a professional email based on the user's request.
                Input format: 'to_email|subject|body' where:
                - to_email: recipient's email address (optional, can be empty: '|subject|body' or '||body' for body-only)
                - subject: a clear, concise subject line (optional, can be empty)
                - body: a well-written, professional email body that addresses the user's intent

                You can create drafts with just the body (body-only), and the user can add recipient and subject later by updating the draft.
                Examples:
                - Full: 'berat@company.com|Project Meeting|Hi Berat, I hope this email finds you well...'
                - Body only: '||Hi Berat, I hope this email finds you well...'
                - With subject: '|Project Meeting|Hi Berat, I hope this email finds you well...'
                """
            ),
            Tool(
                name="get_drafts",
                func=lambda _: json.dumps(get_drafts(), indent=2),
                description="Get all draft emails. No input needed."
            ),
            Tool(
                name="delete_draft_for_recipient",
                func=lambda x: self._delete_draft_for_recipient(x.strip()),
                description="""Delete a draft email for a specific recipient.
                Input: recipient email address (e.g., 'alice@example.com')
                If multiple drafts exist for this recipient, you will be asked to choose which one to delete.
                If only one draft exists, it will be deleted automatically."""
            ),
            Tool(
                name="send_draft_for_recipient",
                func=lambda x: self._send_draft_for_recipient(x.strip()),
                description="""Send a draft email for a specific recipient.
                Input: recipient email address (e.g., 'alice@example.com')
                If multiple drafts exist for this recipient, you will be asked to choose which one to send.
                If only one draft exists, it will be sent automatically."""
            ),
            Tool(
                name="get_drafts_for_recipient",
                func=lambda x: self._get_drafts_for_recipient_display(x.strip()),
                description="""Get all draft emails for a specific recipient.
                Input: recipient email address (e.g., 'alice@example.com')
                Returns a list of all drafts addressed to that recipient with subjects and dates."""
            ),
            Tool(
                name="update_draft_for_recipient",
                func=lambda x: json.dumps(self._parse_update_draft_for_recipient(x), indent=2),
                description="""Update draft email body for a specific recipient with instructions.

CRITICAL: Use this tool when user asks to update/edit a draft for someone.

Input format: 'email@example.com|update_instruction'

Examples of when to use:
- User: "Update draft for alice@example.com to make it more formal"
  → Input: 'alice@example.com|Make it more formal'
- User: "Edit the draft to bob@smith.com, shorten it"
  → Input: 'bob@smith.com|Shorten the content and add bullet points'

Tool behavior:
- If recipient has 1 draft: Updates automatically and returns success message
- If recipient has 2+ drafts: Shows list (1️⃣ 2️⃣ 3️⃣...) with subjects and dates, asks user to choose (1, 2, 3...)
- If recipient has 0 drafts: Returns error message

IMPORTANT: Always show the selection list clearly to user if present. User will reply with a number."""
            ),
        ]
        
        # Agent oluştur - Langchain 0.2.16 API
        # GÜNCELLENMİŞ PROMPT: JSON'u koruması için kesin kurallar eklendi
        react_prompt = """You are an AI email assistant. Your job is to help users manage their emails efficiently.

When users ask you to draft, send, or reply to emails:
1. Understand their intent and context
2. Compose professional, well-written emails with proper greetings and closings
3. Use appropriate tone (formal/informal) based on the context
4. Include relevant details from the user's request
5. For drafts, create complete emails that users can review before sending

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

You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}"""

        from langchain.prompts import PromptTemplate
        prompt = PromptTemplate(
            input_variables=["input", "agent_scratchpad", "tools", "tool_names"],
            template=react_prompt
        )

        agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )

        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=False,
            handle_parsing_errors=True,
            max_iterations=10
        )
        try:
            self.ml_classifier = get_classifier()
            logger.info(" ML Classifier integrated into ChatService")
        except Exception as e:
            logger.error(f" Could not load ML classifier: {str(e)}")
            self.ml_classifier = None

        # ML tool:email classification
        if self.ml_classifier:
            self.tools.append(
                Tool(
                    name="classify_emails_ml",
                    func=self._classify_emails_with_ml,
                    description="Classify emails using ML model (spam/ham/important). Input: JSON filters or empty string"
                )
            )
        

    def _parse_fetch_mails(self, input_str: str) -> dict:
        try:
            if input_str.strip().startswith("{"):
                filters = json.loads(input_str)
                return fetch_mails(
                    label=filters.get("label"),
                    sender=filters.get("sender"),
                    importance=filters.get("importance"),
                    time_period=filters.get("time_period"),
                    since_date=filters.get("since_date"),
                    until_date=filters.get("until_date"),
                    subject_keyword=filters.get("subject_keyword"),
                    folder=filters.get("folder")
                )
            else:
                return fetch_mails()
        except json.JSONDecodeError:
            return {"error": "Invalid JSON format for fetch_mails"}
        except Exception as e:
            return {"error": f"Fetch failed: {str(e)}"}

    def _format_fetch_mails_response(self, input_str: str) -> str:
        """Format fetch_mails response as clean email blocks and LIGHTWEIGHT JSON"""
        emails = self._parse_fetch_mails(input_str)

        if isinstance(emails, dict) and "error" in emails:
            return json.dumps(emails, indent=2, cls=DateTimeEncoder)

        if isinstance(emails, list):
            count = len(emails)
            if count == 0:
                return "No emails found."
            elif count == 1:
                intro = "Here is 1 email:"
            else:
                intro = f"Here are {count} emails:"

            email_blocks = []
            
            # --- KRİTİK DÜZELTME: JSON İÇİN HAFİFLETİLMİŞ LİSTE HAZIRLAMA ---
            # PlayStation gibi uzun body'li maillerin JSON'u patlatmasını engeller
            emails_for_json = []
            
            for i, email in enumerate(emails, 1):
                # 1. Metin bloğu oluşturma (AI okuması için)
                sender = email.get('sender') or email.get('from') or 'Unknown Sender'
                subject = email.get('subject') or '(No subject)'
                date = email.get('date') or email.get('timestamp') or 'Unknown Date'

                if isinstance(date, str):
                    try:
                        dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                        date_str = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        date_str = date
                else:
                    date_str = str(date)

                block = f"📧 Email {i}\nFrom: {sender}\nSubject: {subject}\nDate: {date_str}"
                email_blocks.append(block)

                # 2. JSON için kopya oluştur ve body'yi KISALT
                # Bu kısım sayesinde "game" etiketli uzun mailler sorun çıkarmaz
                try:
                    e_copy = email.copy() if isinstance(email, dict) else email.model_dump()
                    
                    if 'body' in e_copy and e_copy['body']:
                        # Body'yi 200 karakterle sınırla. Frontend kartlarında zaten
                        # tam metne ihtiyaç yoktur, sadece önizleme yeterlidir.
                        if len(e_copy['body']) > 200:
                            e_copy['body'] = e_copy['body'][:200] + "..."
                    
                    emails_for_json.append(e_copy)
                except Exception:
                    # Hata durumunda orijinali ekle ama riskli olabilir, genelde buraya düşmez
                    emails_for_json.append(email)
            # -----------------------------------------------------------

            formatted_response = f"{intro}\n\n" + "\n\n".join(email_blocks)
            
            # HAFİFLETİLMİŞ listeyi JSON'a çevir
            json_str = json.dumps(emails_for_json, indent=2, cls=DateTimeEncoder)
            return f"{formatted_response}\n\n```json\n{json_str}\n```"

        return json.dumps(emails, indent=2, cls=DateTimeEncoder)

    def _parse_move_mails_by_sender(self, input_str: str) -> dict:
        try:
            parts = input_str.split("|", 1)
            if len(parts) < 2:
                return {
                    "success": False,
                    "message": "Invalid format. Use: 'sender|target_folder'"
                }

            sender = parts[0].strip()
            target_folder = parts[1].strip()

            if not sender or not target_folder:
                return {
                    "success": False,
                    "message": "Both sender and target_folder are required"
                }

            return move_mails_by_sender(sender, target_folder)

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to move emails: {str(e)}"
            }

    def _parse_send_email(self, input_str: str) -> dict:
        try:
            parts = input_str.split("|", 2)
            if len(parts) < 3:
                return {"success": False, "message": "Invalid input format. Use: 'to|subject|body'"}

            to = parts[0].strip()
            subject = parts[1].strip()
            body = parts[2].strip()
            return send_email(to, subject, body)
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
                body = ""
                to = ""
                subject = ""

            return draft_email(to, subject, body)
        except Exception as e:
            return {"success": False, "message": f"Invalid input format. Use: 'to|subject|body' or '||body' for body-only draft. Error: {str(e)}"}


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
        """Use Gemini to intelligently update draft body based on user instruction"""
        try:
            draft = get_draft_by_id(draft_id)
            if not draft:
                logger.warning(f"Draft {draft_id} not found for body enhancement")
                return instruction

            current_body = ""
            if isinstance(draft, dict):
                msg = draft.get("message", {})
                if isinstance(msg, dict):
                    msg_id = msg.get("id")
                    if msg_id:
                        from gmail_service import get_gmail_service, _decode_body
                        service = get_gmail_service()
                        try:
                            full_msg = service.users().messages().get(
                                userId="me",
                                id=msg_id,
                                format="full"
                            ).execute()
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

            logger.info(f"Sending request to Gemini for body enhancement (Draft ID: {draft_id})...")
            response = self.llm.invoke(enhancement_prompt)

            if hasattr(response, 'content'):
                enhanced_text = response.content.strip()
            else:
                enhanced_text = str(response).strip()

            if not enhanced_text:
                logger.warning(f"Gemini returned empty response for draft {draft_id}")
                return instruction

            return enhanced_text

        except Exception as e:
            logger.warning(f"Gemini body enhancement failed for draft {draft_id}: {str(e)}")
            return instruction

    def _extract_json_from_response(self, response_text: str) -> str:
        import re

        code_block_match = re.search(r'```json\n([\s\S]*?)\n```', response_text)

        if code_block_match:
            json_str = code_block_match.group(1).strip()
            try:
                json.loads(json_str)
                intro_text = response_text[:code_block_match.start()].strip()
                if '📧 Email' in intro_text:
                    return f"{intro_text}\n\n```json\n{json_str}\n```"
                else:
                    return f"{intro_text} {json_str}".strip()
            except json.JSONDecodeError:
                pass

        json_match = re.search(r'\[[\s\S]*?\]', response_text)

        if json_match:
            json_str = json_match.group(0)
            try:
                json.loads(json_str)
                intro_text = response_text[:json_match.start()].strip()
                if '📧 Email' in intro_text:
                    return f"{intro_text}\n\n```json\n{json_str}\n```"
                else:
                    return f"{intro_text} {json_str}".strip()
            except json.JSONDecodeError:
                return response_text

        return response_text

    def _handle_draft_selection(self, selection_idx: int) -> str:
        """Handle draft selection when user picks a number"""
        if not self.pending_selection:
            return "No draft selection pending. Please try your request again."

        drafts = self.pending_selection.get("drafts", [])
        operation = self.pending_selection.get("operation", "")

        if selection_idx < 1 or selection_idx > len(drafts):
            error_msg = f"❌ Invalid selection. Please choose 1-{len(drafts)}"
            return error_msg

        selected_draft = drafts[selection_idx - 1]
        draft_id = selected_draft.get("id")
        subject = selected_draft.get("subject", "(No subject)")

        try:
            if operation == "send":
                send_draft(draft_id)
                self.pending_selection = None
                return f"✅ Draft sent: '{subject}'"

            elif operation == "delete":
                delete_draft(draft_id)
                self.pending_selection = None
                return f"✅ Draft deleted: '{subject}'"

            elif operation == "update":
                # Update draft with saved instruction
                update_instruction = self.pending_selection.get("update_instruction", "")
                self.pending_selection = None

                if not update_instruction:
                    return f"No update instruction found. Selected draft: '{subject}'"

                # FIX: First process the body with AI
                new_body = self._smart_enhance_body_with_instruction(draft_id, update_instruction)

                # Then update the draft using the new body
                result = update_draft(
                    draft_id=draft_id,
                    body=new_body  # Use the AI-enhanced body
                )
                
                if result.get("success"):
                    return f"✅ Draft updated: '{subject}'"
                else:
                    return f"❌ Failed to update draft: {result.get('message', 'Unknown error')}"

            else:
                self.pending_selection = None
                return f"Unknown operation: {operation}"

        except Exception as e:
            logger.error(f"Error handling draft operation {operation} on {draft_id}: {str(e)}")
            self.pending_selection = None
            return f"❌ Error performing {operation}: {str(e)}"

    def _send_draft_for_recipient(self, to_email: str) -> str:
        try:
            drafts = get_drafts_for_recipient(to_email)

            if not drafts:
                return f"❌ No drafts found for {to_email}"

            elif len(drafts) == 1:
                draft_id = drafts[0].get("id")
                subject = drafts[0].get("subject", "(No subject)")
                send_draft(draft_id)
                return f"✅ Draft sent: '{subject}'"

            else:
                draft_list = "\n".join([
                    f"{i+1}️⃣ {d.get('subject', '(No subject)')[:40]}... ({d.get('date', 'Unknown')[:10]})"
                    for i, d in enumerate(drafts)
                ])
                self.pending_selection = {
                    "drafts": drafts,
                    "operation": "send",
                    "to_email": to_email
                }
                return f"Found {len(drafts)} drafts for {to_email}:\n\n{draft_list}\n\nWhich one would you like to send? (Reply with a number: 1, 2, 3...)"

        except Exception as e:
            logger.error(f"Error sending draft for {to_email}: {str(e)}")
            return f"❌ Error: {str(e)}"

    def _delete_draft_for_recipient(self, to_email: str) -> str:
        try:
            drafts = get_drafts_for_recipient(to_email)

            if not drafts:
                return f"❌ No drafts found for {to_email}"

            elif len(drafts) == 1:
                draft_id = drafts[0].get("id")
                subject = drafts[0].get("subject", "(No subject)")
                delete_draft(draft_id)
                return f"✅ Draft deleted: '{subject}'"

            else:
                draft_list = "\n".join([
                    f"{i+1}️⃣ {d.get('subject', '(No subject)')[:40]}... ({d.get('date', 'Unknown')[:10]})"
                    for i, d in enumerate(drafts)
                ])
                self.pending_selection = {
                    "drafts": drafts,
                    "operation": "delete",
                    "to_email": to_email
                }
                return f"Found {len(drafts)} drafts for {to_email}:\n\n{draft_list}\n\nWhich one would you like to delete? (Reply with a number: 1, 2, 3...)"

        except Exception as e:
            logger.error(f"Error deleting draft for {to_email}: {str(e)}")
            return f"❌ Error: {str(e)}"

    def _update_draft_for_recipient(self, to_email: str, update_instruction: str) -> str:
        try:
            drafts = get_drafts_for_recipient(to_email)

            if not drafts:
                return f"❌ No drafts found for {to_email}"

            elif len(drafts) == 1:
                draft_id = drafts[0].get("id")
                subject = drafts[0].get("subject", "(No subject)")

                # FIX: First process the body with AI
                new_body = self._smart_enhance_body_with_instruction(draft_id, update_instruction)

                # Then update the draft using the new body
                result = update_draft(
                    draft_id=draft_id,
                    body=new_body # Use the AI-enhanced body
                )
                
                if result.get("success"):
                    return f"✅ Draft updated: '{subject}'"
                else:
                    return f"❌ Failed to update draft: {result.get('message', 'Unknown error')}"

            else:
                draft_list = "\n".join([
                    f"{i+1}️⃣ {d.get('subject', '(No subject)')[:40]}... ({d.get('date', 'Unknown')[:10]})"
                    for i, d in enumerate(drafts)
                ])
                self.pending_selection = {
                    "drafts": drafts,
                    "operation": "update",
                    "to_email": to_email,
                    "update_instruction": update_instruction
                }
                return f"Found {len(drafts)} drafts for {to_email}:\n\n{draft_list}\n\nWhich one would you like to update? (Reply with a number: 1, 2, 3...)"

        except Exception as e:
            logger.error(f"Error updating draft for {to_email}: {str(e)}")
            return f"❌ Error: {str(e)}"

    def _get_drafts_for_recipient_display(self, to_email: str) -> str:
        try:
            drafts = get_drafts_for_recipient(to_email)

            if not drafts:
                return f"No drafts found for {to_email}"

            draft_list = "\n".join([
                f"📄 {i+1}. {d.get('subject', '(No subject)')} ({d.get('date', 'Unknown')[:10]})"
                for i, d in enumerate(drafts)
            ])

            return f"Found {len(drafts)} draft(s) for {to_email}:\n\n{draft_list}"

        except Exception as e:
            logger.error(f"Error getting drafts for {to_email}: {str(e)}")
            return f"❌ Error: {str(e)}"

    def chat(self, user_message: str) -> str:
        try:
            if not user_message or not user_message.strip():
                return "Please provide a message to get started."

            message_stripped = user_message.strip()

            if self.pending_selection and message_stripped.isdigit():
                return self._handle_draft_selection(int(message_stripped))

            # Detect draft-related keywords for potential fallback
            draft_keywords = ['update draft', 'edit draft', 'modify draft', 'change draft',
                            'send draft', 'delete draft']
            is_draft_related = any(kw.lower() in message_stripped.lower() for kw in draft_keywords)

            logger.info("Sending request to Gemini Agent...")
            response = self.agent_executor.invoke({"input": user_message})
            output = response.get("output", "No response generated")

            # FALLBACK: If draft-related but agent didn't use tool, try direct invocation
            if is_draft_related and not self.pending_selection:
                import re
                # Extract email address from message
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message_stripped)
                if email_match:
                    email = email_match.group()
                    # Extract instruction (everything after email)
                    instruction = message_stripped.split(email, 1)[1].strip()
                    if instruction:
                        # Determine operation type from message
                        if 'update' in message_stripped.lower() or 'edit' in message_stripped.lower() or 'modify' in message_stripped.lower():
                            logger.info(f"[FALLBACK] Using direct invocation for update_draft_for_recipient: {email}")
                            fallback_result = self._parse_update_draft_for_recipient(f"{email}|{instruction}")
                            return json.dumps(fallback_result, indent=2, cls=DateTimeEncoder)
                        elif 'send' in message_stripped.lower():
                            logger.info(f"[FALLBACK] Using direct invocation for send_draft_for_recipient: {email}")
                            fallback_result = self._send_draft_for_recipient(email)
                            return fallback_result
                        elif 'delete' in message_stripped.lower():
                            logger.info(f"[FALLBACK] Using direct invocation for delete_draft_for_recipient: {email}")
                            fallback_result = self._delete_draft_for_recipient(email)
                            return fallback_result

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
            emails = fetch_mails(**filters, max_results=50)
            
            if not emails:
                return "No emails found to classify."
            
            classified_emails = self.ml_classifier.classify_batch(emails)
            summary = self.ml_classifier.get_classification_summary(classified_emails)
            
            response = f"📊 ML Classification Results\n\n"
            response += f"Total Emails: {summary['total']}\n\n"
            
            for pred, count in summary['by_prediction'].items():
                emoji = "🚫" if pred == "spam" else "⭐" if pred == "important" else "📧"
                response += f"{emoji} {pred.upper()}: {count} emails\n"
            
            return response
            
        except Exception as e:
            logger.error(f"ML classification error: {str(e)}")
            return f" Classification failed: {str(e)}"
    
    
    def clear_history(self):
        pass
