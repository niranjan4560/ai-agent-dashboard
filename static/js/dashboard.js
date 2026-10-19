// static/js/dashboard.js
"use strict";

// ─── Security: HTML escape all untrusted strings ──────────────────────────────
function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function apiFetch(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function setHTML(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

function errorHTML(msg) {
  return `<div class="error-msg">⚠ ${esc(msg)}</div>`;
}

// Parse a JSON body even on error responses; fall back to a readable message.
async function readJSON(res) {
  try {
    return await res.json();
  } catch {
    return { error: res.ok ? "Unexpected response from server" : `Server error (HTTP ${res.status})` };
  }
}

// ─── Session / Auth ───────────────────────────────────────────────────────────

const Session = {
  get token()    { try { return localStorage.getItem("token"); } catch { return null; } },
  get username() { try { return localStorage.getItem("username"); } catch { return null; } },
  save(token, username) {
    try {
      localStorage.setItem("token", token);
      localStorage.setItem("username", username || "");
    } catch { /* storage blocked — session lasts until reload */ }
    window.dispatchEvent(new Event("aria:auth"));
  },
  clear() {
    try {
      localStorage.removeItem("token");
      localStorage.removeItem("username");
    } catch { /* ignore */ }
    window.dispatchEvent(new Event("aria:auth"));
  },
};

function updateAuthUI() {
  const signedIn = Boolean(Session.token);
  const nameEl = document.getElementById("account-name");
  nameEl.hidden = !signedIn;
  nameEl.textContent = signedIn ? `@${Session.username || "you"}` : "";
  document.getElementById("signin-btn").hidden  = signedIn;
  document.getElementById("signout-btn").hidden = !signedIn;
  document.querySelectorAll(".requires-auth").forEach(el => el.classList.toggle("locked", !signedIn));
}

let authMode = "login";

function setAuthMode(mode) {
  authMode = mode;
  document.querySelectorAll(".auth-tab").forEach(t => t.classList.toggle("active", t.dataset.mode === mode));
  const isReg = mode === "register";
  document.getElementById("auth-username-field").hidden = !isReg;
  document.getElementById("auth-title").textContent = isReg ? "Create your ARIA account" : "Sign in to ARIA";
  document.getElementById("auth-submit").textContent = isReg ? "Create account" : "Sign in";
  document.getElementById("auth-password").autocomplete = isReg ? "new-password" : "current-password";
  showAuthError("");
}

function showAuthError(msg) {
  const el = document.getElementById("auth-error");
  el.textContent = msg;
  el.hidden = !msg;
}

function openAuth(mode = "login", notice = "") {
  setAuthMode(mode);
  if (notice) showAuthError(notice);
  document.getElementById("auth-overlay").hidden = false;
  document.getElementById("auth-email").focus();
}

function closeAuth() {
  document.getElementById("auth-overlay").hidden = true;
}

// Called whenever an authenticated request comes back 401.
function handleExpiredSession(message) {
  Session.clear();
  openAuth("login", message || "Your session has expired. Please sign in again.");
}

async function submitAuth(e) {
  e.preventDefault();
  const username = document.getElementById("auth-username").value.trim();
  const email    = document.getElementById("auth-email").value.trim();
  const password = document.getElementById("auth-password").value;
  const submit   = document.getElementById("auth-submit");

  if (!email || !password)            return showAuthError("Email and password are required.");
  if (authMode === "register") {
    if (!/^[A-Za-z0-9_.-]{3,50}$/.test(username))
      return showAuthError("Username must be 3–50 letters, digits, '.', '_' or '-'.");
    if (password.length < 8)          return showAuthError("Password must be at least 8 characters.");
  }

  submit.disabled = true;
  showAuthError("");
  try {
    if (authMode === "register") {
      const res  = await fetch("/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password }),
      });
      const data = await readJSON(res);
      if (!res.ok || data.error) return showAuthError(data.error || "Registration failed.");
    }
    const res  = await fetch("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await readJSON(res);
    if (!res.ok || !data.token) return showAuthError(data.error || "Sign-in failed.");
    Session.save(data.token, data.username);
    document.getElementById("auth-password").value = "";
    closeAuth();
  } catch (err) {
    showAuthError(`Network error: ${err.message}`);
  } finally {
    submit.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("signin-btn").addEventListener("click", () => openAuth("login"));
  document.getElementById("signout-btn").addEventListener("click", () => Session.clear());
  document.getElementById("auth-close").addEventListener("click", closeAuth);
  document.getElementById("auth-overlay").addEventListener("click", e => {
    if (e.target.id === "auth-overlay") closeAuth();
  });
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeAuth(); });
  document.querySelectorAll(".auth-tab").forEach(t => t.addEventListener("click", () => setAuthMode(t.dataset.mode)));
  document.getElementById("auth-form").addEventListener("submit", submitAuth);
  document.querySelectorAll(".requires-auth").forEach(el => el.addEventListener("click", e => {
    if (!Session.token) { e.preventDefault(); e.stopPropagation(); openAuth("login", "Sign in to use ARIA chat and tasks."); }
  }, true));
  updateAuthUI();
});
window.addEventListener("aria:auth", updateAuthUI);

