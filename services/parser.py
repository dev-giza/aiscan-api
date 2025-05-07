import os
import httpx
import requests
import openai
from typing import Optional
import json


class Parser:
    def __init__(self):
        # ChatGPT
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            print("Предупреждение: OPENAI_API_KEY не найден в переменных окружения")
        openai.api_key = self.api_key

    # Для очистки данных пришедших с openfoodfacts
    def extract_product_details(self, product: dict) -> dict:
        """
        Извлекаем только нужные поля из ответа OpenFoodFacts.
        """
        return {
            "product_name": product.get("product_name") or product.get("generic_name") or "No Title",
            "ingredients_text": product.get("ingredients_text", ""),
            "brands": product.get("brands", ""),
            "categories": product.get("categories", ""),
            "categories_old": product.get("categories_old", ""),
            "allergens": product.get("allergens", ""),
            "allergens_from_ingredients": product.get("allergens_from_ingredients", ""),
            "allergens_from_user": product.get("allergens_from_user", ""),
            "origins": product.get("origins", ""),
            "additives_original_tags": product.get("additives_original_tags", ""),
            "additives_tags": product.get("additives_tags", ""),
            "compared_to_category": product.get("compared_to_category", ""),
            "countries": product.get("countries", ""),
            "created_t": product.get("created_t", ""),
            "data_sources": product.get("data_sources", ""),
            "image_front_url": product.get("image_front_url", ""),
            "image_ingredients_url": product.get("image_ingredients_url", ""),
            "ingredients": product.get("ingredients", ""),
            "labels": product.get("labels", ""),
            "known_ingredients_n": product.get("known_ingredients_n", ""),
            "nutriments": product.get("nutriments", ""),
            "serving_quantity": product.get("serving_quantity", ""),
            "serving_quantity_unit": product.get("serving_quantity_unit", ""),
            "serving_size": product.get("serving_size", ""),
        }

    # Возвращает большой массив данных
    async def fetch_from_openfoodfacts(self, barcode: str) -> Optional[dict]:
        """
        Асинхронно обращаемся к OpenFoodFacts, фильтруем данные.
        """
        url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == 1:
                    product = data.get("product", {})
                    return self.extract_product_details(product)
        except Exception as e:
            print(f"Ошибка при получении данных с OpenFoodFacts: {e}")
        return None


    async def fetch_from_roskachestvo(self, barcode: str) -> Optional[dict]:
        url = f"https://rskrf.ru/rest/1/search/barcode?barcode={barcode}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            data = response.json()
            response_data = data.get("response", {})
            research = response_data.get("research", {})
            
            # Extract main product data
            main_product = {
                "title": response_data.get("title", ""),
                "total_rating": response_data.get("total_rating", 0),
                "description": response_data.get("description", ""),
                "category_name": response_data.get("category_name", ""),
                "manufacturer": response_data.get("manufacturer", ""),
                "thumbnail": response_data.get("thumbnail", ""),
            }
            
            # Add research data if available
            if research:
                main_product["image"] = research.get("image", "")
            
            # Extract recommendations - this can handle any quantity
            # recommendations = []
            # for rec in response_data.get("recommendations", []):
            #     recommendation = {
            #         "id": rec.get("id", ""),
            #         "title": rec.get("title", ""),
            #         "total_rating": rec.get("total_rating", 0),
            #         "manufacturer": rec.get("manufacturer", ""),
            #         "price": rec.get("price", ""),
            #         "thumbnail": rec.get("thumbnail", ""),
            #         "category_name": rec.get("category_name", "")
            #     }
            #     recommendations.append(recommendation)
            
            result = {
                "product": main_product,
            }
            
            return result
            
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            print(f"Error: {e}")
            return None
        
parser = Parser()