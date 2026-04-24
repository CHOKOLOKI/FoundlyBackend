from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, List
from fastapi import HTTPException
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from fastapi import Depends
from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy import DateTime
import math

DATABASE_URL = "sqlite:///./foundly.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()

# Database model for items
class DBItem(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    item_name = Column(String)
    description = Column(String, nullable=True)
    category = Column(String)
    lat = Column(Float)
    long = Column(Float)
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# Pydantic model for item input/output
class FoundItem(BaseModel):
    id: Optional[int] = None
    item_name: str
    description: Optional[str] = None
    category: str
    lat: float
    long: float
    is_resolved: bool = False
    created_at: Optional[datetime] = None # Include it in the schema

    class Config:
        from_attributes = True

#DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# formula to calculate distance between two lat/long points
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0 
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)) 
    
    return R * c

# Routes
@app.get("/")
def home():
    return {
        "message": "Foundly Global API is live!",
    }

# 1. Get Nearby Items
@app.get("/items/nearby")
def get_nearby_items(
    user_lat: float, 
    user_long: float, 
    radius_km: float = 5.0, 
    db: Session = Depends(get_db)
):
    all_items = db.query(DBItem).all()
    nearby_items = []
    
    for item in all_items:
        dist = calculate_distance(user_lat, user_long, item.lat, item.long)
        
        if dist <= radius_km:
            item_data = FoundItem.model_validate(item).dict()
            item_data["distance_km"] = round(dist, 2)
            nearby_items.append(item_data)
            
    return nearby_items

# 2. Get All Items
@app.get("/items", response_model=List[FoundItem])
def get_items(category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(DBItem)
    if category:
        query = query.filter(DBItem.category == category)
    return query.all()

# 3. Get Single Item
@app.get("/items/{item_id}", response_model=FoundItem)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(DBItem).filter(DBItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

# 4. Report Item (POST)
@app.post("/report-item", response_model=FoundItem)
def report_item(report: FoundItem, db: Session = Depends(get_db)):
    new_item_data = report.dict(exclude={'id', 'created_at'})
    new_item = DBItem(**new_item_data)
    
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item

# 5. Update Item
@app.put("/items/{item_id}", response_model=FoundItem)
def update_item(item_id: int, updated_report: FoundItem, db: Session = Depends(get_db)):
    db_item = db.query(DBItem).filter(DBItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    db_item.item_name = updated_report.item_name
    db_item.description = updated_report.description
    db_item.category = updated_report.category
    db_item.lat = updated_report.lat
    db_item.long = updated_report.long
    db_item.is_resolved = updated_report.is_resolved
    
    db.commit()
    db.refresh(db_item)
    return db_item

# 6. Delete Item
@app.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(DBItem).filter(DBItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    db.delete(item)
    db.commit()
    return {"message": f"Item {item_id} deleted successfully"}