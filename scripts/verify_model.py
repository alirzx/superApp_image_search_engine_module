#!/usr/bin/env python3
import argparse
import json
import hashlib
from pathlib import Path

def digest(path):
    sha=hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(4*1024*1024),b""):
            sha.update(block)
    return sha.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--path',type=Path,default=Path('.models/siglip2'))
    folder=p.parse_args().path
    manifest=json.loads((folder/'model-manifest.json').read_text())
    if not manifest.get('sha256') or not manifest.get('revision'):raise SystemExit('Incomplete manifest')
    for relative,expected in manifest['sha256'].items():
        path=(folder/relative).resolve()
        if not path.is_relative_to(folder.resolve()) or not path.is_file():raise SystemExit('File missing: '+relative)
        if digest(path)!=expected:raise SystemExit('Checksum mismatch: '+relative)
    print('VERIFIED '+str(len(manifest['sha256']))+' model files; revision='+manifest['revision'])

if __name__=='__main__':main()
