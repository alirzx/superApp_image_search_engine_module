#!/usr/bin/env python3
"""Evaluate text-to-image Recall@K on a labeled API-backed corpus.

Input JSON list:
[{"query":"یک خودروی قرمز","relevant_filenames":["redcar.jpg"]}, ...]
Filenames must be unique within the collection. Do not use sensitive images for tests.
"""
import argparse
import json
import os
import time
import urllib.request
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--collection',default='default');p.add_argument('--url',default='http://127.0.0.1:8004')
    p.add_argument('--top-k',type=int,default=10);a=p.parse_args()
    key=os.getenv('API_KEY')
    if not key:raise SystemExit('Set API_KEY in your environment')
    examples=json.loads(a.dataset.read_text(encoding='utf-8'))
    if not isinstance(examples,list) or not examples:raise SystemExit('Provide a non-empty JSON list')
    relevant=0;latency=[]
    for item in examples:
        payload=json.dumps({'collection_id':a.collection,'query':item['query'],'top_k':a.top_k}).encode()
        req=urllib.request.Request(a.url+'/v1/search/text',data=payload,method='POST',
                         headers={'X-API-Key':key,'Content-Type':'application/json'})
        start=time.perf_counter()
        with urllib.request.urlopen(req,timeout=180) as r:body=json.load(r)
        latency.append((time.perf_counter()-start)*1000)
        found={row['metadata']['filename'] for row in body['results']}
        relevant+=int(bool(found.intersection(item['relevant_filenames'])))
    latency.sort()
    print(json.dumps({'total_queries':len(examples),'recall_at_k':relevant/len(examples),
                      'top_k':a.top_k,'p50_ms':latency[len(latency)//2],
                      'p95_ms':latency[min(len(latency)-1,int(.95*len(latency)))]},indent=2))

if __name__=='__main__':main()
