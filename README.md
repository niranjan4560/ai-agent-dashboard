# ARIA — AI Agent Dashboard

A personal AI-powered dashboard for IT professionals. ARIA (Adaptive Real-time Intelligence Agent) keeps users informed with live data, helps manage tasks, and provides an intelligent AI assistant capable of performing real actions using APIs and database operations.

---

## What I Built

A single-page dashboard with:

- **User Authentication** — Registration and sign-in (JWT, bcrypt-hashed passwords) from a built-in sign-in dialog
- **Weather Widget** — Live weather for any city via OpenWeatherMap (temperature, humidity, wind, feels-like)
- **Crypto Tracker** — Real-time prices and 24h change for Bitcoin, Ethereum, Solana, and XRP via CoinGecko (no API key required)
- **News Feed** — Latest articles on any topic via NewsAPI, with source and publish date
- **GitHub Activity** — Recent public events (pushes, PRs, stars, repository activity) for any GitHub user
- **Todo Manager** — Per-user persistent task list backed by PostgreSQL
- **ARIA Agent Chat** — AI assistant using Google's Gemini 2.5 Flash with real tool-calling. It fetches weather, news, crypto prices, and GitHub activity, and executes task operations based on natural-language requests

All data is live — no hardcoded or dummy values anywhere. If a provider is not configured or unreachable, the widget says so instead of showing fake data.

---

## Tech Stack

| Layer          | Technology                      | Why                                            |
|----------------|---------------------------------|------------------------------------------------|
| Backend        | Python 3.13 + FastAPI           | Fast async API framework with clean routing    |
| Database       | PostgreSQL (Neon in production) | Persistent storage for users, chats, and tasks |
| ORM / driver   | SQLAlchemy 2.1 + psycopg 3      | Database abstraction and model management      |
| Authentication | JWT (PyJWT) + bcrypt            | Stateless, expiring sessions; salted hashes    |
| AI Agent       | Google Gemini 2.5 Flash         | Hosted LLM with function-calling support       |
| Frontend       | Vanilla HTML + CSS + JavaScript | Lightweight, no build step                     |
| Templates      | Jinja2                          | Simple server-side HTML rendering              |
| HTTP           | httpx (async)                   | Non-blocking API calls in FastAPI              |

