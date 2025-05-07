from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Integer, Float, JSON, Index, Enum
from sqlalchemy.dialects.postgresql import JSONB
from pydantic import BaseModel
from typing import Optional, Union
import enum

Base = declarative_base()

class ProductStatus(enum.Enum):
    verified = 'verified'
    pending = 'pending'
    rejected = 'rejected'
    deleted = 'deleted'

class ProductDB(Base):
    __tablename__ = "products"
    __table_args__ = (
        Index('idx_products_tags_gin', 'tags', postgresql_using='gin'),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_name = Column(String, index=True)
    barcode = Column(String, unique=True, index=True)
    manufacturer = Column(String, nullable=True)
    allergens = Column(JSON, nullable=True)
    score = Column(Float)
    nutrition = Column(JSON, nullable=True)
    extra = Column(JSON, nullable=True)
    image_front = Column(String, nullable=True)
    image_ingredients = Column(String, nullable=True)
    tags = Column(JSONB, nullable=True)
    status = Column(Enum(ProductStatus), default=ProductStatus.pending, nullable=False)

class Product(BaseModel):
    product_name: str
    barcode: str
    manufacturer: Optional[str] = None
    allergens: Optional[Union[dict, str]] = None 
    score: Optional[float] = None
    nutrition: Optional[dict] = None
    extra: Optional[dict] = None
    image_front: Optional[str] = None
    image_ingredients: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[ProductStatus] = None
    model_config = {"from_attributes": True, "extra": "allow"}