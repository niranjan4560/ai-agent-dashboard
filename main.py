# main.py
import os
import json
import httpx
from auth import (
    hash_password,
    verify_password,
    create_token,
    decode_token
)

from database import SessionLocal
from models import ChatHistory, User, Todo
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends
from pydantic import BaseModel
from dotenv import load_dotenv
from ollama import AsyncClient

security = HTTPBearer()

# ─── DB helper ───────────────────────────────────────────────────────────────

def save_chat(user_id: int, user_message: str, ai_response: str):
    db = SessionLocal()
    try:
        chat = ChatHistory(
            user_id=user_id,
            user_message=user_message,
            ai_response=ai_response,
        )
        db.add(chat)
        db.commit()
    finally:
        db.close()

def add_todo(user_id, text):

    db = SessionLocal()

    try:

        todo = Todo(
            user_id=user_id,
            text=text,
            priority="medium"
        )

        db.add(todo)
        db.commit()

        return True

    finally:
        db.close()


def get_user_todos(user_id):

    db = SessionLocal()

    try:

        return (
            db.query(Todo)
            .filter(
                Todo.user_id == user_id
            )
            .all()
        )

    finally:
        db.close()


def complete_todo(user_id, task_name):

    db = SessionLocal()

    try:

        todo = (
            db.query(Todo)
            .filter(
                Todo.user_id == user_id,
                Todo.text.ilike(f"%{task_name}%"),
                Todo.done == False
            )
            .first()
        )

        if not todo:
               return False

        todo.done = True

        db.commit()

        return True

    finally:
        db.close()

# ─── Bootstrap ───────────────────────────────────────────────────────────────

load_dotenv()

app = FastAPI(title="AI Agent Dashboard")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ─── Environment Variables ───────────────────────────────────────────────────
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
NEWS_API_KEY        = os.getenv("NEWS_API_KEY", "")
GITHUB_USERNAME     = os.getenv("GITHUB_USERNAME", "")
GITHUB_TOKEN        = os.getenv("GITHUB_TOKEN", "")
OLLAMA_MODEL        = os.getenv("OLLAMA_MODEL", "llama3.2")   # override via .env

# ─── Tool Functions ──────────────────────────────────────────────────────────
# These are called by the agent after Ollama decides to use them.
# They are also called directly by the widget API endpoints.

async def get_weather(city: str = "Kochi") -> dict:
    """Fetch live weather from OpenWeatherMap."""
    if not OPENWEATHER_API_KEY:
        return {"error": "OPENWEATHER_API_KEY not set"}
    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            if r.status_code == 404:
                return {"error": f"City '{city}' not found"}
            if r.status_code != 200:
                return {"error": f"Weather API error {r.status_code}"}
            d = r.json()
            return {
                "city":        d["name"],
                "country":     d["sys"]["country"],
                "temp":        round(d["main"]["temp"], 1),
                "feels_like":  round(d["main"]["feels_like"], 1),
                "humidity":    d["main"]["humidity"],
                "description": d["weather"][0]["description"].title(),
                "icon":        d["weather"][0]["icon"],
                "wind_speed":  d["wind"]["speed"],
            }
    except httpx.TimeoutException:
        return {"error": "Weather API timed out"}


