import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

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

USER_CONFIG = {"monthly_budget": 1500.0}
chat_history = []

MOCK_TRANSACTIONS = [
    {"id": 1, "merchant": "Netflix", "amount": 15.99, "category": "Subs", "is_essential": False},
    {"id": 2, "merchant": "Carrefour", "amount": 82.50, "category": "Food", "is_essential": True},
    {"id": 3, "merchant": "Uber", "amount": 25.00, "category": "Transport", "is_essential": False},
    {"id": 4, "merchant": "Loyer", "amount": 800.00, "category": "Housing", "is_essential": True},
    {"id": 5, "merchant": "Starbucks", "amount": 6.50, "category": "Food", "is_essential": False},
]

# --- 2. ROUTES API ---
@router.post("/update-budget")
async def update_budget(payload: dict = Body(...)):
    """Met à jour le plafond budgétaire global"""
    new_budget = payload.get("budget")
    if new_budget is not None:
        try:
            USER_CONFIG["monthly_budget"] = float(new_budget)
            return {"status": "success", "budget": USER_CONFIG["monthly_budget"]}
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid number")
    raise HTTPException(status_code=400, detail="Missing budget data")



@router.post("/chat")
async def chat_with_coach(payload: dict = Body(...), db: Session = Depends(get_db)):
    user_msg = payload.get("message")
    
    # 1. Récupérer les vraies transactions en base pour le contexte
    db_tx = db.query(Transaction).all()
    tx_summary = ""
    if db_tx:
        tx_summary = ", ".join([f"{t.merchant}: {t.amount}€ ({t.category})" for t in db_tx[-10:]])
    else:
        tx_summary = "No transactions yet."

    # 2. Analyse financière pour le score
    analysis = SerenityEngine.analyze_finances(db_tx if db_tx else MOCK_TRANSACTIONS)
    
    # 3. LE PROMPT DU COACH (L'âme de ton IA)
    # On définit ici son rôle, ton score actuel et tes dépenses récentes
    system_instructions = {
        "role": "system", 
        "content": f"""
        You are a high-level personal financial coach. 
        User Context:
        - Name: Saleh
        - Current Serenity Score: {analysis['score']}/100
        - Monthly Budget Limit: {USER_CONFIG['monthly_budget']}€
        - Recent Transactions: {tx_summary}

        Instructions:
        1. Be professional, motivating, and use emojis.
        2. Always refer to the user's real transactions if they ask about their spending.
        3. If the score is low, be protective and give urgent advice.
        4. Answer in English.
        """
    }

    # 4. Historique de la conversation (on garde les 5 derniers messages + les instructions)
    chat_context = [system_instructions] + chat_history[-5:]
    chat_context.append({"role": "user", "content": user_msg})
    
    # 5. Appel à l'IA
    advice = coach.get_financial_advice(chat_context, analysis["score"], tx_summary)
    
    # Sauvegarde dans l'historique local
    chat_history.append({"role": "user", "content": user_msg})
    chat_history.append({"role": "assistant", "content": advice})
    
    return {"response": advice}

# delete transaction by id
@router.delete("/delete-transaction/{tx_id}")
async def delete_transaction(tx_id: int, db: Session = Depends(get_db)):
    # CORRECTION : Utilisation de Transaction au lieu de models.Transaction
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    try:
        db.delete(tx)
        db.commit()
        return {"status": "success", "message": "Transaction deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# Calculate savings plan

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

@router.delete("/delete-goal/{goal_id}")
async def delete_goal(goal_id: int, db: Session = Depends(get_db)):
    # CORRECTION : Utilisation de Goal au lieu de models.Goal
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.delete(goal)
    db.commit()
    return {"status": "success"}

# --- 3. ROUTES PAGES ---
# Route pour la page d'accueil
    # Calcul du reste avant le seuil de 1500€
USER_CONFIG = {"monthly_budget": 1500.0}
@router.get("/", response_class=HTMLResponse)
async def read_home(request: Request, db: Session = Depends(get_db)):
    db_tx = db.query(Transaction).order_by(Transaction.id.desc()).all()
    tx_to_analyze = db_tx if db_tx else MOCK_TRANSACTIONS
    
    analysis = SerenityEngine.analyze_finances(tx_to_analyze)

    # On récupère le budget actuel depuis USER_CONFIG
    current_budget = USER_CONFIG["monthly_budget"]
    
    # On calcule le reste basé sur ce budget dynamique
    remaining = current_budget - analysis['total_spent']

    return templates.TemplateResponse("index.html", {
        "request": request,
        "name": "Saleh",
        "score": analysis["score"],
        "status": analysis["status"],
        "remaining": round(remaining, 2),
        "budget": current_budget,
        "transactions": db_tx, 
        "dynamic_alert": "ready to save " if not db_tx else None
    })

# Route pour la page des objectifs
@router.get("/goals", response_class=HTMLResponse)
async def read_goals(request: Request, db: Session = Depends(get_db)):
    # CORRECTION : Utilisation de Goal au lieu de models.Goal
    db_goals = db.query(Goal).all()
    return templates.TemplateResponse("goals.html", {
        "request": request,
        "goals": db_goals 
    })

@router.get("/analytics", response_class=HTMLResponse)
async def read_analytics(request: Request, period: str = "week", db: Session = Depends(get_db)):
    #on definit la periode
    days = 7 if period == "week" else 30
    limit_date = datetime.utcnow() - timedelta(days=days)
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
        "values": list(categories_dict.values()), # Pour le graphique
        "period": period
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