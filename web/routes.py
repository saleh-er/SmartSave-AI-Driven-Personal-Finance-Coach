import sys
import os
from pathlib import Path

# Fix pour les imports : on ajoute la racine du projet
root_path = Path(__file__).parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from fastapi import APIRouter, Request, Body, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# On importe les classes directement
from database import get_db
try:
    from models.models import Transaction, Goal
except ImportError:
    from models import Transaction, Goal

from services.serenity_engine import SerenityEngine
from api.open_ai_client import AICoach

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")
coach = AICoach()

# --- 1. MOCK DATA ---
MOCK_TRANSACTIONS = [
    {"id": 1, "merchant": "Netflix", "amount": 15.99, "category": "Subs", "is_essential": False},
    {"id": 2, "merchant": "Carrefour", "amount": 82.50, "category": "Food", "is_essential": True},
    {"id": 3, "merchant": "Uber", "amount": 25.00, "category": "Transport", "is_essential": False},
    {"id": 4, "merchant": "Loyer", "amount": 800.00, "category": "Housing", "is_essential": True},
    {"id": 5, "merchant": "Starbucks", "amount": 6.50, "category": "Food", "is_essential": False},
]

chat_history = []

# --- 2. ROUTES API ---

@router.post("/chat")
async def chat_with_coach(payload: dict = Body(...)):
    user_msg = payload.get("message")
    chat_history.append({"role": "user", "content": user_msg})
    analysis = SerenityEngine.analyze_finances(MOCK_TRANSACTIONS)
    advice = coach.get_financial_advice(chat_history[-5:], analysis["score"], "Netflix, Uber, Starbucks, Loyer")
    chat_history.append({"role": "assistant", "content": advice})
    return {"response": advice}


@router.post("/calculate-plan")
async def calculate_plan(payload: dict = Body(...), db: Session = Depends(get_db)):
    goal_name = payload.get("name")
    target_amount = float(payload.get("target"))
    
    # On récupère les data pour l'IA
    db_tx = db.query(Transaction).all()
    tx_list = db_tx if db_tx else MOCK_TRANSACTIONS
    analysis = SerenityEngine.analyze_finances(tx_list)
    
    prompt = [
      {
            "role": "system", 
            "content": "You are an expert financial coach. Provide motivating, detailed, and structured savings plans in English."
        },
        {
            "role": "user", 
            "content": f"""
                The user wants to save {target_amount}€ for the project: '{goal_name}'.
                Current monthly spending: {analysis['total_spent']}€.
                
                Please provide a comprehensive action plan including:
                1. A quick analysis of their current financial situation.
                2. The exact amount to save daily and weekly to reach the goal.
                3. Two concrete tips to reduce spending based on their categories.
                4. A personalized motivational closing statement.
                
                Use a friendly tone and include emojis. 🚀
            """
        }
    ]
    
    plan_advice = coach.get_financial_advice(prompt, analysis["score"], "Général")
    return {"plan": plan_advice} # C'est ce 'plan' que le JS attend

@router.post("/add-goal")
async def add_goal(payload: dict = Body(...), db: Session = Depends(get_db)):
    try:
        new_goal = Goal(
            name=payload.get("name"),
            target=float(payload.get("target")),
            current=0.0,
            color=payload.get("color", "#6366F1")
        )
        db.add(new_goal)
        db.commit()
        db.refresh(new_goal)
        return {"status": "success", "goal": {"name": new_goal.name, "target": new_goal.target}}
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Goal already exists or invalid data")

@router.delete("/delete-goal/{goal_name}")
async def delete_goal(goal_name: str, db: Session = Depends(get_db)):
    # CORRECTION : Utilisation de Goal au lieu de models.Goal
    goal = db.query(Goal).filter(Goal.name == goal_name).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.delete(goal)
    db.commit()
    return {"status": "success"}

# --- 3. ROUTES PAGES ---

@router.get("/", response_class=HTMLResponse)
async def read_home(request: Request, db: Session = Depends(get_db)):
    # CORRECTION : Utilisation de Transaction au lieu de models.Transaction
    db_tx = db.query(Transaction).all()
    tx_to_analyze = db_tx if db_tx else MOCK_TRANSACTIONS
    
    analysis = SerenityEngine.analyze_finances(tx_to_analyze)
    remaining = 1500.00 - analysis['total_spent']

    return templates.TemplateResponse("index.html", {
        "request": request,
        "name": "Saleh",
        "score": analysis["score"],
        "status": analysis["status"],
        "remaining": round(remaining, 2),
        "transactions": tx_to_analyze[:3],
        "dynamic_alert": None
    })

@router.get("/goals", response_class=HTMLResponse)
async def read_goals(request: Request, db: Session = Depends(get_db)):
    # CORRECTION : Utilisation de Goal au lieu de models.Goal
    db_goals = db.query(Goal).all()
    return templates.TemplateResponse("goals.html", {
        "request": request,
        "goals": db_goals 
    })

@router.get("/analytics", response_class=HTMLResponse)
async def read_analytics(request: Request, db: Session = Depends(get_db)):
    db_tx = db.query(Transaction).all()
    tx_list = db_tx if db_tx else MOCK_TRANSACTIONS
    
    total_spent = sum(t.amount if hasattr(t, 'amount') else t['amount'] for t in tx_list)
    
    # On crée le dictionnaire des catégories
    categories_dict = {}
    for t in tx_list:
        cat = t.category if hasattr(t, 'category') else t['category']
        amt = t.amount if hasattr(t, 'amount') else t['amount']
        categories_dict[cat] = categories_dict.get(cat, 0) + amt
    
    # On envoie TOUT au template
    return templates.TemplateResponse("analytics.html", {
        "request": request, 
        "total_spent": round(total_spent, 2), 
        "categories": categories_dict,  # Indispensable pour tes barres de progression
        "labels": list(categories_dict.keys()), # Pour le graphique
        "values": list(categories_dict.values()) # Pour le graphique
    })

@router.get("/coach", response_class=HTMLResponse)
async def read_coach(request: Request):
    analysis = SerenityEngine.analyze_finances(MOCK_TRANSACTIONS)
    return templates.TemplateResponse("coach.html", {
        "request": request, 
        "analysis": analysis
    })
@router.post("/add-transaction")
async def add_transaction(payload: dict = Body(...), db: Session = Depends(get_db)):
    try:
        new_tx = Transaction(
            merchant=payload.get("merchant"),
            amount=float(payload.get("amount")),
            category=payload.get("category"),
            is_essential=payload.get("is_essential", False),
            # La date sera ajoutée automatiquement par le modèle (datetime.utcnow)
        )
        db.add(new_tx)
        db.commit()
        db.refresh(new_tx)
        return {"status": "success", "transaction": new_tx.merchant}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error adding transaction: {str(e)}")