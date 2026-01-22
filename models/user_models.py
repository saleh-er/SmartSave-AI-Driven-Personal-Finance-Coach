# models/user_models.py
from pydantic import BaseModel
from datetime import datetime

class Transaction(BaseModel):
    id: int
    merchant: str
    amount: float
    category: str
    date: datetime
    is_essential: bool