async def get_news(query: str = "technology", count: int = 5) -> dict:
    """Fetch top headlines from NewsAPI."""
    if not NEWS_API_KEY:
        return {"error": "NEWS_API_KEY not set"}
    count = max(1, min(count, 10))
    url = (
        "https://newsapi.org/v2/everything"
        f"?q={query}&sortBy=publishedAt&pageSize={count}"
        f"&apiKey={NEWS_API_KEY}&language=en"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return {"error": f"News API error {r.status_code}"}
            articles = r.json().get("articles", [])
            return {
                "query": query,
                "articles": [
                    {
                        "title":       (a.get("title") or "")[:200],
                        "source":      a["source"].get("name", "Unknown"),
                        "url":         a.get("url", ""),
                        "published":   (a.get("publishedAt") or "")[:10],
                        "description": (a.get("description") or "")[:120],
                    }
                    for a in articles
                ],
            }
    except httpx.TimeoutException:
        return {"error": "News API timed out"}


async def get_crypto_price(symbol: str = "bitcoin") -> dict:
    """Fetch live crypto price from CoinGecko (no API key needed)."""
    ids = symbol.lower().strip().replace(" ", "-")[:50]
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return {"error": f"CoinGecko API error {r.status_code}"}
            data = r.json()
            if ids not in data:
                return {"error": f"Symbol '{symbol}' not found. Try 'bitcoin', 'ethereum', 'solana'."}
            coin = data[ids]
            return {
                "symbol":     ids,
                "price_usd":  coin["usd"],
                "change_24h": round(coin.get("usd_24h_change", 0), 2),
                "market_cap": coin.get("usd_market_cap", 0),
            }
    except httpx.TimeoutException:
        return {"error": "CoinGecko API timed out"}


async def get_github_activity(username: str = None) -> dict:
    """Fetch recent public GitHub events for a user."""
    user = (username or GITHUB_USERNAME or "").strip()
    if not user:
        return {"error": "No GitHub username provided"}
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    url = f"https://api.github.com/users/{user}/events/public?per_page=10"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 404:
                return {"error": f"GitHub user '{user}' not found"}
            if r.status_code != 200:
                return {"error": f"GitHub API error {r.status_code}"}
            events = r.json()
            return {
                "username": user,
                "events": [
                    {
                        "type": e["type"].replace("Event", ""),
                        "repo": e["repo"]["name"],
                        "date": e["created_at"][:10],
                    }
                    for e in events[:8]
                ],
            }
    except httpx.TimeoutException:
        return {"error": "GitHub API timed out"}


# ─── Tool registry ────────────────────────────────────────────────────────────
# TOOL_MAP: name → async callable used by the agent executor loop
TOOL_MAP = {
    "get_weather":         get_weather,
    "get_news":            get_news,
    "get_crypto_price":    get_crypto_price,
    "get_github_activity": get_github_activity,
}

# TOOLS: Ollama tool definitions (OpenAI function-calling format)
# Ollama reads these to decide WHICH tool to call and with WHAT arguments.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Get current real-time weather for any city. "
                "Returns temperature, feels-like, humidity, wind speed, and conditions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name, e.g. 'Kochi', 'Mumbai', 'London', 'New York'",
                    }
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": (
                "Fetch the latest news articles for any topic or keyword. "
                "Use this whenever the user asks about news, headlines, or recent events on any subject."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Topic to search, e.g. 'artificial intelligence', 'cybersecurity', 'Python'",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of articles to return (1–10). Default 5.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_crypto_price",
            "description": (
                "Get the live price and 24-hour percentage change for any cryptocurrency. "
                "Use full CoinGecko names: 'bitcoin', 'ethereum', 'solana', 'ripple', etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Coin name, e.g. 'bitcoin', 'ethereum', 'solana', 'ripple'",
                    }
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_github_activity",
            "description": (
                "Get recent public GitHub activity (pushes, pull requests, stars, forks) for a user. "
                "If the user does not name someone, use the default configured username."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "GitHub username, e.g. 'torvalds'. Omit to use the default.",
                    }
                },
                "required": [],
            },
        },
    },
]

# ─── Widget API routes ────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/weather")
async def weather_endpoint(city: str = "Kochi"):
    return JSONResponse(await get_weather(city.strip()[:100]))


@app.get("/api/news")
async def news_endpoint(query: str = "technology", count: int = 5):
    return JSONResponse(await get_news(query.strip()[:100], max(1, min(count, 10))))


@app.get("/api/crypto")
async def crypto_endpoint(symbol: str = "bitcoin"):
    return JSONResponse(await get_crypto_price(symbol.strip()[:50]))


@app.get("/api/github")
async def github_endpoint(username: str = ""):
    return JSONResponse(await get_github_activity(username.strip()[:39] or None))


@app.get("/api/time")
async def time_endpoint():
    now = datetime.now()
    return {
        "iso":  now.isoformat(),
        "date": now.strftime("%A, %B %d %Y"),
        "time": now.strftime("%H:%M:%S"),
    }


# ─── Auth routes ──────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/register")
async def register(req: RegisterRequest):
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == req.email).first()
        if existing:
            return {"error": "Email already exists"}
        user = User(
            username=req.username,
            email=req.email,
            password_hash=hash_password(req.password),
        )
        db.add(user)
        db.commit()
        return {"message": "Registration successful"}
    finally:
        db.close()


@app.post("/login")
async def login(req: LoginRequest):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == req.email).first()
        if not user or not verify_password(req.password, user.password_hash):
            return {"error": "Invalid credentials"}
        token = create_token({"user_id": user.id, "email": user.email})
        return {"token": token}
    finally:
        db.close()


@app.get("/my-chats")
async def my_chats(user_id: int):
    db = SessionLocal()
    try:
        chats = (
            db.query(ChatHistory)
            .filter(ChatHistory.user_id == user_id)
            .order_by(ChatHistory.created_at.desc())
            .all()
        )
        return [
            {
                "id":           chat.id,
                "user_message": chat.user_message,
                "ai_response":  chat.ai_response,
                "created_at":   chat.created_at,
            }
            for chat in chats
        ]
    finally:
        db.close()


