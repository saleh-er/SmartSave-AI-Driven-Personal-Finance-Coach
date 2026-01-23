from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from database import Base
from datetime import datetime

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    merchant = Column(String)
    amount = Column(Float)
    category = Column(String)
    date = Column(DateTime, default=datetime.utcnow)
    is_essential = Column(Boolean, default=True)

class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    target = Column(Float)
    current = Column(Float, default=0.0)
    color = Column(String, default="#6366F1")