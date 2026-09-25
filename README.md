# Engola v2

A local web app: one Python process running in Termux, opened in your
phone's own browser at `http://127.0.0.1:8765`. Not Telegram-driven
anymore — Telegram (if you configure it) is just an archive channel now.
Nothing is hosted publicly; the server only listens on the phone's own
loopback interface.

This is a rebuild, not a reskin of the earlier attempts — different
interface (web page, not chat-bot commands), different memory model (a
real searchable long-term store, not just rolling context), and treats
device control, email, and memory as core, not extras.

## What's actually in it

- **Chat**, multi-engine: Gemini today; Grok, GPT, and Claude are wired
  in and light up the moment you add their API keys — same UI, a
  dropdown picks which one answers. Gemini auto-searches Brave mid-answer
  when it needs current info.
- **Long-term memory that's actually retrieved**: every exchange (and
  anything you explicitly tell it to remember) is stored in SQLite with a
  Gemini embedding. Before each reply, it searches that store for what's
  relevant to your current message and hands the model that context —
  this is the "how does it learn" part, not just a longer chat window.
  Falls back to keyword search if Gemini isn't configured.
- **Device control** — battery, clipboard, notifications, torch,
  vibration, volume, GPS, SMS, camera (Termux:API), plus full shell
  access (`/api/device/shell`).
- **Screen reading and input** — via ADB over Wireless Debugging (see
  below). This is the honest path to "read my screen": Android doesn't
  let a plain terminal peek at other apps' pixels without it.
- **Gmail** — read and send, via Google's OAuth loopback flow (your
  phone's own browser completes the login, no domain needed).
- **Auto-archive** — every exchange to a local `.md` transcript, mirrored
  to Telegram live plus as periodic file backups, if you set that up.

## 1. Termux setup

```bash
pkg update && pkg upgrade
pkg install python git termux-api android-tools
```

`termux-api` is for the device quick-actions; `android-tools` gives you
`adb`, for the screen module.

## 2. Get the repo running

```bash
git clone https://github.com/<you>/engola.git   # or unzip this download
cd engola
pip install -r requirements.txt
cp .env.example .env
nano .env
```

Fill in what you already have — `GEMINI_API_KEY`, `BRAVE_SEARCH_API_KEY`,
`ELEVENLABS_API_KEY`. Add `XAI_API_KEY` / `OPENAI_API_KEY` /
`ANTHROPIC_API_KEY` whenever you get those; nothing else needs to change.

```bash
python server.py
```

Open `http://127.0.0.1:8765` in your phone's browser. That's the whole
app — Chat / Device / Mail / Memory tabs across the top.

### Keeping it alive in the background

```bash
termux-wake-lock
tmux new -s engola
./run.sh
# Ctrl+B then D to detach; tmux attach -t engola to come back
```

For auto-start on boot, install **Termux:Boot** and drop a script in
`~/.termux/boot/` that `cd`s here and runs `./run.sh`.

## 3. Gmail

1. console.cloud.google.com → new project (or reuse one) → **APIs &
   Services → Credentials → Create Credentials → OAuth client ID**.
2. Application type: **Desktop app** (not "Web application" — Desktop
   app clients accept the loopback redirect without pre-registering an
   exact port, which matters since Termux's port can move).
3. Copy the Client ID and Client Secret into `.env` as `GOOGLE_CLIENT_ID`
   / `GOOGLE_CLIENT_SECRET`.
4. Enable the **Gmail API** for the project.
5. In the app, open the **Mail** tab → **Link Gmail**. Your phone's own
   browser handles the Google login and bounces straight back — no
   tunnel, no separate device.

## 4. Screen reading (opt-in, bigger trust step than the rest)

Screen reading needs `adb`, paired once by hand — there's no way around
a manual step here, and that's deliberate:

1. Phone **Settings → Developer options → Wireless debugging → On**
   (if Developer options is hidden: Settings → About phone → tap Build
   number 7 times).
2. **Pair device with pairing code** → note the IP:port and 6-digit code.
3. In Termux: `adb pair <ip>:<port>`, enter the code.
4. `adb connect <ip>:<port>` (the regular debugging port, shown on the
   same screen, different from the pairing port).
5. `adb devices` should now list it as `device` (not `unauthorized`).

Once paired, the **Device** tab's "Read screen" button takes a
screenshot and asks Gemini's vision model to describe/read it — real OCR
via a vision model, not a live accessibility feed. The same connection
also lets Engola simulate taps and typing (`device/screen.py` —
`tap`/`swipe`/`type_text`), which is real device automation. Treat
pairing this as a bigger decision than installing `termux-api`: ADB
access is broad.

## 5. Push to GitHub

```bash
git init
git add -A
git commit -m "Engola v2"
git branch -M main
git remote add origin https://github.com/<you>/engola.git
git push -u origin main
```

`.env` and `data/` (transcripts, memory database, OAuth tokens) are
already gitignored — don't remove that.

## Security — read this before you change ENGOLA_HOST

This server can run shell commands and send email as you, with **no
login screen**. Its access control is entirely "only 127.0.0.1 can reach
it" — i.e., only a browser on this same phone. That's why `ENGOLA_HOST`
defaults to `127.0.0.1` and `server.py` prints a warning if you change
it. If you ever want to reach it from another device on your network,
set `ENGOLA_ACCESS_TOKEN` in `.env` first (a shared-secret query param +
cookie check is already wired into `server.py`) — and understand that
still isn't real authentication, just a speed bump.

## Repo layout

```
server.py                Flask app -- every route
config.py                  env var loading
providers/
  registry.py               engine dispatch table
  gemini.py                  chat + embeddings + vision
  grok.py, openai_api.py, anthropic_api.py, openai_compat.py    other engines
  brave.py                   web search
  elevenlabs.py                text-to-speech
  telegram.py                   archive-only send client
device/
  shell.py                   shell exec (+ dangerous-command gate)
  termux_api.py                 phone control via Termux:API
  screen.py                      ADB screen read + input
integrations/
  google_oauth.py            OAuth loopback flow + token storage
  gmail.py                     list/read/send
memory/
  history.py                 rolling short-term chat context
  knowledge.py                  long-term store: SQLite + embeddings + retrieval
  archive.py                     local .md transcripts + Telegram mirror
static/                    the web UI (plain HTML/CSS/JS, no build step)
data/                      runtime only -- db, transcripts, tokens (gitignored)
```

## What's still a stub

Grok, GPT, and Claude providers are fully implemented but inert until
you add their keys — that's intentional, not unfinished. Nothing else
here is a placeholder.
