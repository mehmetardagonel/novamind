#!/bin/bash

# Novamind.AI Development Server Startup Script
# This script handles environment setup and starts both backend and frontend servers on available ports.

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

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.12 or higher."
    exit 1
fi

# Function to find a free port
find_free_port() {
    local port=$1
    while python3 -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.bind(('', $port)); s.close()" 2>/dev/null; result=$?; [ $result -ne 0 ]; do
        port=$((port+1))
    done
    echo $port
}

# Clean up old PID file
if [ -f "$PID_FILE" ]; then
    print_info "Cleaning up old PID file..."
    rm "$PID_FILE"
fi

# Find available ports
print_info "Finding available ports..."
BACKEND_PORT=$(find_free_port 8001)
FRONTEND_PORT=$(find_free_port 5173)

# Ensure they are different
if [ "$BACKEND_PORT" -eq "$FRONTEND_PORT" ]; then
    FRONTEND_PORT=$(find_free_port $((BACKEND_PORT + 1)))
fi

print_success "Selected ports: Backend=$BACKEND_PORT, Frontend=$FRONTEND_PORT"

# ========================================
# OLLAMA SETUP (Open-Source LLM)
# ========================================

print_info "Checking Ollama status..."

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    print_error "Ollama is not installed!"
    print_info "Download and install from: https://ollama.com"
    print_info "After installation, restart this script."
    exit 1
fi

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    print_info "Ollama not running. Starting Ollama..."
    # Start Ollama server in background
    ollama serve > "$SCRIPT_DIR/ollama.log" 2>&1 &
    OLLAMA_PID=$!
    print_success "Ollama started (PID: $OLLAMA_PID)"
    sleep 5 # Wait for startup
fi

# Check/Pull Model
REQUIRED_MODEL="gpt-oss-20b"
# List models and check if required model exists
if ! ollama list | grep -q "$REQUIRED_MODEL"; then
    print_info "Model $REQUIRED_MODEL not found. Pulling..."
    ollama pull $REQUIRED_MODEL
    print_success "Model $REQUIRED_MODEL pulled"
else
    print_success "Model $REQUIRED_MODEL found"
fi

# ========================================
# BACKEND SETUP
# ========================================

print_info "Setting up backend..."

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    print_info "Virtual environment not found. Creating one..."
    cd "$BACKEND_DIR"
    # Use Python 3.12 specifically (required for protobuf compatibility)
    if command -v python3.12 &> /dev/null; then
        python3.12 -m venv venv
    else
        # Fallback to python3 if 3.12 specific command not found, but warn
        print_warning "python3.12 command not found. Trying default python3..."
        python3 -m venv venv
    fi
    print_success "Virtual environment created"
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Install/update backend dependencies
# Always run pip install to ensure requirements.txt changes are picked up
print_info "Checking backend dependencies..."
cd "$BACKEND_DIR"
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt --quiet
if [ $? -eq 0 ]; then
    print_success "Backend dependencies installed"
else
    print_error "Failed to install backend dependencies"
    exit 1
fi

# Check for .env file
if [ ! -f "$BACKEND_DIR/.env" ]; then
    print_warning "Backend .env file not found!"
    if [ -f "$BACKEND_DIR/env.example" ]; then
        print_info "Creating .env from env.example..."
        cp "$BACKEND_DIR/env.example" "$BACKEND_DIR/.env"
        print_warning "⚠️  IMPORTANT: You need to edit $BACKEND_DIR/.env with your credentials."
    else
        print_error "env.example file not found in backend directory!"
        exit 1
    fi
fi

# Start backend server
print_info "Starting backend server on port $BACKEND_PORT..."
cd "$BACKEND_DIR"

# Export FRONTEND_URL so backend knows where requests come from (for CORS/Redirects)
export FRONTEND_URL="http://localhost:$FRONTEND_PORT"
# Set protobuf implementation
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

"$VENV_DIR/bin/uvicorn" main:app --port $BACKEND_PORT > "$SCRIPT_DIR/backend.log" 2>&1 &
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
        cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
    else
        print_info "Creating default .env file..."
        cat > "$FRONTEND_DIR/.env" << EOF
VITE_API_URL=http://localhost:$BACKEND_PORT
VITE_SUPABASE_URL=your_supabase_url_here
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key_here
EOF
    fi
    print_warning "Please edit $FRONTEND_DIR/.env with your Supabase credentials"
fi

# Start frontend server
print_info "Starting frontend server on port $FRONTEND_PORT..."
cd "$FRONTEND_DIR"
# Export VITE_API_URL to override .env and point to the correct dynamic backend port
export VITE_API_URL="http://localhost:$BACKEND_PORT"

npm run dev -- --port $FRONTEND_PORT > "$SCRIPT_DIR/frontend.log" 2>&1 &
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