import os
import json
import asyncio
from typing import List
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

class Analyzer:
    def __init__(self):
        OPENAI_API = os.getenv("OPENAI_API_KEY")
        if not OPENAI_API:
            raise ValueError("API не заданы в переменных окружения.")
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        self.instructions = (
            "You are an expert in food product analysis, like Yuka."
            "Return only a valid JSON object with this structure: "
            "{"
                "product_name: <string>,"
                "manufacturer: <string,"
                "ingredients: <string>,"
                "allergens: <string>,"
                "overall_score: <number>,"
                "explanation_score: <string>"
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
                    "level: <string>,"
                    "risk_group: <string>,"
                    "severity: <string>,"
                "}],"
                "recommendedfor: <string>,"
                "frequency: <string>,"
                "alternatives: <string>,"
                "tags: [<string>, ...],"
            "}"
            "Only process food or personal care/hygiene products. If the item is unrelated, return {}."
            "If the scanned product is outside these categories (e.g. electronics, tools, toys), return an empty JSON object: {} "



            "Translate all text values (not keys) to Russian. Ensure 'product_name' is natural Russian. Translate it if needed."
            "Add explanation for the score and the score itself. Make sure it's in Russian, short and clear."

            "Important: If the product has no harmful components, is made with natural ingredients, and is generally suitable for most people — the score must be higher than 85."
            "Important: Double-check the logic of your score. If the explanation or ingredients are good — the score should reflect that."
            "Assign a fair and objective 'score' from 0 to 100. Use this scale:"
            "- 0–25: very unhealthy (many additives like E621, preservatives, flavor enhancers, high salt/fat)"
            "- 25–50: poor quality (contains harmful additives or high calories/sodium)"
            "- 50–75: acceptable (some additives, but balanced)"
            "- 75–100: healthy (natural, few/no additives, good nutritional profile)"
        
            "Explanation_score must clearly justify the 'score'. Mention both harmful (E-additives, fat, sugar, salt) and healthy aspects (natural, vitamins). Avoid vague answers."
            "Score must reflect the presence of harmful additives (E621, E635, etc.) and nutrition."
    
            "List all harmful E-additives in both 'ingredients' and 'harmful_components'."
            "In 'tags', include 3–6 useful labels like: 'продукты питания', 'гигиена', 'говядина', 'без глютена', 'полуфабрикаты'."
            "Before returning the final JSON, carefully review all values. Avoid extreme scores unless well justified, and ensure overall consistency in the output."
        )

    async def analyze_data(self,data: dict) -> dict:
        input_text = json.dumps(data, ensure_ascii=False, indent=2)
        try:
            response = await asyncio.to_thread(
                self.client.responses.create,
                model="gpt-4.1-nano",
                instructions=self.instructions,
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

    async def analyze_image(self,barcode: str, image_base64_list: List[str]) -> dict:
        messages = [
            {
                "role": "system",
                "content": self.instructions,
            },
            {
                "role": "user",
                "content": [
                    {"type": "text",
                    "text": f"Отсканируй и проанализируй упаковку продукта с баркодом {barcode}. Приложены изображения. " + self.instructions}
                ] + [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}} for img in image_base64_list
                ],
            }
        ]
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
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
        
analyzer = Analyzer()
