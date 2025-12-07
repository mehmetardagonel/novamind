from livekit import agents
from livekit.plugins import google, deepgram, silero
from livekit.agents import Agent, AgentSession, RunContext
from livekit.agents.llm import function_tool

from dotenv import load_dotenv
from typing import Optional
from datetime import datetime
import os

# Load environment variables
load_dotenv(".env")


class Assistant(Agent):
    """Email voice assistant for the NovaMind AI project."""

    def __init__(self):
        super().__init__(
            instructions="""
You are a helpful and friendly Email voice assistant of NovaMind AI.
You help users manage their email accounts using the tools provided.

GENERAL BEHAVIOR
- Always prefer using tools instead of guessing about capabilities.
- If a user asks you to do something that clearly maps to a tool,
  call that tool rather than replying that you can't do it.

CREATING DRAFTS
When the user asks you to write or create an email in natural language
(e.g. "Can you create a draft to Jeff about the meeting tomorrow?
I can't make it to his event but I can see him next weekend."),
you MUST:

- Call the `create_draft` tool ONCE.
- Infer a good `title` (subject) and `summary` (body) from the user's request.
- Let the tool fill in id/sender/recipient/date using its own defaults,
  unless the user explicitly gives those values.
- Do NOT ask the user for each field separately unless they clearly
  say they want to provide them one by one.

LISTING / SEARCHING EMAILS
- Emails are stored in folders: inbox, spam, important, drafts.
- To show emails from a folder, ALWAYS call `search_emails`
  with that folder name as the argument.
  Examples:
    - "Show my inbox"      -> search_emails(folder="inbox")
    - "Show spam"          -> search_emails(folder="spam")
    - "Show important mail"-> search_emails(folder="important")
    - "Show my drafts"     -> search_emails(folder="drafts")
- The user may say "folder", "box", "section", etc.; map them to the
  correct folder names.

LISTING DRAFTS
- When the user says things like:
    "List my drafts", "Show my drafts", "What drafts do I have?"
  you should either:
    - Call `list_drafts` (preferred, since it needs no arguments), or
    - Call `search_emails` with folder="drafts".
- Never say "I can't list drafts" – you CAN, using these tools.

If the user asks something unrelated to tools, respond normally in conversation.
            """
        )

        # Mock email database with folders
        self.email_database = {
            "inbox": [
                {
                    "id": "inb_001",
                    "sender": "alice@example.com",
                    "recipient": "you@example.com",
                    "title": "Meeting Tomorrow",
                    "summary": "Hi, just a reminder about our meeting scheduled for tomorrow.",
                    "date": "2025-01-12 09:14:22",
                },
                {
                    "id": "inb_002",
                    "sender": "news@techdaily.com",
                    "recipient": "you@example.com",
                    "title": "Your Weekly Tech Roundup",
                    "summary": "Here are the top tech stories of the week.",
                    "date": "2025-01-11 18:45:10",
                },
                {
                    "id": "inb_003",
                    "sender": "noreply@university.edu",
                    "recipient": "you@example.com",
                    "title": "Course Registration Reminder",
                    "summary": "Don't forget to complete your Spring 2025 course registration.",
                    "date": "2025-01-10 12:22:54",
                },
                {
                    "id": "inb_004",
                    "sender": "friend@example.com",
                    "recipient": "you@example.com",
                    "title": "Weekend Plans",
                    "summary": "Are we still on for this weekend?",
                    "date": "2025-01-09 16:33:41",
                },
                {
                    "id": "inb_005",
                    "sender": "bank@securemail.com",
                    "recipient": "you@example.com",
                    "title": "Account Notice",
                    "summary": "Your monthly account summary is now available.",
                    "date": "2025-01-08 08:10:05",
                },
            ],
            "spam": [
                {
                    "id": "spm_001",
                    "sender": "lottery@freecash.win",
                    "recipient": "you@example.com",
                    "title": "YOU WON $5,000,000!",
                    "summary": "Claim your prize now before it expires!",
                    "date": "2025-01-12 04:11:39",
                },
                {
                    "id": "spm_002",
                    "sender": "promo@deals4u.biz",
                    "recipient": "you@example.com",
                    "title": "Limited-Time Offer!",
                    "summary": "Get 90% off all electronics today only.",
                    "date": "2025-01-11 15:21:10",
                },
                {
                    "id": "spm_003",
                    "sender": "unknown@randommail.ru",
                    "recipient": "you@example.com",
                    "title": "URGENT REQUEST",
                    "summary": "Please respond immediately regarding your account.",
                    "date": "2025-01-10 23:55:01",
                },
                {
                    "id": "spm_004",
                    "sender": "offers@cheaptravel.cn",
                    "recipient": "you@example.com",
                    "title": "Fly For Almost Free",
                    "summary": "Book a flight to anywhere with unbelievable discounts.",
                    "date": "2025-01-09 10:04:44",
                },
                {
                    "id": "spm_005",
                    "sender": "robot@spamco.net",
                    "recipient": "you@example.com",
                    "title": "Low Interest Loan!",
                    "summary": "Instant approval, no credit checks!",
                    "date": "2025-01-08 06:48:28",
                },
            ],
            "important": [
                {
                    "id": "imp_001",
                    "sender": "professor@university.edu",
                    "recipient": "you@example.com",
                    "title": "Project Deadline Update",
                    "summary": "The deadline for the final project has been moved.",
                    "date": "2025-01-12 14:20:19",
                },
                {
                    "id": "imp_002",
                    "sender": "hr@company.com",
                    "recipient": "you@example.com",
                    "title": "Interview Schedule",
                    "summary": "Your interview is confirmed for next Wednesday.",
                    "date": "2025-01-11 11:37:02",
                },
                {
                    "id": "imp_003",
                    "sender": "billing@serviceprovider.com",
                    "recipient": "you@example.com",
                    "title": "Payment Due Reminder",
                    "summary": "Your monthly subscription payment is due tomorrow.",
                    "date": "2025-01-10 17:49:15",
                },
                {
                    "id": "imp_004",
                    "sender": "teamlead@projecthub.com",
                    "recipient": "you@example.com",
                    "title": "Sprint Planning",
                    "summary": "Please review the tasks before tomorrow’s meeting.",
                    "date": "2025-01-09 09:12:56",
                },
                {
                    "id": "imp_005",
                    "sender": "security@apple.com",
                    "recipient": "you@example.com",
                    "title": "New Login Detected",
                    "summary": "A new login to your account was detected. Was this you?",
                    "date": "2025-01-08 22:05:33",
                },
            ]
        }

        # Track drafts in a separate list too
        self.drafts = []

    # ---------- TOOLS ----------

    @function_tool
    async def search_emails(self, context: RunContext, folder: str) -> str:
        """Show emails in a folder.

        Args:
            folder: Which folder to show.
                Valid values: 'inbox', 'spam', 'important', 'drafts'.
                If the value looks like a query such as 'from:inbox' or 'in:spam',
                strip the prefix and use just the folder name.
        """
        folder_lower = folder.lower().strip()

        # Normalize things like "from:inbox", "in:spam", "label:important"
        for prefix in ("from:", "in:", "label:"):
            if folder_lower.startswith(prefix):
                folder_lower = folder_lower[len(prefix) :].strip()
                break

        if folder_lower not in self.email_database:
            return f"Sorry, I don't have any emails for '{folder_lower}'."

        listings = self.email_database[folder_lower]
        if not listings:
            return f"There are no emails in {folder_lower}."

        result = f"Found {len(listings)} emails in {folder_lower}:\n\n"
        for listing in listings:
            result += f"• {listing['id']}\n"
            result += f"  Sender: {listing['sender']}\n"
            result += f"  Recipient: {listing['recipient']}\n"
            result += f"  Title: {listing['title']}\n"
            result += f"  Summary: {listing['summary']}\n"
            result += f"  Date: {listing['date']}\n\n"

        return result

    @function_tool
    async def list_drafts(self, context: RunContext) -> str:
        """List all currently saved email drafts."""

        if not self.drafts:
            return "You don't have any drafts at the moment."

        result = f"You currently have {len(self.drafts)} drafts:\n\n"
        for draft in self.drafts:
            result += f"• {draft['id']}\n"
            result += f"  To: {draft['recipient']}\n"
            result += f"  Title: {draft['title']}\n"
            result += f"  Summary: {draft['summary']}\n"
            result += f"  Date: {draft['date']}\n\n"

        return result

    @function_tool
    async def create_draft(
        self,
        context: RunContext,
        title: str,
        summary: str,
        id: Optional[str] = None,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
        date: Optional[str] = None,
    ) -> str:
        """Create an email draft.

        Args:
            title: Title/subject of the email. Infer from the user's request.
            summary: Summary or body of the email. Infer from the user's request.
            id: Optional ID of the draft (e.g., 'draft_001'). Auto-generated if omitted.
            sender: Optional email address of the current user. Default: 'you@example.com'.
            recipient: Optional destination email (e.g., 'jeff@example.com').
                Infer from the user's request if possible, or use a placeholder.
            date: Optional creation date of the draft. Default: current date and time.
        """
        # Auto-generate missing pieces so the LLM does NOT need to ask the user.
        if id is None:
            id = f"draft_{len(self.drafts) + 1:03d}"

        if sender is None:
            # For demo purposes; in real app you’d take from auth/session
            sender = "you@example.com"

        if recipient is None:
            # Very simple heuristic; in a real app you’d map "Jeff" -> his address
            recipient = "unknown@example.com"

        if date is None:
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        draft = {
            "id": id,
            "sender": sender,
            "recipient": recipient,
            "title": title,
            "summary": summary,
            "date": date,
        }

        # Store in drafts list
        self.drafts.append(draft)

        result = "✓ Draft created!\n\n"
        result += f"ID: {draft['id']}\n"
        result += f"Sender: {draft['sender']}\n"
        result += f"Recipient: {draft['recipient']}\n"
        result += f"Title: {draft['title']}\n"
        result += f"Summary: {draft['summary']}\n"
        result += f"Date: {draft['date']}\n\n"
        result += "Your draft is created successfully."

        return result

async def entrypoint(ctx: agents.JobContext):
    """Entry point for the agent."""

    session = AgentSession(
        stt=deepgram.STT(model="nova-2"),
        llm=google.LLM(model=os.getenv("LLM_CHOICE", "gemini-2.5-flash")),
        tts=deepgram.TTS(),
        vad=silero.VAD.load(),
    )

    await session.start(
        room=ctx.room,
        agent=Assistant(),
    )

    await session.generate_reply(
        instructions="Greet the user warmly and ask how you can help with their emails."
    )

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
