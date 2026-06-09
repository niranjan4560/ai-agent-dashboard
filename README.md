# ARIA — AI Agent Dashboard

A personal AI-powered dashboard for IT professionals. ARIA (Adaptive Real-time Intelligence Agent) keeps users informed with live data, helps manage tasks, and provides an intelligent AI assistant capable of performing real actions using APIs and database operations.

---

## What I Built

A single-page dashboard with:

- **User Authentication** — Secure registration and login using JWT-based authentication
- **Weather Widget** — Live weather for any city via OpenWeatherMap (temperature, humidity, wind, feels-like)
- **Crypto Tracker** — Real-time prices and 24h change for Bitcoin, Ethereum, Solana, and XRP via CoinGecko (no API key required)
- **News Feed** — Latest articles on any topic via NewsAPI, with source and publish date
- **GitHub Activity** — Recent public events (pushes, PRs, stars, repository activity) for any GitHub user
- **Todo Manager** — Persistent task management system backed by PostgreSQL
- **ARIA Agent Chat** — AI-powered assistant using Ollama (Llama 3) with real tool-calling. It intelligently fetches weather, news, crypto prices, and GitHub activity, and executes task operations in real time based on natural-language requests

All data is live — no hardcoded or dummy values anywhere.

---

## Tech Stack

| Layer          | Technology                      | Why                                            |
|----------------|---------------------------------|------------------------------------------------|
| Backend        | Python + FastAPI                | Fast async API framework with clean routing    |
| Database       | PostgreSQL                      | Persistent storage for users, chats, and tasks |
| ORM            | SQLAlchemy                      | Database abstraction and model management      |
| Authentication | JWT + Passlib                   | Secure stateless user authentication           |
| AI Agent       | Ollama (Llama 3)                | Local AI model with tool-calling support       |
| Frontend       | Vanilla HTML + CSS + JavaScript | Lightweight, no framework overhead             |
| Templates      | Jinja2                          | Simple server-side HTML rendering              |
| HTTP           | httpx (async)                   | Non-blocking API calls in FastAPI              |

**APIs used:**
- [OpenWeatherMap](https://openweathermap.org/api) — Weather
- [NewsAPI](https://newsapi.org) — News headlines
- [CoinGecko](https://www.coingecko.com/en/api) — Crypto prices (free, no key needed)
- [GitHub REST API](https://docs.github.com/en/rest) — Public activity
- [Ollama](https://ollama.com) — Local LLM inference

---

## Project Structure

```
ai-dashboard/
├── main.py                  # FastAPI app — routes, tool functions, AI agent loop
├── database.py              # PostgreSQL configuration
├── models.py                # SQLAlchemy database models
├── auth.py                  # JWT authentication helpers
├── init_db.py               # Database initialization script
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── README.md                # This file
├── templates/
│   └── index.html           # Single-page dashboard HTML (Jinja2)
└── static/
    ├── css/
    │   └── style.css        # All styles — dark terminal aesthetic
    └── js/
        └── dashboard.js     # Widget loaders, clock, AI agent chat logic
```

---

## Setup & Run

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/ai-dashboard.git
cd ai-dashboard
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

Edit `.env` and fill in your values:

```env
DATABASE_URL=postgresql://username:password@localhost/ai_dashboard
SECRET_KEY=your_secret_key_here
OPENWEATHER_API_KEY=your_openweather_api_key
NEWS_API_KEY=your_newsapi_key
GITHUB_USERNAME=your_github_username
GITHUB_TOKEN=your_github_token        # optional, increases rate limit
OLLAMA_MODEL=llama3
```

**Where to get API keys (all free tiers available):**
- OpenWeatherMap: https://home.openweathermap.org/api_keys
- NewsAPI: https://newsapi.org/register
- GitHub PAT: https://github.com/settings/tokens (scope: `public_repo`)
- CoinGecko: No key needed ✓
- Ollama: https://ollama.com (runs locally, no key needed)

### 4. Create PostgreSQL database

```sql
CREATE DATABASE ai_dashboard;
```

### 5. Initialize database tables

```bash
python init_db.py
```

### 6. Start Ollama

```bash
ollama serve
```

Pull the model if not already downloaded:

```bash
ollama pull llama3
```

### 7. Run the application

```bash
uvicorn main:app --reload --port 8000
```

### 8. Open the dashboard

Visit [http://localhost:8000](http://localhost:8000)

---

## How the AI Agent Works

ARIA uses **Ollama's tool-calling (function calling)** feature in an agentic loop:

1. User sends a message (e.g. *"What's the weather in Tokyo?"*)
2. Ollama decides which tool(s) to call (`get_weather`, `get_news`, `get_crypto_price`, `get_github_activity`, `create_task`, `list_tasks`, `complete_task`)
3. The backend executes the tool — making a real HTTP request or database operation
4. The tool result is fed back to Ollama as a `tool` role message
5. Ollama synthesizes the data into a natural-language reply
6. The loop repeats up to 5 rounds if Ollama needs multiple tools

The conversation history is maintained on the frontend and sent with each request, giving ARIA full context of the conversation.

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
Instead of injecting raw API data into the prompt, Ollama decides which tool to call based on the user's intent. This is more robust and extensible — adding a new data source is as simple as adding a new tool definition and async function.

**4. Agentic loop (up to 5 rounds)**
A single round of tool use isn't always enough (e.g. comparing weather in two cities, or fetching GitHub data then reasoning about it). The loop lets ARIA chain multiple tool calls naturally within one conversation turn.

**5. PostgreSQL for persistence**
PostgreSQL provides reliable storage for user accounts, chat history, and todo tasks — ensuring data remains available across sessions and for multiple users.

**6. JWT authentication**
JWT tokens provide secure, stateless authentication without requiring server-side sessions, making the application scalable and straightforward to manage.

**7. Local AI using Ollama**
Running Llama 3 locally avoids external AI API costs and keeps the project self-contained while still providing intelligent conversational and tool-calling capabilities.

**8. CoinGecko for crypto**
No API key required for basic price queries — reduces setup friction significantly.

**9. Auto-refresh every 5 minutes**
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
10. **Rate limit handling** — Smarter retry logic, caching, and user-facing feedback when API limits are hit

---

## Notes

- The crypto widget uses CoinGecko's public API — no key needed, but it has rate limits (~30 req/min). If you see errors, wait a moment and refresh.
- NewsAPI free tier only allows queries on articles up to 1 month old and has a 100 requests/day limit.
- GitHub's unauthenticated API is limited to 60 requests/hour. Setting `GITHUB_TOKEN` raises this to 5,000/hour.
- PostgreSQL must be running before starting the application.
- Ollama must be running locally with the configured model downloaded before starting the application.
