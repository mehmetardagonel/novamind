# NovaMind

An AI-powered unified email management platform that brings together Gmail and Outlook accounts with intelligent features including natural language commands, voice interaction, and machine learning-based email classification.

## Features

### Multi-Provider Email Support
- **Gmail Integration** - Full OAuth2 authentication with Gmail API
- **Outlook Integration** - Microsoft Graph API support for Outlook accounts
- **Unified Inbox** - Manage all your email accounts from a single interface
- **Multi-Account Support** - Connect and switch between multiple email accounts

### AI-Powered Assistant
- **Natural Language Commands** - Interact with your emails using plain English
- **Powered by Google Gemini** - Advanced AI for understanding complex requests
- **Context-Aware Responses** - The assistant understands email context and history
- **Email Drafting** - Compose professional emails with AI assistance

Example commands:
- "Show me today's emails"
- "Draft an email to john@example.com about the project deadline"
- "Find all emails from last week with attachments"
- "Delete all promotional emails"

### Voice Interaction
- **Speech-to-Text** - Speak your commands using Deepgram integration
- **Text-to-Speech** - Listen to email summaries and AI responses
- **Hands-Free Operation** - Manage your inbox without typing

### ML Email Classification
- **Spam Detection** - TF-IDF + Logistic Regression model for spam filtering
- **Importance Classification** - SentenceTransformer embeddings (all-MiniLM-L6-v2) for priority detection
- **Confidence Scores** - Each classification includes a confidence percentage
- **Automatic Categorization** - Emails are classified as Spam, Important, or Regular

### Additional Features
- **RAG Service** - Retrieval Augmented Generation for intelligent email search
- **Email Caching** - Fast response times with smart caching
- **Translation Services** - Multi-language support
- **Label Management** - Create, edit, and organize email labels
- **Draft Management** - Save and manage email drafts across accounts

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | FastAPI, Python 3.12+, LangChain |
| **AI/ML** | Google Gemini API, scikit-learn, SentenceTransformers |
| **Frontend** | Vue 3, Vite, Pinia |
| **Database** | Supabase (PostgreSQL) |
| **Authentication** | OAuth2 (Google, Microsoft) |
| **Voice** | Deepgram API (STT/TTS) |
| **Email APIs** | Gmail API, Microsoft Graph API |

## Project Structure

```
novamind/
├── backend/
│   ├── main.py                 # FastAPI application & routes
│   ├── chat_service.py         # AI assistant service
│   ├── gmail_service.py        # Gmail API integration
│   ├── outlook_service.py      # Outlook/Microsoft Graph integration
│   ├── email_account_service.py # Unified email account management
│   ├── email_tools.py          # Email operation utilities
│   ├── ml_service.py           # ML classification wrapper
│   ├── rag_service.py          # RAG for intelligent search
│   ├── voice_router.py         # Voice command endpoints
│   ├── translation_service.py  # Translation utilities
│   ├── email_cache.py          # Caching layer
│   └── ml_model/
│       ├── classify.py         # Classification logic
│       └── models/             # Trained ML models
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── MainApp.vue     # Main application shell
│   │   │   ├── EmailListView.vue # Email list display
│   │   │   ├── LoginScreen.vue # Authentication UI
│   │   │   └── ...
│   │   └── views/
│   │       ├── ComposeView.vue # Email composition
│   │       ├── AccountsView.vue # Account management
│   │       └── ...
│   └── package.json
├── start_dev.sh                # Development server startup
├── stop_dev.sh                 # Stop development servers
└── Makefile                    # Build commands
```

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+
- Gmail API credentials (for Gmail integration)
- Microsoft Azure app registration (for Outlook integration)
- Deepgram API key (for voice features)
- Google Gemini API key (for AI assistant)
- Supabase project (for database/auth)

### Installation

1. **Clone the repository**
   ```bash
   git clone git@github.com:mehmetardagonel/novamind.git
   cd novamind
   ```

2. **Backend Setup**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   ```

4. **Environment Configuration**

   Create `backend/.env` with the following variables:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   DEEPGRAM_API_KEY=your_deepgram_api_key
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_anon_key
   ```

5. **Start the Application**
   ```bash
   ./start_dev.sh
   ```

   The application will be available at:
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8001
   - API Documentation: http://localhost:8001/docs

### Stopping the Application

```bash
./stop_dev.sh
```

## API Documentation

Once the backend is running, interactive API documentation is available at:
- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

## Troubleshooting

### Port Conflicts
```bash
./stop_dev.sh
lsof -ti:8001 | xargs kill -9
lsof -ti:5173 | xargs kill -9
./start_dev.sh
```

### ML Models Not Loading
```bash
cd backend
source venv/bin/activate
python -c "from ml_service import get_classifier; get_classifier()"
```

### Missing Dependencies
```bash
# Backend
cd backend && source venv/bin/activate && pip install -r requirements.txt

# Frontend
cd frontend && npm install
```

## License

This project is proprietary software.

## Contributing

For contribution guidelines, please contact the project maintainers.