# ─── To-Do API ───────────────────────────────────────────────────────────────

class TodoCreate(BaseModel):
    text:     str
    priority: str = "medium"   # low | medium | high

class TodoUpdate(BaseModel):
    text:     str | None = None
    priority: str | None = None
    done:     bool | None = None


@app.get("/api/todos")
async def get_todos(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if not payload:
        return JSONResponse({"error": "Unauthorised"}, status_code=401)
    db = SessionLocal()
    try:
        todos = (
            db.query(Todo)
            .filter(Todo.user_id == payload["user_id"])
            .order_by(Todo.created_at.asc())
            .all()
        )
        return [
            {
                "id":         t.id,
                "text":       t.text,
                "priority":   t.priority,
                "done":       t.done,
                "created_at": t.created_at,
            }
            for t in todos
        ]
    finally:
        db.close()


@app.post("/api/todos")
async def create_todo(
    req: TodoCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    payload = decode_token(credentials.credentials)
    if not payload:
        return JSONResponse({"error": "Unauthorised"}, status_code=401)
    if not req.text.strip():
        return JSONResponse({"error": "Task text cannot be empty"}, status_code=400)
    priority = req.priority if req.priority in ("low", "medium", "high") else "medium"
    db = SessionLocal()
    try:
        todo = Todo(
            user_id  = payload["user_id"],
            text     = req.text.strip()[:500],
            priority = priority,
        )
        db.add(todo)
        db.commit()
        db.refresh(todo)
        return {"id": todo.id, "text": todo.text, "priority": todo.priority, "done": todo.done}
    finally:
        db.close()


@app.patch("/api/todos/{todo_id}")
async def update_todo(
    todo_id: int,
    req: TodoUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    payload = decode_token(credentials.credentials)
    if not payload:
        return JSONResponse({"error": "Unauthorised"}, status_code=401)
    db = SessionLocal()
    try:
        todo = db.query(Todo).filter(
            Todo.id == todo_id, Todo.user_id == payload["user_id"]
        ).first()
        if not todo:
            return JSONResponse({"error": "Task not found"}, status_code=404)
        if req.text     is not None: todo.text     = req.text.strip()[:500]
        if req.priority is not None and req.priority in ("low","medium","high"):
            todo.priority = req.priority
        if req.done     is not None: todo.done     = req.done
        db.commit()
        return {"id": todo.id, "text": todo.text, "priority": todo.priority, "done": todo.done}
    finally:
        db.close()


@app.delete("/api/todos/{todo_id}")
async def delete_todo(
    todo_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    payload = decode_token(credentials.credentials)
    if not payload:
        return JSONResponse({"error": "Unauthorised"}, status_code=401)
    db = SessionLocal()
    try:
        todo = db.query(Todo).filter(
            Todo.id == todo_id, Todo.user_id == payload["user_id"]
        ).first()
        if not todo:
            return JSONResponse({"error": "Task not found"}, status_code=404)
        db.delete(todo)
        db.commit()
        return {"deleted": todo_id}
    finally:
        db.close()


@app.delete("/api/todos/clear/done")
async def clear_done_todos(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if not payload:
        return JSONResponse({"error": "Unauthorised"}, status_code=401)
    db = SessionLocal()
    try:
        deleted = (
            db.query(Todo)
            .filter(Todo.user_id == payload["user_id"], Todo.done == True)
            .delete()
        )
        db.commit()
        return {"cleared": deleted}
    finally:
        db.close()


# ─── AI Agent Chat ────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    history: list = []


def _format_tool_result(name: str, result: dict) -> str:
    """
    Convert a raw tool result dict into a clean, readable string
    that the LLM can use to compose its reply.
    """
    if "error" in result:
        return f"Tool '{name}' returned an error: {result['error']}"

    if name == "get_weather":
        return (
            f"Weather in {result['city']}, {result['country']}: "
            f"{result['temp']}°C (feels like {result['feels_like']}°C), "
            f"{result['description']}, humidity {result['humidity']}%, "
            f"wind {result['wind_speed']} m/s."
        )

    if name == "get_news":
        articles = result.get("articles", [])
        if not articles:
            return f"No news articles found for '{result.get('query', '')}'"
        lines = [f"Top news for '{result['query']}':"]
        for i, a in enumerate(articles[:5], 1):
            lines.append(f"{i}. {a['title']} — {a['source']} ({a['published']})")
        return "\n".join(lines)

    if name == "get_crypto_price":
        sign = "+" if result["change_24h"] >= 0 else ""
        price = (
            f"${result['price_usd']:,.2f}"
            if result["price_usd"] >= 1
            else f"${result['price_usd']:.6f}"
        )
        return (
            f"{result['symbol'].title()} price: {price} "
            f"({sign}{result['change_24h']}% in 24h)."
        )

    if name == "get_github_activity":
        events = result.get("events", [])
        if not events:
            return f"No recent public activity found for @{result['username']}."
        lines = [f"Recent GitHub activity for @{result['username']}:"]
        for e in events[:5]:
            lines.append(f"• {e['type']} on {e['repo']} ({e['date']})")
        return "\n".join(lines)

    # Fallback: dump JSON
    return json.dumps(result)


@app.post("/api/agent/chat")
async def agent_chat(
    req: ChatRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    msg = req.message.lower()
    # ── Auth ──────────────────────────────────────────────────────────────────
    payload = decode_token(credentials.credentials)

    if not payload:
        return JSONResponse(
            {"error": "Invalid or expired token"},
            status_code=401
        )

    user_id = payload["user_id"]

    # Add Todo 
    if msg.startswith("add "):

        task_text = req.message[4:].strip()

        add_todo(user_id, task_text)

        return {
            "reply": f"✅ Task added: {task_text}",
            "todo_updated": True,
            "messages": []
        }

    # Complete Todo
    if msg.startswith("complete "):

        task_text = (req.message.replace("complete", "").replace("task", "").strip())

        success = complete_todo(user_id,task_text)

        if success:

            reply = f"✅ Task marked as completed: {task_text}"

        else:

           reply = f"❌ Task not found: {task_text}"

        save_chat(user_id,req.message,reply)

        return {
           "reply": reply,
           "messages": [],
           "todo_updated": True
       }

    # List Todos
    if "show my tasks" in msg or "list tasks" in msg:

        todos = get_user_todos(user_id)

        if not todos:
            return {
                "reply": "No tasks found.",
                "messages": []
            }

        reply = "📋 Your Tasks:\n\n"

        for todo in todos:
            status = "✅" if todo.done else "⬜"
            reply += f"{status} {todo.text}\n"

        return {
            "reply": reply,
            "messages": []
        }
    
    # ── Build initial message list ────────────────────────────────────────────
    system_msg = {
        "role": "system",
        "content": (
            "You are ARIA, an intelligent AI assistant embedded in a personal IT dashboard. "
            "You have access to real-time tools: get_weather, get_news, get_crypto_price, "
            "and get_github_activity. "
            "ALWAYS call the appropriate tool when the user asks about weather, news, "
            "cryptocurrency prices, or GitHub activity — never guess or make up data. "
            "After receiving tool results, summarise them clearly and concisely for the user. "
            "For questions unrelated to your tools, answer from your own knowledge."
        ),
    }

    # Cap history to last 20 messages to prevent token overflow
    history = (req.history or [])[-20:]
    messages = [system_msg] + history + [{"role": "user", "content": req.message}]

    client = AsyncClient()

    # ── Agentic tool-calling loop (up to 5 rounds) ────────────────────────────
    # Each round: send messages → Ollama may request tool calls → execute → repeat.
    # Loop exits when Ollama returns a plain text reply with no tool calls.
    for _round in range(5):

        response = await client.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            tools=TOOLS,          # tells Ollama which tools are available
        )

        assistant_msg = response.message  # ollama.Message object

        # Append the assistant turn to the conversation
        messages.append({
            "role":    "assistant",
            "content": assistant_msg.content or "",
        })

        # ── No tool calls → final answer ready ───────────────────────────────
        tool_calls = assistant_msg.tool_calls or []
        if not tool_calls:
            final_reply = (assistant_msg.content or "").strip()
            save_chat(user_id, req.message, final_reply)
            # Return updated history (strip system prompt before sending to client)
            return {
                "reply":    final_reply,
                "messages": messages[1:],   # exclude system message
            }

        # ── Execute every tool call Ollama requested ──────────────────────────
        for tc in tool_calls:
            tool_name = tc.function.name
            tool_args = dict(tc.function.arguments)   # already a dict from Ollama

            fn = TOOL_MAP.get(tool_name)
            if fn:
                try:
                    raw_result = await fn(**tool_args)
                except Exception as exc:
                    raw_result = {"error": str(exc)}
            else:
                raw_result = {"error": f"Unknown tool: {tool_name}"}

            # Format the result into a readable string for the LLM
            readable = _format_tool_result(tool_name, raw_result)

            # Feed the tool result back as a "tool" role message
            messages.append({
                "role":    "tool",
                "content": readable,
            })

    # If we hit 5 rounds without a final text reply, return what we have
    fallback = "I reached the tool-call limit for this query. Please try a simpler question."
    save_chat(user_id, req.message, fallback)
    return {"reply": fallback, "messages": messages[1:]}