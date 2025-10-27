# Quick Start Guide

Follow these steps to get your FastAPI backend running in 5 minutes!

## Step 1: Set Up Python Environment

```bash
# Go to the backend folder
cd backend

# Create a virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# You should see (venv) in your terminal prompt now
```

## Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- FastAPI - the web framework
- Uvicorn - the web server
- SQLAlchemy - for database
- Pydantic - for data validation
- JWT libraries - for authentication
- Password hashing - for security

## Step 3: Set Up Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Generate a secure secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Edit .env and paste the generated key as SECRET_KEY
# You can use nano, vim, or any text editor:
nano .env
```

## Step 4: Run the Server

```bash
uvicorn app.main:app --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

## Step 5: Test It!

### Open the Interactive API Docs

1. Open your browser
2. Go to: http://localhost:8000/docs
3. You'll see the Swagger UI with all your API endpoints!

### Try Registering a User

1. Click on `POST /auth/register` to expand it
2. Click "Try it out"
3. Fill in the example data:
   ```json
   {
     "email": "user@example.com",
     "username": "myusername",
     "password": "mypassword123",
     "full_name": "My Name"
   }
   ```
4. Click "Execute"
5. You should see a successful response with your user data!

### Try Logging In

1. Click on `POST /auth/login` to expand it
2. Click "Try it out"
3. Enter:
   - username: `myusername`
   - password: `mypassword123`
4. Click "Execute"
5. You'll get back an `access_token`!

### Try a Protected Route

1. Copy the `access_token` from the login response
2. Click the "Authorize" button at the top of the page
3. Paste your token in the Value field
4. Click "Authorize" then "Close"
5. Now click on `GET /auth/me`
6. Click "Try it out" then "Execute"
7. You'll see your user information!

## Understanding What You Built

### File Structure
```
app/
├── main.py           → The FastAPI app (start here!)
├── config.py         → Settings and configuration
├── database.py       → Database connection
├── models/
│   └── user.py       → User table definition
├── schemas/
│   └── auth.py       → Request/response formats
├── api/
│   └── auth.py       → Login/register endpoints
└── utils/
    └── security.py   → Password hashing, JWT tokens
```

### How It Works

1. **User registers** → Password is hashed → Saved to database
2. **User logs in** → Password verified → JWT token created
3. **User makes request** → Token validated → User identified

### The Database

Your SQLite database is automatically created as `feature_voting.db` in the backend folder. It contains one table: `users`.

## Next Steps

Now that you have a working backend, you can:

1. **Read the code comments** - Every file has detailed explanations
2. **Experiment** - Try changing things and see what happens
3. **Add features** - Ideas, voting, etc.
4. **Build a frontend** - Create a React app to use this API

## Troubleshooting

### "Module not found" error
- Make sure your virtual environment is activated (you should see `(venv)` in your terminal)
- Run `pip install -r requirements.txt` again

### Port 8000 already in use
- Another app is using that port
- Stop it or use a different port: `uvicorn app.main:app --reload --port 8001`

### Can't import app
- Make sure you're in the `backend` directory when running uvicorn
- The command is `uvicorn app.main:app` not `python app/main.py`

## Tips

- **Keep the terminal open** - The server runs in the terminal
- **Check the logs** - Errors show up in the terminal
- **Use the docs** - http://localhost:8000/docs is your best friend
- **Read the comments** - The code is heavily commented to help you learn

Happy coding! 🎉
