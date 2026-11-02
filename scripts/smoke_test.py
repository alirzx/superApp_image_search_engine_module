#!/usr/bin/env python3
"""Basic authenticated API smoke after model is downloaded and service is ready."""
import argparse
import os
import urllib.request
import json
p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8004');a=p.parse_args()
api_key=os.getenv('API_KEY')
if not api_key:raise SystemExit('Set API_KEY environment variable')
for path in ['/health/live','/health/ready','/v1/models','/v1/collections']:
    req=urllib.request.Request(a.url+path,headers={'X-API-Key':api_key})
    with urllib.request.urlopen(req,timeout=120) as r:
        print(path,r.status,json.dumps(json.load(r),ensure_ascii=False))
