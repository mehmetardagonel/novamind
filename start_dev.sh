#!/bin/bash

# Novamind.AI Development Server Startup Script
# This script handles environment setup and starts both backend and frontend servers

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/venv"
PID_FILE="$SCRIPT_DIR/.dev_servers.pid"

# Port configuration
BACKEND_PORT=8001
FRONTEND_PORT=5173

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Novamind.AI Development Startup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to kill process on port
kill_port() {
    local port=$1
    print_warning "Port $port is already in use. Attempting to free it..."
    lsof -ti:$port | xargs kill -9 2>/dev/null || true
    sleep 1
}

# Clean up old PID file
if [ -f "$PID_FILE" ]; then
    print_info "Cleaning up old PID file..."
    rm "$PID_FILE"
fi

# Clean up any existing processes on our ports
print_info "Checking for processes on ports $BACKEND_PORT and $FRONTEND_PORT..."
if lsof -Pi :$BACKEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_warning "Port $BACKEND_PORT is in use. Killing existing process..."
    lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null || true
    sleep 1
fi

if lsof -Pi :$FRONTEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_warning "Port $FRONTEND_PORT is in use. Killing existing process..."
    lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Also clean up port 8000 if something is there
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_warning "Port 8000 is in use. Killing existing process..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

print_success "Ports are clear"

# ========================================
# BACKEND SETUP
# ========================================

print_info "Setting up backend..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    print_info "Virtual environment not found. Creating one..."
    cd "$BACKEND_DIR"
    python3 -m venv venv
    print_success "Virtual environment created"
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    print_info "Installing backend dependencies..."
    cd "$BACKEND_DIR"
    pip install --upgrade pip > /dev/null 2>&1
    pip install -r requirements.txt
    print_success "Backend dependencies installed"
else
    print_success "Backend dependencies already installed"
fi

# Check for .env file
if [ ! -f "$BACKEND_DIR/.env" ]; then
    print_warning "Backend .env file not found!"
    if [ -f "$BACKEND_DIR/env.example" ]; then
        print_info "Creating .env from env.example..."
        cp "$BACKEND_DIR/env.example" "$BACKEND_DIR/.env"
        print_warning "⚠️  IMPORTANT: You need to edit $BACKEND_DIR/.env with your credentials:"
        echo "  - GOOGLE_CLIENT_ID"
        echo "  - GOOGLE_CLIENT_SECRET"
        echo "  - GOOGLE_PROJECT_ID"
        echo "  - SUPABASE_URL"
        echo "  - SUPABASE_KEY"
        echo ""
        print_warning "Backend may fail without valid credentials. Edit .env and restart."
        echo ""
    else
        print_error "env.example file not found in backend directory!"
        exit 1
    fi
fi

# Start backend server
print_info "Starting backend server on port $BACKEND_PORT..."
cd "$BACKEND_DIR"
# Set protobuf implementation to pure Python for Python 3.14 compatibility
# Note: --reload is disabled due to Python 3.14 + protobuf compatibility issues
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python "$VENV_DIR/bin/uvicorn" main:app --port $BACKEND_PORT > "$SCRIPT_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "BACKEND_PID=$BACKEND_PID" >> "$PID_FILE"
print_success "Backend server started (PID: $BACKEND_PID)"

# Wait a bit for backend to initialize
sleep 2

# ========================================
# FRONTEND SETUP
# ========================================

print_info "Setting up frontend..."

# Check if Node.js is installed
if ! command -v npm &> /dev/null; then
    print_error "Node.js/npm is not installed. Please install Node.js 18 or higher."
    exit 1
fi

# Check if node_modules exists
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    print_info "Installing frontend dependencies..."
    cd "$FRONTEND_DIR"
    npm install
    print_success "Frontend dependencies installed"
else
    print_success "Frontend dependencies already installed"
fi

# Check for .env file
if [ ! -f "$FRONTEND_DIR/.env" ]; then
    print_warning "Frontend .env file not found!"
    if [ -f "$FRONTEND_DIR/.env.example" ]; then
        print_info "Creating .env from .env.example..."
        cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
        print_warning "Please edit $FRONTEND_DIR/.env with your Supabase credentials"
    else
        print_info "Creating default .env file..."
        cat > "$FRONTEND_DIR/.env" << EOF
VITE_API_URL=http://localhost:$BACKEND_PORT
VITE_SUPABASE_URL=your_supabase_url_here
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key_here
EOF
        print_warning "Please edit $FRONTEND_DIR/.env with your Supabase credentials"
    fi
fi

# Start frontend server
print_info "Starting frontend server on port $FRONTEND_PORT..."
cd "$FRONTEND_DIR"
npm run dev > "$SCRIPT_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "FRONTEND_PID=$FRONTEND_PID" >> "$PID_FILE"
print_success "Frontend server started (PID: $FRONTEND_PID)"

# Wait for servers to fully start
sleep 3

# ========================================
# FINAL STATUS
# ========================================

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Servers Started Successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Backend:${NC}  http://localhost:$BACKEND_PORT"
echo -e "${BLUE}Frontend:${NC} http://localhost:$FRONTEND_PORT"
echo -e "${BLUE}API Docs:${NC} http://localhost:$BACKEND_PORT/docs"
echo ""
echo -e "${YELLOW}Logs:${NC}"
echo -e "  Backend:  $SCRIPT_DIR/backend.log"
echo -e "  Frontend: $SCRIPT_DIR/frontend.log"
echo ""
echo -e "${YELLOW}To stop the servers:${NC}"
echo -e "  Run: ./stop_dev.sh"
echo -e "  Or manually: kill $BACKEND_PID $FRONTEND_PID"
echo ""
echo -e "${BLUE}========================================${NC}"

# Keep script running to show any immediate errors
sleep 2

# Check if processes are still running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    print_error "Backend failed to start! Check $SCRIPT_DIR/backend.log"
    tail -20 "$SCRIPT_DIR/backend.log"
    exit 1
fi

if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    print_error "Frontend failed to start! Check $SCRIPT_DIR/frontend.log"
    tail -20 "$SCRIPT_DIR/frontend.log"
    exit 1
fi

print_success "All systems operational!"
