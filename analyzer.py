import os
import json
import asyncio
import io
from PIL import Image
from typing import List
from dotenv import load_dotenv
from openai import OpenAI
from database import Product

load_dotenv()

OPENAI_API = os.getenv("OPENAI_API_KEY")
if not OPENAI_API:
    raise ValueError("API не заданы в переменных окружения.")

client = OpenAI(api_key=OPENAI_API)

instructions = (
    "You are an expert in food product analysis, similar to Yuka."
    "Your task is to analyze a product and provide a detailed report strictly as a JSON object. "
    "Return only a valid JSON object without any markdown formatting, code fences, triple backticks, or extra text. "
    "The JSON object must follow exactly this structure: "
    "{"
        "product_name: <string>,"
        "manufacturer: <string,"
        "ingredients: <string>,"
        "overall_score: <number>,"
        "allergens: <string>,"
        "explanation_score: <string>,"
        "nutrition: {"
            "proteins: <number>,"
            "fats: <number>,"
            "carbohydrates: <number>,"
            "calories: <number>,"
            "kcal: <number>,"
        "}"
        "harmful_components: [{"
            "name: <string>,"
            "effect: <string>,"
            "recommendation: <string>,"
        "}],"
        "recommendedfor: <string>,"
        "frequency: <string>,"
        "alternatives: <string>"
    "}"
    "If some data is missing, use null or an empty string."
    "Translate all text values to Russian, while keys remain in English. "
    "Always return only a valid JSON object."
)

async def analyze_data(data: dict) -> dict:
    input_text = json.dumps(data, ensure_ascii=False, indent=2)
    try:
        response = await asyncio.to_thread(
            client.responses.create,
            model="gpt-4.1-nano",
            instructions=instructions,
            input=input_text,
        )
        output = response.output_text.strip()
        try:
            result = json.loads(output)
        except json.JSONDecodeError:
            result = {"analysis": output}
        return result
    except Exception as e:
        print(f"Error analyzing text: {str(e)}")
        return {"analysis": "Unable to analyze text"}

def compress_image(image_bytes: bytes, quality: int = 50) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as img:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        return buffer.getvalue()

async def analyze_image(barcode: str, image_base64_list: List[str]) -> dict:
    messages = [
        {
            "role": "system",
            "content": instructions,
        },
        {
            "role": "user",
            "content": [
                {"type": "text",
                 "text": f"Отсканируй и проанализируй упаковку продукта с баркодом {barcode}. Приложены изображения."+instructions}
            ] + [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}} for img in image_base64_list
            ],
        }
    ]
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4.1",
            messages=messages,
            response_format={"type": "json_object"}
        )
        output = response.choices[0].message.content.strip()
        try:
            result = json.loads(output)
        except json.JSONDecodeError:
            result = {"analysis": output}
        result["barcode"] = barcode
        return result

    except Exception as e:
        print(f"Error analyzing images: {str(e)}")
        return {"analysis": "Unable to analyze images", "barcode": barcode}