const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};
async function api(path, opts) {
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || res.statusText), { status: res.status, data });
  return data;
}

// -------------------------------------------------------------- system state
const STATE_LABELS = { ready: "READY", thinking: "THINKING", searching: "SEARCHING", reading: "READING", executing: "EXECUTING", speaking: "SPEAKING", listening: "LISTENING", error: "ERROR" };
function setState(state) {
  const pill = $("#statusPill");
  pill.dataset.state = state;
  $("#statusLabel").textContent = STATE_LABELS[state] || state.toUpperCase();
}

// -------------------------------------------------------------- markdown
function escapeHtml(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
function renderMarkdown(raw) {
  const lines = escapeHtml(raw).split("\n");
  let html = ""; let inList = false;
  const inline = (s) => s.replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, "$1<em>$2</em>");
  for (const line of lines) {
    const bullet = line.match(/^\s*[-*]\s+(.*)/);
    if (bullet) { if (!inList) { html += "<ul>"; inList = true; } html += `<li>${inline(bullet[1])}</li>`; continue; }
    if (inList) { html += "</ul>"; inList = false; }
    if (line.trim() === "") { html += "<br>"; continue; }
    html += `<p>${inline(line)}</p>`;
  }
  if (inList) html += "</ul>";
  return html;
}

// --------------------------------------------------------- tool activity
const ACTIVITY_META = {
  web_search: { icon: "◎", label: "Web Search" },
  ingest_url: { icon: "▤", label: "Reading" },
  run_shell: { icon: "❯", label: "Shell" },
  device_action: { icon: "◈", label: "Device" },
  read_screen: { icon: "▣", label: "Screen" },
  list_recent_emails: { icon: "✉", label: "Mail" },
  read_email: { icon: "✉", label: "Mail" },
  send_email: { icon: "✉", label: "Mail" },
  send_telegram_message: { icon: "✈", label: "Telegram" },
  android_intent: { icon: "◆", label: "System" },
  apilayer_lookup: { icon: "◇", label: "Lookup" },
};
function summarizeCall(call) {
  const a = call.args || {};
  if (call.name === "web_search") return `"${a.query}"`;
  if (call.name === "ingest_url") return a.url;
  if (call.name === "run_shell") return a.command;
  if (call.name === "device_action") return a.action;
  if (call.name === "send_email") return `to ${a.to}`;
  if (call.name === "send_telegram_message") return "message sent";
  if (call.name === "android_intent") return `${a.kind}${a.query ? ": " + a.query : ""}`;
  return JSON.stringify(a).slice(0, 60);
}
function renderActivity(toolCalls) {
  if (!toolCalls || !toolCalls.length) return null;
  const wrap = el("div", "activity-list");
  toolCalls.forEach((call) => {
    const meta = ACTIVITY_META[call.name] || { icon: "•", label: call.name };
    const card = el("div", "activity-card");
    const head = el("div", "activity-head");
    head.appendChild(el("span", "activity-icon", meta.icon));
    head.appendChild(el("span", "activity-label", meta.label));
    card.appendChild(head);
    card.appendChild(el("div", "activity-summary", summarizeCall(call)));
    const detail = el("pre", "activity-detail", JSON.stringify(call.result, null, 2));
    card.appendChild(detail);
    card.addEventListener("click", () => card.classList.toggle("open"));
    wrap.appendChild(card);
  });
  return wrap;
}

// ------------------------------------------------------------------ nav
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.tab === "systems") { openSystemsSheet(); return; }
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $(`#panel-${btn.dataset.tab}`).classList.add("active");
  });
});

// ---------------------------------------------------------------- sheets
$("#statusPill").addEventListener("click", openSystemsSheet);
function openSystemsSheet() { $("#systemsSheet").hidden = false; }
$("#closeSheet").addEventListener("click", () => { $("#systemsSheet").hidden = true; });

