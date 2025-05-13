import os
from fastapi import HTTPException, Header

def verify_api_key(expected_key: str,x_api_key: str = Header(...)):
    # Отключаем проверку, если RESET_DB=True
    if os.getenv("RESET_DB", "False").lower() == "true":
        return
    if not expected_key or x_api_key != expected_key:
        raise HTTPException(status_code=403, detail="Forbidden: invalid API key")