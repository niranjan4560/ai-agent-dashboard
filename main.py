# main.py
import os
import json
import asyncio
import httpx
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

from auth import (
    hash_password,
    verify_password,
    create_token,
    decode_token,
)
from database import SessionLocal
from models import ChatHistory, User, Todo
from datetime import datetime
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from dotenv import load_dotenv

# ─── Bootstrap ────────────────────────────────────────────────────────────────

load_dotenv()

security = HTTPBearer()

app = FastAPI(title="AI Agent Dashboard")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ─── Environment Variables ────────────────────────────────────────────────────

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
NEWS_API_KEY        = os.getenv("NEWS_API_KEY", "")
GITHUB_USERNAME     = os.getenv("GITHUB_USERNAME", "")
GITHUB_TOKEN        = os.getenv("GITHUB_TOKEN", "")
GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL        = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Gemini client created lazily — missing key does not crash the app at startup.
def _get_gemini_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in your .env file.")
    return genai.Client(api_key=GEMINI_API_KEY)

# ─── Gemini call with retry ───────────────────────────────────────────────────
# Retries on 503 (overloaded) and 429 (quota/rate-limit).
# Raises immediately on all other errors (400 bad request, 401 invalid key, etc.)

_RETRYABLE_CODES = {429, 500, 503}
_MAX_RETRIES     = 3
_RETRY_DELAYS    = [2, 5, 10]   # seconds between each attempt


async def _gemini_generate(
    client: genai.Client,
    contents: list,
    config: types.GenerateContentConfig,
) -> object:
    """
    Call Gemini with automatic retry on transient errors (503 overloaded, 429 quota).
    Raises a clean ValueError with a user-friendly message for all other failures.
    """
    last_exc = None

    for attempt in range(_MAX_RETRIES):
        try:
            return await client.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )

        # ── Retryable: server overload (503) or rate-limit (429) ─────────────
        except genai_errors.ServerError as exc:
            last_exc = exc
            if exc.code in _RETRYABLE_CODES and attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(_RETRY_DELAYS[attempt])
                continue
            # Non-retryable server error (e.g. 500 that keeps failing)
            raise ValueError(
                f"Gemini server error ({exc.code}): {exc.message or 'Unknown server error'}. "
                "Please try again in a moment."
            ) from exc

        except genai_errors.ClientError as exc:
            # 429 is technically a ClientError in some SDK versions
            if exc.code == 429 and attempt < _MAX_RETRIES - 1:
                last_exc = exc
                await asyncio.sleep(_RETRY_DELAYS[attempt])
                continue
            # 400 bad request, 401 invalid key, 403 permission denied — don't retry
            _CLIENT_MESSAGES = {
                400: "Bad request sent to Gemini. Please rephrase your message.",
                401: "Invalid Gemini API key. Check GEMINI_API_KEY in your .env file.",
                403: "Gemini API access denied. Your API key may not have permission for this model.",
                404: "Gemini model not found. Check the GEMINI_MODEL value in your .env file.",
                429: "Gemini quota exceeded. You've hit your API rate limit — please wait and retry.",
            }
            msg = _CLIENT_MESSAGES.get(
                exc.code,
                f"Gemini request error ({exc.code}): {exc.message or 'Unknown error'}."
            )
            raise ValueError(msg) from exc

        # ── Anything else (network error, SDK bug, etc.) ──────────────────────
        except Exception as exc:
            raise ValueError(
                f"Unexpected error calling Gemini: {type(exc).__name__}: {exc}"
            ) from exc

    # All retries exhausted
    raise ValueError(
        f"Gemini is temporarily unavailable after {_MAX_RETRIES} attempts "
        f"(last error: {last_exc}). Please try again in a minute."
    )

# ─── DB helpers ───────────────────────────────────────────────────────────────

def save_chat(user_id: int, user_message: str, ai_response: str) -> None:
    db = SessionLocal()
    try:
        db.add(ChatHistory(
            user_id=user_id,
            user_message=user_message,
            ai_response=ai_response,
        ))
        db.commit()
    finally:
        db.close()


def add_todo(user_id: int, text: str, priority: str = "medium") -> bool:
    db = SessionLocal()
    try:
        db.add(Todo(user_id=user_id, text=text, priority=priority))
        db.commit()
        return True
    finally:
        db.close()


def get_user_todos(user_id: int) -> list:
    db = SessionLocal()
    try:
        return (
            db.query(Todo)
            .filter(Todo.user_id == user_id)
            .order_by(Todo.created_at.asc())
            .all()
        )
    finally:
        db.close()