$("#paletteBtn").addEventListener("click", () => { $("#palette").hidden = false; });
$("#closePalette").addEventListener("click", () => { $("#palette").hidden = true; });
document.querySelectorAll(".palette-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    $("#palette").hidden = true;
    const input = $("#chatInput");
    input.value = btn.dataset.prompt;
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
  });
});

// ---------------------------------------------------------------- voice
let voiceOn = localStorage.getItem("engola_voice") === "1";
function renderVoiceState() {
  $("#voiceState").textContent = voiceOn ? "On -- replies auto-speak" : "Off";
}
function toggleVoice() {
  voiceOn = !voiceOn;
  localStorage.setItem("engola_voice", voiceOn ? "1" : "0");
  renderVoiceState();
}
$("#voiceToggle").addEventListener("click", toggleVoice);
$("#voiceToggleSettings").addEventListener("click", toggleVoice);
renderVoiceState();

// ------------------------------------------------------------- audio dock
const player = $("#player");
const dock = $("#dock");
const dockBtn = $("#dockPlayPause");
const dockSeek = $("#dockSeek");
const dockTime = $("#dockTime");
function fmtTime(s) { if (!isFinite(s)) return "0:00"; const m = Math.floor(s / 60), sec = Math.floor(s % 60); return `${m}:${sec.toString().padStart(2, "0")}`; }

async function loadAndPlay(text) {
  dockBtn.textContent = "…";
  try {
    const res = await fetch("/api/speak", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || "speak failed");
    const blob = await res.blob();
    player.src = URL.createObjectURL(blob);
    dock.hidden = false;
    setState("speaking");
    await player.play();
    dockBtn.textContent = "❚❚";
  } catch (err) {
    console.error("Voice playback failed:", err.message);
    dock.hidden = true;
    dockBtn.textContent = "▶";
    setState("error");
    setTimeout(() => setState("ready"), 2000);
  }
}
dockBtn.addEventListener("click", () => {
  if (player.paused) { player.play(); dockBtn.textContent = "❚❚"; } else { player.pause(); dockBtn.textContent = "▶"; }
});
dockSeek.addEventListener("input", () => { if (player.duration) player.currentTime = (dockSeek.value / 100) * player.duration; });
$("#dockClose").addEventListener("click", () => { player.pause(); dock.hidden = true; });
player.addEventListener("timeupdate", () => { if (player.duration) dockSeek.value = (player.currentTime / player.duration) * 100; dockTime.textContent = fmtTime(player.currentTime); });
player.addEventListener("ended", () => { dockBtn.textContent = "▶"; setState("ready"); });

async function autoSpeak(text) { if (!voiceOn) return; await loadAndPlay(text); }

// ----------------------------------------------------------------- chat
let currentEngine = null;
async function loadEngines() {
  const { engines, default: def } = await api("/api/engines");
  const sel = $("#engineSelect");
  sel.innerHTML = "";
  engines.forEach((e) => {
    const opt = el("option");
    opt.value = e.id;
    opt.textContent = e.configured ? e.label : `${e.label} (no key)`;
    opt.disabled = !e.configured;
    sel.appendChild(opt);
  });
  currentEngine = def;
  sel.value = def;
  sel.addEventListener("change", () => (currentEngine = sel.value));
}

function addMessage(role, text, engineTag, embed, toolCalls) {
  document.querySelector(".empty-state")?.remove();
  const wrap = el("div", `msg ${role}`);
  if (role === "assistant" && text === "…") {
    wrap.classList.add("typing");
    wrap.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
  } else if (role === "assistant") {
    const activity = renderActivity(toolCalls);
    if (activity) wrap.appendChild(activity);
    const body = el("div");
    body.innerHTML = renderMarkdown(text);
    wrap.appendChild(body);
  } else {
    wrap.textContent = text;
  }
  if (embed && embed.src) {
    const frame = el("iframe", "embed-frame");
    frame.src = embed.src;
    frame.allow = "accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture";
    frame.allowFullscreen = true;
    wrap.appendChild(frame);
  }
  if (role === "assistant" && text !== "…") {
    const meta = el("div", "msg-meta");
    if (engineTag) meta.appendChild(el("span", "engine-tag", engineTag));
    const replay = el("button", "replay-btn", "▶");
    replay.title = "Play this reply";
    replay.addEventListener("click", () => loadAndPlay(text));
    meta.appendChild(replay);
    wrap.appendChild(meta);
  }
  $("#messages").appendChild(wrap);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return wrap;
}

