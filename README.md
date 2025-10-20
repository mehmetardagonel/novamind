# 🤖 NovaMind AI Email Assistant

An intelligent email management assistant powered by Google Gemini AI with natural language processing and real-time chat interface.

## ✨ Features

### Current Features (v1.0)
- 🤖 **AI-Powered Email Assistant** - Natural language understanding with Google Gemini 2.5 Flash
- 💬 **Real-time Chat Interface** - WebSocket-based communication
- 📧 **Email Operations**
  - Draft email creation with AI-generated content
  - Update existing drafts with natural instructions
  - Fetch emails with smart filtering (sender, label, time period, importance)
  - Move emails to folders
  - Delete emails by category
- 🎯 **Function Calling** - AI automatically calls the right functions based on user intent
- 💾 **Session Management** - Persistent chat history with SQLite
- 🔄 **Draft Management** - In-memory draft versioning system
- 📊 **Email Visualization** - Beautiful email list display with badges and metadata

### Architecture Highlights
- **Modular Design** - Separate email service layer (currently MockEmailService)
- **Dependency Injection** - Easy to swap mock services with real Gmail/Outlook APIs
- **Session-based Drafts** - Each session maintains its own draft history
- **Rate Limiting** - Configurable request limits per session

## 🏗️ Tech Stack

- **Backend:** FastAPI (Python 3.10+)
- **AI:** Google Gemini AI (gemini-2.5-flash)
- **Database:** SQLite with SQLAlchemy ORM
- **WebSocket:** Real-time bidirectional communication
- **Frontend:** Vanilla HTML/CSS/JavaScript

## 📁 Project Structure

```
project/
│
├── main.py                      # FastAPI application entry point
├── ai_processor.py              # Gemini AI integration & function calling
├── action_handler.py            # Email action executor
├── database.py                  # SQLAlchemy models & DB setup
├── session_manager.py           # WebSocket, chat history, draft manager
│
├── email_services/              # Email service implementations
│   ├── __init__.py
│   ├── base.py                  # Abstract base class
│   └── mock_service.py          # Mock email service for testing
│
├── static/
│   └── chat.html                # Chat UI interface
│
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variables template
├── .gitignore                   # Git ignore rules
└── README.md                    # This file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- Google Gemini API Key ([Get one here](https://makersuite.google.com/app/apikey))

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/novamind-email-assistant.git
cd novamind-email-assistant
```

2. **Create virtual environment**
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Setup environment variables**
```bash
# Copy example file
cp .env.example .env

# Edit .env and add your API key
# GOOGLE_API_KEY=your_actual_api_key_here
```

5. **Run the application**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

6. **Open your browser**
```
http://localhost:8000/test-chat
```

## 🎮 Usage Examples

### Natural Language Commands

The AI understands natural language and automatically performs actions:

**Draft Emails:**
```
"Draft an email to John about the project deadline"
"Write an email to sarah@company.com regarding tomorrow's meeting"
```

**Update Drafts:**
```
"Add budget discussion to the draft"
"Update the draft to mention Friday deadline"
```

**Fetch Emails:**
```
"Show me important emails from today"
"Get all emails from my boss"
"Show Work labeled emails from this week"
```

**Organize Emails:**
```
"Move all emails from notifications@service.com to Promotions folder"
"Delete spam emails"
```

## 🔧 Configuration

### Environment Variables

See `.env.example` for all available options:

- `GOOGLE_API_KEY` - Your Gemini AI API key (required)
- `DATABASE_URL` - Database connection string (default: SQLite)
- `RATE_LIMIT_PER_MINUTE` - Max requests per minute (default: 10)
- `SESSION_TIMEOUT` - Session timeout in minutes (default: 30)
- `DEBUG` - Enable debug mode (default: True)

### Rate Limiting

Configure in `.env`:
```bash
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_PER_HOUR=100
```

## 📡 API Endpoints

### WebSocket
- `ws://localhost:8000/ws/chat/{session_token}` - Chat WebSocket connection

### REST API
- `POST /api/session/create` - Create new chat session
- `GET /api/chat/history/{session_token}` - Get chat history
- `GET /api/session/status/{session_token}` - Get session status
- `GET /health` - Health check
- `GET /test-chat` - Test chat interface

## 🏗️ Architecture

### Email Service Layer

The project uses dependency injection for email services:

```python
# Current: Mock service for testing
email_service = MockEmailService(delay=0.3)

# Future: Real Gmail service
# email_service = GmailService(credentials)

# Future: Outlook service  
# email_service = OutlookService(credentials)
```

All services implement `EmailServiceBase` abstract class:
- `fetch_emails(params)` - Retrieve emails
- `move_emails(params)` - Move emails to folders
- `delete_emails(params)` - Delete emails
- `create_draft(params)` - Create email draft
- `update_draft(params)` - Update existing draft

### Draft Management

Drafts are stored in-memory per session with version tracking:

```python
draft_data = {
    'to': 'john@example.com',
    'subject': 'Re: Project Update',
    'body_full': '...',
    'draft_id': 'draft_123',
    'version': 2
}
```

## 🔮 Roadmap

### Phase 2: Real Email Integration
- [ ] Gmail API integration
- [ ] Outlook API integration
- [ ] OAuth2 authentication flow
- [ ] Email sending functionality

### Phase 3: Advanced Features
- [ ] User authentication & multi-user support
- [ ] Email search with AI
- [ ] Smart categorization
- [ ] Email reminders
- [ ] Attachment handling

### Phase 4: Production Ready
- [ ] PostgreSQL database
- [ ] Redis caching
- [ ] Docker deployment
- [ ] CI/CD pipeline
- [ ] Mobile responsive UI

## 🐛 Known Issues

- Draft updates currently use simple AI prompting (will be improved)
- No email sending functionality yet (coming in Phase 2)
- Single-user system (multi-user support in Phase 3)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Google Gemini AI for powerful language understanding
- FastAPI for excellent async web framework
- SQLAlchemy for robust ORM

## 📧 Contact

Project Link: [https://github.com/yourusername/novamind-email-assistant](https://github.com/yourusername/novamind-email-assistant)

---

**Made with ❤️ by [Your Name]**