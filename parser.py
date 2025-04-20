import httpx
from bs4 import BeautifulSoup
from typing import Optional

# Для очистки данных пришедших с openfoodfacts
def extract_product_details(product: dict) -> dict:
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
async def fetch_from_openfoodfacts(barcode: str) -> Optional[dict]:
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
                return extract_product_details(product)
    except Exception as e:
        print(f"Ошибка при получении данных с OpenFoodFacts: {e}")
    return None

async def fetch_from_barcode_list(barcode: str) -> Optional[dict]:
    """
    Фолбэк: Получает минимальные данные с barcode-list.ru.
    Из HTML-страницы ищем таблицу с классом "randomBarcodes", пропускаем первую (заголовочную) строку
    и извлекаем название продукта из третьего <td> первой строки данных.
    """
    BARCODELIST_URL = "https://barcode-list.ru/barcode/RU/%D0%9F%D0%BE%D0%B8%D1%81%D0%BA.htm?barcode={barcode}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(BARCODELIST_URL.format(barcode=barcode), timeout=10)
            if response.status_code == 200:
                html_text = response.text
                soup = BeautifulSoup(html_text, "html.parser")
                table = soup.find("table", class_="randomBarcodes")
                if table:
                    rows = table.find_all("tr")
                    # Проверяем, что есть минимум две строки (первая – заголовок, вторая – данные)
                    if len(rows) > 1:
                        data_row = rows[1]  # первая строка данных
                        tds = data_row.find_all("td")
                        if len(tds) >= 3:
                            product_name = tds[2].get_text(strip=True)
                            return {"product_name": product_name}
        except Exception as e:
            print(f"Ошибка при запросе Barcode List: {e}")
    return None


async def fetch_from_barcode_list_com(barcode: str) -> Optional[dict]:
    """
    Альтернативный фолбэк: Получает данные с barcode-list.com.
    Извлекает название продукта из таблицы, где класс — 'randomBarcodes'.
    """
    BARCODELIST_COM_URL = f"https://barcode-list.com/barcode/EN/barcode-{barcode}/Search.htm"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(BARCODELIST_COM_URL, timeout=10)
            if response.status_code == 200:
                html_text = response.text
                soup = BeautifulSoup(html_text, "html.parser")
                table = soup.find("table", class_="randomBarcodes")
                if not table:
                    table = soup.find("table")  
                if table:
                    rows = table.find_all("tr")
                    if len(rows) > 1:
                        data_row = rows[1]
                        tds = data_row.find_all("td")
                        if len(tds) >= 3:
                            product_name = tds[2].text.strip()
                            return {"product_name": product_name}
        except Exception as e:
            print(f"Ошибка при запросе Barcode List COM: {e}")
    return None

async def fetch_product_name(barcode: str) -> Optional[dict]:
    result = await fetch_from_barcode_list(barcode)
    print(result)
    if not result:
        result = await fetch_from_barcode_list_com(barcode)
    return result