// Weather icon map (OpenWeatherMap icon codes → emoji)
function weatherEmoji(iconCode) {
  const map = {
    "01d":"☀️","01n":"🌙","02d":"⛅","02n":"⛅",
    "03d":"☁️","03n":"☁️","04d":"☁️","04n":"☁️",
    "09d":"🌧️","09n":"🌧️","10d":"🌦️","10n":"🌦️",
    "11d":"⛈️","11n":"⛈️","13d":"❄️","13n":"❄️",
    "50d":"🌫️","50n":"🌫️",
  };
  // iconCode comes from our own backend — safe, but whitelist anyway
  return map[iconCode] || "🌡️";
}

// ─── Live Clock ───────────────────────────────────────────────────────────────

function updateClock() {
  const now = new Date();
  const timeEl = document.getElementById("live-time");
  const dateEl = document.getElementById("live-date");
  if (timeEl) timeEl.textContent = now.toLocaleTimeString("en-IN", { hour12: false });
  if (dateEl) dateEl.textContent = now.toLocaleDateString("en-IN", {
    weekday: "long", year: "numeric", month: "long", day: "numeric"
  });
}
setInterval(updateClock, 1000);
updateClock();

// ─── Weather ──────────────────────────────────────────────────────────────────

async function loadWeather() {
  const city = document.getElementById("weather-city-input").value.trim() || "Kochi";
  setHTML("weather-body", `<div class="skeleton-block"></div>`);
  try {
    const d = await apiFetch(`/api/weather?city=${encodeURIComponent(city)}`);
    if (d.error) throw new Error(d.error);
    setHTML("weather-body", `
      <div class="weather-main">
        <div class="weather-icon">${weatherEmoji(d.icon)}</div>
        <div>
          <div class="weather-temp">${esc(String(d.temp))}<span class="weather-unit">°C</span></div>
          <div class="weather-city">${esc(d.city)}, ${esc(d.country)}</div>
          <div class="weather-desc">${esc(d.description)}</div>
        </div>
      </div>
      <div class="weather-stats">
        <div class="weather-stat">
          <div class="weather-stat-label">Feels Like</div>
          <div class="weather-stat-value">${esc(String(d.feels_like))}°C</div>
        </div>
        <div class="weather-stat">
          <div class="weather-stat-label">Humidity</div>
          <div class="weather-stat-value">${esc(String(d.humidity))}%</div>
        </div>
        <div class="weather-stat">
          <div class="weather-stat-label">Wind</div>
          <div class="weather-stat-value">${esc(String(d.wind_speed))} m/s</div>
        </div>
        <div class="weather-stat">
          <div class="weather-stat-label">Condition</div>
          <div class="weather-stat-value" style="font-size:11px">${esc(d.description)}</div>
        </div>
      </div>
    `);
  } catch (e) {
    setHTML("weather-body", errorHTML(e.message));
  }
}

// ─── Crypto ───────────────────────────────────────────────────────────────────

const CRYPTO_COINS = ["bitcoin", "ethereum", "solana", "ripple"];

