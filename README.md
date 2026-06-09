# ARIA — AI Agent Dashboard

A personal AI-powered dashboard for IT professionals. ARIA (Adaptive Real-time Intelligence Agent) keeps you informed with live data and lets you interact with an AI agent that calls real APIs to answer your questions.

---

## What I Built

A single-page dashboard with:

- **Weather Widget** — Live weather for any city via OpenWeatherMap (temperature, humidity, wind, feels-like)
- **Crypto Tracker** — Real-time prices and 24h change for Bitcoin, Ethereum, Solana, and XRP via CoinGecko (no API key required)
- **News Feed** — Latest articles on any topic via NewsAPI, with source and publish date
- **GitHub Activity** — Recent public events (pushes, PRs, stars) for any GitHub user
- **ARIA Agent Chat** — A conversational AI agent powered by Claude (claude-opus-4-5) with tool-calling. It can intelligently fetch weather, news, crypto prices, and GitHub activity in real time based on your natural-language questions

All data is live — no hardcoded or dummy values anywhere.

---

## Tech Stack

| Layer     | Technology                        | Why                                       |
|-----------|-----------------------------------|-------------------------------------------|
| Backend   | Python + FastAPI                  | Fast async API, clean routing, easy setup |
| AI Agent  | Anthropic Claude API (claude-opus-4-5) | Tool-calling support, conversational     |
| Frontend  | Vanilla HTML + CSS + JavaScript   | No framework overhead, full control       |
| Templates | Jinja2                            | Simple server-side HTML rendering         |
| HTTP      | httpx (async)                     | Non-blocking API calls in FastAPI         |

**APIs used:**
- [OpenWeatherMap](https://openweathermap.org/api) — Weather
- [NewsAPI](https://newsapi.org) — News headlines
- [CoinGecko](https://www.coingecko.com/en/api) — Crypto prices (free, no key needed)
- [GitHub REST API](https://docs.github.com/en/rest) — Public activity
- [Anthropic API](https://www.anthropic.com) — AI agent with tool use

---

## Project Structure

```
ai-dashboard/
├── main.py                  # FastAPI app — routes, tool functions, AI agent loop
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

Edit `.env` and fill in your API keys:

```env
ANTHROPIC_API_KEY=your_key_here
OPENWEATHER_API_KEY=your_key_here
NEWS_API_KEY=your_key_here
GITHUB_USERNAME=your_github_username
GITHUB_TOKEN=your_github_pat_here   # optional, increases rate limit
```

**Where to get API keys (all free tiers available):**
- Anthropic: https://console.anthropic.com
- OpenWeatherMap: https://home.openweathermap.org/api_keys
- NewsAPI: https://newsapi.org/register
- GitHub PAT: https://github.com/settings/tokens (scope: `public_repo`)
- CoinGecko: No key needed ✓

### 4. Load environment variables and start the server

```bash
# Linux / macOS
export $(cat .env | xargs)
uvicorn main:app --reload --port 8000

# Windows (PowerShell)
Get-Content .env | ForEach-Object { $k,$v = $_ -split '=',2; [System.Environment]::SetEnvironmentVariable($k,$v) }
uvicorn main:app --reload --port 8000
```

### 5. Open the dashboard

Visit [http://localhost:8000](http://localhost:8000)

---

## How the AI Agent Works

The ARIA agent uses **Claude's tool-calling (function calling)** feature in an agentic loop:

1. User sends a message (e.g. *"What's the weather in Tokyo?"*)
2. Claude decides which tool(s) to call (`get_weather`, `get_news`, `get_crypto_price`, `get_github_activity`)
3. The backend executes the tool — making a real HTTP request to the relevant API
4. The tool result is sent back to Claude as a `tool_result` message
5. Claude synthesizes the data into a natural-language reply
6. The loop repeats up to 5 rounds if Claude needs multiple tools

The conversation history is maintained on the frontend and sent with each request, giving ARIA full context of the conversation.

**Example prompts to try:**
- *"What's the current Ethereum price and how is Bitcoin doing?"*
- *"Show me the latest news on cybersecurity"*
- *"Weather in Kochi and Mumbai — which is hotter?"*
- *"What has @torvalds been doing on GitHub?"*

---

## Key Design Decisions

**1. Python + FastAPI over Node.js/React**
My strongest language is Python. FastAPI gives async support (important for parallel API calls) with minimal boilerplate, and Jinja2 handles templating cleanly.

**2. Vanilla JS frontend**
No build step, no framework complexity. The dashboard is a single page with straightforward fetch calls — vanilla JS is more than sufficient and keeps the project easy to run.

**3. Tool-calling over prompt-stuffing**
Instead of injecting raw API data into the prompt, Claude decides *which* tool to call based on the user's intent. This is more robust and extensible — adding a new data source is as simple as adding a new tool definition and async function.

**4. Agentic loop (up to 5 rounds)**
A single round of tool use isn't always enough (e.g. comparing weather in two cities requires two calls). The loop lets ARIA chain multiple tool calls naturally.

**5. CoinGecko for crypto**
No API key required for basic price queries — reduces setup friction significantly.

**6. Auto-refresh every 5 minutes**
All widgets silently refresh in the background so data stays current without user interaction.

---

## What I'd Improve with More Time

1. **WebSocket live updates** — Push real-time price changes via WebSockets instead of polling every 5 minutes
2. **Task/calendar integration** — Google Calendar or Todoist via OAuth so ARIA can manage your schedule
3. **System monitoring widget** — CPU, RAM, disk usage using `psutil` — especially relevant for IT professionals
4. **Persistent chat history** — Store conversations in SQLite or PostgreSQL so ARIA remembers context across sessions
5. **User preferences** — Let users save their default city, GitHub username, and favorite crypto coins
6. **Stock market widget** — Add stock price tracking via Alpha Vantage or Yahoo Finance
7. **Email summaries** — Gmail integration to summarize unread emails via IMAP
8. **ARIA voice input** — Browser Web Speech API for hands-free queries
9. **Dashboard layout editor** — Drag-and-drop widget arrangement saved to localStorage
10. **Rate limit handling** — Smarter retry logic and user-facing feedback when API limits are hit

---

## Notes

- The crypto widget uses CoinGecko's public API — no key needed, but it has rate limits (~30 req/min). If you see errors, wait a moment and refresh.
- NewsAPI free tier only allows queries on articles up to 1 month old and has a 100 requests/day limit.
- GitHub's unauthenticated API is limited to 60 requests/hour. Setting `GITHUB_TOKEN` raises this to 5,000/hour.
