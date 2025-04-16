import base64
import uvicorn
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from typing import List

from database import db, Product
from analyzer import analyze_data, analyze_image, compress_image
from parser import fetch_from_openfoodfacts, fetch_from_barcode_list


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
    if details:
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

    fallback_details = await fetch_from_barcode_list(barcode)
    if fallback_details:
        product_name = fallback_details.get("product_name", "No Product Name")
        fallback_details.pop("product_name", None)
        new_product = Product(barcode=barcode, product_name=product_name, **fallback_details)
        await db.save_data(new_product)
        return new_product

    raise HTTPException(status_code=404, detail="Продукт не найден")

@app.post("/update", response_model=Product)
async def update_product(barcode: str, images: List[UploadFile] = File(...)):
    # images
    image_base64_list = []
    for image in images:
        contents = await image.read()
        compressed = compress_image(contents, quality=90) 
        encoded = base64.b64encode(compressed).decode('utf-8')
        image_base64_list.append(encoded)
    analysis = await analyze_image(barcode, image_base64_list)
    fallback_details = await fetch_from_barcode_list(barcode)
    new_product = Product(
        barcode=barcode,
        product_name=fallback_details.get("product_name", "No Product Name"),
        manufacturer=analysis.get("manufacturer"),
        score=analysis.get("overall_score", 0),
        nutrition=analysis.get("nutrition"),
        allergens=analysis.get("allergens"),
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


@app.get("/products", response_model=List[Product])
async def get_all_products():
    return await db.get_all_data()

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)