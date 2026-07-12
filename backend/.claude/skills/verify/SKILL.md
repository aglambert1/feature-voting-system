---
name: verify
description: Verify backend changes by driving the real FastAPI dev server through actual HTTP calls (real login, real JWT) against the local SQLite dev DB. Use for API/model/service changes in backend/.
---

# Backend verification

Drive the real running server, not imports. This captures the recipe that
worked so the next session skips the cold-start trial-and-error.

## Start the server

```bash
cd backend
./venv/bin/python -m uvicorn app.main:app --port 8000 > /tmp/verify_backend.log 2>&1 &
sleep 4
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/docs   # expect 200
```

Port 8000 matters if you also want the frontend dev server to talk to this
instance without extra config — `frontend/.env` sets
`VITE_API_URL=http://localhost:8000`. Use a different port only for
backend-only verification.

Uses the local SQLite dev DB (`backend/feature_voting.db`, from
`DATABASE_URL=sqlite:///./feature_voting.db` in `.env`) — safe to seed
throw-away rows into it; it's not shared state.

## Auth: login is form-encoded, not JSON

`POST /auth/login` takes `OAuth2PasswordRequestForm`
(`app/api/auth.py`) — `application/x-www-form-urlencoded`, not JSON.
Posting JSON gets a 422 "Field required" that looks like a missing-body
error but is actually a wrong-content-type error.

```bash
RESP=$(curl -s -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=<username>&password=<password>")
TOKEN=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

`username` accepts either the actual username or email (see docstring in
`auth.py`), but the JWT's `sub` claim is always the **username**, not
email — don't hand-roll a token with `sub=email`, `get_current_user` looks
up by username and will 401 with "Could not validate credentials".

## Seeding fixtures

No fixture/factory script exists for ad-hoc manual verification (only
`scripts/seed_demo_data.py`, which is a larger demo dataset, not a scoped
fixture for one feature). For a scoped seed, write a one-off script under
the session scratchpad that imports `app.database.SessionLocal` and the
relevant models directly, checks for existing rows by a distinguishing
field (e.g. `title==`) before inserting so reruns are idempotent, and
prints the IDs/token you need. Run it with
`./venv/bin/python <script path>` from `backend/`.

## Common gotchas

- List endpoints redirect on trailing slash: `GET /ideas/?product_id=4` →
  307 to `/ideas?product_id=4`. Hit the no-trailing-slash form directly or
  follow redirects (`curl -L`).
- `sys.path.insert(0, ".")` at the top of a standalone seed script is
  needed since it's not run as a package module.

## Cleanup

Kill background servers when done:

```bash
lsof -ti:8000 2>/dev/null | xargs -r kill 2>/dev/null
```

Seeded rows in the dev SQLite DB are generally fine to leave (local,
low-risk) — flag them to the user rather than silently deleting.
