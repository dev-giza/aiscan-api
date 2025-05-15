import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from typing import Optional, List
from models import Product, ProductDB, ProductStatus

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

class Database:
    def __init__(self):
        self.engine = engine

    async def init_db(self) -> None:
        if os.getenv("RESET_DB"):
            async with engine.begin() as conn:
                from models import Base
                await conn.run_sync(Base.metadata.drop_all)
        async with self.engine.begin() as conn:
            from models import Base
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
                extra=product.extra,
                image_front=product.image_front,
                image_ingredients=product.image_ingredients,
                tags=product.tags,
                status=product.status or ProductStatus.pending,
            )
            session.add(db_product)
            await session.commit()

    async def get_all_data(self) -> List[Product]:
        async with async_session() as session:
            result = await session.execute(select(ProductDB))
            products = result.scalars().all()
            return [Product.model_validate(p) for p in products]
        
    async def delete_data(self, barcode: str) -> None:
        async with async_session() as session:
            await session.execute(
                ProductDB.__table__.delete().where(ProductDB.barcode == barcode)
            )
            await session.commit()

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
                existing.image_front = product.image_front
                existing.image_ingredients = product.image_ingredients
                existing.tags = product.tags
                existing.status = product.status or ProductStatus.pending
                session.add(existing)
            else:
                db_product = ProductDB(
                    barcode=product.barcode,
                    product_name=product.product_name,
                    manufacturer=product.manufacturer,
                    score=product.score,
                    nutrition=product.nutrition,
                    allergens=product.allergens,
                    extra=product.extra,
                    image_front=product.image_front,
                    image_ingredients=product.image_ingredients,
                    tags=product.tags,
                    status=product.status or ProductStatus.pending,
                )
                session.add(db_product)
            await session.commit()

    async def get_db_product(self, barcode: str) -> Optional[ProductDB]:
        async with async_session() as session:
            result = await session.execute(select(ProductDB).filter(ProductDB.barcode == barcode))
            return result.scalars().first()

db = Database()