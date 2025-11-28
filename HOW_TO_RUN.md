# How to Run Novamind.AI - Complete Guide

## 📋 Prerequisites (One-Time Setup)

### 1. Make sure you have the required software installed:
- **Python 3.12** (you already have this ✓)
- **Node.js** (you already have this ✓)

### 2. Enable Gmail API (IMPORTANT - First Time Only)
This step is **required** for the app to work with Gmail:

1. **Open this link in your browser:**
   ```
   https://console.developers.google.com/apis/api/gmail.googleapis.com/overview?project=437464220214
   ```

2. **Click the blue "ENABLE" button**

3. **Wait 2-3 minutes** for the changes to take effect

4. ✅ Done! You only need to do this once.

---

## 🚀 Starting the Application

### Method 1: Using the Automated Script (Recommended)

1. **Open Terminal**

2. **Navigate to the project folder:**
   ```bash
   cd /Users/arda/Desktop/novamind_ai/novamind
   ```

3. **Run the start script:**
   ```bash
   ./start_dev.sh
   ```

4. **Wait for the success message:**
   You'll see:
   ```
   ========================================
      Servers Started Successfully!
   ========================================

   Backend:  http://localhost:8001
   Frontend: http://localhost:5173
   API Docs: http://localhost:8001/docs
   ```

5. **Open your browser and go to:**
   ```
   http://localhost:5173
   ```

### Method 2: Using Make Commands (Alternative)

If you prefer make commands:

```bash
cd /Users/arda/Desktop/novamind_ai/novamind
make start
```

---

## 🎯 Using the Application

### First Time Setup:

1. **Open the application:**
   - Go to http://localhost:5173

2. **Authenticate with Gmail:**
   - Click on **"Inbox"** in the sidebar
   - You'll be redirected to Google OAuth login
   - **Sign in with your Google account**
   - **Allow permissions** when prompted
   - You'll be redirected back to the app

3. **Now you can use all features:**
   - ✉️ View emails in Inbox, Sent, Drafts, etc.
   - 🤖 Use the **AI Assistant** (click on "AI Assistant" in the sidebar)
   - ✍️ Compose new emails
   - 📧 Manage drafts

### Using the AI Assistant:

1. **Click "AI Assistant" in the sidebar**

2. **Type commands like:**
   - "Show me today's emails"
   - "Draft an email to john@example.com about the meeting"
   - "Delete all spam emails"
   - "Move emails from Amazon to shopping folder"
   - "Show me important emails from last week"

3. **The AI will help you manage your emails!**

---

## 🛑 Stopping the Application

### Option 1: Using the Stop Script
```bash
cd /Users/arda/Desktop/novamind_ai/novamind
./stop_dev.sh
```

### Option 2: Using Make
```bash
make stop
```

### Option 3: Press Ctrl+C in Terminal
If you see the logs running, just press `Ctrl+C`

---

## 🔧 Troubleshooting

### Problem: "No emails found" or Gmail API errors

**Solution:**
1. Make sure you enabled the Gmail API (see Prerequisites section)
2. Wait 2-3 minutes after enabling
3. Refresh your browser

### Problem: Backend won't start

**Solution:**
```bash
# Stop everything first
./stop_dev.sh

# Kill any processes on the ports
lsof -ti:8001 | xargs kill -9
lsof -ti:5173 | xargs kill -9

# Start again
./start_dev.sh
```

### Problem: Frontend won't load

**Solution:**
```bash
cd /Users/arda/Desktop/novamind_ai/novamind/frontend
npm install
cd ..
./start_dev.sh
```

### Problem: Backend dependencies missing

**Solution:**
```bash
cd /Users/arda/Desktop/novamind_ai/novamind/backend
source venv/bin/activate
pip install -r requirements.txt
cd ..
./start_dev.sh
```

---

## 📝 Quick Commands Reference

| Action | Command |
|--------|---------|
| Start servers | `./start_dev.sh` |
| Stop servers | `./stop_dev.sh` |
| Restart servers | `./stop_dev.sh && sleep 2 && ./start_dev.sh` |
| View backend logs | `tail -f backend.log` |
| View frontend logs | `tail -f frontend.log` |
| Check if running | `make status` |

---

## 🌐 Important URLs

- **Application**: http://localhost:5173
- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs
- **Enable Gmail API**: https://console.developers.google.com/apis/api/gmail.googleapis.com/overview?project=437464220214

---

## 📂 Project Structure

```
novamind/
├── backend/           # FastAPI backend
│   ├── venv/         # Python 3.12 virtual environment
│   ├── main.py       # Main API endpoints
│   ├── chat_service.py  # AI chatbot service
│   └── .env          # Configuration (includes GEMINI_API_KEY)
├── frontend/         # Vue.js frontend
│   └── src/
│       ├── views/    # Page components
│       └── components/  # Reusable components
├── start_dev.sh      # Start script
├── stop_dev.sh       # Stop script
└── Makefile          # Make commands
```

---

## ✅ Daily Workflow

1. **Start your day:**
   ```bash
   cd /Users/arda/Desktop/novamind_ai/novamind
   ./start_dev.sh
   ```

2. **Use the application** at http://localhost:5173

3. **When you're done:**
   ```bash
   ./stop_dev.sh
   ```

That's it! 🎉

---

## 💡 Tips

- The application remembers your Gmail authentication, so you only need to log in once
- The AI Assistant maintains conversation context within a session
- You can have multiple draft emails for the same recipient
- All your Gmail operations are done through the official Gmail API (safe and secure)

---

## 🆘 Need Help?

If something doesn't work:
1. Check the logs: `tail -f backend.log` or `tail -f frontend.log`
2. Make sure Gmail API is enabled
3. Try stopping and restarting: `./stop_dev.sh && sleep 2 && ./start_dev.sh`
4. Check that ports 8001 and 5173 are not used by other apps
