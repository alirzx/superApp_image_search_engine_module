"""SuperApp Module 4: two search operations, durable indexing and a private media API."""
import asyncio
import hmac
import logging
import time
import uuid
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File, Form, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from PIL import Image
from app.config import Settings
from app.api.schemas import TextSearch, CollectionCreate
from app.services.engine import Engine
from app.processing.images import decode_image, InvalidImage

logging.basicConfig(level=logging.INFO)
REQ=Counter('image_search_requests_total','Search requests', ['kind'])
LAT=Histogram('image_search_request_seconds','End-to-end search latency', ['kind'])


def create_app(settings: Settings | None = None, provider=None):
    settings=settings or Settings()
    engine=Engine(settings,provider)

    @asynccontextmanager
    async def lifespan(app):
        await engine.start()
        yield
        await engine.close()

    app=FastAPI(title='SuperApp Image Search Engine',version='0.1.0',lifespan=lifespan)
    app.state.engine=engine
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware,allow_origins=[s.strip() for s in settings.cors_origins.split(',')],
                           allow_methods=['GET','POST','DELETE'],allow_headers=['X-API-Key','Content-Type'])

    def auth(x_api_key: Annotated[str | None,Header(alias='X-API-Key')]=None):
        if settings.api_auth_enabled and not hmac.compare_digest(x_api_key or '',settings.api_key):
            raise HTTPException(401,'Invalid API key')

    def ready(): engine.need_ready()

    async def safe_read(file: UploadFile):
        data=await file.read(settings.max_image_size_mb*1024*1024+1)
        if len(data)>settings.max_image_size_mb*1024*1024:raise HTTPException(413,'Image too large')
        return data

    def response(collection,kind,results,duration):
        return {'request_id':uuid.uuid4().hex,'collection_id':collection,'query_type':kind,
                'model_id':settings.model_id,'model_revision':engine.provider.signature if engine.provider else None,
                'results':results,'processing_time_ms':round(duration*1000,2)}

    @app.get('/health/live')
    def live():return {'status':'ok'}

    @app.get('/health/ready')
    def health_ready():
        if not engine.ready:return JSONResponse(status_code=503,content={'status':'unavailable','reason':'model_or_index_not_ready'})
        return {'status':'ready','vectors':engine.repo.index_count()}

    @app.get('/metrics',dependencies=[Depends(auth)])
    def metrics():
        if not settings.metrics_enabled:raise HTTPException(404,'Metrics disabled')
        return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)

    @app.get('/v1/models',dependencies=[Depends(auth)])
    def models():return {'models':[{'id':settings.model_id,'signature':engine.provider.signature if engine.provider else None,
                                'dimension':engine.provider.dimension if engine.provider else None,'ready':engine.ready,
                                'device':'cpu','backend':'pytorch'}]}

    @app.get('/v1/collections',dependencies=[Depends(auth)])
    def collections():return {'collections':engine.repo.collections()}

    @app.post('/v1/collections',status_code=201,dependencies=[Depends(auth)])
    def create_collection(payload: CollectionCreate):
        name=payload.name.strip()
        if not name:raise HTTPException(422,'Collection name cannot be blank')
        id_=uuid.uuid4().hex
        return engine.repo.create_collection(id_,name)

    @app.post('/v1/images',status_code=202,dependencies=[Depends(auth)])
    async def upload_image(file: UploadFile=File(...),collection_id: str=Form('default')):
        data=await safe_read(file)
        return await asyncio.to_thread(engine.upload,data,collection_id,file.filename or 'image')

    @app.post('/v1/images/batch',status_code=202,dependencies=[Depends(auth)])
    async def upload_batch(files: list[UploadFile]=File(...),collection_id: str=Form('default')):
        engine.need_ready();engine.validate_collection(collection_id)
        if not files or len(files)>settings.max_batch_images:raise HTTPException(422,'Invalid batch size')
        successes=[];failures=[]
        for n,file in enumerate(files):
            try:
                data=await safe_read(file)
                successes.append(await asyncio.to_thread(engine.upload,data,collection_id,file.filename or 'image'))
            except HTTPException as exc:failures.append({'index':n,'filename':Path(file.filename or 'image').name[:160],'error':exc.detail})
        return {'accepted':successes,'rejected':failures}

    @app.get('/v1/images/{image_id}',dependencies=[Depends(auth)])
    def image_meta(image_id: str):
        image=engine.repo.image(image_id)
        if not image:raise HTTPException(404,'Image not found')
        return {'image_id':image['id'],'collection_id':image['collection_id'],
                'filename':image['filename'],'width':image['width'],'height':image['height'],
                'status':image['status'],'error':image['error'],
                'thumbnail_url':f'/v1/images/{image_id}/thumbnail'}

    @app.get('/v1/images/{image_id}/thumbnail',dependencies=[Depends(auth)])
    def thumbnail(image_id: str):
        image=engine.repo.image(image_id)
        if not image:raise HTTPException(404,'Image not found')
        path=engine.objects.get(image['thumbnail_key'])
        if not path.is_file():raise HTTPException(404,'Image media not found')
        return FileResponse(path,media_type='image/webp',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

    @app.delete('/v1/images/{image_id}',status_code=204,dependencies=[Depends(auth)])
    def delete(image_id: str):engine.delete(image_id)

    @app.get('/v1/jobs/{job_id}',dependencies=[Depends(auth)])
    def job(job_id: str):
        result=engine.repo.job(job_id)
        if not result:raise HTTPException(404,'Job not found')
        return {'job_id':result['id'],'image_id':result['image_id'],'status':result['status'],'error':result['error']}

    @app.post('/v1/search/text',dependencies=[Depends(auth)])
    async def text_search(payload: TextSearch):
        t=time.perf_counter()
        query=payload.query.strip()
        if not query:raise HTTPException(422,'Empty text query')
        if payload.top_k>settings.max_top_k:raise HTTPException(422,'top_k exceeds limit')
        engine.validate_collection(payload.collection_id)
        vec=await engine.encode_text(query)
        results=await asyncio.to_thread(engine.results,payload.collection_id,vec,payload.top_k)
        dt=time.perf_counter()-t;REQ.labels('text').inc();LAT.labels('text').observe(dt)
        return response(payload.collection_id,'text',results,dt)

    @app.post('/v1/search/image',dependencies=[Depends(auth)])
    async def image_search(file: UploadFile=File(...),collection_id: str=Form('default'),top_k: int=Form(10)):
        t=time.perf_counter()
        if not 1<=top_k<=settings.max_top_k:raise HTTPException(422,'Invalid top_k')
        engine.validate_collection(collection_id)
        data=await safe_read(file)
        try:image=await asyncio.to_thread(decode_image,data,settings.max_image_pixels)
        except InvalidImage as exc:raise HTTPException(422,str(exc)) from exc
        vec=await engine.encode_image(image)
        results=await asyncio.to_thread(engine.results,collection_id,vec,top_k)
        dt=time.perf_counter()-t;REQ.labels('image').inc();LAT.labels('image').observe(dt)
        return response(collection_id,'image',results,dt)

    return app


app=create_app()
