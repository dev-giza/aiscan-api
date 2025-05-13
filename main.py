import uvicorn
from fastapi import FastAPI
from database import db
from routes import panel_router, scanner_router


app = FastAPI(title="Yumi API")

app.include_router(scanner_router)
app.include_router(panel_router)

@app.on_event("startup")
async def startup_event():
    await db.init_db()


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)