async function loadCrypto() {
  setHTML("crypto-body", `<div class="skeleton-block"></div>`);
  try {
    const results = await Promise.all(
      CRYPTO_COINS.map(c => apiFetch(`/api/crypto?symbol=${c}`))
    );
    // One message instead of four when the whole service is down
    const errs = new Set(results.map(d => d.error));
    if (!errs.has(undefined) && errs.size === 1) throw new Error(results[0].error);
    const rows = results.map(d => {
      if (d.error) return errorHTML(d.error);
      const changeClass = d.change_24h >= 0 ? "positive" : "negative";
      const changeSign  = d.change_24h >= 0 ? "▲" : "▼";
      const price = d.price_usd >= 1
        ? d.price_usd.toLocaleString("en-US", { style: "currency", currency: "USD" })
        : `$${d.price_usd.toFixed(5)}`;
      return `
        <div class="crypto-row">
          <div class="crypto-name">${esc(d.symbol)}</div>
          <div>
            <div class="crypto-price">${esc(price)}</div>
            <div class="crypto-change ${changeClass}">${changeSign} ${Math.abs(d.change_24h).toFixed(2)}%</div>
          </div>
        </div>`;
    }).join("");
    setHTML("crypto-body", `<div class="crypto-list">${rows}</div>`);
  } catch (e) {
    setHTML("crypto-body", errorHTML(e.message));
  }
}

// ─── News ─────────────────────────────────────────────────────────────────────

async function loadNews() {
  const query = document.getElementById("news-query-input").value.trim() || "technology";
  setHTML("news-body", `<div class="skeleton-block"></div>`);
  try {
    const d = await apiFetch(`/api/news?query=${encodeURIComponent(query)}&count=7`);
    if (d.error) throw new Error(d.error);
    const items = d.articles.map(a => {
      // URL goes into href — validate it's http/https only
      const safeUrl = /^https?:\/\//.test(a.url) ? a.url : "#";
      return `
      <div class="news-item">
        <a class="news-title" href="${esc(safeUrl)}" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a>
        <div class="news-meta">
          <span class="news-source">${esc(a.source)}</span>
          <span>${esc(a.published)}</span>
        </div>
        ${a.description ? `<div class="news-desc">${esc(a.description)}</div>` : ""}
      </div>`;
    }).join("");
    setHTML("news-body", `<div class="news-list">${items}</div>`);
  } catch (e) {
    setHTML("news-body", errorHTML(e.message));
  }
}

// ─── GitHub ───────────────────────────────────────────────────────────────────

const TYPE_LABELS = {
  Push: "Push", PullRequest: "PR", Issues: "Issue",
  Fork: "Fork", Watch: "Star", Create: "Create",
  Delete: "Delete", Member: "Member", Release: "Release",
};

async function loadGitHub() {
  const username = document.getElementById("github-user-input").value.trim();
  setHTML("github-body", `<div class="skeleton-block"></div>`);
  try {
    const url = username
      ? `/api/github?username=${encodeURIComponent(username)}`
      : "/api/github";
    const d = await apiFetch(url);
    if (d.error) {
      if (d.error.includes("No GitHub username")) {
        setHTML("github-body", `<div class="github-no-user">Enter a GitHub username above or set GITHUB_USERNAME in your .env file.</div>`);
        return;
      }
      throw new Error(d.error);
    }
    const events = d.events.map(e => `
      <div class="github-event">
        <span class="github-event-badge">${esc(TYPE_LABELS[e.type] || e.type)}</span>
        <div>
          <div class="github-repo">${esc(e.repo)}</div>
          <div class="github-date">${esc(e.date)}</div>
        </div>
      </div>
    `).join("");
    setHTML("github-body", `
      <div style="margin-bottom:10px;font-size:12px;color:var(--text-dim)">
        Recent activity for <strong style="color:var(--accent2)">@${esc(d.username)}</strong>
      </div>
      <div class="github-list">${events}</div>
    `);
  } catch (e) {
    setHTML("github-body", errorHTML(e.message));
  }
}

// ─── AI Agent Chat ────────────────────────────────────────────────────────────

let chatHistory = [];

function chatReset() { chatHistory = []; }

function appendMessage(role, text) {
  const container = document.getElementById("agent-messages");
  const div = document.createElement("div");
  div.className = `msg msg--${role}`;

  const iconMap = { user: "◉", aria: "◈", system: "◈", thinking: "◈", error: "⚠" };

  // Use textContent for the message body — never innerHTML with user/AI text
  const iconSpan = document.createElement("span");
  iconSpan.className = "msg-icon";
  iconSpan.textContent = iconMap[role] || "◈";

  const p = document.createElement("p");
  p.textContent = text; // safe: no HTML injection possible

  div.appendChild(iconSpan);
  div.appendChild(p);
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return div;
}

