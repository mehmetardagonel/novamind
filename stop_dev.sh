#!/bin/bash

# Novamind.AI Development Server Stop Script
# This script gracefully stops both backend and frontend servers

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.dev_servers.pid"

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

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Novamind.AI Server Shutdown${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    print_warning "PID file not found. Attempting to find and stop servers manually..."

    # Try to kill processes on known ports
    BACKEND_PORT=8001
    FRONTEND_PORT=5173

    # Check backend port
    if lsof -ti:$BACKEND_PORT >/dev/null 2>&1; then
        print_info "Found process on backend port $BACKEND_PORT"
        lsof -ti:$BACKEND_PORT | xargs kill -15 2>/dev/null
        print_success "Stopped backend server"
    else
        print_info "No process found on backend port $BACKEND_PORT"
    fi

    # Check frontend port
    if lsof -ti:$FRONTEND_PORT >/dev/null 2>&1; then
        print_info "Found process on frontend port $FRONTEND_PORT"
        lsof -ti:$FRONTEND_PORT | xargs kill -15 2>/dev/null
        print_success "Stopped frontend server"
    else
        print_info "No process found on frontend port $FRONTEND_PORT"
    fi

    echo ""
    print_success "Cleanup complete"
    exit 0
fi

# Read PIDs from file
source "$PID_FILE"

# Function to stop a process
stop_process() {
    local pid=$1
    local name=$2

    if [ -z "$pid" ]; then
        print_warning "$name PID not found in file"
        return
    fi

    # Check if process exists
    if ! kill -0 $pid 2>/dev/null; then
        print_warning "$name (PID: $pid) is not running"
        return
    fi

    # Try graceful shutdown first (SIGTERM)
    print_info "Stopping $name (PID: $pid)..."
    kill -15 $pid 2>/dev/null

    # Wait up to 5 seconds for graceful shutdown
    local count=0
    while kill -0 $pid 2>/dev/null && [ $count -lt 5 ]; do
        sleep 1
        count=$((count + 1))
    done

    # If still running, force kill (SIGKILL)
    if kill -0 $pid 2>/dev/null; then
        print_warning "$name didn't stop gracefully, force killing..."
        kill -9 $pid 2>/dev/null
        sleep 1
    fi

    # Verify it's stopped
    if ! kill -0 $pid 2>/dev/null; then
        print_success "$name stopped successfully"
    else
        print_error "Failed to stop $name"
    fi
}

# Stop backend
if [ ! -z "$BACKEND_PID" ]; then
    stop_process $BACKEND_PID "Backend server"
fi

# Stop frontend
if [ ! -z "$FRONTEND_PID" ]; then
    stop_process $FRONTEND_PID "Frontend server"
fi

# Clean up PID file
print_info "Cleaning up PID file..."
rm -f "$PID_FILE"

# Clean up log files (optional - commented out by default)
# print_info "Cleaning up log files..."
# rm -f "$SCRIPT_DIR/backend.log" "$SCRIPT_DIR/frontend.log"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   All Servers Stopped${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
print_info "To restart the servers, run: ./start_dev.sh"
echo ""
