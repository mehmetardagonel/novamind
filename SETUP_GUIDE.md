# Detailed Setup Guide for Novamind.AI

This guide provides step-by-step instructions for setting up the Novamind.AI email assistant from scratch.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Supabase Setup](#supabase-setup)
3. [Gmail API Setup](#gmail-api-setup)
4. [Backend Setup](#backend-setup)
5. [Frontend Setup](#frontend-setup)
6. [Running the Application](#running-the-application)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### 1. Install Python 3.12

**macOS (using Homebrew):**
```bash
brew install python@3.12
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev
```

**Windows:**
Download from [python.org](https://www.python.org/downloads/)

Verify installation:
```bash
python3.12 --version
# Should output: Python 3.12.x
```

### 2. Install Node.js

**macOS (using Homebrew):**
```bash
brew install node@20
```

**Ubuntu/Debian:**
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

**Windows:**
Download from [nodejs.org](https://nodejs.org/)

Verify installation:
```bash
node --version  # Should output: v20.x.x or v22.x.x
npm --version   # Should output: 9.x.x or higher
```

---

## Supabase Setup

### Step 1: Create a Supabase Account

1. Go to [supabase.com](https://supabase.com)
2. Click "Start your project"
3. Sign up with GitHub, Google, or email

### Step 2: Create a New Project

1. Click "New Project"
2. Fill in project details:
   - **Name**: novamind-email-assistant (or your preferred name)
   - **Database Password**: Create a strong password (save this!)
   - **Region**: Choose closest to your location
3. Click "Create new project"
4. Wait 2-3 minutes for project to be provisioned

### Step 3: Get API Credentials

1. In your project dashboard, go to **Settings** (gear icon) → **API**
2. Copy the following (you'll need these later):
   - **Project URL** (looks like: `https://xxxxx.supabase.co`)
   - **anon/public key** (starts with `eyJhbGci...`)
   - **JWT Secret** (click "Reveal" next to JWT Secret)

### Step 4: Configure Email Authentication

1. Go to **Authentication** → **Providers**
2. Click on **Email** provider
3. Ensure the following are enabled:
   - ✅ Enable email provider
   - ✅ Confirm email (recommended for security)
4. Customize email templates (optional):
   - Go to **Authentication** → **Email Templates**
   - Customize "Confirm signup" email if desired

### Step 5: Configure Email Settings (Important!)

1. Go to **Authentication** → **URL Configuration**
2. Set **Site URL** to: `http://localhost:5173` (or your frontend URL)
3. Add **Redirect URLs**:
   - `http://localhost:5173/**`
   - `http://localhost:5179/**` (alternative port)
4. Click "Save"

---

## Gmail API Setup

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Sign in with your Google account
3. Click **Select a project** → **New Project**
4. Enter project details:
   - **Project name**: novamind-email-assistant
   - **Location**: No organization
5. Click **Create**

### Step 2: Enable Gmail API

1. In your new project, go to **APIs & Services** → **Library**
2. Search for "Gmail API"
3. Click on **Gmail API**
4. Click **Enable**

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Choose **External** (unless you have a Google Workspace)
3. Click **Create**
4. Fill in required fields:
   - **App name**: Novamind Email Assistant
   - **User support email**: Your email
   - **Developer contact**: Your email
5. Click **Save and Continue**
6. **Scopes**: Click **Add or Remove Scopes**
   - Search for: `gmail.modify`
   - Select: `https://www.googleapis.com/auth/gmail.modify`
   - Search for: `gmail.settings.basic`
   - Select: `https://www.googleapis.com/auth/gmail.settings.basic`
7. Click **Update** → **Save and Continue**
8. **Test users**: Add your Gmail address
9. Click **Save and Continue**

### Step 4: Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **OAuth 2.0 Client ID**
3. Configure:
   - **Application type**: Desktop app
   - **Name**: Novamind Desktop Client
4. Click **Create**
5. Click **Download JSON**
6. **Rename** the downloaded file to `client_secret.json`
7. **Move** `client_secret.json` to the `backend/` directory of your project

---

## Backend Setup

### Step 1: Navigate to Backend Directory

```bash
cd novamind/backend
```

### Step 2: Create Virtual Environment

```bash
# Create venv with Python 3.12
python3.12 -m venv venv

# Activate venv
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# Verify Python version in venv
python --version  # Should show Python 3.12.x
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This will install:
- FastAPI
- Uvicorn
- Supabase client
- simplegmail
- And other dependencies

### Step 4: Create Environment File

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your credentials:
```bash
# Use your favorite editor
nano .env
# or
code .env
```

3. Update the following values:
```env
# Supabase (from Step 3 of Supabase Setup)
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGci... (your anon key)
SUPABASE_JWT_SECRET=your-jwt-secret

# Gmail (if you completed Gmail API Setup)
GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxx
```

### Step 5: Verify client_secret.json

Ensure `client_secret.json` is in the `backend/` directory:
```bash
ls -la client_secret.json
```

---

## Frontend Setup

### Step 1: Navigate to Frontend Directory

```bash
cd ../frontend  # From backend directory
# or
cd novamind/frontend  # From root
```

### Step 2: Install Dependencies

```bash
npm install
```

This will install:
- Vue 3
- Vue Router
- Pinia
- Axios
- Supabase JS client
- PrimeVue
- And other dependencies

### Step 3: Create Environment File

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env`:
```bash
nano .env
# or
code .env
```

3. Update with your Supabase credentials:
```env
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGci... (same as backend)
```

---

## Running the Application

### Terminal 1: Start Backend

```bash
cd novamind/backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

**Expected output:**
```
INFO:     Will watch for changes in these directories: ['/path/to/backend']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
✅ Supabase authentication configured
🚀 NovaMind Email Assistant API is running
INFO:     Application startup complete.
```

### Terminal 2: Start Frontend

```bash
cd novamind/frontend
npm run dev
```

**Expected output:**
```
VITE v7.x.x  ready in 398 ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

### Access the Application

1. Open browser to: `http://localhost:5173`
2. You should see the login page

---

## First-Time OAuth Flow (Gmail)

The first time you try to access Gmail features, you need to complete the OAuth flow:

### Method 1: Through the Application (Recommended)

1. Log in to the application
2. Click "Inbox"
3. If prompted, follow the OAuth flow in your browser
4. Grant permissions to the application
5. You'll be redirected back to the app

### Method 2: Manual OAuth (if needed)

If you need to manually authenticate:

```bash
cd backend
source venv/bin/activate
python

# In Python shell:
from simplegmail import Gmail
gmail = Gmail()
# Follow the browser prompts
```

This creates `gmail_token.json` in the `backend/` directory.

---

## Troubleshooting

### Backend Won't Start

**Error: "Python 3.14 is not compatible"**
```bash
# Verify Python version
python --version

# Recreate venv with correct version
rm -rf venv
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Error: "No module named 'supabase'"**
```bash
# Ensure venv is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Frontend Issues

**Error: "Cannot find module '@supabase/supabase-js'"**
```bash
# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install
```

**Port 5173 already in use**
```bash
# Vite will automatically try next port (5174, 5175, etc.)
# Update backend CORS if needed to include new port
```

### Supabase Authentication Issues

**"Invalid JWT token"**
- Verify `SUPABASE_URL` and `SUPABASE_KEY` match in both backend and frontend `.env`
- Ensure you're using the **anon** key, not service role key
- Check that JWT Secret is correct in backend `.env`

**Email not verified**
- Check your email inbox for verification link
- Check spam folder
- In Supabase dashboard: Authentication → Users → manually verify user

### Gmail API Issues

**"Your 'client_secret.json' file is nonexistent"**
```bash
# Verify file location
ls -la backend/client_secret.json

# If missing, download from Google Cloud Console
# and place in backend/ directory
```

**"Gmail API not configured" error**
- Ensure `client_secret.json` is present
- Run OAuth flow to generate `gmail_token.json`
- Verify Gmail API is enabled in Google Cloud Console

**"Insufficient Permission" errors**
- Check OAuth scopes include `gmail.modify`
- Re-run OAuth flow with correct scopes
- Delete `gmail_token.json` and re-authenticate

### Network Errors

**"Network Error" when clicking Inbox**
- Verify backend is running: `curl http://localhost:8000`
- Check browser console for CORS errors
- Ensure frontend port is in backend CORS config
- Verify you're logged in (check browser local storage for Supabase session)

---

## Production Deployment

For production deployment, you'll need to:

1. **Update Supabase URLs** in frontend `.env`
2. **Configure production OAuth redirect** in Google Cloud
3. **Set environment variables** in your hosting platform
4. **Build frontend**: `npm run build`
5. **Use production WSGI server** for backend
6. **Set up HTTPS** for secure authentication

Refer to deployment guides for:
- [Vercel](https://vercel.com/docs) (Frontend)
- [Railway](https://docs.railway.app/) (Backend)
- [Render](https://render.com/docs) (Full-stack)

---

## Getting Help

- **GitHub Issues**: Report bugs or request features
- **Supabase Docs**: https://supabase.com/docs
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **Gmail API Docs**: https://developers.google.com/gmail/api

---

**Happy coding! 🚀**
