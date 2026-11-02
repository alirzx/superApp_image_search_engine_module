import io
import pytest
from PIL import Image
from app.processing.images import decode_image,prepare_image,InvalidImage

def data(mode='RGB'):
    p=io.BytesIO();Image.new(mode,(35,45),(255,0,0)).save(p,format='PNG');return p.getvalue()

def test_prepare_valid():
    result=prepare_image(data(),2000)
    assert result.width==35 and result.height==45
    assert decode_image(result.canonical,2000).size==(35,45)
    assert len(result.digest)==64

def test_bad_pixels_and_bytes():
    with pytest.raises(InvalidImage):decode_image(data(),100)
    with pytest.raises(InvalidImage):decode_image(b'random',2000)
