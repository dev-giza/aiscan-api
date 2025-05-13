from fastapi import APIRouter, HTTPException, UploadFile, File, Header, Depends
from typing import List
import base64
import os
from database import db, Product, ProductStatus
from services.analyzer import analyzer
from services.parser import parser
from services.media import media
from services.locker import verify_api_key
import requests
import asyncio

router = APIRouter(tags=["Scanner"])

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {"jpeg", "jpg", "png", "webp"}

def download_and_save_image_sync(url: str, barcode: str, suffix: str = "roskachestvo") -> str:
    filename = f"{barcode}_{suffix}.jpg"
    filepath = os.path.join("static/images", filename)
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, timeout=10, headers=headers)
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            if not any(img in content_type for img in ("image/jpeg", "image/png", "image/webp")):
                print(f"Файл по ссылке {url} не является изображением (jpeg/png/webp), content-type: {content_type}")
                return None
            os.makedirs("static/images", exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(response.content)
            return f"https://iscan.store/static/images/{filename}"
        else:
            print(f"Не удалось скачать изображение: {url}, статус {response.status_code}")
    except Exception as e:
        print(f"Ошибка при скачивании изображения: {e}")
    return None

@router.get("/find/{barcode}", response_model=Product)
async def find_product(
    barcode: str,
    api_key: None = Depends(lambda x_api_key: verify_api_key(os.getenv("API_SECRET_KEY"), x_api_key))
):
    parser.validate_barcode(barcode)
    existing = await db.find_data(barcode)
    if existing:
        return existing
    # Сначала пробуем Роскачество
    roskachestvo_data = await parser.fetch_from_roskachestvo(barcode)
    if roskachestvo_data and roskachestvo_data.get("product", {}).get("title"):
        image_url = roskachestvo_data["product"].get("thumbnail")
        local_image_url = None
        if image_url:
            local_image_url = await asyncio.to_thread(download_and_save_image_sync, image_url, barcode, "roskachestvo")
        analysis = await analyzer.analyze_data(roskachestvo_data["product"])
        new_product = Product(
            barcode=barcode,
            product_name=analysis.get("product_name", roskachestvo_data["product"].get("title", "No Product Name")),
            manufacturer=analysis.get("manufacturer", roskachestvo_data["product"].get("manufacturer")),
            score=analysis.get("overall_score", roskachestvo_data["product"].get("total_rating")),
            nutrition=analysis.get("nutrition"),
            allergens=analysis.get("allergens"),
            image_front=local_image_url or roskachestvo_data["product"].get("thumbnail"),
            image_ingredients=None,
            tags=analysis.get("tags"),
            status=ProductStatus.verified,
            extra={
                "description": roskachestvo_data["product"].get("description"),
                "category_name": roskachestvo_data["product"].get("category_name"),
                "ingredients": analysis.get("ingredients"),
                "explanation_score": analysis.get("explanation_score"),
                "harmful_components": analysis.get("harmful_components"),
                "recommendedfor": analysis.get("recommendedfor"),
                "frequency": analysis.get("frequency"),
                "alternatives": analysis.get("alternatives"),
                "roskachestvo_recommendations": roskachestvo_data.get("recommendations", [])
            }
        )
        await db.save_data(new_product)
        return new_product
    # Если нет в Роскачестве — пробуем OpenFoodFacts
    details = await parser.fetch_from_openfoodfacts(barcode)
    if details and details.get("product_name") and details.get("ingredients_text"):
        analysis = await analyzer.analyze_data(details)
        new_product = Product(
            barcode=barcode,
            product_name=analysis.get("product_name", "No Product Name"),
            manufacturer=analysis.get("manufacturer"),  
            score=analysis.get("overall_score"),
            nutrition=analysis.get("nutrition"),
            allergens=analysis.get("allergens"),
            image_front=details.get("image_front_url"),
            image_ingredients=details.get("image_ingredients_url"),
            tags=analysis.get("tags"),
            status=ProductStatus.verified,
            extra={
                "ingredients": analysis.get("ingredients"),
                "explanation_score": analysis.get("explanation_score"),
                "harmful_components": analysis.get("harmful_components"),
                "recommendedfor": analysis.get("recommendedfor"),
                "frequency": analysis.get("frequency"),
                "alternatives": analysis.get("alternatives"),
            }
        )
        await db.save_data(new_product)
        return new_product
    # Если не найдено ни в Роскачестве, ни в OpenFoodFacts — ищем в barcode-list
    exists = await parser.product_exists_in_barcode_lists(barcode)
    if not exists:
        raise HTTPException(status_code=404, detail="Продукт с таким штрихкодом не найден ни в одной базе")
    # Если найден только в barcode-list, сохраняем только barcode и возвращаем null-данные
    empty_product = Product(
        barcode=barcode,
        product_name="",
        manufacturer=None,
        score=None,
        nutrition=None,
        allergens=None,
        image_front=None,
        image_ingredients=None,
        tags=None,
        status=None,
        extra=None
    )
    await db.save_data(empty_product)
    return empty_product

@router.post("/update", response_model=Product)
async def update_product(
    barcode: str,
    images: List[UploadFile] = File(...),
    api_key: None = Depends(lambda x_api_key: verify_api_key(os.getenv("API_SECRET_KEY"), x_api_key))
):
    parser.validate_barcode(barcode)
    if len(images) != 2:
        raise HTTPException(status_code=400, detail="Нужно загрузить ровно 2 фотографии: фронт и состав.")
    image_paths = []
    base64_images = []
    os.makedirs("static/images", exist_ok=True)
    for i, image in enumerate(images):
        contents = await image.read()
        if len(contents) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413, 
                detail=f"Файл {image.filename} слишком большой. Максимальный размер: {MAX_FILE_SIZE_MB}MB."
            )
        filename_lower = image.filename.lower()
        if not any(filename_lower.endswith(f".{ext}") for ext in ALLOWED_EXTENSIONS):
            raise HTTPException(
                status_code=400,
                detail=f"Недопустимый формат файла {image.filename}. Разрешены только: {', '.join(ALLOWED_EXTENSIONS)}."
            )
        compressed = media.convert_to_jpeg(contents)
        suffix = "front" if i == 0 else "ingredients"
        filename = f"{barcode}_{suffix}.jpg"
        filepath = os.path.join("static/images", filename)
        with open(filepath, "wb") as f:
            f.write(compressed)
        url_path = f"https://iscan.store/static/images/{filename}"
        image_paths.append(url_path)
        encoded = base64.b64encode(compressed).decode('utf-8')
        base64_images.append(encoded)
    analysis = await analyzer.analyze_image(barcode, base64_images)
    new_product = Product(
        barcode=barcode,
        product_name=analysis.get("product_name", "No Product Name"),
        manufacturer=analysis.get("manufacturer"),
        score=analysis.get("overall_score", 0),
        nutrition=analysis.get("nutrition"),
        allergens=analysis.get("allergens"),
        image_front=image_paths[0],
        image_ingredients=image_paths[1],
        tags=analysis.get("tags"),
        status=ProductStatus.pending,
        extra={
            "ingredients": analysis.get("ingredients"),
            "explanation_score": analysis.get("explanation_score"),
            "harmful_components": analysis.get("harmful_components"),
            "recommendedfor": analysis.get("recommendedfor"),
            "frequency": analysis.get("frequency"),
            "alternatives": analysis.get("alternatives")
        }
    )
    await db.upsert_data(new_product)
    return new_product 