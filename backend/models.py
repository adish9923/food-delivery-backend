from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from database import Base
from datetime import datetime

class Food(Base):
    __tablename__ = "foods"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    price = Column(Float)
    image = Column(String(500))
    category = Column(String(50), default="General")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    food_id = Column(Integer, ForeignKey("foods.id"))
    name = Column(String(100))
    price = Column(Float)
    quantity = Column(Integer, default=1)
    image = Column(String(500))

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    items = Column(String(1000))  # JSON string of order items
    total = Column(Float)
    customer_name = Column(String(100))
    phone = Column(String(20))
    address = Column(String(500))
    status = Column(String(50), default="confirmed")
    created_at = Column(DateTime, default=datetime.utcnow)
