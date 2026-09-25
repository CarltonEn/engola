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

// ------------------------------------------------------------------ tabs
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $(`#panel-${btn.dataset.tab}`).classList.add("active");
  });
});

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

function addMessage(role, text, engineTag) {
  const wrap = el("div", `msg ${role}`, text);
  if (engineTag) wrap.appendChild(el("span", "engine-tag", engineTag));
  if (role === "assistant") {
    const btn = el("button", "speak-btn", "🔊 Speak");
    btn.addEventListener("click", () => speak(text, btn));
    wrap.appendChild(document.createElement("br"));
    wrap.appendChild(btn);
  }
  $("#messages").appendChild(wrap);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return wrap;
}

async function speak(text, btn) {
  btn.classList.add("loading");
  btn.textContent = "…";
  try {
    const res = await fetch("/api/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || "speak failed");
    const blob = await res.blob();
    const player = $("#player");
    player.src = URL.createObjectURL(blob);
    player.hidden = false;
    player.play();
  } catch (err) {
    alert("Speak failed: " + err.message);
  } finally {
    btn.classList.remove("loading");
    btn.textContent = "🔊 Speak";
  }
}

// ---------------------------------------------------------------- status
async function loadStatus() {
  const strip = $("#statusStrip");
  try {
    const s = await api("/api/status");
    const items = [
      ["Brave", s.brave_search],
      ["ElevenLabs", s.elevenlabs],
      ["Telegram archive", s.telegram_archive],
      ["Gmail", s.gmail.linked ? true : (s.gmail.configured ? "unlinked" : false)],
    ];
    strip.innerHTML = "";
    items.forEach(([label, state]) => {
      const span = el("span", state === true ? "on" : "");
      span.innerHTML = `<span class="dot"></span>${label}${state === "unlinked" ? " (not linked)" : ""}`;
      strip.appendChild(span);
    });
  } catch {
    strip.textContent = "status unavailable";
  }
}

$("#chatForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#chatInput");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  addMessage("user", text);
  const pending = addMessage("assistant", "…");
  try {
    const { reply, engine } = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, engine: currentEngine }),
    });
    pending.textContent = reply;
    pending.appendChild(el("span", "engine-tag", engine));
  } catch (err) {
    pending.className = "msg error";
    pending.textContent = err.message;
  }
});

// --------------------------------------------------------------- device
$("#deviceActions").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const out = $("#deviceOutput");
  out.textContent = "…";
  try {
    const { result } = await api("/api/device/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: btn.dataset.action }),
    });
    out.textContent = typeof result === "string" ? result : JSON.stringify(result, null, 2);
  } catch (err) {
    out.textContent = "Error: " + err.message;
  }
});

$("#readScreenBtn").addEventListener("click", async () => {
  const out = $("#screenOutput");
  out.textContent = "Reading…";
  try {
    const { description } = await api("/api/device/screen");
    out.textContent = description;
  } catch (err) {
    out.textContent = "Error: " + err.message;
  }
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
    const result = await api("/api/device/shell", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command, force }),
    });
    out.textContent = `exit ${result.exit_code}\n${result.stdout || ""}${result.stderr ? "\nstderr:\n" + result.stderr : ""}`;
  } catch (err) {
    if (err.status === 409) {
      if (confirm(`"${command}" looks destructive. Run it anyway?`)) {
        return runShell(command, true, out);
      }
      out.textContent = "Cancelled.";
    } else {
      out.textContent = "Error: " + err.message;
    }
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
  } catch (err) {
    list.innerHTML = `<li>Error: ${err.message}</li>`;
  }
}

async function readMail(id) {
  const box = $("#mailReading");
  box.hidden = false;
  box.textContent = "Loading…";
  try {
    const m = await api("/api/email/" + id);
    box.textContent = `From: ${m.from}\nSubject: ${m.subject}\nDate: ${m.date}\n\n${m.body}`;
  } catch (err) {
    box.textContent = "Error: " + err.message;
  }
}

$("#refreshMail")?.addEventListener("click", refreshMail);
$("#composeBtn").addEventListener("click", () => {
  $("#composeForm").hidden = false;
  $("#mailReading").hidden = true;
});
$("#cancelMailBtn").addEventListener("click", () => ($("#composeForm").hidden = true));
$("#sendMailBtn").addEventListener("click", async () => {
  try {
    await api("/api/email/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        to: $("#mailTo").value.trim(),
        subject: $("#mailSubject").value.trim(),
        body: $("#mailBody").value,
      }),
    });
    $("#composeForm").hidden = true;
    $("#mailTo").value = $("#mailSubject").value = $("#mailBody").value = "";
    refreshMail();
  } catch (err) {
    alert("Send failed: " + err.message);
  }
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
    del.addEventListener("click", async () => {
      await api("/api/knowledge/" + n.id, { method: "DELETE" });
      li.remove();
    });
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
  await api("/api/knowledge", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  loadNotes();
});

// ----------------------------------------------------------------- boot
loadEngines();
loadStatus();
loadMail();
loadNotes();
if (new URLSearchParams(location.search).get("gmail_linked")) {
  history.replaceState({}, "", "/");
}