**APIs used:**
- [OpenWeatherMap](https://openweathermap.org/api) — Weather
- [NewsAPI](https://newsapi.org) — News headlines
- [CoinGecko](https://www.coingecko.com/en/api) — Crypto prices (free, no key needed)
- [GitHub REST API](https://docs.github.com/en/rest) — Public activity
- [Google Gemini API](https://ai.google.dev/gemini-api/docs) — LLM inference

### Architecture

```
Browser ──HTTPS──▶ FastAPI (Render web service)
                     ├── serves templates/ + static/  (the UI — same origin, no CORS needed)
                     ├── /api/weather|news|crypto|github ──▶ third-party APIs (server-side keys)
                     ├── /register, /login, /api/todos, /my-chats ──▶ PostgreSQL (Neon)
                     └── /api/agent/chat ──▶ Gemini (tool calls run on the server)
```

API keys live only on the server; the browser never sees them.

---

## Project Structure

```
ai-agent-dashboard/
├── main.py                  # FastAPI app — routes, tool functions, AI agent loop
├── database.py              # Engine/session setup from DATABASE_URL
├── models.py                # SQLAlchemy models (users, chat_history, todos)
├── auth.py                  # Password hashing + JWT helpers
├── init_db.py               # Optional: create tables manually (the app also does this on startup)
├── requirements.txt         # Pinned runtime dependencies
├── requirements-dev.txt     # + test dependencies
├── render.yaml              # Render Blueprint (production deployment)
├── Procfile                 # Start command for Procfile-based hosts (Railway, Heroku…)
├── .python-version          # Python version for hosts and CI
├── .env.example             # Environment variable template (placeholders only)
├── run.sh / run.bat         # One-command local startup
├── tests/                   # pytest suite (API, auth, tasks, agent loop)
├── .github/workflows/ci.yml # Runs tests on PostgreSQL + SQLite for every push/PR
├── templates/index.html     # Single-page dashboard (Jinja2)
└── static/
    ├── css/style.css        # Styles — dark terminal aesthetic, responsive
    └── js/dashboard.js      # Widgets, clock, sign-in, chat, tasks
```

---

## Setup & Run (local)

### 1. Clone the repository

```bash
git clone https://github.com/niranjan4560/ai-agent-dashboard.git
cd ai-agent-dashboard
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` — see [Environment variables](#environment-variables) below. At minimum set `DATABASE_URL`.

**Where to get API keys (all have free tiers):**
- Google Gemini API: https://aistudio.google.com/apikey
- OpenWeatherMap: https://home.openweathermap.org/api_keys
- NewsAPI: https://newsapi.org/register
- GitHub PAT (optional, no scopes needed for public data): https://github.com/settings/tokens
- CoinGecko: No key needed ✓

### 4. Create a PostgreSQL database

```sql
CREATE DATABASE ai_dashboard;
```

(or create a free database at [neon.tech](https://neon.tech) and use its connection string).

### 5. Run the application

```bash
uvicorn main:app --reload --port 8000
```

Tables are created automatically on startup (`python init_db.py` does the same manually). This only creates *missing* tables — it never drops or changes existing data.

### 6. Open the dashboard

Visit [http://localhost:8000](http://localhost:8000), click **Sign in → Create account**, and you're in. API docs: [http://localhost:8000/docs](http://localhost:8000/docs).

### Quick start scripts

`run.sh` (macOS/Linux) and `run.bat` (Windows — double-click it) create a virtual environment, install dependencies and start the server on http://localhost:8000. They require a `.env` file.

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | **Yes** | PostgreSQL URL. `postgres://` and `postgresql://` both work. Neon URLs need `?sslmode=require`. |
| `SECRET_KEY` | **Yes in production** | Long random string that signs login tokens. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Changing it signs everyone out. |
| `APP_ENV` | No | `production` makes a missing `SECRET_KEY` a startup error. Default `development` (random key per process). |
| `GEMINI_API_KEY` | For AI chat | Without it, chat replies with a clear "not configured" message; task shortcuts still work. |
| `GEMINI_MODEL` | No | Default `gemini-2.5-flash`. |
| `CHAT_RATE_LIMIT_PER_MINUTE` | No | ARIA messages per user per minute (default 10) — protects your Gemini quota. |
| `JWT_EXPIRE_MINUTES` | No | Session length, default 1440 (24 h). |
| `OPENWEATHER_API_KEY` | For weather | |
| `NEWS_API_KEY` | For news | |
| `GITHUB_USERNAME` | No | Default user shown in the GitHub widget. |
| `GITHUB_TOKEN` | No | Raises the GitHub limit from 60 to 5,000 requests/hour. |
| `CORS_ORIGINS` | No | Comma-separated origins, only if a front-end on another domain calls the API. |
| `LOG_LEVEL` | No | Default `INFO`. |

Locally these go in `.env` (git-ignored). In production, set them in the hosting provider's dashboard — never commit them.

---

## Testing

```bash
pip install -r requirements-dev.txt
python -m pytest                       # uses a throwaway SQLite file
TEST_DATABASE_URL=postgresql://user:pass@localhost/aria_test python -m pytest   # real PostgreSQL
```

The tests only ever use `TEST_DATABASE_URL` (tables are dropped between tests) — never your `DATABASE_URL`. External APIs and Gemini are replaced with fakes at the HTTP/SDK boundary, so tests need no keys or network. They cover registration/login validation, token expiry and forgery, per-user isolation of tasks and chats, task CRUD, widget success/error paths, the chat rate limit, and the Gemini tool-calling loop.

CI (`.github/workflows/ci.yml`) runs the suite on PostgreSQL 16 and SQLite for every push to `main` and every pull request.

---

## Deployment (Render + Neon, free tiers)

The app is one web service (API + UI), plus a PostgreSQL database.

**1. Database — Neon**
1. Sign up at [neon.tech](https://neon.tech) and create a project (any region close to your Render region).
2. Copy the connection string from **Connection Details** (it looks like `postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`).

**2. Web service — Render**
1. Merge this work into `main` (the Blueprint deploys `main`).
2. In [Render](https://dashboard.render.com): **New → Blueprint**, connect the GitHub repo `niranjan4560/ai-agent-dashboard`. Render reads `render.yaml`.
3. When prompted, paste `DATABASE_URL` (from Neon) and your `GEMINI_API_KEY`, `OPENWEATHER_API_KEY`, `NEWS_API_KEY`, `GITHUB_USERNAME`, `GITHUB_TOKEN` (leave any you don't have blank). `SECRET_KEY` is generated automatically.
4. Click **Apply**. Render builds (`pip install -r requirements.txt`), starts `uvicorn`, and waits for `/healthz` to report healthy. HTTPS is provided automatically at `https://aria-dashboard-xxxx.onrender.com` (the exact name is shown in the dashboard).
5. Auto-deploy is on: every push to `main` redeploys.

**3. Verify**
- `https://<your-app>.onrender.com/healthz` → `{"status":"ok","database":"ok",…}` (the `integrations` block shows which keys are configured — booleans only, never values).
- Open the site, create an account, add a task, ask ARIA "weather in London".
- Check **Logs** in Render for errors.

**Free-tier behaviour:** Render's free web services sleep after ~15 minutes without traffic; the first request afterwards takes up to a minute while it wakes. Neon's free tier also suspends idle compute (wake-up is about a second). The app uses connection pre-ping, so this is handled transparently.

Other hosts: any platform that runs a Python web process works — use the start command from the `Procfile` and set the same environment variables.

---

## Security & privacy

- **Stored data:** username, email, bcrypt password hash, tasks, and chat messages (your message and ARIA's reply). Messages sent to ARIA are also processed by Google's Gemini API. This is disclosed in the sign-in dialog.
- All task and chat endpoints derive the user from the signed token; users cannot read or change each other's data.
- Tokens expire (24 h default); a missing/invalid/expired token returns `401` and the UI asks you to sign in again.
- Third-party API keys stay server-side and are never returned by the API or logged.
- Input is validated (email format, username charset, password 8–72 bytes, message and task lengths); external API parameters are URL-encoded.
- Responses carry `X-Content-Type-Options`, `X-Frame-Options` and `Referrer-Policy` headers. The UI escapes all third-party text before rendering.
- The login token is stored in `localStorage` (standard for a bearer-token SPA). There is no password reset or email verification yet.
- This project has not been audited for any regulatory compliance.

---

## How the AI Agent Works

ARIA uses Google's Gemini Function Calling capability in an agentic execution loop:

1. User sends a message (e.g. *"What's the weather in Tokyo?"*)
2. Gemini analyzes the request and determines whether one or more tools are required.
3. The backend executes the tool — making a real HTTP request or database operation
4. Tool results are returned to Gemini, which combines them with its reasoning.
5. A natural-language response is generated and returned to the user.
6. The process can repeat for up to five rounds when multiple tool calls are required.

The conversation history is maintained on the frontend and sent with each request, giving ARIA full context of the conversation.

### Available Tools
- get_weather
- get_news
- get_crypto_price
- get_github_activity

### Information Tools

ARIA can fetch:
- Live weather for any city
- Latest news on any topic
- Cryptocurrency prices and 24h change
- GitHub public activity for any user

### Productivity Tools

ARIA can execute:
- Create tasks (`add DAA revision task`)
- List tasks (`show my tasks`)
- Mark tasks as complete (`complete DAA revision task`)

All task operations are stored in PostgreSQL and reflected live in the dashboard.

Task shortcuts (`add …`, `complete …`, `show my tasks`) are handled directly by the backend and work even without a Gemini key. Chat and tasks require a free account; the other widgets work for anonymous visitors.

**Example prompts to try:**
- *"What's the current Ethereum price and how is Bitcoin doing?"*
- *"Show me the latest news on cybersecurity"*
- *"Weather in Kochi and Mumbai — which is hotter?"*
- *"Show my GitHub activity"*
- *"Add a task: review pull requests"*
- *"Show my tasks"*
- *"Complete the review pull requests task"*

---

## Key Design Decisions

**1. Python + FastAPI over Node.js/React**
My strongest language is Python. FastAPI gives async support (important for parallel API calls) with minimal boilerplate, and Jinja2 handles templating cleanly.

**2. Vanilla JS frontend**
No build step, no framework complexity. The dashboard is a single page with straightforward fetch calls — vanilla JS is more than sufficient and keeps the project easy to run.

**3. Tool-calling over prompt-stuffing**
Instead of injecting raw API data into the prompt, Gemini decides which tool to call based on the user's intent. This is more robust and extensible — adding a new data source is as simple as adding a new tool definition and async function.

**4. Agentic loop (up to 5 rounds)**
A single round of tool use isn't always enough (e.g. comparing weather in two cities, or fetching GitHub data then reasoning about it). The loop lets ARIA chain multiple tool calls naturally within one conversation turn.

**5. PostgreSQL for persistence**
PostgreSQL provides reliable storage for user accounts, chat history, and todo tasks — ensuring data remains available across sessions and for multiple users.

**6. JWT authentication**
JWT tokens (HS256, signed with `SECRET_KEY`, 24 h expiry by default) provide stateless authentication without server-side sessions. Passwords are stored as salted bcrypt hashes.

**7. CoinGecko for crypto**
No API key required for basic price queries — reduces setup friction significantly.

**8. Auto-refresh every 5 minutes**
All widgets silently refresh in the background so data stays current without user interaction.

---

## What I'd Improve with More Time

1. **WebSocket live updates** — Push real-time price changes via WebSockets instead of polling every 5 minutes
2. **Task/calendar integration** — Google Calendar or Todoist via OAuth so ARIA can manage schedules and reminders
3. **System monitoring widget** — CPU, RAM, disk, and network usage using `psutil` — especially relevant for IT professionals
4. **Long-term AI memory** — Enable ARIA to remember user preferences and context across multiple sessions
5. **User preferences** — Let users save their default city, GitHub username, and favourite crypto coins
6. **Stock market widget** — Add stock price tracking via Alpha Vantage or Yahoo Finance
7. **Email summaries** — Gmail integration to summarise unread emails via IMAP
8. **ARIA voice input** — Browser Web Speech API for hands-free queries
9. **Dashboard layout editor** — Drag-and-drop widget arrangement saved per user in the database
10. **Rate limit handling** — Response caching for widget APIs and a shared (Redis) rate limiter when running more than one instance
11. **Schema migrations** — Add Alembic once the schema starts changing (tables are currently created with `create_all`, which never alters existing tables)

---

## Notes

- The crypto widget uses CoinGecko's public API — no key needed, but it has rate limits (~30 req/min). If you see errors, wait a moment and refresh.
- NewsAPI free tier only allows queries on articles up to 1 month old and has a 100 requests/day limit.
- GitHub's unauthenticated API is limited to 60 requests/hour. Setting `GITHUB_TOKEN` raises this to 5,000/hour.
- PostgreSQL must be reachable before starting the application (`/healthz` reports `503` if it is not).
- NewsAPI's free *Developer* plan is intended for development use; for a public production site check their terms or upgrade.