async function sendMessage() {
  const input = document.getElementById("agent-input");
  const btn   = document.getElementById("send-btn");
  const text  = input.value.trim();
  if (!text) return;
  if (!Session.token) { openAuth("login", "Sign in to chat with ARIA."); return; }

  input.value = "";
  input.disabled = true;
  btn.disabled   = true;

  appendMessage("user", text);
  const thinkingEl = appendMessage("thinking", "ARIA is thinking…");

  try {
    const res = await fetch("/api/agent/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${Session.token}`
      },
      body: JSON.stringify({ message: text, history: chatHistory })
    });

    const data = await readJSON(res);
    thinkingEl.remove();

    if (res.status === 401) {
      appendMessage("error", data.error || "Please sign in again.");
      handleExpiredSession(data.error);
    } else if (data.error) {
    appendMessage("error", data.error);
    } else {
        appendMessage("aria", data.reply);
        if (data.todo_updated && window.loadTodos) {
              window.loadTodos();
        }
        chatHistory = data.messages || [];
    }
      // Trim to last 20 messages to avoid token overflow
      if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);
  } catch (e) {
    thinkingEl.remove();
    appendMessage("error", `Network error: ${e.message}`);
  } finally {
    input.disabled = false;
    btn.disabled   = false;
    input.focus();
  }
}

function quickPrompt(text) {
  document.getElementById("agent-input").value = text;
  sendMessage();
}

// ─── Key bindings ─────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("agent-input").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  document.getElementById("weather-city-input").addEventListener("keydown", e => {
    if (e.key === "Enter") loadWeather();
  });
  document.getElementById("news-query-input").addEventListener("keydown", e => {
    if (e.key === "Enter") loadNews();
  });
  document.getElementById("github-user-input").addEventListener("keydown", e => {
    if (e.key === "Enter") loadGitHub();
  });
});

// ─── Boot: load all widgets in parallel ──────────────────────────────────────

(async function init() {
  await Promise.allSettled([
    loadWeather(),
    loadCrypto(),
    loadNews(),
    loadGitHub(),
  ]);
})();

// ─── To-Do Widget ────────────────────────────────────────────────────────────

