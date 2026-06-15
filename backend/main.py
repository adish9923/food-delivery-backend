from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from database import engine, SessionLocal
from models import Base, Food, CartItem, Order, User
import json
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import Body

app = FastAPI()

# CORS - allow frontend to call API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

# ───── Pydantic Schemas ─────

class OrderCreate(BaseModel):
    items: list
    total: float
    customer_name: str
    phone: str
    address: str

class CartItemCreate(BaseModel):
    food_id: int
    name: str
    price: float
    image: str

class CartItemUpdate(BaseModel):
    quantity: int

class FoodCreate(BaseModel):
    name: str
    price: float
    image: str = ""
    category: str = "General"

class FoodUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    image: Optional[str] = None
    category: Optional[str] = None

# ───── Auth Config ─────
SECRET_KEY = "foodie-express-secret-key-2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

class SignupRequest(BaseModel):
    username: str
    email: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    email: str
    user_id: int

# ───── Helpers ─────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str = Depends(security)):
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    credentials_exception = HTTPException(status_code=401, detail="Invalid token")
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
        return user_id
    except JWTError:
        raise credentials_exception

# ───── Auth Endpoints ─────

@app.post("/auth/signup", response_model=AuthResponse)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = pwd_context.hash(req.password)
    user = User(username=req.username, email=req.email, hashed_password=hashed)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"user_id": user.id, "username": user.username})
    return AuthResponse(access_token=token, username=user.username, email=user.email, user_id=user.id)

