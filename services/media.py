import io
from PIL import Image


class Media:
    def convert_to_jpeg(self, image_bytes: bytes) -> bytes:
        with Image.open(io.BytesIO(image_bytes)) as img:
            buffer = io.BytesIO()
            rgb_img = img.convert('RGB')  # На случай, если исходник был с альфа-каналом (например, PNG)
            rgb_img.save(buffer, format="JPEG", quality=90)
            return buffer.getvalue()
        
    def compress_image(self,image_bytes: bytes, quality: int = 50) -> bytes:
        with Image.open(io.BytesIO(image_bytes)) as img:
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality)
            return buffer.getvalue()

media = Media()