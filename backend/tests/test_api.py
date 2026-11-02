import asyncio
import io
from pathlib import Path
import numpy as np
import pytest
import httpx
from PIL import Image
from app.config import Settings
from app.main import create_app
from app.inference.base import normalize
from app.storage.repository import Repository


class FakeDualEncoder:
    """Deterministic vectors for contract tests, NOT a production model."""
    dimension=3
    signature='test-dual-encoder@fixed-v1'
    def encode_image(self,image):
        px=np.asarray(image.resize((1,1)),dtype=np.float32).reshape(3)
        return normalize(px,self.dimension)
    def encode_text(self,text):
        if 'red' in text or 'قرمز' in text:return normalize([1.,0.,0.],3)
        if 'green' in text or 'سبز' in text:return normalize([0.,1.,0.],3)
        return normalize([0.,0.,1.],3)


def png(color):
    f=io.BytesIO();Image.new('RGB',(64,48),color).save(f,'PNG');return f.getvalue()

@pytest.fixture
def testing_app(tmp_path):
    config=Settings(app_env='test',api_key='test-key-that-is-long-enough-for-ci',
                    data_dir=tmp_path,vector_backend='numpy',_env_file=None,job_poll_interval=0.05)
    return create_app(config,FakeDualEncoder())


@pytest.mark.asyncio
async def test_end_to_end_search_and_persistence(testing_app):
    async with testing_app.router.lifespan_context(testing_app):
        tr=httpx.ASGITransport(app=testing_app)
        async with httpx.AsyncClient(transport=tr,base_url='http://test') as client:
            h={'X-API-Key':'test-key-that-is-long-enough-for-ci'}
            r=await client.get('/v1/collections');assert r.status_code==401
            r=await client.get('/health/ready');assert r.status_code==200
            cr=await client.post('/v1/collections',json={'name':'Cars'},headers=h)
            collection=cr.json()['id'];assert cr.status_code==201
            red=await client.post('/v1/images',data={'collection_id':collection},files={'file':('red.png',png('red'),'image/png')},headers=h)
            green=await client.post('/v1/images',data={'collection_id':collection},files={'file':('green.png',png('green'),'image/png')},headers=h)
            assert red.status_code==green.status_code==202
            red_id=red.json()['image_id'];green_id=green.json()['image_id']
            for _ in range(200):
                s=await client.get('/v1/jobs/'+green.json()['job_id'],headers=h)
                if s.json()['status']=='completed':break
                await asyncio.sleep(0.02)
            assert s.json()['status']=='completed'
            t=await client.post('/v1/search/text',json={'collection_id':collection,'query':'خودروی قرمز','top_k':2},headers=h)
            assert t.status_code==200,t.text
            assert t.json()['results'][0]['image_id']==red_id
            im=await client.post('/v1/search/image',data={'collection_id':collection},files={'file':('sample.png',png('green'),'image/png')},headers=h)
            assert im.status_code==200 and im.json()['results'][0]['image_id']==green_id
            thumb=await client.get('/v1/images/'+red_id+'/thumbnail',headers=h)
            assert thumb.status_code==200 and thumb.headers['content-type']=='image/webp'
            assert (await client.get('/v1/images/'+red_id+'/thumbnail')).status_code==401
            other=await client.post('/v1/search/text',json={'collection_id':'default','query':'red'},headers=h)
            assert other.status_code==200 and other.json()['results']==[]
            assert (await client.delete('/v1/images/'+green_id,headers=h)).status_code==204
            after=await client.post('/v1/search/text',json={'collection_id':collection,'query':'green'},headers=h)
            assert len(after.json()['results'])==1 and after.json()['results'][0]['image_id']==red_id
    # Restart: index reconstructs from SQLite embeddings; no re-embedding required.
    settings=testing_app.state.engine.settings
    restarted=create_app(settings,FakeDualEncoder())
    async with restarted.router.lifespan_context(restarted):
        assert restarted.state.engine.index.count(collection)==1
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted),base_url='http://test') as client:
            assert (await client.delete('/v1/images/'+red_id,headers=h)).status_code==204
            empty=await client.post('/v1/search/text',json={'collection_id':collection,'query':'red'},headers=h)
            assert empty.status_code==200 and empty.json()['results']==[]

@pytest.mark.asyncio
async def test_upload_validation_and_batch(testing_app):
    async with testing_app.router.lifespan_context(testing_app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=testing_app),base_url='http://test') as client:
            h={'X-API-Key':'test-key-that-is-long-enough-for-ci'}
            bad=await client.post('/v1/images',files={'file':('bad.txt',b'not image','text/plain')},headers=h)
            assert bad.status_code==422
            files=[('files',('a.png',png('red'),'image/png')),('files',('invalid.png',b'x','image/png'))]
            batch=await client.post('/v1/images/batch',data={'collection_id':'default'},files=files,headers=h)
            assert batch.status_code==202 and len(batch.json()['accepted'])==1 and len(batch.json()['rejected'])==1
            assert (await client.post('/v1/search/text',json={'query':'x','top_k':500},headers=h)).status_code==422


def test_signature_mismatch(tmp_path):
    repo=Repository(tmp_path/'db.sqlite')
    repo.signature('model_a')
    with pytest.raises(RuntimeError,match='Model version changed'):repo.signature('model_b')


def test_normalization():
    from app.inference.base import normalize
    x=normalize(np.array([3,4],dtype=np.float64),2)
    assert x.dtype==np.float32 and np.isclose(np.linalg.norm(x),1)
    with pytest.raises(ValueError):normalize([0,0],2)
