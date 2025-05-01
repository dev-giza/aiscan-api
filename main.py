
import io
import os
import base64
from PIL import Image
import uvicorn
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from typing import List

from database import db, Product
from analyzer import analyze_data, analyze_image, compress_image
from parser import fetch_from_openfoodfacts, fetch_product_name

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {"jpeg", "jpg", "png", "webp"}

def convert_to_jpeg(image_bytes: bytes) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as img:
        buffer = io.BytesIO()
        rgb_img = img.convert('RGB')  # На случай, если исходник был с альфа-каналом (например, PNG)
        rgb_img.save(buffer, format="JPEG", quality=90)
        return buffer.getvalue()

app = FastAPI(title="AIScan API")

@app.on_event("startup")
async def startup_event():
    await db.init_db()

@app.get("/find/{barcode}", response_model=Product)
async def find_product(barcode: str):
    # DB
    existing = await db.find_data(barcode)
    if existing:
        return existing

    # API 1
    details = await fetch_from_openfoodfacts(barcode)
    if details and details.get("product_name") and details.get("ingredients_text"):
        # Analyzer
        analysis = await analyze_data(details)

        # Формируем новый объект Product, распределяя данные по полям:
        new_product = Product(
            barcode=barcode,
            product_name=analysis.get("product_name", "No Product Name"),
            manufacturer=analysis.get("manufacturer"),  
            score=analysis.get("overall_score"),
            nutrition=analysis.get("nutrition"),
            allergens=analysis.get("allergens"),
            image_front=details.get("image_front_url"),
            image_ingredients=details.get("image_ingredients_url"),
            extra={
                "ingredients": analysis.get("ingredients"),
                "explanation_score": analysis.get("explanation_score"),
                "harmful_components": analysis.get("harmful_components"),
                "recommendedfor": analysis.get("recommendedfor"),
                "frequency": analysis.get("frequency"),
                "alternatives": analysis.get("alternatives")
            }
        )
        await db.save_data(new_product)
        return new_product

    fallback_details = await fetch_product_name(barcode)
    if not fallback_details:
        raise HTTPException(status_code=404, detail="Информация о продукте не найдена")
    product_name = fallback_details.get("product_name", "No Product Name")

    fallback_details.pop("product_name", None)
    new_product = Product(barcode=barcode, product_name=product_name, **fallback_details)
    await db.save_data(new_product)
    return new_product


@app.post("/update", response_model=Product)
async def update_product(barcode: str, images: List[UploadFile] = File(...)):
    if len(images) != 2:
        raise HTTPException(status_code=400, detail="Нужно загрузить ровно 2 фотографии: фронт и состав.")
    # images
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
        
        compressed = convert_to_jpeg(contents)

        suffix = "front" if i == 0 else "ingredients"
        filename = f"{barcode}_{suffix}.jpg"
        filepath = os.path.join("static/images", filename)
        with open(filepath, "wb") as f:
            f.write(compressed)
        url_path = f"https://iscan.store/static/images/{filename}"
        image_paths.append(url_path)

        encoded = base64.b64encode(compressed).decode('utf-8')
        base64_images.append(encoded)

    analysis = await analyze_image(barcode, base64_images)
    fallback_details = await fetch_product_name(barcode)
    new_product = Product(
        barcode=barcode,
        product_name=fallback_details.get("product_name", "No Product Name"),
        manufacturer=analysis.get("manufacturer"),
        score=analysis.get("overall_score", 0),
        nutrition=analysis.get("nutrition"),
        allergens=analysis.get("allergens"),
        image_front=image_paths[0],
        image_ingredients=image_paths[1],
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

@app.post("/reprocess/{barcode}", response_model=Product)
async def reprocess_product(barcode: str):
    # Удаляем существующий продукт
    existing = await db.find_data(barcode)
    if existing:
        await db.delete_data(barcode)

    # Повторно ищем как в /find
    details = await fetch_from_openfoodfacts(barcode)
    if details and details.get("product_name") and details.get("ingredients_text"):
        analysis = await analyze_data(details)
        new_product = Product(
            barcode=barcode,
            product_name=analysis.get("product_name", "No Product Name"),
            manufacturer=analysis.get("manufacturer"),
            score=analysis.get("overall_score"),
            nutrition=analysis.get("nutrition"),
            allergens=analysis.get("allergens"),
            image_front=details.get("image_front_url"),
            image_ingredients=details.get("image_ingredients_url"),
            extra={
                "ingredients": analysis.get("ingredients"),
                "explanation_score": analysis.get("explanation_score"),
                "harmful_components": analysis.get("harmful_components"),
                "recommendedfor": analysis.get("recommendedfor"),
                "frequency": analysis.get("frequency"),
                "alternatives": analysis.get("alternatives")
            }
        )
        await db.save_data(new_product)
        return new_product

    fallback_details = await fetch_product_name(barcode)
    if fallback_details:
        product_name = fallback_details.get("product_name", "No Product Name")
        fallback_details.pop("product_name", None)
        new_product = Product(barcode=barcode, product_name=product_name, **fallback_details)
        await db.save_data(new_product)
        return new_product

    raise HTTPException(status_code=404, detail="Не удалось переанализировать продукт")

@app.get("/products", response_model=List[Product])
async def get_all_products():
    return await db.get_all_data()

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)