def complete_todo(user_id: int, task_name: str) -> bool:
    db = SessionLocal()
    try:
        todo = (
            db.query(Todo)
            .filter(
                Todo.user_id == user_id,
                Todo.text.ilike(f"%{task_name}%"),
                Todo.done == False,
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

# ─── External API Tool Functions ──────────────────────────────────────────────

async def get_weather(city: str = "Kochi") -> dict:
    """Fetch live weather from OpenWeatherMap."""
    if not OPENWEATHER_API_KEY:
        return {"error": "OPENWEATHER_API_KEY not set"}
    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url)
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
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url)
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
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url)
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
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, headers=headers)
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

TOOL_MAP = {
    "get_weather":         get_weather,
    "get_news":            get_news,
    "get_crypto_price":    get_crypto_price,
    "get_github_activity": get_github_activity,
}

GEMINI_TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_weather",
                description=(
                    "Get current real-time weather for any city. "
                    "Returns temperature, feels-like temperature, humidity, wind speed, "
                    "and sky conditions."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "city": types.Schema(
                            type="STRING",
                            description="City name, e.g. 'Kochi', 'Mumbai', 'London', 'New York'",
                        ),
                    },
                    required=["city"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_news",
                description=(
                    "Fetch the latest news articles for any topic or keyword. "
                    "Use this whenever the user asks about news, headlines, or recent events."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="Topic to search, e.g. 'AI', 'cybersecurity', 'Python'",
                        ),
                        "count": types.Schema(
                            type="INTEGER",
                            description="Number of articles to return (1–10). Default 5.",
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_crypto_price",
                description=(
                    "Get the live price and 24-hour change for any cryptocurrency. "
                    "Use CoinGecko names: 'bitcoin', 'ethereum', 'solana', 'ripple', etc."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "symbol": types.Schema(
                            type="STRING",
                            description="Coin name, e.g. 'bitcoin', 'ethereum', 'solana'",
                        ),
                    },
                    required=["symbol"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_github_activity",
                description=(
                    "Get recent public GitHub activity (pushes, PRs, stars, forks) for a user. "
                    "Omit username to use the dashboard's default configured user."
                ),
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "username": types.Schema(
                            type="STRING",
                            description="GitHub username, e.g. 'torvalds'. Optional.",
                        ),
                    },
                    required=[],
                ),
            ),
        ]
    )
]

SYSTEM_INSTRUCTION = (
    "You are ARIA, an intelligent AI assistant embedded in a personal IT dashboard. "
    "You have access to real-time tools: get_weather, get_news, get_crypto_price, "
    "and get_github_activity. "
    "ALWAYS call the appropriate tool when the user asks about weather, news, "
    "cryptocurrency prices, or GitHub activity — never guess or make up data. "
    "After receiving tool results, summarise them clearly and concisely for the user. "
    "For questions unrelated to your tools, answer from your own knowledge."
)

# ─── Tool result formatter ────────────────────────────────────────────────────

def _format_tool_result(name: str, result: dict) -> str:
    """Convert a raw tool result dict into a clean readable string for the LLM."""
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

    return json.dumps(result)

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
        if db.query(User).filter(User.email == req.email).first():
            return {"error": "Email already exists"}
        db.add(User(
            username=req.username,
            email=req.email,
            password_hash=hash_password(req.password),
        ))
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

# ─── To-Do REST API ───────────────────────────────────────────────────────────

class TodoCreate(BaseModel):
    text:     str
    priority: str = "medium"


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
            {"id": t.id, "text": t.text, "priority": t.priority,
             "done": t.done, "created_at": t.created_at}
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
            user_id=payload["user_id"],
            text=req.text.strip()[:500],
            priority=priority,
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
        if req.priority is not None and req.priority in ("low", "medium", "high"):
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


