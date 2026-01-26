import csv
import sys
import os
import json
from io import StringIO, BytesIO
from pathlib import Path
from datetime import datetime, timedelta
from fastapi.responses import StreamingResponse
from fastapi import File, UploadFile
from services.ocr_engine import OCREngine
from fpdf import FPDF
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
from services.budget_analyzer import BudgetAnalyzer
from services.serenity_engine import SerenityEngine
from api.open_ai_client import AICoach

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")
coach = AICoach()

CONFIG_FILE = "user_settings.json"

def save_budget_to_disk(amount):
    """Enregistre le budget dans un fichier JSON"""
    with open(CONFIG_FILE, "w") as f:
        json.dump({"monthly_budget": float(amount)}, f)

def load_budget_from_disk():
    """Charge le budget depuis le fichier ou renvoie 1500 par défaut"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                return float(data.get("monthly_budget", 1500.0))
        except Exception as e:
            print(f"Erreur de lecture du budget: {e}")
            return 1500.0
    return 1500.0

# --- 1. VARIABLES GLOBALES ---
USER_CONFIG = {"monthly_budget": load_budget_from_disk()}
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
    """Met à jour le plafond et le sauvegarde sur le disque"""
    new_budget = payload.get("budget")
    if new_budget is not None:
        try:
            val = float(new_budget)
            USER_CONFIG["monthly_budget"] = val
            # SAUVEGARDE PHYSIQUE ICI
            save_budget_to_disk(val) 
            return {"status": "success", "budget": val}
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid number")
    raise HTTPException(status_code=400, detail="Missing budget data")

# --- UPLOAD RECEIPT AND OCR PROCESSING ---
@router.post("/scan-receipt")
async def scan_receipt(file: UploadFile = File(...)):
    try:
        # 1. Read the image file sent from the browser
        contents = await file.read()
        
        # 2. Call our OCR engine to extract data
        # We pass the bytes directly to the engine
        extracted_data = OCREngine.extract_data(contents)
        
        # 3. Return the result to the UI
        return {
            "status": "success",
            "data": extracted_data
        }
        
    except Exception as e:
        # If something goes wrong (blurry image, etc.), return an error
        return {
            "status": "error",
            "message": str(e)
        }
# --- EXPORT CSV ---
@router.get("/export-csv")
async def export_csv(db: Session = Depends(get_db)):
    transactions = db.query(Transaction).all()
    
    # Create a string buffer to write CSV data
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Date', 'Merchant', 'Category', 'Amount', 'Essential'])
    
    # Data rows
    for tx in transactions:
        writer.writerow([tx.date.strftime('%Y-%m-%d'), tx.merchant, tx.category, tx.amount, tx.is_essential])
    
    output.seek(0)
    return StreamingResponse(
        output, 
        media_type="text/csv", 
        headers={"Content-Disposition": "attachment; filename=smartsave_report.csv"}
    )

# --- EXPORT PDF ---
@router.get("/export-pdf")
async def export_pdf(db: Session = Depends(get_db)):
    transactions = db.query(Transaction).all()
    pdf = FPDF()
    pdf.add_page()
    
    # Title
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="SmartSave - Financial Report", ln=True, align='C')
    pdf.ln(10)
    
    # Table Header
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(40, 10, "Date", 1)
    pdf.cell(60, 10, "Merchant", 1)
    pdf.cell(40, 10, "Category", 1)
    pdf.cell(40, 10, "Amount", 1)
    pdf.ln()
    
    # Table Body
    pdf.set_font("Arial", '', 12)
    total = 0
    for tx in transactions:
        pdf.cell(40, 10, tx.date.strftime('%Y-%m-%d'), 1)
        pdf.cell(60, 10, tx.merchant, 1)
        pdf.cell(40, 10, tx.category, 1)
        pdf.cell(40, 10, f"{tx.amount} EUR", 1)
        pdf.ln()
        total += tx.amount
        
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=f"TOTAL SPENT: {total} EUR", ln=True)
    
    # Return PDF as a stream
    response = BytesIO(pdf.output(dest='S').encode('latin-1'))
    return StreamingResponse(
        response, 
        media_type="application/pdf", 
        headers={"Content-Disposition": "attachment; filename=smartsave_report.pdf"}
    )
# Route for home page
@router.get("/", response_class=HTMLResponse)
async def read_home(request: Request, db: Session = Depends(get_db)):
    db_tx = db.query(Transaction).order_by(Transaction.id.desc()).all()
    tx_to_analyze = db_tx if db_tx else MOCK_TRANSACTIONS
    
    analysis = SerenityEngine.analyze_finances(
        tx_to_analyze, budget=USER_CONFIG["monthly_budget"])

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
#router for settings page
@router.get("/settings", response_class=HTMLResponse)
async def read_settings(request: Request):
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "budget": USER_CONFIG["monthly_budget"],
        "name": "Saleh"
    })
#router for reset data
@router.post("/reset-data")
async def reset_data(db: Session = Depends(get_db)):
    try:
        # Supprime toutes les transactions et tous les objectifs
        db.query(Transaction).delete()
        db.query(Goal).delete()
        db.commit()
        return {"status": "success", "message": "All data cleared"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

from services.budget_analyzer import BudgetAnalyzer

# route for chat with financial coach
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
        4. DETECTION: Identify the language used by the user (Arabic,spanich, French, or English).
        5. LANGUAGE: ALWAYS reply in the SAME language used by Saleh. If he speaks Arabic, you MUST reply in Arabic.
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

# Generate monthly report
@router.get("/generate-report")
async def generate_report(db: Session = Depends(get_db)):
    db_tx = db.query(Transaction).all()
    if not db_tx:
        return {"report": "No transactions found. Add some expenses to get an AI analysis! 💸"}
    
    # Résumé structuré pour l'IA
    summary = "\n".join([f"- {t.merchant}: {t.amount}€ ({t.category})" for t in db_tx[-20:]])
    
    prompt = [
        {"role": "system", "content": "You are a professional financial advisor. Analyze the user's spending and provide a structured, motivating report in English with emojis."},
        {"role": "user", "content": f"Transactions:\n{summary}\nBudget Limit: {USER_CONFIG['monthly_budget']}€\n\nPlease provide a monthly summary and 3 tips."}
    ]
    
    report = coach.get_financial_advice(prompt, 100, "Monthly Review")
    return {"report": report}

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

# ajout d'un route Add-saving-goal
@router.post("/add-savings/{goal_id}")
async def add_savings(goal_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    amount_to_add = float(payload.get("amount", 0))
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    try:
        goal.current += amount_to_add
        db.commit()
        db.refresh(goal)
        return {"status": "success", "new_current": goal.current}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating savings")



# Route pour la page des objectifs
@router.get("/goals", response_class=HTMLResponse)
async def read_goals(request: Request, db: Session = Depends(get_db)):
    # CORRECTION : Utilisation de Goal au lieu de models.Goal
    db_goals = db.query(Goal).all()
    return templates.TemplateResponse("goals.html", {
        "request": request,
        "goals": db_goals 
    })

# Route for analytics page

@router.get("/analytics", response_class=HTMLResponse)
async def read_analytics(request: Request, period: str = "week", db: Session = Depends(get_db)):
    # Define the time limit based on period
    days_to_count = 7 if period == "week" else 30
    limit_date = datetime.now() - timedelta(days=days_to_count)
    
    # 1. retrieve transactions from DB within the period
    db_tx = db.query(Transaction).filter(Transaction.date >= limit_date).all()
    # Si la base est vide, on utilise les MOCK_TRANSACTIONS pour le visuel
    tx_list = db_tx if db_tx else MOCK_TRANSACTIONS
    
    total_spent = sum(float(t.amount if hasattr(t, 'amount') else t['amount']) for t in tx_list)

    # 2. calculate category totals
    cat_totals = {}
    for t in tx_list:
        name = t.category if hasattr(t, 'category') else t['category']
        amt = float(t.amount if hasattr(t, 'amount') else t['amount'])
        cat_totals[name] = cat_totals.get(name, 0) + amt

    # 3. Define icons for categories
    icons = {
        "Food": "fa-utensils", "Transport": "fa-car", "Housing": "fa-house",
        "Shopping": "fa-bag-shopping", "Health": "fa-heart-pulse", 
        "Entertainment": "fa-gamepad", "Bills": "fa-file-invoice-dollar",
        "Fun": "fa-face-smile", "Subs": "fa-tv"
    }

    # 4. Préparation des insights (Top Categories)
    category_insights = []
    for name, amt in sorted(cat_totals.items(), key=lambda x: x[1], reverse=True):
        percentage = int((amt / total_spent * 100)) if total_spent > 0 else 0
        is_high = percentage > 30 # Alerte si > 30% des dépenses totales
        
        category_insights.append({
            "name": name,
            "amount": round(amt, 2),
            "percentage": percentage,
            "icon": icons.get(name, "fa-tag"),
            "color": "#EF4444" if is_high else "#10B981", # Rouge si élevé, Vert sinon
            "status": "High Spending" if is_high else "On track"
        })

    # 5. Logique des graphiques (Labels & Values)
    if period == "week":
        labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        values = [0.0] * 7
        for t in tx_list:
            dt = t.date if hasattr(t, 'date') else datetime.now()
            # dt.weekday() donne 0 pour Lundi, 6 pour Dimanche
            values[dt.weekday()] += float(t.amount if hasattr(t, 'amount') else t['amount'])
    else:
        # Mode mois : on découpe en 4 semaines
        labels = ["Week 1", "Week 2", "Week 3", "Week 4"]
        values = [0.0] * 4
        now = datetime.now()
        for t in tx_list:
            dt = t.date if hasattr(t, 'date') else now
            day_of_month = dt.day
            # Attribution à une semaine (1-7, 8-14, 15-21, 22+)
            if day_of_month <= 7: values[0] += float(t.amount)
            elif day_of_month <= 14: values[1] += float(t.amount)
            elif day_of_month <= 21: values[2] += float(t.amount)
            else: values[3] += float(t.amount)

    # 6. Envoi au template
    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "total_spent": round(total_spent, 2),
        "labels": labels,
        "values": values,
        "period": period,
        "category_insights": category_insights
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