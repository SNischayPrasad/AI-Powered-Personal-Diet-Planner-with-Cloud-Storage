# 14 · Local / virtual simulation

Everything runs on one laptop, free and offline (apart from installing packages). Locally:

- **SQLite** plays the managed cloud database;
- a **folder** plays the object-storage bucket;
- the **rule-based engine** plays the AI.

Step 16 swaps in PostgreSQL and an S3 server with Docker for a closer "virtual cloud".

Commands are shown for **Windows (PowerShell)** and **macOS / Linux (bash)** where they
differ. Run everything from the project folder unless noted.

## Step 1: Install the required software

| Tool | Version | Check |
|---|---|---|
| Python | 3.11 or newer (3.13 recommended) | `python --version` (`python3` on macOS/Linux) |
| Node.js | 20.19+ (22 LTS recommended) | `node --version` |
| Git | any recent | `git --version` |
| Docker Desktop | optional, for step 16 | `docker --version` |

Windows: install Python from python.org and tick **"Add python.exe to PATH"**. On macOS:
`brew install python node git`.

## Step 2: Clone the project

```bash
git clone https://github.com/SNischayPrasad/AI-Powered-Personal-Diet-Planner-with-Cloud-Storage.git
cd AI-Powered-Personal-Diet-Planner-with-Cloud-Storage
```

## Step 3: Create a Python virtual environment

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell blocks the script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
once. Alternatively, use `.venv\Scripts\activate.bat` from Command Prompt.

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your prompt now starts with `(.venv)`.

## Step 4: Install the dependencies

```bash
pip install -r requirements-dev.txt
npm --prefix frontend ci
```

## Step 5: Configure environment variables

Windows:

```powershell
copy .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

The defaults work as they are. To keep logins valid across restarts, generate a signing key
and paste it after `JWT_SECRET_KEY=` in `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`.env` is gitignored: never commit it.

## Step 6: Start the backend

```bash
uvicorn backend.app:app --reload
```

You should see `AI Diet Planner v1.0.0 started (… database=sqlite, storage=local, ai=rule_based)`.
Check it in the browser at http://localhost:8000/api/health (`{"status":"ok",…}`), and look
at the interactive API docs at http://localhost:8000/api/docs.

## Step 7: Start the frontend

In a **second terminal** (same folder):

```bash
npm --prefix frontend run dev
```

Open **http://localhost:5173**. The landing page shows a sample thali and the cloud status
panel reports *Database: sqlite · Storage: local*.

## Step 8: Register a demo user

Click **Create a free account** and register with synthetic details, e.g. *Asha Demo* ·
`asha.demo@example.com` · `Demo-password-1`. You land on the profile page, already signed in.

Or from a terminal:

```bash
curl -X POST http://localhost:8000/api/register -H "Content-Type: application/json" -d "{\"name\":\"Asha Demo\",\"email\":\"asha.demo@example.com\",\"password\":\"Demo-password-1\"}"
```

## Step 9: Complete the profile

Enter age 29, female, 162 cm, 58 kg, lightly active, vegetarian, balanced, allergy *Peanuts*,
cuisine *Indian*, then **Save profile**.

## Step 10: Generate a diet plan

Go to **Generate plan** and press the **Generate plan** button. The result page shows breakfast, lunch, snack
and dinner, the calorie total vs target, macro meters, a hydration reminder and tips. The
badge reads *Rule-based engine*. No dish contains peanuts or meat.

## Step 11: Save the plan

Plans are saved to the database automatically when generated. On the plan page, **Save as text** or **Save as JSON**
also stores a copy in object storage, and the download buttons (**Text file**, **JSON**)
export it to your computer.

## Step 12: Upload a sample file

Open **Cloud files** and drag in `sample_data/images/lunch-thali.png` (or any JPEG, PNG,
WebP or PDF under 4 MB). It appears with a preview. Try a `.txt` file too: it is rejected
with a clear message.

