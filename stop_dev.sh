#!/bin/bash

# Novamind.AI Development Server Stop Script (Cross-platform)
# Works on Linux/macOS and Windows (Git Bash / MSYS2 / Cygwin)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.dev_servers.pid"

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Detect if running on Windows
is_windows=false
case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*)
        is_windows=true
        ;;
esac

kill_port() {
    local port=$1

    print_info "Searching for processes on port $port..."

    # Try lsof
    pids=$(lsof -ti:"$port" 2>/dev/null)

    # Try ss (WSL fix)
    if [ -z "$pids" ]; then
        pids=$(ss -ltnp 2>/dev/null | grep ":$port " | awk '{print $NF}' | sed 's/pid=//;s/,.*//' )
    fi

    if [ -z "$pids" ]; then
        print_info "No process found on port $port"
        return
    fi

    print_info "Killing processes on port $port: $pids"

    for pid in $pids; do
        kill -15 "$pid" 2>/dev/null
        sleep 1
        kill -9 "$pid" 2>/dev/null
    done

    print_success "Port $port cleared"
}

kill_windows_port() {
    local port=$1
    print_info "Checking Windows-side processes on port $port..."

    pids=$(powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "
        try {
            Get-NetTCPConnection -LocalPort $port -ErrorAction Stop |
            Select-Object -ExpandProperty OwningProcess
        } catch { }
    " | tr -d '\r')

    if [[ -z "$pids" ]]; then
        print_info "No Windows-side process found on port $port"
        return
    fi

    print_info "Killing Windows PIDs using port $port: $pids"

    for pid in $pids; do
        powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "
            try { Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue } catch { }
        " >/dev/null 2>&1
    done

    print_success "Windows port $port cleared"
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Novamind.AI Server Shutdown${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# If PID file missing, fallback to port-based kill
if [ ! -f "$PID_FILE" ]; then
    print_warning "PID file not found. Attempting manual port cleanup..."

    BACKEND_PORT=8001
    FRONTEND_PORT=5173

    kill_port $BACKEND_PORT
    kill_port $FRONTEND_PORT

    echo ""
    print_success "Cleanup complete"
    exit 0
fi

# Read PID file
source "$PID_FILE"

stop_pid() {
    local pid=$1
    local name=$2

    if [ -z "$pid" ]; then
        print_warning "$name PID missing"
        return
    fi

    print_info "Stopping $name (PID $pid)..."

    if $is_windows; then
        taskkill /PID $pid /F >/dev/null 2>&1 && \
            print_success "$name stopped" || \
            print_warning "$name may not be running"
    else
        kill -15 "$pid" 2>/dev/null
        sleep 2
        kill -0 "$pid" 2>/dev/null && kill -9 "$pid"
        kill -0 "$pid" 2>/dev/null || print_success "$name stopped"
    fi
}

# Stop by PIDs
[ ! -z "$BACKEND_PID" ] && stop_pid $BACKEND_PID "Backend server"
[ ! -z "$FRONTEND_PID" ] && stop_pid $FRONTEND_PID "Frontend server"

print_info "Removing PID file..."
rm -f "$PID_FILE"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   All Servers Stopped${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
print_info "To restart the servers, run: ./start_dev.sh"
echo ""
