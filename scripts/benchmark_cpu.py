#!/usr/bin/env python3
"""Real CPU embedding microbenchmark, intentionally separate from unit tests."""
import argparse
import json
import os
import resource
import statistics
import time
from pathlib import Path
import numpy as np
from PIL import Image


def summary(values):
    ordered=sorted(values)
    return {'p50_ms':round(statistics.median(ordered)*1000,2),
            'p95_ms':round(ordered[min(len(ordered)-1,int(.95*len(ordered)))]*1000,2),
            'mean_ms':round(statistics.mean(ordered)*1000,2)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model-path',type=Path,default=Path('.models/siglip2'))
    p.add_argument('--model-id',default='google/siglip2-base-patch32-256')
    p.add_argument('--revision',default='')
    p.add_argument('--threads',type=int,default=2)
    p.add_argument('--warmup',type=int,default=3)
    p.add_argument('--runs',type=int,default=15)
    args=p.parse_args()
    if args.runs<2 or args.warmup<0:raise SystemExit('Require runs>=2 and warmup>=0')
    from sys import path
    path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
    from app.inference.siglip2 import Siglip2CPU
    start=time.perf_counter()
    provider=Siglip2CPU(args.model_path,args.model_id,args.revision,args.threads)
    loaded=time.perf_counter()-start
    image=Image.fromarray(np.random.default_rng(17).integers(0,256,(256,256,3),dtype=np.uint8))
    results={}
    for label, fn in [('image',lambda:provider.encode_image(image)),
                      ('text_fa',lambda:provider.encode_text('یک گربه سفید روی مبل')),
                      ('text_en',lambda:provider.encode_text('a white cat on a sofa'))]:
        for _ in range(args.warmup):fn()
        timings=[]
        for _ in range(args.runs):
            t=time.perf_counter();fn();timings.append(time.perf_counter()-t)
        results[label]=summary(timings)
    output={'model_signature':provider.signature,'dimension':provider.dimension,
            'threads':args.threads,'load_seconds':round(loaded,2),
            'peak_rss_mib':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1),
            'timings':results,'note':'Microbenchmark, not API end-to-end latency.'}
    print(json.dumps(output,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
