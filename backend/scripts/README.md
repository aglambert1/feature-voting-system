# Scripts & Utilities

## Data Management (`backend/scripts/`)

### delete_product.py
Delete a product and all associated data (competitors, reports, ideas, embeddings, files).

```bash
cd backend
./venv/bin/python scripts/delete_product.py <product_id> --dry-run   # preview only - shows what will be deleted without execution
./venv/bin/python scripts/delete_product.py <product_id>             # delete with confirmation
./venv/bin/python scripts/delete_product.py <product_id> --yes       # skip confirmation
```

| Option | Description |
|---|---|
| `--dry-run` | Show what would be deleted without making changes |
| `--yes`, `-y` | Skip confirmation prompt |

### seed_demo_data.py
Create realistic demo data (product, users, ideas, votes, comments). Idempotent.

```bash
cd backend
./venv/bin/python -m scripts.seed_demo_data            # seed data
./venv/bin/python -m scripts.seed_demo_data --cleanup   # remove seeded data
```

### reset_db.py
Delete the SQLite database file and start fresh. Located at `backend/reset_db.py`.

```bash
cd backend
python reset_db.py           # interactive (asks for confirmation)
python reset_db.py --force   # no confirmation
```

---

## Server Management (project root)

### start.sh
Start backend (uvicorn :8000) and frontend (vite :5173) with duplicate detection.

```bash
./start.sh
```

### kill_servers.sh
Stop all backend and frontend processes.

```bash
./kill_servers.sh
```

### check_servers.sh
Show status of running servers without starting/stopping.

```bash
./check_servers.sh
```

### verify.sh
Quick health check: venv, node_modules, .env, database, imports.

```bash
./verify.sh
```

### setup_and_test.sh
Full project setup from scratch: creates venv, installs dependencies, runs tests.

```bash
./setup_and_test.sh
```

---

## MCP Server (`backend/mcp_server/`)

Local MCP server for Claude Desktop. Exposes ~23 tools for competitive intelligence, customer ideas, synthesis, and internal feedback as structured evidence.

```bash
cd backend
./venv/bin/python -m mcp_server    # run via stdio for Claude Desktop
```

Claude Desktop config (`~/.claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "feature-iq": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/feature-voting-system/backend",
      "env": {
        "DATABASE_URL": "postgresql://...",
        "VOYAGE_API_KEY": "..."
      }
    }
  }
}
```

---

## Database Migrations (`backend/alembic/`)

Migrations are managed with Alembic.

```bash
cd backend
./venv/bin/alembic upgrade head          # apply all pending migrations
./venv/bin/alembic revision --autogenerate -m "description"  # create new migration
```

---

## Testing

All tests are in `backend/tests/` and run via pytest. This is also what CI runs.

```bash
cd backend && ./venv/bin/python -m pytest tests/ -v
```
