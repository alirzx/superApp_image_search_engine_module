"""FAISS IDMap(IndexFlatIP), independently scoped per collection.

SQLite holds authoritative vectors: snapshots here are rebuildable caches.
Numpy adapter is strictly for hermetic unit/integration testing.
"""
from pathlib import Path
from threading import RLock
import os
import numpy as np


class VectorIndex:
    def __init__(self, dimension: int, data_dir: Path, backend: str = 'faiss'):
        self.dimension=dimension
        self.data_dir=data_dir
        self.backend=backend
        self.lock=RLock()
        self.indexes={}
        self._dirty=0
        self.faiss=None
        if backend=='faiss':
            import faiss
            self.faiss=faiss
            faiss.omp_set_num_threads(1)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _new(self):
        if self.faiss is None: return []
        return self.faiss.IndexIDMap2(self.faiss.IndexFlatIP(self.dimension))

    def _add_unlocked(self, collection: str, vector_id: int, vec: np.ndarray):
        idx=self.indexes.setdefault(collection, self._new())
        v=np.asarray(vec,dtype=np.float32).reshape(1,-1)
        if v.shape[1]!=self.dimension: raise ValueError('Embedding dimension mismatch')
        if self.faiss:
            idx.add_with_ids(v, np.array([vector_id],dtype=np.int64))
        else:
            idx.append((vector_id,v[0].copy()))

    def rebuild(self, rows: list[dict], signature: str):
        with self.lock:
            fresh={}
            self.indexes=fresh
            for row in rows:
                if row['signature']!=signature or row['dimension']!=self.dimension:
                    raise RuntimeError('Stored vectors incompatible with configured model')
                vec=np.frombuffer(row['vector'],dtype=np.float32)
                self._add_unlocked(row['collection_id'],row['vector_id'],vec)
            if self.faiss: self.snapshot()
            self._dirty=0

    def add(self, collection: str, vector_id: int, vec: np.ndarray):
        with self.lock:
            self._add_unlocked(collection,vector_id,vec)
            if self.faiss:
                self._dirty+=1
                if self._dirty>=50:
                    self.snapshot()
                    self._dirty=0

    def remove(self, collection: str, vector_id: int):
        with self.lock:
            idx=self.indexes.get(collection)
            if idx is None: return
            if self.faiss:
                idx.remove_ids(np.array([vector_id],dtype=np.int64))
                self._dirty+=1
                if self._dirty>=50:
                    self.snapshot()
                    self._dirty=0
            else:
                idx[:]=[(id_,v) for id_,v in idx if id_!=vector_id]

    def search(self, collection: str, vec: np.ndarray, k: int):
        with self.lock:
            idx=self.indexes.get(collection)
            if idx is None: return []
            if (idx.ntotal==0 if self.faiss else len(idx)==0): return []
            q=np.asarray(vec,dtype=np.float32).reshape(1,-1)
            if self.faiss:
                scores,ids=idx.search(q,min(k,idx.ntotal))
                return [(int(i),float(score)) for i,score in zip(ids[0],scores[0]) if i>=0]
            vals=[(id_,float(np.dot(q[0],v))) for id_,v in idx]
            return sorted(vals,key=lambda r:r[1],reverse=True)[:k]

    def count(self, collection: str):
        with self.lock:
            idx=self.indexes.get(collection)
            return (idx.ntotal if self.faiss else len(idx)) if idx is not None else 0

    def snapshot(self, collection: str | None = None):
        """Atomic, derived snapshots; startup always validates by rebuilding from SQLite."""
        if self.faiss is None: return
        with self.lock:
            names=[collection] if collection is not None else list(self.indexes)
            for name in names:
                idx=self.indexes[name]
                path=self.data_dir/f'{name}.faiss'
                tmp=self.data_dir/f'{name}.faiss.tmp'
                self.faiss.write_index(idx,str(tmp))
                os.replace(tmp,path)
