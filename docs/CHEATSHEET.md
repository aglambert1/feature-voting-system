# Quick Reference - Feature Voting System

Quick commands and references for daily development.

---

## Scripts

### Daily Development

```bash
./start.sh                  # Start servers (use this daily)
```

### Setup & Reset

```bash
./setup_and_test.sh         # Full environment setup + testing (3-5 min)
cd backend && python reset_db.py  # Reset database only
cd backend && python reset_db.py --force  # Reset database (no confirmation)
```

### When to Use

| Script | Use When | Time |
|--------|----------|------|
| `./start.sh` | Daily development | 10-20 sec |
| `./setup_and_test.sh` | First setup, broken environment, major updates | 3-5 min |
| `reset_db.py` | Need fresh database, testing migrations | 5 sec |

---

## URLs

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## Common Commands

### Backend

```bash
cd backend
source venv/bin/activate           # Activate virtual environment
uvicorn app.main:app --reload      # Start backend manually
pytest -v                          # Run tests
deactivate                         # Deactivate venv
```

### Frontend

```bash
cd frontend
npm install                        # Install dependencies
npm run dev                        # Start dev server
npm run build                      # Build for production
npm run lint                       # Run linter
```

---

## Configuration

### Backend `.env`

```env
DATABASE_URL=sqlite:///./feature_voting.db
SECRET_KEY=your-secret-key-here          # Generate: openssl rand -hex 32
ADMIN_USERNAME=admin
ADMIN_PASSWORD=password                  # CHANGE THIS!
ANTHROPIC_API_KEY=sk-ant-your-key-here  # Required for CI features
```

### Frontend `.env`

```env
VITE_API_URL=http://localhost:8000
```

---

## File Locations

### Logs

```bash
logs/backend_latest.log            # Latest backend logs
logs/frontend_latest.log           # Latest frontend logs
tail -f logs/*.log                 # View live logs
```

### Database

```bash
backend/feature_voting.db          # SQLite database
backend/feature_voting.db.backup.* # Automatic backups
```

---

## Troubleshooting

### Port Already in Use

```bash
# Check ports
lsof -ti :8000 :5173

# Kill processes
kill $(lsof -ti :8000 :5173)

# Or use start.sh (will prompt)
./start.sh
```

### Database Issues

```bash
cd backend
python reset_db.py --force         # Quick reset
# OR
rm feature_voting.db               # Manual delete (recreates on start)
```

### Virtual Environment Issues

```bash
cd backend
rm -rf venv
./setup_and_test.sh                # From project root
```

### Node Modules Issues

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Stuck? Nuclear Option

```bash
./setup_and_test.sh                # Resets everything
```

---

## Default Credentials

**Username**: `admin`
**Password**: `password` (configured in `backend/.env`)

**Important**: Change admin password immediately after first login!

---

## Testing

### Run All Tests

```bash
./setup_and_test.sh                # Full test suite
```

### Backend Tests Only

```bash
cd backend
source venv/bin/activate
pytest -v tests/                   # All tests
pytest tests/test_auth.py -v      # Specific file
```

### Manual API Testing

1. Start backend: `./start.sh` or manually
2. Open: http://localhost:8000/docs
3. Test endpoints in Swagger UI

---

## Workflows

### Morning Routine

```bash
./start.sh
# Open browser to http://localhost:5173
```

### After Git Pull

```bash
./start.sh                         # Should just work
# If errors:
./setup_and_test.sh                # Reinstall dependencies
```

### When Something Breaks

```bash
# Step 1: Try database reset
cd backend && python reset_db.py --force

# Step 2: Try full reset
./setup_and_test.sh
```

---

## Pro Tips

1. **Use `./start.sh` for daily work** - handles server management automatically
2. **Press Ctrl+C once** to stop both servers gracefully
3. **Check logs** when debugging: `tail -f logs/*.log`
4. **Reset database frequently** during development to avoid data issues
5. **Keep `.env` backed up** - contains important configuration

---

## Documentation

- [USER_GUIDE.md](USER_GUIDE.md) - Complete user documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [development/SETUP.md](development/SETUP.md) - Detailed setup guide
- [CHANGELOG.md](../CHANGELOG.md) - Version history

---

## Getting Help

1. Check logs: `tail -f logs/*.log`
2. Check API docs: http://localhost:8000/docs
3. Review [Troubleshooting](development/SETUP.md#troubleshooting) in setup guide
4. Check [CHANGELOG.md](../CHANGELOG.md) for known issues

---

**Quick Reference Version**: 1.0
**Last Updated**: December 2024
