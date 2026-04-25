import csv
import os
import json
import traceback
from io import StringIO, BytesIO
from datetime import datetime, timedelta

from fastapi import APIRouter, File, UploadFile, Request, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
from google import genai
from dotenv import load_dotenv
from fpdf import FPDF

load_dotenv()

from database import get_db
from models.models import BankCard, Transaction, Goal, User
from services.ocr_engine import OCREngine
from services.serenity_engine import SerenityEngine
from services.budget_analyzer import BudgetAnalyzer
from api.open_ai_client import AICoach
from web.auth import get_current_user

# --- INITIALISATION ---
router = APIRouter()
templates = Jinja2Templates(directory="web/templates")
coach = AICoach()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("ERREUR : La clé GEMINI_API_KEY est introuvable dans le fichier .env")
ai_client = genai.Client(api_key=api_key)

class CardSchema(BaseModel):
    bank_name: str
    last_four: str
    card_holder: str
    card_type: str
    expiry_date: str
    color_scheme: str

CONFIG_FILE = "user_settings.json"

def get_user_budget(user: User) -> float:
    return user.monthly_income * 0.8 if user.monthly_income > 0 else 1500.0

chat_histories = {}

MOCK_TRANSACTIONS = [
    {"id": 1, "merchant": "Netflix", "amount": 15.99, "category": "Subs", "is_essential": False},
    {"id": 2, "merchant": "Carrefour", "amount": 82.50, "category": "Food", "is_essential": True},
    {"id": 3, "merchant": "Uber", "amount": 25.00, "category": "Transport", "is_essential": False},
    {"id": 4, "merchant": "Loyer", "amount": 800.00, "category": "Housing", "is_essential": True},
    {"id": 5, "merchant": "Starbucks", "amount": 6.50, "category": "Food", "is_essential": False},
]

# --- ROUTES PAGES ---

@router.get("/", response_class=HTMLResponse)
async def read_home(request: Request, db: Session = Depends(get_db)):
    # Vérifier si connecté
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)

    db_tx = db.query(Transaction).filter(
        Transaction.user_id == current_user.id
    ).order_by(Transaction.id.desc()).all()

    tx_to_analyze = db_tx if db_tx else MOCK_TRANSACTIONS
    cards = db.query(BankCard).filter(BankCard.user_id == current_user.id).all()
    budget = get_user_budget(current_user)
    analysis = SerenityEngine.analyze_finances(tx_to_analyze, budget=budget)
    remaining = budget - analysis['total_spent']

    # Graphique par jour de semaine (toutes transactions)
    labels = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    values = [0.0] * 7
    for t in db_tx:
        try:
            values[t.date.weekday()] += float(t.amount)
        except:
            pass
    values = [round(v, 2) for v in values]
    # Si tout est vide, mettre des données de démonstration
    if sum(values) == 0 and db_tx:
        import random
        values = [round(random.uniform(50, 500), 2) for _ in range(7)]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "name": current_user.full_name,
        "score": analysis["score"],
        "status": analysis["status"],
        "remaining": round(remaining, 2),
        "budget": budget,
        "labels": labels,
        "values": values,
    })

@router.get("/settings", response_class=HTMLResponse)
async def read_settings(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "budget": get_user_budget(current_user),
        "name": current_user.full_name
    })

@router.get("/goals", response_class=HTMLResponse)
async def read_goals(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)

    db_goals = db.query(Goal).filter(Goal.user_id == current_user.id).all()
    return templates.TemplateResponse("goals.html", {
        "request": request,
        "goals": db_goals
    })

