"""Request handling and durable, one-at-a-time image embedding worker."""
import asyncio
import logging
import re
import uuid
from pathlib import Path
from PIL import Image
import numpy as np

from app.config import Settings
from app.inference.base import normalize, EmbeddingProvider
from app.processing.images import prepare_image, decode_image, InvalidImage
from app.storage.repository import Repository
from app.storage.objects import ObjectStore
from app.storage.vector import VectorIndex

log=logging.getLogger(__name__)
COLLECTION_RE=re.compile(r'^[a-zA-Z0-9_-]{1,64}$')


class Engine:
    def __init__(self, settings: Settings, injected_provider: EmbeddingProvider | None = None):
        self.settings=settings
        settings.data_dir.mkdir(parents=True,exist_ok=True)
        self.repo=Repository(settings.data_dir/'metadata/image-search.sqlite')
        self.objects=ObjectStore(settings.data_dir/'images')
        self.provider=injected_provider
        self.index=None
        self.error=None
        self.worker_task=None
        self._inference_lock=asyncio.Lock()
        self._stop=False

    async def start(self):
        if self.provider is None:
            try:
                from app.inference.siglip2 import Siglip2CPU
                self.provider=await asyncio.to_thread(Siglip2CPU,self.settings.model_local_path,
                    self.settings.model_id,self.settings.model_revision,self.settings.inference_threads)
            except Exception as exc:
                log.exception('Model initialization failed (download offline before startup)')
                self.error=f'{type(exc).__name__}: {exc}'
                return
        self.repo.signature(self.provider.signature)
        self.index=VectorIndex(self.provider.dimension,self.settings.data_dir/'indexes',self.settings.vector_backend)
        self.index.rebuild(self.repo.all_embeddings(),self.provider.signature)
        self.error=None
        self.worker_task=asyncio.create_task(self.worker_loop())

    async def close(self):
        self._stop=True
        if self.worker_task:
            self.worker_task.cancel()
            try: await self.worker_task
            except asyncio.CancelledError: pass

    @property
    def ready(self):
        return self.provider is not None and self.index is not None and self.error is None

    def need_ready(self):
        if not self.ready:
            from fastapi import HTTPException
            raise HTTPException(503,'Model or index unavailable; check /health/ready')

    async def encode_image(self,image):
        self.need_ready()
        async with self._inference_lock:
            raw=await asyncio.to_thread(self.provider.encode_image,image)
        return normalize(raw,self.provider.dimension)

    async def encode_text(self,query):
        self.need_ready()
        async with self._inference_lock:
            raw=await asyncio.to_thread(self.provider.encode_text,query)
        return normalize(raw,self.provider.dimension)

    def validate_collection(self, id_):
        from fastapi import HTTPException
        if not COLLECTION_RE.fullmatch(id_):
            raise HTTPException(422,'Invalid collection_id')
        if not self.repo.collection_exists(id_):
            raise HTTPException(404,'Collection not found')

    def upload(self, data: bytes, collection_id: str, filename: str):
        from fastapi import HTTPException
        self.need_ready()
        self.validate_collection(collection_id)
        if len(data)>self.settings.max_image_size_mb*1024*1024:
            raise HTTPException(413,'Image too large')
        try: prepared=prepare_image(data,self.settings.max_image_pixels)
        except InvalidImage as exc: raise HTTPException(422,str(exc)) from exc
        image_id=uuid.uuid4().hex
        job_id=uuid.uuid4().hex
        original,thumbnail=self.objects.put(image_id,prepared.canonical,prepared.thumbnail)
        metadata=dict(id=image_id,collection_id=collection_id,filename=Path(filename or 'image').name[:160],
                      storage_key=original,thumbnail_key=thumbnail,width=prepared.width,height=prepared.height,
                      sha256=prepared.digest)
        try:self.repo.insert_image(metadata,job_id)
        except Exception:
            self.objects.remove(original);self.objects.remove(thumbnail)
            raise
        return {'image_id':image_id,'job_id':job_id,'status':'queued','collection_id':collection_id}

    async def worker_loop(self):
        while not self._stop:
            try:
                job=await asyncio.to_thread(self.repo.take_job)
                if job:
                    image=await asyncio.to_thread(self.repo.image,job['image_id'])
                    try:
                        path=self.objects.get(image['storage_key'])
                        decoded=await asyncio.to_thread(decode_image,path.read_bytes(),self.settings.max_image_pixels)
                        vec=await self.encode_image(decoded)
                        # commit embedding+status atomically; FAISS is rebuilt from SQLite at startup.
                        vector_id=await asyncio.to_thread(self.repo.complete,job['id'],image['id'],
                                               self.provider.signature,vec.tobytes(),self.provider.dimension)
                        try:
                            await asyncio.to_thread(self.index.add,image['collection_id'],vector_id,vec)
                        except Exception:
                            log.exception('FAISS update failed; rebuilding from SQLite')
                            try: await asyncio.to_thread(self.index.rebuild,self.repo.all_embeddings(),self.provider.signature)
                            except Exception as rebuild_exc:
                                self.error=f'Index rebuild failed: {rebuild_exc}'
                                return
                    except Exception as exc:
                        log.exception('Indexing failed for image id=%s',image['id'])
                        await asyncio.to_thread(self.repo.fail,job['id'],image['id'],str(exc))
                else:
                    await asyncio.sleep(self.settings.job_poll_interval)
            except asyncio.CancelledError: raise
            except Exception:
                log.exception('Worker error')
                await asyncio.sleep(1)

    def results(self, collection: str, vector: np.ndarray, k: int):
        self.need_ready()
        self.validate_collection(collection)
        hits=self.index.search(collection,vector,k)
        mapping=self.repo.images_by_vectors([i for i,_ in hits],collection)
        results=[]
        for id_,score in hits:
            image=mapping.get(id_)
            if not image:continue
            results.append({'image_id':image['id'],'score':score,'rank':len(results)+1,
                'thumbnail_url':f"/v1/images/{image['id']}/thumbnail",
                'metadata':{'filename':image['filename'],'width':image['width'],'height':image['height']}})
        return results

    def delete(self,id_):
        from fastapi import HTTPException
        image=self.repo.image(id_)
        if not image:raise HTTPException(404,'Image not found')
        # Delete metadata first so concurrent search/media calls can no longer expose it.
        with self.repo.connect() as db:
            row=db.execute('SELECT vector_id FROM embeddings WHERE image_id=?',(id_,)).fetchone()
        self.repo.delete_image(id_)
        if row and self.index:
            try:self.index.remove(image['collection_id'],row['vector_id'])
            except Exception:
                log.exception('Index remove failed, rebuilding')
                try:self.index.rebuild(self.repo.all_embeddings(),self.provider.signature)
                except Exception as exc:self.error=f'Index rebuild failed: {exc}'
        self.objects.remove(image['storage_key']);self.objects.remove(image['thumbnail_key'])