@app.post("/api/agent/chat")
async def agent_chat(
    req: ChatRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    # Auth runs first — before any business logic
    payload = decode_token(credentials.credentials)
    if not payload:
        return JSONResponse({"error": "Invalid or expired token"}, status_code=401)
    user_id = payload["user_id"]

    msg       = req.message.strip()
    msg_lower = msg.lower()

    # ── Shortcut: Add Todo ────────────────────────────────────────────────────
    if msg_lower.startswith("add "):
        task_text = msg[4:].strip()
        if task_text:
            add_todo(user_id, task_text)
            reply = f"✅ Task added: {task_text}"
            save_chat(user_id, msg, reply)
            return {"reply": reply, "todo_updated": True, "messages": []}
        return {"reply": "Please specify a task name after 'add'.", "messages": []}

    # ── Shortcut: Complete Todo ───────────────────────────────────────────────
    if msg_lower.startswith("complete "):
        task_text = msg[len("complete "):].strip()
        success   = complete_todo(user_id, task_text)
        reply     = (
            f"✅ Task marked as completed: {task_text}"
            if success
            else f"❌ Task not found: {task_text}"
        )
        save_chat(user_id, msg, reply)
        return {"reply": reply, "todo_updated": True, "messages": []}

    # ── Shortcut: List Todos ──────────────────────────────────────────────────
    if "show my tasks" in msg_lower or "list tasks" in msg_lower or "list my tasks" in msg_lower:
        todos = get_user_todos(user_id)
        if not todos:
            reply = "📋 You have no tasks yet. Say 'add <task name>' to create one."
        else:
            lines = ["📋 Your Tasks:\n"]
            for t in todos:
                status = "✅" if t.done else "⬜"
                lines.append(f"{status} [{t.priority}] {t.text}")
            reply = "\n".join(lines)
        save_chat(user_id, msg, reply)
        return {"reply": reply, "messages": []}

    # ── Gemini agentic tool-calling loop ──────────────────────────────────────
    try:
        gemini_client = _get_gemini_client()
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    # Build conversation history as typed Gemini Content objects
    contents: list[types.Content] = []
    for turn in (req.history or [])[-20:]:
        role = turn.get("role", "user")
        text = turn.get("content", "")
        if role == "assistant":
            role = "model"
        if role in ("user", "model") and text:
            contents.append(types.Content(
                role=role,
                parts=[types.Part(text=text)],
            ))

    contents.append(types.Content(
        role="user",
        parts=[types.Part(text=msg)],
    ))

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=GEMINI_TOOLS,
        max_output_tokens=1024,
        temperature=0.4,
    )

    # Agentic loop — up to 5 rounds of tool calls
    for _round in range(5):

        # ── Call Gemini with retry on transient errors ────────────────────────
        try:
            response = await _gemini_generate(gemini_client, contents, config)
        except ValueError as exc:
            # Clean user-facing error — no stack trace exposed
            error_msg = str(exc)
            save_chat(user_id, msg, f"[Error] {error_msg}")
            return JSONResponse({"error": error_msg}, status_code=503)

        # Guard: empty or malformed response
        if not response.candidates:
            error_msg = "Gemini returned an empty response. Please try again."
            save_chat(user_id, msg, f"[Error] {error_msg}")
            return JSONResponse({"error": error_msg}, status_code=503)

        candidate = response.candidates[0]

        # Guard: safety block or other non-STOP finish reason
        finish_reason = str(candidate.finish_reason)
        if finish_reason not in ("STOP", "FinishReason.STOP", "1"):
            if "SAFETY" in finish_reason:
                error_msg = "Your message was blocked by Gemini's safety filters. Please rephrase."
            elif "MAX_TOKENS" in finish_reason:
                error_msg = "Response was too long. Please ask a more specific question."
            else:
                error_msg = f"Gemini stopped unexpectedly ({finish_reason}). Please try again."
            save_chat(user_id, msg, f"[Error] {error_msg}")
            return JSONResponse({"error": error_msg}, status_code=422)

        # Guard: content parts may be None on some finish reasons
        all_parts = candidate.content.parts if candidate.content else []
        if not all_parts:
            error_msg = "Gemini returned no content. Please try again."
            save_chat(user_id, msg, f"[Error] {error_msg}")
            return JSONResponse({"error": error_msg}, status_code=503)

        fn_call_parts = [p for p in all_parts if p.function_call is not None]
        text_parts    = [p for p in all_parts if p.text]

        # ── No function calls → final answer ─────────────────────────────────
        if not fn_call_parts:
            final_reply = "\n".join(p.text for p in text_parts).strip()
            if not final_reply:
                final_reply = "I was unable to generate a response. Please try again."
            save_chat(user_id, msg, final_reply)
            updated_history = [
                {
                    "role": c.role if c.role != "model" else "assistant",
                    "content": p.text,
                }
                for c in contents
                for p in c.parts
                if p.text
            ] + [{"role": "assistant", "content": final_reply}]
            return {"reply": final_reply, "messages": updated_history}

        # ── Function calls requested ──────────────────────────────────────────
        contents.append(types.Content(role="model", parts=all_parts))

        function_response_parts = []
        for part in fn_call_parts:
            fn_name = part.function_call.name
            fn_args = dict(part.function_call.args)

            executor = TOOL_MAP.get(fn_name)
            if executor:
                try:
                    raw_result = await executor(**fn_args)
                except Exception as exc:
                    raw_result = {"error": str(exc)}
            else:
                raw_result = {"error": f"Unknown tool: {fn_name}"}

            readable = _format_tool_result(fn_name, raw_result)
            function_response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fn_name,
                        response={"result": readable},
                    )
                )
            )

        contents.append(types.Content(role="user", parts=function_response_parts))
        # Loop back — Gemini reads the results and produces its final reply

    # 5 rounds exhausted without a text reply
    fallback = "I reached the tool-call limit. Please try a simpler question."
    save_chat(user_id, msg, fallback)
    return {"reply": fallback, "messages": []}