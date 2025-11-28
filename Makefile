.PHONY: help setup start stop restart clean logs status install-backend install-frontend env

# Default target
help:
	@echo ""
	@echo "========================================="
	@echo "  Novamind.AI Development Commands"
	@echo "========================================="
	@echo ""
	@echo "Setup Commands:"
	@echo "  make setup           - Complete first-time setup (venv, dependencies, env files)"
	@echo "  make install-backend - Install backend dependencies only"
	@echo "  make install-frontend- Install frontend dependencies only"
	@echo "  make env             - Create .env files from examples"
	@echo ""
	@echo "Server Commands:"
	@echo "  make start           - Start both backend and frontend servers"
	@echo "  make stop            - Stop both servers"
	@echo "  make restart         - Restart both servers"
	@echo "  make status          - Show server status"
	@echo ""
	@echo "Development Commands:"
	@echo "  make logs            - Show server logs"
	@echo "  make logs-backend    - Show backend logs only"
	@echo "  make logs-frontend   - Show frontend logs only"
	@echo "  make clean           - Clean temporary files and logs"
	@echo "  make clean-all       - Clean everything (including venv and node_modules)"
	@echo ""
	@echo "========================================="
	@echo ""

# Complete setup
setup: install-backend install-frontend env
	@echo ""
	@echo "✅ Setup complete!"
	@echo "Run 'make start' to start the development servers"
	@echo ""

# Install backend dependencies
install-backend:
	@echo "Installing backend dependencies..."
	@cd backend && \
	if [ ! -d "venv" ]; then \
		echo "Creating virtual environment..."; \
		python3 -m venv venv; \
	fi && \
	. venv/bin/activate && \
	pip install --upgrade pip --quiet && \
	pip install -r requirements.txt
	@echo "✅ Backend dependencies installed"

# Install frontend dependencies
install-frontend:
	@echo "Installing frontend dependencies..."
	@cd frontend && npm install
	@echo "✅ Frontend dependencies installed"

# Create environment files
env:
	@echo "Creating environment files..."
	@if [ ! -f backend/.env ]; then \
		if [ -f backend/env.example ]; then \
			cp backend/env.example backend/.env; \
			echo "✅ Created backend/.env from env.example"; \
			echo "⚠️  Please edit backend/.env with your credentials"; \
		else \
			echo "❌ backend/env.example not found"; \
		fi \
	else \
		echo "ℹ️  backend/.env already exists"; \
	fi
	@if [ ! -f frontend/.env ]; then \
		if [ -f frontend/.env.example ]; then \
			cp frontend/.env.example frontend/.env; \
			echo "✅ Created frontend/.env from .env.example"; \
			echo "⚠️  Please edit frontend/.env with your Supabase credentials"; \
		else \
			echo "❌ frontend/.env.example not found"; \
		fi \
	else \
		echo "ℹ️  frontend/.env already exists"; \
	fi

# Start servers
start:
	@echo "Starting development servers..."
	@./start_dev.sh

# Stop servers
stop:
	@echo "Stopping development servers..."
	@./stop_dev.sh

# Restart servers
restart: stop
	@sleep 2
	@$(MAKE) start

# Show server status
status:
	@echo ""
	@echo "========================================="
	@echo "  Server Status"
	@echo "========================================="
	@echo ""
	@if [ -f .dev_servers.pid ]; then \
		. .dev_servers.pid; \
		echo "Backend (PID $$BACKEND_PID):"; \
		if kill -0 $$BACKEND_PID 2>/dev/null; then \
			echo "  ✅ Running on http://localhost:8001"; \
		else \
			echo "  ❌ Not running"; \
		fi; \
		echo ""; \
		echo "Frontend (PID $$FRONTEND_PID):"; \
		if kill -0 $$FRONTEND_PID 2>/dev/null; then \
			echo "  ✅ Running on http://localhost:5173"; \
		else \
			echo "  ❌ Not running"; \
		fi; \
	else \
		echo "❌ No servers running (PID file not found)"; \
		echo ""; \
		echo "Checking ports manually:"; \
		if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1; then \
			echo "  Backend: ⚠️  Port 8001 is in use"; \
		else \
			echo "  Backend: ❌ Not running"; \
		fi; \
		if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then \
			echo "  Frontend: ⚠️  Port 5173 is in use"; \
		else \
			echo "  Frontend: ❌ Not running"; \
		fi; \
	fi
	@echo ""
	@echo "========================================="
	@echo ""

# Show logs
logs:
	@echo "Backend logs:"
	@echo "========================================="
	@tail -n 50 backend.log 2>/dev/null || echo "No backend logs found"
	@echo ""
	@echo "Frontend logs:"
	@echo "========================================="
	@tail -n 50 frontend.log 2>/dev/null || echo "No frontend logs found"

logs-backend:
	@tail -f backend.log

logs-frontend:
	@tail -f frontend.log

# Clean temporary files
clean:
	@echo "Cleaning temporary files..."
	@rm -f .dev_servers.pid
	@rm -f backend.log frontend.log
	@rm -rf backend/__pycache__
	@rm -rf backend/*.pyc
	@rm -f backend/gmail_token.json
	@echo "✅ Cleanup complete"

# Clean everything including dependencies
clean-all: clean
	@echo "Removing all dependencies..."
	@read -p "This will delete venv and node_modules. Continue? (y/N) " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf backend/venv; \
		rm -rf frontend/node_modules; \
		rm -rf frontend/.vite; \
		echo "✅ All dependencies removed"; \
		echo "Run 'make setup' to reinstall"; \
	else \
		echo "Cancelled"; \
	fi
