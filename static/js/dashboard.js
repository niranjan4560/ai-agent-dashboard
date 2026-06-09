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

  input.value = "";
  input.disabled = true;
  btn.disabled   = true;

  appendMessage("user", text);
  const thinkingEl = appendMessage("thinking", "ARIA is thinking…");

  try {
    const token = localStorage.getItem("token");

    const res = await fetch("/api/agent/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`
    },
    body: JSON.stringify({message: text,history: chatHistory})
  });

    const data = await res.json();
    console.log("Agent Response:", data);
    thinkingEl.remove();

    if (data.error) {
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

  // Auth header — reads the same token your agent chat uses
  function authHdr() {
    const token = localStorage.getItem("token");
    return {
      "Content-Type":  "application/json",
      "Authorization": `Bearer ${token}`,
    };
  }

  // ── Load from server ──────────────────────────────────────────
  async function loadTodos() {
    try {
      const res  = await fetch("/api/todos", { headers: authHdr() });
      const data = await res.json();
      if (Array.isArray(data)) { todos = data; render(); }
    } catch (e) { console.error("Todos load error", e); }
  }
  window.loadTodos = loadTodos;

  // ── Render ────────────────────────────────────────────────────
  function render() {
    // Stats badge
    const pending = todos.filter(t => !t.done).length;
    statsEl.textContent = pending ? `${pending} left` : "all done ✓";

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
      li.textContent = filter === "done"    ? "No completed tasks yet."
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
      const res  = await fetch("/api/todos", {
        method:  "POST",
        headers: authHdr(),
        body:    JSON.stringify({ text, priority: priEl.value }),
      });
      const data = await res.json();
      if (data.id) {
        todos.push({ ...data, created_at: new Date().toISOString() });
        inputEl.value = "";
        priEl.value   = "medium";
        render();
        inputEl.focus();
      }
    } catch (e) { console.error("Add todo error", e); }
    finally     { addBtn.disabled = false; }
  }

  // ── Toggle done ───────────────────────────────────────────────
  async function toggleDone(id, done) {
    try {
      const res  = await fetch(`/api/todos/${id}`, {
        method:  "PATCH",
        headers: authHdr(),
        body:    JSON.stringify({ done }),
      });
      const data = await res.json();
      if (data.id) {
        const idx = todos.findIndex(t => t.id === id);
        if (idx !== -1) todos[idx].done = data.done;
        render();
      }
    } catch (e) { console.error("Toggle todo error", e); }
  }

  // ── Delete ────────────────────────────────────────────────────
  async function deleteTodo(id) {
    try {
      await fetch(`/api/todos/${id}`, { method: "DELETE", headers: authHdr() });
      todos = todos.filter(t => t.id !== id);
      render();
    } catch (e) { console.error("Delete todo error", e); }
  }

  // ── Clear completed ───────────────────────────────────────────
  async function clearDone() {
    if (!todos.some(t => t.done)) return;
    try {
      await fetch("/api/todos/clear/done", { method: "DELETE", headers: authHdr() });
      todos = todos.filter(t => !t.done);
      render();
    } catch (e) { console.error("Clear done error", e); }
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

  // ── Boot — wait for token then load ──────────────────────────
  function tryLoad() {
    if (localStorage.getItem("token")) {
      loadTodos();
    } else {
      // If the page has a login flow that sets the token after DOMContentLoaded,
      // retry briefly until it's available
      let attempts = 0;
      const poll = setInterval(() => {
        if (localStorage.getItem("token") || ++attempts > 30) {
          clearInterval(poll);
          if (localStorage.getItem("token")) loadTodos();
        }
      }, 300);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", tryLoad);
  } else {
    tryLoad();
  }
})();


setInterval(() => {
  loadWeather();
  loadCrypto();
  loadNews();
  loadGitHub();
}, 5 * 60 * 1000);