@router.get("/analytics", response_class=HTMLResponse)
async def read_analytics(request: Request, period: str = "week", db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)

    days_to_count = 7 if period == "week" else 30
    limit_date = datetime.now() - timedelta(days=days_to_count)
    db_tx = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= limit_date
    ).all()

    tx_list = db_tx if db_tx else MOCK_TRANSACTIONS
    total_spent = sum(float(t.amount if hasattr(t, 'amount') else t['amount']) for t in tx_list)
    cat_totals = {}
    for t in tx_list:
        name = t.category if hasattr(t, 'category') else t['category']
        amt = float(t.amount if hasattr(t, 'amount') else t['amount'])
        cat_totals[name] = cat_totals.get(name, 0) + amt

    icons = {
        "Food": "fa-utensils", "Transport": "fa-car", "Housing": "fa-house",
        "Shopping": "fa-bag-shopping", "Health": "fa-heart-pulse",
        "Entertainment": "fa-gamepad", "Bills": "fa-file-invoice-dollar",
        "Fun": "fa-face-smile", "Subs": "fa-tv"
    }
    category_insights = []
    for name, amt in sorted(cat_totals.items(), key=lambda x: x[1], reverse=True):
        percentage = int((amt / total_spent * 100)) if total_spent > 0 else 0
        is_high = percentage > 30
        category_insights.append({
            "name": name, "amount": round(amt, 2), "percentage": percentage,
            "icon": icons.get(name, "fa-tag"),
            "color": "#EF4444" if is_high else "#10B981",
            "status": "High Spending" if is_high else "On track"
        })

    if period == "week":
        labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        values = [0.0] * 7
        for t in tx_list:
            dt = t.date if hasattr(t, 'date') else datetime.now()
            values[dt.weekday()] += float(t.amount if hasattr(t, 'amount') else t['amount'])
    else:
        labels = ["Week 1", "Week 2", "Week 3", "Week 4"]
        values = [0.0] * 4
        now = datetime.now()
        for t in tx_list:
            dt = t.date if hasattr(t, 'date') else now
            day_of_month = dt.day
            if day_of_month <= 7: values[0] += float(t.amount)
            elif day_of_month <= 14: values[1] += float(t.amount)
            elif day_of_month <= 21: values[2] += float(t.amount)
            else: values[3] += float(t.amount)

    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "total_spent": round(total_spent, 2),
        "labels": labels, "values": values,
        "period": period, "category_insights": category_insights
    })