async function loadStatus() {
  const strip = $("#statusStrip");
  try {
    const s = await api("/api/status");
    const items = [["Brave", s.brave_search], ["ElevenLabs", s.elevenlabs], ["Telegram", s.telegram_archive], ["Gmail", s.gmail.linked ? true : (s.gmail.configured ? "unlinked" : false)]];
    strip.innerHTML = "";
    items.forEach(([label, state]) => {
      const span = el("span", state === true ? "on" : "");
      span.innerHTML = `<span class="dot"></span>${label}${state === "unlinked" ? " (not linked)" : ""}`;
      strip.appendChild(span);
    });
  } catch { strip.textContent = "status unavailable"; }
}

// ------------------------------------------------------------- voice input
const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
const micBtn = $("#micCommand");
if (SpeechRecognitionCtor && micBtn) {
  const recognition = new SpeechRecognitionCtor();
  recognition.lang = "en-US"; recognition.interimResults = false; recognition.maxAlternatives = 1;
  let listening = false;
  recognition.addEventListener("result", (e) => { $("#chatInput").value = e.results[0][0].transcript; $("#chatForm").requestSubmit(); });
  recognition.addEventListener("end", () => { listening = false; micBtn.classList.remove("listening"); setState("ready"); });
  recognition.addEventListener("error", () => { listening = false; micBtn.classList.remove("listening"); setState("ready"); });
  micBtn.addEventListener("click", () => {
    if (listening) { recognition.stop(); return; }
    listening = true; micBtn.classList.add("listening"); setState("listening"); recognition.start();
  });
} else if (micBtn) {
  micBtn.addEventListener("click", () => alert("Voice input isn't supported in this browser. Try Chrome."));
}

function resizeChatInput() {
  const el = $("#chatInput");
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 140) + "px";
}
$("#chatInput").addEventListener("input", resizeChatInput);
$("#chatInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("#chatForm").requestSubmit();
  }
});

$("#chatForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#chatInput");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  resizeChatInput();
  addMessage("user", text);
  const pending = addMessage("assistant", "…");
  setState("thinking");
  try {
    const { reply, engine, embed, tool_calls } = await api("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: text, engine: currentEngine }),
    });
    pending.remove();
    if (tool_calls && tool_calls.some((c) => c.name === "web_search")) setState("searching");
    else if (tool_calls && tool_calls.some((c) => c.name === "ingest_url")) setState("reading");
    else if (tool_calls && tool_calls.length) setState("executing");
    addMessage("assistant", reply, engine, embed, tool_calls);
    setTimeout(() => setState("ready"), 900);
    autoSpeak(reply);
  } catch (err) {
    pending.className = "msg error";
    pending.textContent = err.message;
    setState("error");
    setTimeout(() => setState("ready"), 2000);
  }
});

// --------------------------------------------------------------- device
$("#deviceActions").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const out = $("#deviceOutput");
  out.textContent = "…";
  try {
    const { result } = await api("/api/device/action", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: btn.dataset.action }) });
    out.textContent = typeof result === "string" ? result : JSON.stringify(result, null, 2);
    if (btn.dataset.action === "battery") $("#deviceBattery").textContent = typeof result === "string" ? result.slice(0, 40) : "see below";
  } catch (err) { out.textContent = "Error: " + err.message; }
});

