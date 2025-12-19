.PHONY: help setup verify start stop restart check clean test test-backend test-frontend test-integration fix-bcrypt logs

# Default target - show help
.DEFAULT_GOAL := help

help:  ## Show this help message
	@echo ""
	@echo "Feature Voting System - Development Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make setup          # First time setup"
	@echo "  make start          # Start development servers"
	@echo "  make test           # Run all tests"
	@echo "  make clean          # Clean all build artifacts"
	@echo ""

setup:  ## Full system setup and testing (first time or after major changes)
	@echo "Running full setup and testing..."
	./setup_and_test.sh

verify:  ## Quick environment verification (health check)
	@echo "Verifying environment..."
	./verify.sh

start:  ## Start development servers (backend + frontend)
	@echo "Starting development servers..."
	./start.sh

stop:  ## Stop all running servers
	@echo "Stopping all servers..."
	./kill_servers.sh

restart:  ## Restart servers (stop + start)
	@echo "Restarting servers..."
	./kill_servers.sh
	@sleep 2
	./start.sh

check:  ## Check server status (show PIDs and ports)
	@echo "Checking server status..."
	./check_servers.sh

clean:  ## Clean all build artifacts and stop servers
	@echo "Cleaning build artifacts..."
	./kill_servers.sh
	@echo "Removing backend database..."
	rm -f backend/feature_voting.db
	@echo "Removing frontend build..."
	rm -rf frontend/dist
	@echo "Clean complete. Run 'make setup' to reinitialize."

clean-deep:  ## Deep clean (remove venv and node_modules too)
	@echo "WARNING: This will remove venv and node_modules."
	@echo "You will need to run 'make setup' after this."
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	$(MAKE) clean
	@echo "Removing backend virtual environment..."
	rm -rf backend/venv
	@echo "Removing frontend node_modules..."
	rm -rf frontend/node_modules
	@echo "Deep clean complete. Run 'make setup' to reinitialize."

test:  ## Run all tests (backend + frontend)
	@echo "Running all tests..."
	$(MAKE) test-backend
	$(MAKE) test-frontend

test-backend:  ## Run backend tests (pytest)
	@echo "Running backend tests..."
	cd backend && source venv/bin/activate && python -m pytest tests/ test_*.py -v

test-frontend:  ## Run frontend tests (lint + build)
	@echo "Running frontend lint..."
	cd frontend && npm run lint
	@echo "Running frontend build test..."
	cd frontend && npm run build

test-integration:  ## Run integration tests (manual test scripts)
	@echo "Running integration tests..."
	@echo ""
	@echo "Test 1: Module 7 Integration Test"
	./scripts/tests/test_module7_simple.sh
	@echo ""
	@echo "Test 2: Edit Endpoint Test"
	./scripts/tests/test_edit.sh

fix-bcrypt:  ## Fix bcrypt compatibility issues
	@echo "Fixing bcrypt compatibility..."
	./fix_bcrypt.sh

logs:  ## Show recent server logs
	@echo "Backend logs:"
	@echo "============================================"
	@tail -20 logs/backend_latest.log 2>/dev/null || echo "No backend logs found"
	@echo ""
	@echo "Frontend logs:"
	@echo "============================================"
	@tail -20 logs/frontend_latest.log 2>/dev/null || echo "No frontend logs found"

logs-follow:  ## Follow server logs in real-time
	@echo "Following logs (Ctrl+C to stop)..."
	@tail -f logs/*.log 2>/dev/null || echo "No logs found. Start servers first."

dev:  ## Full development workflow (verify + start)
	@echo "Starting development workflow..."
	$(MAKE) verify
	$(MAKE) start

# Backend-specific targets
backend-shell:  ## Start backend with activated venv in new shell
	@echo "Starting backend shell..."
	@cd backend && source venv/bin/activate && exec $$SHELL

backend-test:  ## Quick backend import test
	@cd backend && source venv/bin/activate && python -c "from app.main import app; print('✓ Backend imports OK')"

# Frontend-specific targets
frontend-build:  ## Build frontend for production
	@echo "Building frontend for production..."
	cd frontend && npm run build

frontend-preview:  ## Preview production build
	@echo "Previewing production build..."
	cd frontend && npm run preview

# Database targets
db-reset:  ## Reset database (backup current, create fresh)
	@echo "Resetting database..."
	@if [ -f backend/feature_voting.db ]; then \
		cp backend/feature_voting.db backend/feature_voting.db.backup.$$(date +%Y%m%d_%H%M%S); \
		echo "✓ Database backed up"; \
		rm backend/feature_voting.db; \
		echo "✓ Database removed"; \
	else \
		echo "No existing database found"; \
	fi
	@echo "Database will be recreated on next backend startup"

db-backup:  ## Backup current database
	@echo "Backing up database..."
	@if [ -f backend/feature_voting.db ]; then \
		cp backend/feature_voting.db backend/feature_voting.db.backup.$$(date +%Y%m%d_%H%M%S); \
		echo "✓ Database backed up to backend/feature_voting.db.backup.*"; \
	else \
		echo "No database found to backup"; \
	fi

# Install/update dependencies
install:  ## Install/update all dependencies
	@echo "Installing backend dependencies..."
	cd backend && source venv/bin/activate && pip install -r requirements.txt
	@echo "Installing frontend dependencies..."
	cd frontend && npm install
	@echo "✓ All dependencies installed"

update:  ## Update dependencies to latest versions
	@echo "Updating backend dependencies..."
	cd backend && source venv/bin/activate && pip install --upgrade -r requirements.txt
	@echo "Updating frontend dependencies..."
	cd frontend && npm update
	@echo "✓ All dependencies updated"

# Git helpers
status:  ## Show git status
	@git status

commit:  ## Interactive commit (staged files)
	@git status
	@echo ""
	@read -p "Commit message: " msg && git commit -m "$$msg"

push:  ## Push to remote
	@git push

pull:  ## Pull from remote and reinstall dependencies if needed
	@git pull
	@echo "Checking if dependencies changed..."
	@if git diff HEAD@{1} HEAD -- backend/requirements.txt | grep -q .; then \
		echo "Backend dependencies changed, reinstalling..."; \
		$(MAKE) install; \
	fi
	@if git diff HEAD@{1} HEAD -- frontend/package.json | grep -q .; then \
		echo "Frontend dependencies changed, reinstalling..."; \
		$(MAKE) install; \
	fi