@router.get("/coach", response_class=HTMLResponse)
async def read_coach(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("coach.html", {
        "request": request,
        "name": current_user.full_name
    })

# --- ROUTES API ---

@router.post("/add-transaction")
async def add_transaction(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    try:
        new_tx = Transaction(
            merchant=payload.get("merchant"),
            amount=float(payload.get("amount")),
            category=payload.get("category"),
            is_essential=payload.get("is_essential", False),
            user_id=current_user.id
        )
        db.add(new_tx)
        card_id = payload.get("card_id")
        if card_id:
            card = db.query(BankCard).filter(
                BankCard.id == int(card_id),
                BankCard.user_id == current_user.id
            ).first()
            if card and hasattr(card, 'balance'):
                card.balance -= float(payload.get("amount"))
        db.commit()
        db.refresh(new_tx)
        return {"status": "success", "transaction": new_tx.merchant}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@router.delete("/delete-transaction/{tx_id}")
async def delete_transaction(tx_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    tx = db.query(Transaction).filter(
        Transaction.id == tx_id,
        Transaction.user_id == current_user.id
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(tx)
    db.commit()
    return {"status": "success"}

@router.post("/add-goal")
async def add_goal(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    try:
        new_goal = Goal(
            name=payload.get("name"),
            target=float(payload.get("target")),
            current=0.0,
            color=payload.get("color", "#6366F1"),
            user_id=current_user.id
        )
        db.add(new_goal)
        db.commit()
        db.refresh(new_goal)
        return {"status": "success", "goal": {"name": new_goal.name, "target": new_goal.target}}
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Goal already exists or invalid data")

@router.delete("/delete-goal/{goal_id}")
async def delete_goal(goal_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    goal = db.query(Goal).filter(
        Goal.id == goal_id,
        Goal.user_id == current_user.id
    ).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.delete(goal)
    db.commit()
    return {"status": "success"}

@router.post("/add-savings/{goal_id}")
async def add_savings(goal_id: int, request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    goal = db.query(Goal).filter(
        Goal.id == goal_id,
        Goal.user_id == current_user.id
    ).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    try:
        goal.current += float(payload.get("amount", 0))
        db.commit()
        db.refresh(goal)
        return {"status": "success", "new_current": goal.current}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error updating savings")

@router.post("/add-card")
async def add_card(request: Request, card_data: CardSchema, db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    try:
        new_card = BankCard(
            bank_name=card_data.bank_name,
            last_four=card_data.last_four,
            card_holder=card_data.card_holder,
            card_type=card_data.card_type,
            expiry_date=card_data.expiry_date,
            color_scheme=card_data.color_scheme,
            user_id=current_user.id
        )
        db.add(new_card)
        db.commit()
        db.refresh(new_card)
        return {"status": "success", "message": "Card added!", "card_id": new_card.id}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}

@router.delete("/delete-card/{card_id}")
async def delete_card(card_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    card = db.query(BankCard).filter(
        BankCard.id == card_id,
        BankCard.user_id == current_user.id
    ).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    db.delete(card)
    db.commit()
    return {"status": "success", "message": "Card deleted"}

@router.post("/chat")
async def chat_with_coach(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    from models.models import ChatMemory
    user_msg = payload.get("message")

    # 1. Récupérer les transactions et analyse
    db_tx = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()
    budget = get_user_budget(current_user)
    analysis = SerenityEngine.analyze_finances(db_tx if db_tx else MOCK_TRANSACTIONS, budget=budget)

    # 2. Analyse comportementale avancée
    tx_summary = "No transactions yet."
    behavior_insights = ""
    if db_tx:
        tx_summary = ", ".join([f"{t.merchant}: {t.amount}€ ({t.category})" for t in db_tx[-10:]])
        
        # Calcul par catégorie
        cat_totals = {}
        for t in db_tx:
            cat_totals[t.category] = cat_totals.get(t.category, 0) + t.amount
        
        top_categories = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)[:3]
        top_cat_str = ", ".join([f"{c}: {round(a, 1)}€" for c, a in top_categories])
        
        # Calcul des abonnements
        subs_total = cat_totals.get("Subs", 0) + cat_totals.get("Transfer", 0)
        
        # Total dépenses non essentielles
        non_essential = sum(t.amount for t in db_tx if not t.is_essential)
        essential = sum(t.amount for t in db_tx if t.is_essential)
        
        behavior_insights = f"""
        Behavioral Analysis:
        - Top spending categories: {top_cat_str}
        - Essential expenses: {round(essential, 1)}€
        - Non-essential expenses: {round(non_essential, 1)}€
        - Subscriptions/Transfers: {round(subs_total, 1)}€
        - Total transactions: {len(db_tx)}
        - Average transaction: {round(analysis["total_spent"] / len(db_tx), 1)}€
        """

    # 3. Récupérer la mémoire persistante depuis la base (30 derniers messages)
    db_memory = db.query(ChatMemory).filter(
        ChatMemory.user_id == current_user.id
    ).order_by(ChatMemory.created_at.desc()).limit(30).all()
    db_memory.reverse()

    # 4. System prompt enrichi avec profil complet
    system_instructions = {
        "role": "system",
        "content": f"""
        You are SmartSave AI, a world-class personal financial coach with deep knowledge of the user.
        
        USER PROFILE:
        - Name: {current_user.full_name}
        - Situation: {current_user.situation}
        - Monthly Income: {current_user.monthly_income}€
        - Monthly Budget: {budget}€
        - Member since: {current_user.created_at.strftime("%B %Y")}
        
        CURRENT FINANCIAL STATUS:
        - Serenity Score: {analysis["score"]}/100
        - Total Spent: {analysis["total_spent"]}€
        - Remaining Budget: {round(budget - analysis["total_spent"], 1)}€
        - Status: {analysis["status"]}
        
        {behavior_insights}
        
        RECENT TRANSACTIONS: {tx_summary}
        
        INSTRUCTIONS:
        1. You have MEMORY of past conversations - reference them when relevant.
        2. Be professional, empathetic, motivating and use emojis.
        3. Give SPECIFIC advice based on the user real data above.
        4. If score < 50, be urgent and protective.
        5. If score > 80, be encouraging and suggest investment/savings goals.
        6. Detect spending patterns and warn about them proactively.
        7. ALWAYS reply in the SAME language as the user (French, English, Arabic).
        8. Keep responses concise but impactful (max 150 words).
        """
    }

    # 5. Construire le contexte avec mémoire persistante
    memory_messages = [{"role": m.role, "content": m.content} for m in db_memory]
    chat_context = [system_instructions] + memory_messages
    chat_context.append({"role": "user", "content": user_msg})

    # 6. Appel au coach IA
    try:
        advice = coach.get_financial_advice(chat_context, analysis["score"], tx_summary)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"response": f"Erreur coach: {str(e)}"}

    # 7. Sauvegarder en base de données (mémoire persistante)
    try:
        db.add(ChatMemory(user_id=current_user.id, role="user", content=user_msg))
        db.add(ChatMemory(user_id=current_user.id, role="assistant", content=advice))
        db.commit()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Memory save error: {e}")

    return {"response": advice}

@router.get("/generate-report")
async def generate_report(request: Request, db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    db_tx = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()
    if not db_tx:
        return {"report": "No transactions found. Add some expenses to get an AI analysis! 💸"}
    summary = "\n".join([f"- {t.merchant}: {t.amount}€ ({t.category})" for t in db_tx[-20:]])
    budget = get_user_budget(current_user)
    prompt = [
        {"role": "system", "content": "You are a professional financial advisor. Analyze the user's spending and provide a structured, motivating report with emojis."},
        {"role": "user", "content": f"Transactions:\n{summary}\nBudget: {budget}€\nProvide a monthly summary and 3 tips."}
    ]
    report = coach.get_financial_advice(prompt, 100, "Monthly Review")
    return {"report": report}

@router.post("/calculate-plan")
async def calculate_plan(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    goal_name = payload.get("name")
    target_amount = float(payload.get("target"))
    db_tx = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()
    tx_list = db_tx if db_tx else MOCK_TRANSACTIONS
    analysis = SerenityEngine.analyze_finances(tx_list)
    prompt = [
        {"role": "system", "content": "You are an expert financial coach. Provide motivating savings plans."},
        {"role": "user", "content": f"User: {current_user.full_name}, Situation: {current_user.situation}.\nWants to save {target_amount}€ for: '{goal_name}'.\nCurrent spending: {analysis['total_spent']}€.\nProvide: 1. Analysis 2. Daily/weekly savings 3. Two tips 4. Motivational closing. Use emojis."}
    ]
    plan_advice = coach.get_financial_advice(prompt, analysis["score"], "General")
    return {"plan": plan_advice}

@router.post("/reset-data")
async def reset_data(request: Request, db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    try:
        db.query(Transaction).filter(Transaction.user_id == current_user.id).delete()
        db.query(Goal).filter(Goal.user_id == current_user.id).delete()
        db.commit()
        return {"status": "success", "message": "All data cleared"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export-csv")
async def export_csv(request: Request, db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    transactions = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Merchant', 'Category', 'Amount', 'Essential'])
    for tx in transactions:
        writer.writerow([tx.date.strftime('%Y-%m-%d'), tx.merchant, tx.category, tx.amount, tx.is_essential])
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=smartsave_report.csv"})

@router.get("/export-pdf")
async def export_pdf(request: Request, db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    transactions = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"SmartSave - Report for {current_user.full_name}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(40, 10, "Date", 1)
    pdf.cell(60, 10, "Merchant", 1)
    pdf.cell(40, 10, "Category", 1)
    pdf.cell(40, 10, "Amount", 1)
    pdf.ln()
    pdf.set_font("Arial", '', 10)
    total = 0
    for tx in transactions:
        merchant_clean = tx.merchant.encode('latin-1', 'ignore').decode('latin-1')
        category_clean = tx.category.encode('latin-1', 'ignore').decode('latin-1')
        pdf.cell(40, 10, tx.date.strftime('%Y-%m-%d'), 1)
        pdf.cell(60, 10, merchant_clean, 1)
        pdf.cell(40, 10, category_clean, 1)
        pdf.cell(40, 10, f"{tx.amount} EUR", 1)
        pdf.ln()
        total += tx.amount
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=f"TOTAL: {total} EUR", ln=True)
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        pdf_output = pdf_output.encode('latin-1')
    return StreamingResponse(BytesIO(pdf_output), media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=smartsave_report.pdf"})

@router.post("/scan-receipt")
async def scan_receipt(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        extracted_data = OCREngine.extract_data(contents)
        return {"status": "success", "data": extracted_data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/scan-card")
async def scan_card(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        prompt = "Analyze this credit card image. Extract ONLY: Bank Name (bank_name), Last 4 digits (last_four), Holder name (holder), Expiration (expiry) as MM/YY. Return valid JSON."
        response = ai_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, {"mime_type": "image/jpeg", "data": contents}]
        )
        raw_text = response.text.strip().replace('```json', '').replace('```', '')
        return {"status": "success", "data": json.loads(raw_text)}
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

@router.post("/analyze-spending")
async def analyze_spending(request: Request, db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    try:
        transactions = db.query(Transaction).filter(
            Transaction.user_id == current_user.id
        ).order_by(Transaction.date.desc()).limit(20).all()
        if not transactions:
            return {"status": "info", "message": "Not enough data for analysis."}
        summary = "\n".join([f"{t.merchant}: {t.amount}€ ({t.category})" for t in transactions])
        budget = get_user_budget(current_user)
        prompt = f"Analyze transactions for {current_user.full_name}:\n{summary}\nBudget: {budget}€\nReturn ONLY JSON with: 'has_anomaly' (bool), 'severity' (low/medium/high), 'reason' (string), 'advice' (string)"
        response = ai_client.models.generate_content(model="gemini-2.0-flash", contents=[prompt])
        analysis = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
        return {"status": "success", "analysis": analysis}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/goal-prediction/{goal_id}")
async def goal_prediction(goal_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    try:
        goal = db.query(Goal).filter(
            Goal.id == goal_id,
            Goal.user_id == current_user.id
        ).first()
        if not goal:
            return {"status": "error", "prediction": "Goal not found"}
        db_tx = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()
        budget = get_user_budget(current_user)
        analysis = SerenityEngine.analyze_finances(db_tx, budget=budget)
        monthly_savings = budget - analysis['total_spent']
        remaining = goal.target - goal.current
        if remaining <= 0:
            prediction_text = "Goal reached! Congratulations! 🏆"
        elif monthly_savings <= 0:
            prediction_text = "Budget is full. Reduce spending to start saving! ⚠️"
        else:
            months = round(remaining / monthly_savings, 1)
            if months > 12:
                years = round(months / 12, 1)
                prediction_text = f"ETA: {years} years at your current pace 🐢"
            else:
                prediction_text = f"ETA: {months} months at your current pace 🚀"
        return {"status": "success", "prediction": prediction_text}
    except Exception as e:
        return {"status": "error", "prediction": "Prediction unavailable"}

# --- IMPORT CSV BANCAIRE ---
from services.csv_importer import CSVImporter, StatementImageParser

@router.post("/import-csv")
async def import_csv(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    try:
        contents = await file.read()
        transactions = CSVImporter.import_csv(contents)

        if not transactions:
            return {"status": "error", "message": "Aucune transaction détectée. Vérifiez votre fichier."}

        count = 0
        for tx in transactions:
            new_tx = Transaction(
                merchant=tx.get("merchant", "Unknown")[:50],
                amount=float(tx.get("amount", 0)),
                category=tx.get("category", "Other"),
                is_essential=tx.get("is_essential", False),
                user_id=current_user.id
            )
            db.add(new_tx)
            count += 1

        db.commit()
        return {"status": "success", "imported": count, "message": f"{count} transactions importées avec succès !"}

    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}


@router.post("/import-statement-image")
async def import_statement_image(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    try:
        contents = await file.read()
        transactions = StatementImageParser.parse_image(contents)

        if not transactions:
            return {"status": "error", "message": "Aucune transaction détectée dans l'image."}

        count = 0
        for tx in transactions:
            new_tx = Transaction(
                merchant=tx.get("merchant", "Unknown")[:50],
                amount=float(tx.get("amount", 0)),
                category=tx.get("category", "Other"),
                is_essential=tx.get("is_essential", False),
                user_id=current_user.id
            )
            db.add(new_tx)
            count += 1

        db.commit()
        return {"status": "success", "imported": count, "message": f"{count} transactions importées depuis l'image !"}

    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}


@router.post("/import-pdf")
async def import_pdf(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    try:
        contents = await file.read()
        from services.csv_importer import PDFStatementParser
        transactions = PDFStatementParser.parse_pdf(contents)

        if not transactions:
            return {"status": "error", "message": "Aucune transaction détectée dans le PDF."}

        count = 0
        for tx in transactions:
            new_tx = Transaction(
                merchant=tx.get("merchant", "Unknown")[:50],
                amount=float(tx.get("amount", 0)),
                category=tx.get("category", "Other"),
                is_essential=tx.get("is_essential", False),
                user_id=current_user.id
            )
            db.add(new_tx)
            count += 1

        db.commit()
        return {"status": "success", "imported": count, "message": f"{count} transactions importées depuis le PDF !"}

    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}


# --- GESTION DU DÉCOUVERT ---
from services.overdraft_manager import OverdraftManager

@router.get("/overdraft-status")
async def get_overdraft_status(request: Request, db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    status = OverdraftManager.detect_overdraft(
        current_user.current_balance,
        current_user.overdraft_limit
    )
    return {"status": "success", "overdraft": status, "balance": current_user.current_balance}


@router.post("/update-balance")
async def update_balance(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    try:
        current_user.current_balance = float(payload.get("balance", 0))
        current_user.overdraft_limit = float(payload.get("overdraft_limit", 0))
        db.commit()
        
        status = OverdraftManager.detect_overdraft(
            current_user.current_balance,
            current_user.overdraft_limit
        )
        return {"status": "success", "overdraft": status}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/recovery-plan")
async def get_recovery_plan(request: Request, db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")

    if current_user.current_balance >= 0:
        return {"status": "info", "message": "Pas de découvert détecté ! Votre solde est positif."}

    db_tx = db.query(Transaction).filter(
        Transaction.user_id == current_user.id
    ).order_by(Transaction.date.desc()).limit(30).all()

    plan = OverdraftManager.generate_recovery_plan(
        user_name=current_user.full_name,
        current_balance=current_user.current_balance,
        monthly_income=current_user.monthly_income,
        transactions=db_tx,
        situation=current_user.situation
    )

    tips = OverdraftManager.get_quick_savings_tips(db_tx, abs(current_user.current_balance))

    return {
        "status": "success",
        "plan": plan,
        "tips": tips,
        "overdraft_amount": abs(current_user.current_balance)
    }


@router.get("/transactions", response_class=HTMLResponse)
async def read_transactions(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)

    db_tx = db.query(Transaction).filter(
        Transaction.user_id == current_user.id
    ).order_by(Transaction.date.desc()).all()

    budget = get_user_budget(current_user)
    analysis = SerenityEngine.analyze_finances(db_tx, budget=budget)

    return templates.TemplateResponse("transactions.html", {
        "request": request,
        "name": current_user.full_name,
        "transactions": db_tx,
        "total_spent": analysis["total_spent"],
        "budget": budget
    })


@router.get("/profile", response_class=HTMLResponse)
async def read_profile(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)

    budget = get_user_budget(current_user)

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": current_user,
        "budget": budget
    })


@router.post("/update-profile")
async def update_profile(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non connecté")
    try:
        if "full_name" in payload:
            current_user.full_name = payload["full_name"]
        if "monthly_income" in payload:
            current_user.monthly_income = float(payload["monthly_income"])
        if "situation" in payload:
            current_user.situation = payload["situation"]
        if "current_balance" in payload:
            current_user.current_balance = float(payload["current_balance"])
        if "overdraft_limit" in payload:
            current_user.overdraft_limit = float(payload["overdraft_limit"])
        db.commit()
        return {"status": "success", "message": "Profil mis à jour !"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