$("#readScreenBtn").addEventListener("click", async () => {
  const out = $("#screenOutput");
  out.textContent = "Reading…";
  try { out.textContent = (await api("/api/device/screen")).description; }
  catch (err) { out.textContent = "Error: " + err.message; }
});
$("#viewScreenBtn").addEventListener("click", () => {
  const img = $("#screenImg");
  img.src = "/api/device/screen/image?t=" + Date.now();
  img.hidden = false;
});

$("#shellForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#shellInput");
  const command = input.value.trim();
  if (!command) return;
  const out = $("#shellOutput");
  out.textContent = "Running…";
  await runShell(command, false, out);
});
async function runShell(command, force, out) {
  try {
    const result = await api("/api/device/shell", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ command, force }) });
    out.textContent = `exit ${result.exit_code}\n${result.stdout || ""}${result.stderr ? "\nstderr:\n" + result.stderr : ""}`;
  } catch (err) {
    if (err.status === 409) {
      if (confirm(`"${command}" looks destructive. Run it anyway?`)) return runShell(command, true, out);
      out.textContent = "Cancelled.";
    } else { out.textContent = "Error: " + err.message; }
  }
}

// ----------------------------------------------------------------- mail
async function loadMail() {
  const status = await api("/api/email/status");
  $("#mailLinked").hidden = !status.linked;
  $("#mailUnlinked").hidden = status.linked;
  if (status.linked) await refreshMail();
}
async function refreshMail() {
  const list = $("#mailList");
  list.innerHTML = "<li>Loading…</li>";
  try {
    const { messages } = await api("/api/email/list");
    list.innerHTML = "";
    messages.forEach((m) => {
      const li = el("li");
      li.appendChild(el("div", "from", m.from));
      li.appendChild(el("div", "subject", m.subject || "(no subject)"));
      li.appendChild(el("div", "snippet", m.snippet));
      li.addEventListener("click", () => readMail(m.id));
      list.appendChild(li);
    });
  } catch (err) { list.innerHTML = `<li>Error: ${err.message}</li>`; }
}
async function readMail(id) {
  const box = $("#mailReading");
  box.hidden = false; box.textContent = "Loading…";
  try {
    const m = await api("/api/email/" + id);
    box.textContent = `From: ${m.from}\nSubject: ${m.subject}\nDate: ${m.date}\n\n${m.body}`;
  } catch (err) { box.textContent = "Error: " + err.message; }
}
$("#refreshMail")?.addEventListener("click", refreshMail);
$("#composeBtn").addEventListener("click", () => { $("#composeForm").hidden = false; $("#mailReading").hidden = true; });
$("#cancelMailBtn").addEventListener("click", () => ($("#composeForm").hidden = true));
$("#sendMailBtn").addEventListener("click", async () => {
  try {
    await api("/api/email/send", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ to: $("#mailTo").value.trim(), subject: $("#mailSubject").value.trim(), body: $("#mailBody").value }) });
    $("#composeForm").hidden = true;
    $("#mailTo").value = $("#mailSubject").value = $("#mailBody").value = "";
    refreshMail();
  } catch (err) { alert("Send failed: " + err.message); }
});

// --------------------------------------------------------------- memory
async function loadNotes() {
  const { notes } = await api("/api/knowledge");
  const list = $("#notesList");
  list.innerHTML = "";
  notes.forEach((n) => {
    const li = el("li");
    li.appendChild(el("span", "note-text", n.text));
    const meta = el("span");
    meta.appendChild(el("span", "note-date", n.created_at.slice(0, 10)));
    const del = el("button", "del", "×");
    del.addEventListener("click", async () => { await api("/api/knowledge/" + n.id, { method: "DELETE" }); li.remove(); });
    meta.appendChild(del);
    li.appendChild(meta);
    list.appendChild(li);
  });
}
$("#rememberForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#rememberInput");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  await api("/api/knowledge", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
  loadNotes();
});

// ----------------------------------------------------------------- boot
loadEngines();
loadStatus();
loadMail();
loadNotes();
setState("ready");
if (new URLSearchParams(location.search).get("gmail_linked")) history.replaceState({}, "", "/");