(function todoWidget() {
  let todos  = [];
  let filter = "all";   // "all" | "pending" | "done"

  // DOM refs
  const listEl    = document.getElementById("todo-list");
  const inputEl   = document.getElementById("todo-input");
  const priEl     = document.getElementById("todo-priority");
  const addBtn    = document.getElementById("todo-add-btn");
  const clearBtn  = document.getElementById("todo-clear-btn");
  const statsEl   = document.getElementById("todo-stats");
  const errorEl   = document.getElementById("todo-error");

  // Auth header — reads the same token your agent chat uses
  function authHdr() {
    return {
      "Content-Type":  "application/json",
      "Authorization": `Bearer ${Session.token}`,
    };
  }

  function showError(msg) {
    errorEl.textContent = msg ? `⚠ ${msg}` : "";
    errorEl.hidden = !msg;
  }

  // Shared request wrapper: surfaces errors and handles expired sessions.
  async function request(url, options = {}) {
    const res  = await fetch(url, { ...options, headers: authHdr() });
    const data = await readJSON(res);
    if (res.status === 401) {
      handleExpiredSession(data.error);
      throw new Error(data.error || "Please sign in again.");
    }
    if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`);
    showError("");
    return data;
  }

  // ── Load from server ──────────────────────────────────────────
  async function loadTodos() {
    if (!Session.token) { todos = []; render(); return; }
    try {
      const data = await request("/api/todos");
      if (Array.isArray(data)) { todos = data; render(); }
    } catch (e) { showError(e.message); }
  }
  window.loadTodos = loadTodos;

  // ── Render ────────────────────────────────────────────────────
  function render() {
    // Stats badge
    const pending = todos.filter(t => !t.done).length;
    statsEl.textContent = !Session.token ? "" : pending ? `${pending} left` : todos.length ? "all done ✓" : "";

    // Apply filter
    const visible = todos.filter(t => {
      if (filter === "pending") return !t.done;
      if (filter === "done")    return  t.done;
      return true;
    });

    listEl.innerHTML = "";

    if (visible.length === 0) {
      const li = document.createElement("li");
      li.className = "todo-empty";
      li.textContent = !Session.token       ? "Sign in to keep a personal task list."
                     : filter === "done"    ? "No completed tasks yet."
                     : filter === "pending" ? "Nothing pending — good work!"
                     : "No tasks yet — add one above.";
      listEl.appendChild(li);
      return;
    }

    // Sort: pending before done, then high → medium → low
    const pw = { high: 0, medium: 1, low: 2 };
    const sorted = [...visible].sort((a, b) => {
      if (a.done !== b.done) return a.done ? 1 : -1;
      return (pw[a.priority] ?? 1) - (pw[b.priority] ?? 1);
    });

    sorted.forEach(t => {
      const li  = document.createElement("li");
      li.className = "todo-item" + (t.done ? " done-item" : "");

      // Priority dot
      const dot = document.createElement("span");
      dot.className = `priority-dot ${esc(t.priority)}`;

      // Checkbox
      const chk = document.createElement("input");
      chk.type      = "checkbox";
      chk.className = "todo-check";
      chk.checked   = t.done;
      chk.addEventListener("change", () => toggleDone(t.id, chk.checked));

      // Text
      const txt = document.createElement("span");
      txt.className   = "todo-text";
      txt.textContent = t.text;   // textContent — safe, no XSS

      // Delete
      const del = document.createElement("button");
      del.className   = "todo-del";
      del.title       = "Delete";
      del.textContent = "×";
      del.addEventListener("click", () => deleteTodo(t.id));

      li.append(dot, chk, txt, del);
      listEl.appendChild(li);
    });
  }

  // ── Add ───────────────────────────────────────────────────────
  async function addTodo() {
    const text = inputEl.value.trim();
    if (!text) { inputEl.focus(); return; }
    addBtn.disabled = true;
    try {
      const data = await request("/api/todos", {
        method:  "POST",
        body:    JSON.stringify({ text, priority: priEl.value }),
      });
      if (data.id) {
        todos.push({ ...data, created_at: new Date().toISOString() });
        inputEl.value = "";
        priEl.value   = "medium";
        render();
        inputEl.focus();
      }
    } catch (e) { showError(e.message); }
    finally     { addBtn.disabled = false; }
  }

  // ── Toggle done ───────────────────────────────────────────────
  async function toggleDone(id, done) {
    try {
      const data = await request(`/api/todos/${id}`, {
        method:  "PATCH",
        body:    JSON.stringify({ done }),
      });
      if (data.id) {
        const idx = todos.findIndex(t => t.id === id);
        if (idx !== -1) todos[idx].done = data.done;
      }
    } catch (e) { showError(e.message); }
    render();   // re-sync the checkbox with the known state
  }

  // ── Delete ────────────────────────────────────────────────────
  async function deleteTodo(id) {
    try {
      await request(`/api/todos/${id}`, { method: "DELETE" });
      todos = todos.filter(t => t.id !== id);
      render();
    } catch (e) { showError(e.message); }
  }

  // ── Clear completed ───────────────────────────────────────────
  async function clearDone() {
    if (!todos.some(t => t.done)) return;
    try {
      await request("/api/todos/clear/done", { method: "DELETE" });
      todos = todos.filter(t => !t.done);
      render();
    } catch (e) { showError(e.message); }
  }

  // ── Events ────────────────────────────────────────────────────
  addBtn.addEventListener("click", addTodo);
  inputEl.addEventListener("keydown", e => { if (e.key === "Enter") addTodo(); });
  clearBtn.addEventListener("click", clearDone);

  document.querySelectorAll(".todo-filter").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".todo-filter").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      filter = btn.dataset.filter;
      render();
    });
  });

  // ── Boot — load now, and again whenever the user signs in/out ──
  window.addEventListener("aria:auth", () => {
    showError("");
    if (!Session.token) chatReset();
    loadTodos();
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadTodos);
  } else {
    loadTodos();
  }
})();


setInterval(() => {
  loadWeather();
  loadCrypto();
  loadNews();
  loadGitHub();
}, 5 * 60 * 1000);
