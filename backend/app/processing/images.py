"""Validate untrusted images then produce EXIF-free canonical WebP bytes."""
import hashlib
import io
import warnings
from dataclasses import dataclass
from PIL import Image, ImageOps, UnidentifiedImageError


class InvalidImage(ValueError):
    pass


@dataclass(frozen=True)
class PreparedImage:
    canonical: bytes
    thumbnail: bytes
    width: int
    height: int
    digest: str


def decode_image(data: bytes, max_pixels: int) -> Image.Image:
    if not data:
        raise InvalidImage('Empty image')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in {'JPEG', 'PNG', 'WEBP'}:
                    raise InvalidImage('Only JPEG, PNG and WebP are supported')
                if source.width * source.height > max_pixels:
                    raise InvalidImage('Image exceeds maximum pixel count')
                source.load()
                image = ImageOps.exif_transpose(source)
                # For alpha images composite over white; model expects RGB.
                if image.mode in ('RGBA', 'LA') or 'transparency' in image.info:
                    rgba = image.convert('RGBA')
                    bg = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
                    bg.alpha_composite(rgba)
                    image = bg.convert('RGB')
                else:
                    image = image.convert('RGB')
                return image.copy()
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InvalidImage('Invalid or unsafe image') from exc


def prepare_image(data: bytes, max_pixels: int) -> PreparedImage:
    image = decode_image(data, max_pixels)
    output = io.BytesIO()
    image.save(output, format='WEBP', quality=90, method=4)
    thumb = image.copy()
    thumb.thumbnail((360, 360), Image.Resampling.LANCZOS)
    mini = io.BytesIO()
    thumb.save(mini, format='WEBP', quality=80, method=4)
    return PreparedImage(output.getvalue(), mini.getvalue(), image.width, image.height,
                         hashlib.sha256(output.getvalue()).hexdigest())