@app.post("/auth/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not pwd_context.verify(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({"user_id": user.id, "username": user.username})
    return AuthResponse(access_token=token, username=user.username, email=user.email, user_id=user.id)

@app.get("/auth/me")
def get_me(user_id: int = Depends(verify_token), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user.id, "username": user.username, "email": user.email, "created_at": str(user.created_at)}

# ───── Food Endpoints ─────

@app.get("/")
def home():
    return {"message": "Food Delivery API Running"}

@app.post("/add-food")
def add_food(name: str = "Chicken Biryani", price: float = 299, image: str = "", category: str = "General", db: Session = Depends(get_db)):
    food = Food(name=name, price=price, image=image, category=category)
    db.add(food)
    db.commit()
    return {"message": f"{name} added successfully"}

@app.get("/foods")
def get_foods(category: str = None, db: Session = Depends(get_db)):
    q = db.query(Food)
    if category:
        q = q.filter(Food.category == category)
    foods = q.all()
    return [
        {"id": f.id, "name": f.name, "price": f.price, "image": f.image, "category": f.category}
        for f in foods
    ]

@app.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    cats = db.query(Food.category).distinct().all()
    return [c[0] for c in cats if c[0]]

# ───── Admin Food CRUD Endpoints ─────

@app.post("/admin/foods")
def admin_create_food(food: FoodCreate, db: Session = Depends(get_db)):
    """Create a new food item"""
    new_food = Food(name=food.name, price=food.price, image=food.image, category=food.category)
    db.add(new_food)
    db.commit()
    db.refresh(new_food)
    return {
        "id": new_food.id,
        "name": new_food.name,
        "price": new_food.price,
        "image": new_food.image,
        "category": new_food.category,
        "message": f"{food.name} added successfully"
    }

@app.put("/admin/foods/{food_id}")
def admin_update_food(food_id: int, food: FoodUpdate, db: Session = Depends(get_db)):
    """Update an existing food item"""
    existing = db.query(Food).filter(Food.id == food_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Food not found")
    
    if food.name is not None:
        existing.name = food.name
    if food.price is not None:
        existing.price = food.price
    if food.image is not None:
        existing.image = food.image
    if food.category is not None:
        existing.category = food.category
    
    db.commit()
    db.refresh(existing)
    return {
        "id": existing.id,
        "name": existing.name,
        "price": existing.price,
        "image": existing.image,
        "category": existing.category,
        "message": f"{existing.name} updated successfully"
    }

@app.delete("/admin/foods/{food_id}")
def admin_delete_food(food_id: int, db: Session = Depends(get_db)):
    """Delete a food item"""
    existing = db.query(Food).filter(Food.id == food_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Food not found")
    
    name = existing.name
    # Also remove from any carts
    db.query(CartItem).filter(CartItem.food_id == food_id).delete()
    db.delete(existing)
    db.commit()
    return {"message": f"{name} deleted successfully", "id": food_id}

@app.get("/admin/foods/{food_id}")
def admin_get_food(food_id: int, db: Session = Depends(get_db)):
    """Get single food item details"""
    food = db.query(Food).filter(Food.id == food_id).first()
    if not food:
        raise HTTPException(status_code=404, detail="Food not found")
    return {
        "id": food.id,
        "name": food.name,
        "price": food.price,
        "image": food.image,
        "category": food.category
    }

# ───── Cart Endpoints (User-Scoped) ─────

@app.get("/cart")
def get_cart(user_id: int = Depends(verify_token), db: Session = Depends(get_db)):
    items = db.query(CartItem).filter(CartItem.user_id == user_id).all()
    total = sum(item.price * item.quantity for item in items)
    return {
        "items": [
            {
                "id": item.id,
                "food_id": item.food_id,
                "name": item.name,
                "price": item.price,
                "quantity": item.quantity,
                "image": item.image,
            }
            for item in items
        ],
        "total": round(total, 2),
    }

@app.post("/cart/add")
def add_to_cart(item: CartItemCreate, user_id: int = Depends(verify_token), db: Session = Depends(get_db)):
    # Check if already in cart for this user
    existing = db.query(CartItem).filter(
        CartItem.food_id == item.food_id,
        CartItem.user_id == user_id
    ).first()
    if existing:
        existing.quantity += 1
    else:
        cart_item = CartItem(
            user_id=user_id,
            food_id=item.food_id,
            name=item.name,
            price=item.price,
            quantity=1,
            image=item.image,
        )
        db.add(cart_item)
    db.commit()
    return {"message": f"{item.name} added to cart"}

@app.put("/cart/update/{item_id}")
def update_cart_item(item_id: int, data: CartItemUpdate, user_id: int = Depends(verify_token), db: Session = Depends(get_db)):
    item = db.query(CartItem).filter(
        CartItem.id == item_id,
        CartItem.user_id == user_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if data.quantity <= 0:
        db.delete(item)
    else:
        item.quantity = data.quantity
    db.commit()
    return {"message": "Cart updated"}

@app.delete("/cart/remove/{item_id}")
def remove_from_cart(item_id: int, user_id: int = Depends(verify_token), db: Session = Depends(get_db)):
    item = db.query(CartItem).filter(
        CartItem.id == item_id,
        CartItem.user_id == user_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"message": "Item removed from cart"}

@app.delete("/cart/clear")
def clear_cart(user_id: int = Depends(verify_token), db: Session = Depends(get_db)):
    db.query(CartItem).filter(CartItem.user_id == user_id).delete()
    db.commit()
    return {"message": "Cart cleared"}

# ───── Order Endpoints ─────

@app.post("/orders")
def place_order(order: OrderCreate, user_id: int = Depends(verify_token), db: Session = Depends(get_db)):
    new_order = Order(
        user_id=user_id,
        items=json.dumps(order.items),
        total=order.total,
        customer_name=order.customer_name,
        phone=order.phone,
        address=order.address,
        status="confirmed",
        created_at=datetime.utcnow(),
    )
    db.add(new_order)
    # Clear user's cart after order
    db.query(CartItem).filter(CartItem.user_id == user_id).delete()
    db.commit()
    return {"message": "Order placed successfully!", "order_id": new_order.id}

@app.get("/orders")
def get_orders(user_id: int = Depends(verify_token), db: Session = Depends(get_db)):
    orders = db.query(Order).filter(Order.user_id == user_id).order_by(Order.id.desc()).all()
    return [
        {
            "id": o.id,
            "items": json.loads(o.items),
            "total": o.total,
            "customer_name": o.customer_name,
            "phone": o.phone,
            "address": o.address,
            "status": o.status,
            "created_at": str(o.created_at),
        }
        for o in orders
    ]