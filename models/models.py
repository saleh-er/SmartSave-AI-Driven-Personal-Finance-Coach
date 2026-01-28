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

    #add a credit card model
class BankCard(Base):
    __tablename__ = "bank_cards"
    
    id = Column(Integer, primary_key=True, index=True)
    bank_name = Column(String)     # Ex: Revolut, Attijari
    last_four = Column(String)     # Ex: 4242
    card_holder = Column(String)   # Nom sur la carte
    card_type = Column(String)     # Visa, Mastercard
    expiry_date = Column(String)   # MM/YY
    color_scheme = Column(String)  # Pour le design (ex: "neon-purple", "emerald")