## Step 13: Retrieve a previous plan

Generate a second plan, then open **Saved plans**. Both are listed newest first. Open the
older one: it is identical to when it was created.

## Step 14: Test logout and login

Click **Log out**, and you see "You have been logged out." Visiting http://localhost:5173/dashboard
now redirects to login. Log in again and all plans and files are still there. This is data
stored centrally, not in the browser.

## Step 15: Verify the stored data

Database (structured data):

```bash
python -c "import sqlite3; c=sqlite3.connect('data/diet_planner.db'); print(c.execute('select email, dietary_preference, goal from users').fetchall()); print(c.execute('select title, source, created_at from diet_plans').fetchall()); print(c.execute('select filename, storage_path, size_bytes from user_files').fetchall())"
```

Object storage (files). Windows:

```powershell
Get-ChildItem -Recurse data\object_storage
```

macOS / Linux:

```bash
find data/object_storage -type f
```

You will see `users/<your-user-id>/meal-images/<uuid>.png` and `…/plan-exports/<uuid>.txt`,
exactly the keys stored in `user_files.storage_path`.

Finally, run the automated checks:

```bash
pytest
python scripts/smoke_test.py
```

`pytest` should pass all 297 tests. The smoke test, run while the API is up, should end with
`28 passed, 0 failed`.

## Step 16 (optional): virtual cloud with Docker

Run PostgreSQL (the managed database) and RustFS (S3-compatible object storage) locally.

1. In `.env`, set `POSTGRES_PASSWORD`, `RUSTFS_ACCESS_KEY` and `RUSTFS_SECRET_KEY` to values
   of your choice (letters and digits).
2. Start the services:

   ```bash
   docker compose up -d postgres s3 s3-init
   ```

3. Point the API at them in `.env`:

   ```ini
   DATABASE_URL=postgresql://dietplanner:<POSTGRES_PASSWORD>@localhost:5432/dietplanner
   STORAGE_PROVIDER=s3
   S3_ENDPOINT_URL=http://localhost:9000
   S3_ACCESS_KEY_ID=<RUSTFS_ACCESS_KEY>
   S3_SECRET_ACCESS_KEY=<RUSTFS_SECRET_KEY>
   S3_FORCE_PATH_STYLE=true
   ```

4. Restart `uvicorn`. The status panel now says *postgresql · s3*. Browse the bucket at
   http://localhost:9001.

To run the **production image** (frontend + API in one container, as deployed):

```bash
docker compose --profile app up --build
```

Then open http://localhost:8000. `JWT_SECRET_KEY` must be set in `.env`.

## Optional: seed demo users and try an LLM

```bash
python scripts/seed_demo_data.py
```

This creates Asha, Kabir and Rohan (synthetic) and prints a one-time password, or uses
`DEMO_PASSWORD`.

For AI plans, set in `.env`, e.g. `AI_PROVIDER=openai_compatible`,
`OPENAI_COMPAT_BASE_URL=http://localhost:11434/v1` and `OPENAI_COMPAT_MODEL=llama3.1` for a
local Ollama, or `AI_PROVIDER=anthropic` with `ANTHROPIC_API_KEY`. Restart the API. If the
model is unreachable, plans still come from the rules, with the reason shown.

## Troubleshooting

| Problem | Fix |
|---|---|
| `uvicorn: command not found` | Activate the virtual environment (step 3) |
| Port 8000 or 5173 in use | `uvicorn backend.app:app --port 8001`, and start Vite with `VITE_DEV_API_PROXY=http://localhost:8001` |
| Logged out after every API restart | Set `JWT_SECRET_KEY` in `.env` (step 5) |
| 429 "Too many attempts" | Wait a minute; the login rate limit is 10/minute |
| `npm ci` errors | Check `node --version` is 20.19+ |
| Want a clean slate | Stop the API and delete the `data/` folder |
