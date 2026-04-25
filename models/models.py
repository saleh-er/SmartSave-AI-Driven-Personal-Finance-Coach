from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    monthly_income = Column(Float, default=0.0)
    situation = Column(String, default="employee")
    created_at = Column(DateTime, default=datetime.utcnow)
    current_balance = Column(Float, default=0.0)
    overdraft_limit = Column(Float, default=0.0)
    transactions = relationship("Transaction", back_populates="owner", cascade="all, delete")
    goals = relationship("Goal", back_populates="owner", cascade="all, delete")
    cards = relationship("BankCard", back_populates="owner", cascade="all, delete")
    chat_memory = relationship("ChatMemory", back_populates="owner", cascade="all, delete")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    merchant = Column(String)
    amount = Column(Float)
    category = Column(String)
    date = Column(DateTime, default=datetime.utcnow)
    is_essential = Column(Boolean, default=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="transactions")

class Goal(Base):
    __tablename__ = "goals"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    target = Column(Float)
    current = Column(Float, default=0.0)
    color = Column(String, default="#6366F1")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="goals")

class BankCard(Base):
    __tablename__ = "bank_cards"
    id = Column(Integer, primary_key=True, index=True)
    bank_name = Column(String)
    last_four = Column(String)
    card_holder = Column(String)
    card_type = Column(String)
    expiry_date = Column(String)
    color_scheme = Column(String)
    balance = Column(Float, default=0.0)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="cards")

class ChatMemory(Base):
    __tablename__ = "chat_memory"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner = relationship("User", back_populates="chat_memory")
