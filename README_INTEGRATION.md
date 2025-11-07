# Frontend-Backend Integration Guide

## Overview

This branch (`feature/arda-connect-frontend-to-backend`) connects the Vue.js frontend with the FastAPI backend, implementing user authentication and preparing for email management features.

## Architecture

```
┌─────────────────────┐
│   Vue.js Frontend   │
│   (Port: 5173)      │
│                     │
│  - Login/Signup     │
│  - Main Dashboard   │
│  - Email Management │
└──────────┬──────────┘
           │
           │ HTTP/REST
           │ (Proxied by Vite)
           ↓
┌─────────────────────┐
│  FastAPI Backend    │
│   (Port: 8000)      │
│                     │
│  - JWT Auth         │
│  - Gmail API        │
│  - Email Operations │
└─────────────────────┘
```

## Features Implemented

### Backend
- ✅ JWT-based authentication (login/signup)
- ✅ User management with SQLite database
- ✅ Protected email endpoints (read/send)
- ✅ CORS configuration for frontend
- ✅ Gmail API integration via simplegmail

### Frontend
- ✅ Pinia state management for auth
- ✅ Axios API client with interceptors
- ✅ Login and Signup screens with real API
- ✅ Protected routes with auth guard
- ✅ User profile display
- ✅ Logout functionality
- ✅ Vite proxy configuration

## Setup Instructions

### Prerequisites
- Python 3.8+
- Node.js 20.19+ or 22.12+
- Gmail API credentials (for email features)

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.env` file from example:
```bash
cp .env.example .env
```

4. Edit `.env` and update:
```
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///./novamind.db
```

5. Run the backend:
```bash
uvicorn main:app --reload
```

The API will be available at http://localhost:8000

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install Node dependencies:
```bash
npm install
```

3. The `.env` file is already configured:
```
VITE_API_URL=http://localhost:8000
```

4. Run the frontend:
```bash
npm run dev
```

The frontend will be available at http://localhost:5173

## Testing the Integration

### 1. Create a User Account

1. Open http://localhost:5173
2. Click "Sign Up"
3. Fill in the form:
   - Email: `test@example.com`
   - Username: `testuser`
   - Full Name: `Test User` (optional)
   - Password: `password123`
   - Confirm Password: `password123`
4. Click "Sign Up"
5. You should be redirected to the main app

### 2. Login

1. Go to http://localhost:5173/login
2. Enter:
   - Username: `testuser`
   - Password: `password123`
3. Click "Login"
4. You should see the main dashboard with your user info

### 3. Test Logout

1. Click the "Logout" button in the sidebar
2. You should be redirected to the login page
3. Your session should be cleared

### 4. Test Protected Routes

1. Try to access http://localhost:5173/app without logging in
2. You should be automatically redirected to login

## API Endpoints

### Authentication

- **POST /api/auth/signup** - Create new user account
  ```json
  {
    "email": "user@example.com",
    "username": "username",
    "password": "password",
    "full_name": "Full Name" // optional
  }
  ```

- **POST /api/auth/login** - Login (OAuth2 form data)
  ```
  username=testuser&password=password123
  ```

- **GET /api/auth/me** - Get current user (requires auth token)

### Email Operations (requires authentication)

- **GET /backend/read-email** - Fetch emails with filters
  - Query params: `sender`, `subject_contains`, `unread`, `labels`, `newer_than_days`

- **POST /backend/send-email** - Send email
  ```json
  {
    "to": "recipient@example.com",
    "subject": "Email Subject",
    "body": "Email body text"
  }
  ```

## Project Structure

```
novamind/
├── backend/
│   ├── main.py              # FastAPI app with auth + email endpoints
│   ├── auth.py              # JWT authentication logic
│   ├── database.py          # SQLAlchemy models and DB setup
│   ├── models.py            # Pydantic models for emails
│   ├── filters.py           # Email filter models
│   ├── requirements.txt     # Python dependencies
│   └── .env.example         # Environment variables template
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.js    # Axios instance with interceptors
│   │   │   ├── auth.js      # Auth API functions
│   │   │   └── emails.js    # Email API functions
│   │   ├── stores/
│   │   │   └── auth.js      # Pinia auth store
│   │   ├── components/
│   │   │   ├── LoginScreen.vue
│   │   │   ├── SignUpScreen.vue
│   │   │   └── MainApp.vue
│   │   ├── router/
│   │   │   └── index.js
│   │   └── main.js
│   ├── vite.config.js       # Vite config with proxy
│   ├── package.json
│   └── .env.example
│
└── README_INTEGRATION.md    # This file
```

## Technology Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - ORM for database operations
- **python-jose** - JWT token generation/validation
- **passlib** - Password hashing (bcrypt)
- **simplegmail** - Gmail API wrapper
- **uvicorn** - ASGI server

### Frontend
- **Vue 3** - Progressive JavaScript framework
- **Pinia** - State management
- **Axios** - HTTP client
- **Vue Router** - Routing
- **Vite** - Build tool and dev server

## Security Features

- JWT-based authentication with secure token storage
- Password hashing using bcrypt
- CORS configuration to allow only frontend origin
- Request interceptors that automatically add auth tokens
- Automatic logout on 401 Unauthorized responses
- Protected backend routes requiring valid JWT tokens

## Next Steps (Phase 2)

- [ ] Integrate chatbot from `feature/berat-ai-assistant`
- [ ] Add WebSocket support for real-time chat
- [ ] Implement EmailHistory component with real Gmail data
- [ ] Implement EmailComposer component with send functionality
- [ ] Add email filtering and search
- [ ] Integrate ML classifier for email categorization
- [ ] Add LiveKit for voice assistant

## Troubleshooting

### Backend won't start
- Check if port 8000 is already in use
- Verify all dependencies are installed: `pip install -r requirements.txt`
- Check `.env` file exists and has valid values

### Frontend won't start
- Check if port 5173 is already in use
- Run `npm install` to ensure all dependencies are installed
- Clear node_modules and reinstall if needed

### Login fails
- Check backend is running on port 8000
- Open browser DevTools Network tab to see exact error
- Verify user exists in database or try creating new account

### CORS errors
- Verify backend CORS middleware includes `http://localhost:5173`
- Check Vite proxy configuration in `vite.config.js`
- Restart both frontend and backend servers

## Contributing

This is part of the NovaMind project. Follow the git workflow:
1. Create feature branch from `main`
2. Make changes and test thoroughly
3. Commit with descriptive messages
4. Push and create pull request to `main`

## License

[To be determined]
