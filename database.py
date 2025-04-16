import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, Integer, Float, select, JSON
from pydantic import BaseModel
from typing import Optional, Union, List

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не задан в переменных окружения.")

# Важно: используем драйвер asyncpg и отключаем кэширование подготовленных запросов
engine = create_async_engine(
    DATABASE_URL, 
    echo=True, 
    connect_args={"statement_cache_size": 0}
)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()


class ProductDB(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_name = Column(String, index=True)
    barcode = Column(String, unique=True, index=True)
    manufacturer = Column(String, nullable=True)
    allergens = Column(JSON, nullable=True)
    score = Column(Float)
    nutrition = Column(JSON, nullable=True)
    extra = Column(JSON, nullable=True)


class Product(BaseModel):
    product_name: str
    barcode: str
    manufacturer: Optional[str] = None
    allergens: Optional[Union[dict, str]] = None 
    score: Optional[float] = None
    nutrition: Optional[dict] = None
    extra: Optional[dict] = None


    model_config = {
        "from_attributes": True,
        "extra": "allow",
    }


class Database:
    def __init__(self):
        self.engine = engine

    async def init_db(self) -> None:

        # Cleaner
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            print("Все таблицы удалены.")

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def find_data(self, barcode: str) -> Optional[Product]:
        async with async_session() as session:
            result = await session.execute(select(ProductDB).filter(ProductDB.barcode == barcode))
            product_instance = result.scalars().first()
            if product_instance:
                return Product.model_validate(product_instance)
            return None

    async def save_data(self, product: Product) -> None:
        async with async_session() as session:
            db_product = ProductDB(
                barcode=product.barcode,
                product_name=product.product_name,
                manufacturer=product.manufacturer,
                score=product.score,
                nutrition=product.nutrition,
                allergens=product.allergens,
                extra=product.extra
            )
            session.add(db_product)
            await session.commit()
            print(f"Данные по баркоду {product.barcode} сохранены.")

    async def get_all_data(self) -> List[Product]:
        async with async_session() as session:
            result = await session.execute(select(ProductDB))
            products = result.scalars().all()
            return [Product.model_validate(p) for p in products]

    async def upsert_data(self, product: Product) -> None:
        async with async_session() as session:
            result = await session.execute(select(ProductDB).filter_by(barcode=product.barcode))
            existing = result.scalars().first()
            if existing:
                existing.product_name = product.product_name
                existing.manufacturer = product.manufacturer
                existing.score = product.score
                existing.nutrition = product.nutrition
                existing.allergens = product.allergens
                existing.extra = product.extra
                session.add(existing)
                print(f"Обновлены данные по баркоду {product.barcode}")
            else:
                db_product = ProductDB(
                    barcode=product.barcode,
                    product_name=product.product_name,
                    manufacturer=product.manufacturer,
                    score=product.score,
                    nutrition=product.nutrition,
                    allergens=product.allergens,
                    extra=product.extra
                )
                session.add(db_product)
                print(f"Добавлены данные по баркоду {product.barcode}")
            await session.commit()




db = Database()