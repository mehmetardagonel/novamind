# NovaMind AI Email Assistant

NovaMind is an intelligent email management assistant powered by Google Gemini AI, featuring a real-time chat interface for managing Gmail through natural language.

## Quick Start

### 1. Enable Gmail API (First Time Only)

Visit this link and click the **ENABLE** button:
```
https://console.developers.google.com/apis/api/gmail.googleapis.com/overview?project=437464220214
```

Wait 2-3 minutes for the changes to take effect.

### 2. Start the Application

```bash
cd /Users/arda/Desktop/novamind_ai/novamind
./start_dev.sh
```

The script will automatically:
- Check and clear ports 8001 and 5173
- Set up Python virtual environment
- Install dependencies
- Start backend and frontend servers

Once started, open your browser:
```
http://localhost:5173
```

### 3. First Time Authentication

1. Click **"Inbox"** in the sidebar
2. Sign in with your Google account
3. Allow permissions when prompted
4. You'll be redirected back to the app

### 4. Using the AI Assistant

Click **"AI Assistant"** in the sidebar and try commands like:
- "Show me today's emails"
- "Draft an email to john@example.com about the meeting"
- "Delete all spam emails"
- "Show me important emails from last week"
- "Classify my emails"  ← NEW: ML-powered classification

## 🤖 ML Email Classification

NovaMind includes an intelligent ML-based email classifier that automatically categorizes emails as:
- 🚫 **Spam**: Promotional and unwanted emails
- ⭐ **Important**: Urgent and high-priority emails  
- 📧 **Ham**: Regular inbox emails

### Features

- **Automatic Classification**: Emails are classified using machine learning models
- **Confidence Scores**: Each prediction includes a confidence percentage
- **Natural Language Commands**: Ask the AI assistant to classify emails
- **Dual Model System**: 
  - Spam detection using TF-IDF + Logistic Regression
  - Importance detection using SentenceTransformer embeddings (all-MiniLM-L6-v2)

### ML Models

The classification system uses two trained models:
- `spam_model.pkl` (2.4 MB): Spam/ham detection
- `embedding_model.pkl` (47.6 MB): Importance classification

### Usage Examples

Try these commands in the AI Assistant:
- "Classify my emails"
- "Show me spam emails"
- "Find important emails from today"
- "Which emails are spam?"
- "Check my inbox for important messages"

### Technical Details

- **Model Location**: `backend/ml_model/`
- **Wrapper Service**: `backend/ml_service.py`
- **Integration**: Automatically loaded when backend starts
- **Classification Tool**: `classify_emails_ml` (available to AI assistant)
- **Batch Processing**: Supports up to 50 emails per request

## Stopping the Application

```bash
./stop_dev.sh
```

Or press `Ctrl+C` in the terminal.

## Troubleshooting

### Gmail API Errors / No Emails Found

**Solution:**
1. Make sure you enabled the Gmail API (see Quick Start step 1)
2. Wait 2-3 minutes after enabling
3. Refresh your browser

### Backend Won't Start

```bash
./stop_dev.sh
lsof -ti:8001 | xargs kill -9
lsof -ti:5173 | xargs kill -9
./start_dev.sh
```

### ML Models Not Loading

**Solution:**
```bash
cd backend
source venv/bin/activate
python -c "from ml_service import get_classifier; get_classifier()"
```

If errors appear, check that model files exist in `backend/ml_model/models/`

### Missing Dependencies

Backend:
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

Frontend:
```bash
cd frontend
npm install
```

## Important URLs

- **Application**: http://localhost:5173
- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs
- **Enable Gmail API**: https://console.developers.google.com/apis/api/gmail.googleapis.com/overview?project=437464220214

## Tech Stack

- **Backend**: FastAPI (Python 3.12), LangChain, Google Gemini API
- **Frontend**: Vue 3, Vite, Pinia
- **Database/Auth**: Supabase
- **Email**: Gmail API with OAuth2
- **ML Models**: scikit-learn, SentenceTransformers, TF-IDF

## Configuration

Backend environment variables are already configured in `backend/.env`. The key configurations include:
- `GEMINI_API_KEY`: Google Gemini AI API key
- `GOOGLE_CLIENT_ID`: Google OAuth client ID
- `GOOGLE_CLIENT_SECRET`: Google OAuth client secret
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_KEY`: Supabase anonymous key

## Project Structure

```
novamind/
├── backend/              # FastAPI backend
│   ├── venv/            # Python 3.12 virtual environment
│   ├── main.py          # API endpoints
│   ├── chat_service.py  # AI chatbot service (ML integrated)
│   ├── email_tools.py   # Email operation tools
│   ├── gmail_service.py # Gmail API integration
│   ├── ml_service.py    # ML classification wrapper
│   ├── ml_model/        # ML models and utilities
│   │   ├── __init__.py
│   │   ├── classify.py  # Classification logic
│   │   ├── text_utils.py # Text preprocessing
│   │   └── models/      # Trained ML models
│   │       ├── spam_model.pkl
│   │       └── embedding_model.pkl
│   └── .env             # Configuration
├── frontend/            # Vue.js frontend
│   ├── src/
│   │   ├── views/       # Page components
│   │   └── components/  # Reusable components
│   └── package.json
├── start_dev.sh         # Start script
├── stop_dev.sh          # Stop script
└── Makefile             # Make commands
```

## Useful Commands

| Action | Command |
|--------|---------|
| Start servers | `./start_dev.sh` |
| Stop servers | `./stop_dev.sh` |
| Restart servers | `./stop_dev.sh && sleep 2 && ./start_dev.sh` |
| View backend logs | `tail -f backend.log` |
| View frontend logs | `tail -f frontend.log` |
| Check status | `make status` |
| Test ML models | `cd backend && python -c "from ml_service import get_classifier; get_classifier()"` |


