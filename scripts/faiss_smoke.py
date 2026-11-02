#!/usr/bin/env python3
"""Run separately on a machine with faiss-cpu installed."""
import tempfile
from pathlib import Path
import numpy as np
from sys import path
path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.storage.vector import VectorIndex

with tempfile.TemporaryDirectory() as directory:
    index=VectorIndex(3,Path(directory),'faiss')
    index.add('default',1,np.array([1.,0.,0.],dtype=np.float32))
    index.add('default',2,np.array([0.,1.,0.],dtype=np.float32))
    index.add('another',3,np.array([1.,0.,0.],dtype=np.float32))
    result=index.search('default',np.array([1.,0.,0.],dtype=np.float32),2)
    assert result[0][0]==1 and abs(result[0][1]-1.)<1e-5
    assert len(result)==2
    index.remove('default',1)
    assert index.count('default')==1
    print('FAISS native bindings / index operations: OK')
