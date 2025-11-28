# NovaMind AI Email Assistant

NovaMind is an intelligent email management assistant powered by Google Gemini AI, featuring a real-time chat interface, email summarization, and smart organization capabilities.

## 🚀 Quick Start

The easiest way to run the application is using the development script:

```bash
./start_dev.sh
```

This script will automatically:
- Check for required ports (8001, 5173)
- Set up the Python virtual environment for the backend
- Install backend dependencies
- Install frontend dependencies
- Start both the FastAPI backend and Vue.js frontend

Once started, access the app at:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs

To stop the servers, run:
```bash
./stop_dev.sh
```

## ⚙️ Configuration

Before running the application, ensure you have the necessary environment variables set up.

### Backend (`backend/.env`)
Create a `.env` file in the `backend/` directory based on `.env.example`:

```env
# App Security
SECRET_KEY=your_secret_key_here

# Database (Supabase)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_JWT_SECRET=your_supabase_jwt_secret

# Gmail API (Optional for email features)
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
```

### Frontend (`frontend/.env`)
The frontend comes pre-configured, but you can create a `.env` file in `frontend/` if you need to override defaults:

```env
VITE_API_URL=http://localhost:8001
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

## 🛠 Manual Setup

If you prefer to run the services manually:

### Backend
1. Navigate to `backend/`:
   ```bash
   cd backend
   ```
2. Create and activate virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the server:
   ```bash
   uvicorn main:app --port 8001 --reload
   ```

### Frontend
1. Navigate to `frontend/`:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the dev server:
   ```bash
   npm run dev
   ```

## 🏗 Tech Stack

- **Backend**: FastAPI, Python 3.10+, SQLAlchemy, simplegmail
- **Frontend**: Vue 3, Vite, Pinia, Tailwind CSS
- **Database/Auth**: Supabase
- **AI**: Google Gemini 2.5 Flash

## 📝 License
This project is licensed under the MIT License.