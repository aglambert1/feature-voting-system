# Quick Reference Guide

## Available Scripts

### First Time Setup
```bash
./setup_and_test.sh  # Full setup with testing (~2-5 min)
```

### Daily Development
```bash
./verify.sh          # Quick check (~2 sec)
./start.sh           # Start both servers (~5 sec)
```

### Troubleshooting
```bash
./setup_and_test.sh  # Fix broken environment
./verify.sh          # Check what's wrong
```

## Script Summary

| Script | Purpose | Time | When to Use |
|--------|---------|------|-------------|
| `setup_and_test.sh` | Complete setup + testing | 2-5 min | First time, after updates, when broken |
| `start.sh` | Start both servers | ~5 sec | Daily development |
| `verify.sh` | Quick environment check | ~2 sec | Before starting work, after git pull |

## Common Commands

### Backend
```bash
cd backend
source venv/bin/activate      # Activate virtual environment
uvicorn app.main:app --reload # Start backend server
deactivate                     # Deactivate virtual environment
```

### Frontend
```bash
cd frontend
npm install                    # Install dependencies
npm run dev                    # Start dev server
npm run build                  # Build for production
npm run lint                   # Run linter
```

## URLs

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

## File Locations

### Configuration
- Backend env: `backend/.env`
- Frontend env: `frontend/.env`
- Backend deps: `backend/requirements.txt`
- Frontend deps: `frontend/package.json`

### Database
- SQLite DB: `backend/feature_voting.db`
- Backups: `backend/feature_voting.db.backup.*`

### Logs (when using start.sh)
- Backend: `/tmp/backend.log`
- Frontend: `/tmp/frontend.log`

## Workflow Cheat Sheet

### Morning Routine
```bash
./verify.sh && ./start.sh
```

### After Git Pull
```bash
./verify.sh || ./setup_and_test.sh
./start.sh
```

### Something Broke
```bash
./setup_and_test.sh  # Nuclear option - fresh start
```

## Environment Variables

### Backend (.env)
```env
ANTHROPIC_API_KEY=sk-ant-your-key-here  # Required for AI features
SECRET_KEY=your-secret-key               # Auto-generated
DATABASE_URL=sqlite:///./feature_voting.db
ALLOWED_ORIGINS=["http://localhost:5173"]
```

### Frontend (.env)
```env
VITE_API_URL=http://localhost:8000
```

## Troubleshooting Quick Fixes

### Port Already in Use
```bash
# Backend (port 8000)
lsof -i :8000
kill -9 <PID>

# Frontend (port 5173)
lsof -i :5173
kill -9 <PID>
```

### Virtual Environment Issues
```bash
cd backend
rm -rf venv
./setup_and_test.sh  # From project root
```

### Node Modules Issues
```bash
cd frontend
rm -rf node_modules
npm install
```

### Database Issues
```bash
cd backend
rm feature_voting.db  # Will be recreated on next start
```

## Testing

### Manual API Testing
1. Start backend: `cd backend && source venv/bin/activate && uvicorn app.main:app --reload`
2. Open: http://localhost:8000/docs
3. Try endpoints in Swagger UI

### Backend Unit Tests
```bash
cd backend
source venv/bin/activate
python test_schemas.py
```

## Default Credentials

```
Username: admin
Password: admin123
```

**Change these in production!**

## Getting Help

1. Check [SCRIPTS_README.md](./SCRIPTS_README.md) for detailed script docs
2. Check [README.md](./README.md) for project overview
3. Check [backend/START_HERE.md](./backend/START_HERE.md) for backend guide
4. Check logs: `tail -f /tmp/backend.log` or `/tmp/frontend.log`

## Pro Tips

1. Always run `./verify.sh` before starting work
2. Use `./start.sh` - it's faster than manual startup
3. Press `Ctrl+C` once to stop both servers gracefully
4. Keep your `.env` files backed up
5. The setup script backs up your database automatically
