#!/usr/bin/env python3
"""Explicit out-of-band model download and content-addressed manifest creation."""
import argparse
import hashlib
import json
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download


def digest(path):
    sha=hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(4*1024*1024),b""):
            sha.update(block)
    return sha.hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model-id',default='google/siglip2-base-patch32-256')
    parser.add_argument('--revision',help='Optional pin; if omitted resolves current main to immutable SHA')
    parser.add_argument('--output',type=Path,default=Path('.models/siglip2'))
    args=parser.parse_args()
    sha=HfApi().model_info(args.model_id,revision=args.revision).sha
    if not sha:raise SystemExit('Unable to resolve model revision')
    args.output.mkdir(parents=True,exist_ok=True)
    snapshot_download(repo_id=args.model_id,revision=sha,local_dir=args.output,
                      allow_patterns=['*.json','*.safetensors','*.model','*.txt'])
    hashes={}
    for p in args.output.rglob('*'):
        if p.is_file() and '.cache' not in p.parts and p.name!='model-manifest.json':
            hashes[p.relative_to(args.output).as_posix()]=digest(p)
    manifest={'model_id':args.model_id,'revision':sha,'sha256':hashes}
    (args.output/'model-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Pinned MODEL_REVISION='+sha)
    print('Downloaded and recorded '+str(len(hashes))+' files at '+str(args.output))

if __name__=='__main__':main()
