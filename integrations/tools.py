"""Real tool-calling: defines what the chat model can actually invoke, and
executes it for real against the existing device/shell/gmail/telegram code.
The model can only get a result by genuinely calling one of these -- there
is no path for it to narrate a fake result, which is the whole point after
tonight's fabrication issues.

Currently wired for Gemini only (see providers/gemini.py::respond_with_tools).
Other engines answer in plain text without tool access until ported."""
from device import shell, termux_api, screen
from integrations import apilayer
from integrations import gmail, intents

TOOLS = [
    {
        "name": "run_shell",
        "description": "Run a shell command on the user's Termux/Android device and return its real stdout/stderr/exit code.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "device_action",
        "description": "Run a quick device action.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": [
                    "battery", "clipboard_get", "torch_on", "torch_off",
                    "vibrate", "location", "volume", "sms_list", "photo",
                ]},
            },
            "required": ["action"],
        },
    },
    {
        "name": "read_screen",
        "description": "Take a screenshot and get an AI description of what's currently on screen (requires ADB pairing to be set up).",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "list_recent_emails",
        "description": "List the user's most recent Gmail messages.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional Gmail search query"},
                "max_results": {"type": "integer"},
            },
        },
    },
    {
        "name": "read_email",
        "description": "Read one email's full content by message ID (get IDs from list_recent_emails first).",
        "parameters": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
        },
    },
    {
        "name": "send_email",
        "description": "Send an email as the user via their linked Gmail.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "send_telegram_message",
        "description": "Send a message to the user's own Telegram (their archive DM).",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "apilayer_lookup",
        "description": "verify_email (email verification), flight_status (needs flight IATA code), country_info, ip_location, stock_quote (needs symbol), news_headlines (real live news, use for finance/world news briefs -- pass a keyword), geocode (address to coordinates), scrape (fetch a webpage via a scraping proxy), search (real search-engine results, an alternative to web search).",
        "parameters": {
            "type": "object",
            "properties": {
                "product": {"type": "string", "enum": ["verify_email", "verify_phone", "exchange_rate", "ip_location", "validate_vat", "stock_quote", "whois", "screenshot", "barcode"]},
                "value": {"type": "string", "description": "email, phone number, or IP as needed"},
                "base": {"type": "string", "description": "for exchange_rate only"},
                "target": {"type": "string", "description": "for exchange_rate only"},
            },
            "required": ["product"],
        },
    },
    {
        "name": "android_intent",
        "description": (
            "Open a native Android feature. 'maps' needs query. 'calendar_event' needs title "
            "(opens the add-event screen for the user to confirm -- does not silently save it). "
            "'dial' needs number. 'open_url' needs url. Cannot read calendar or contacts."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["maps", "calendar_event", "dial", "open_url"]},
                "query": {"type": "string"},
                "title": {"type": "string"},
                "when": {"type": "string"},
                "number": {"type": "string"},
                "url": {"type": "string"},
            },
            "required": ["kind"],
        },
    },
]


def execute(name: str, args: dict) -> dict:
    """Never raises -- a tool failure becomes an honest error result the
    model can relay, not a crashed request."""
    try:
        if name == "run_shell":
            command = args.get("command", "")
            if shell.is_dangerous(command):
                return {"error": "Command flagged as dangerous. Tell the user what you'd run and ask them to run it themselves in the Device tab with the force option."}
            return shell.run(command)

        if name == "device_action":
            return {"result": termux_api.run_action(args.get("action", ""))}

        if name == "read_screen":
            return {"description": screen.read_screen()}

        if name == "list_recent_emails":
            return {"messages": gmail.list_recent(args.get("query", ""), int(args.get("max_results", 10)))}

        if name == "read_email":
            return gmail.read(args["message_id"])

        if name == "send_email":
            return gmail.send(args["to"], args["subject"], args["body"])

        if name == "send_telegram_message":
            from providers import telegram
            telegram.send_message(args["text"])
            return {"sent": True}

        if name == "apilayer_lookup":
            product = args.get("product", "")
            if product == "verify_email":
                return apilayer.verify_email(args.get("value", ""))
            if product == "verify_phone":
                return apilayer.verify_phone(args.get("value", ""))
            if product == "exchange_rate":
                return apilayer.exchange_rate(args.get("base", "USD"), args.get("target", "EUR"))
            if product == "ip_location":
                return apilayer.ip_to_location(args.get("value", ""))
            if product == "validate_vat":
                return apilayer.validate_vat(args.get("value", ""))
            if product == "stock_quote":
                return apilayer.stock_quote(args.get("value", ""))
            if product == "whois":
                return apilayer.whois_lookup(args.get("value", ""))
            if product == "screenshot":
                return apilayer.screenshot_url(args.get("value", ""))
            if product == "barcode":
                return apilayer.barcode_lookup(args.get("value", ""))
            return {"error": f"Unknown apilayer product '{product}'"}

        if name == "android_intent":
            return intents.run(args)

        return {"error": f"Unknown tool '{name}'"}
    except Exception as exc:
        return {"error": str(exc)}
