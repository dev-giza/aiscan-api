from fastapi import APIRouter, HTTPException, Header, Depends, Query, Body
from typing import List, Dict
from database import db, Product, ProductDB
import os
from services.locker import verify_api_key
from sqlalchemy import select
from services.parser import parser
import requests
import asyncio
from services.analyzer import analyzer

router = APIRouter(tags=["Panel"])

@router.get("/products", response_model=List[Product])
async def panel_get_all_products(
    api_key: None = Depends(lambda x_api_admin_key: verify_api_key(os.getenv("API_ADMIN_KEY"), x_api_admin_key))
):
    return await db.get_all_data()

@router.get("/products/{barcode}", response_model=Product)
async def panel_get_product(barcode: str, api_key: None = Depends(lambda x_api_admin_key: verify_api_key(os.getenv("API_ADMIN_KEY"), x_api_admin_key))):
    product = await db.find_data(barcode)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    return product

@router.post("/products/batch-roskachestvo")
async def batch_import_roskachestvo(
    barcodes: List[str] = Body(..., embed=True),
    api_key: None = Depends(lambda x_api_admin_key: verify_api_key(os.getenv("API_ADMIN_KEY"), x_api_admin_key))
) -> Dict[str, str]:
    results = {}
    for barcode in barcodes:
        parser.validate_barcode(barcode)
        try:
            roskachestvo_data = await parser.fetch_from_roskachestvo(barcode)
            if not roskachestvo_data or not roskachestvo_data.get("product", {}).get("title"):
                results[barcode] = "not_found"
                continue
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
                status="verified",
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
            await db.upsert_data(new_product)
            results[barcode] = "ok"
            await asyncio.sleep(1)  # чтобы не получить бан от Роскачества
        except Exception as e:
            results[barcode] = f"error: {e}"
    return results

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

@router.patch("/products/{barcode}", response_model=Product)
async def panel_update_product(
    barcode: str,
    product_update: Product = Body(...),
    api_key: None = Depends(lambda x_api_admin_key: verify_api_key(os.getenv("API_ADMIN_KEY"), x_api_admin_key))
):
    async with db.engine.begin() as conn:
        result = await conn.execute(select(ProductDB).where(ProductDB.barcode == barcode))
        db_product = result.scalars().first()
        if not db_product:
            raise HTTPException(status_code=404, detail="Продукт не найден")
        update_data = product_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_product, key, value)
        conn.add(db_product)
    return Product.model_validate(db_product) 