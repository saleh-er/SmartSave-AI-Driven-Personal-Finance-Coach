from fastapi import APIRouter, Request, Body
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from services.serenity_engine import SerenityEngine
from api.open_ai_client import AICoach

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")
coach = AICoach()

# --- 1. DONNÉES GLOBALES (Mémoire vive du serveur) ---

USER_GOALS = [
    {"name": "Japan Trip", "current": 1300, "target": 2000, "color": "#6366F1"},
    {"name": "Emergency Fund", "current": 4500, "target": 5000, "color": "#10B981"}
]

MOCK_TRANSACTIONS = [
    {"id": 1, "merchant": "Netflix", "amount": 15.99, "category": "Subs", "is_essential": False},
    {"id": 2, "merchant": "Carrefour", "amount": 82.50, "category": "Food", "is_essential": True},
    {"id": 3, "merchant": "Uber", "amount": 25.00, "category": "Transport", "is_essential": False},
    {"id": 4, "merchant": "Loyer", "amount": 800.00, "category": "Housing", "is_essential": True},
    {"id": 5, "merchant": "Starbucks", "amount": 6.50, "category": "Food", "is_essential": False},
]

chat_history = []

# --- 2. ROUTES API (LOGIQUE & CALCULS) ---

@router.post("/chat")
async def chat_with_coach(payload: dict = Body(...)):
    user_msg = payload.get("message")
    chat_history.append({"role": "user", "content": user_msg})
    
    recent_history = chat_history[-5:]
    analysis = SerenityEngine.analyze_finances(MOCK_TRANSACTIONS)
    
    # On passe le score réel à l'IA pour qu'elle sache de quoi elle parle
    advice = coach.get_financial_advice(recent_history, analysis["score"], "Netflix, Uber, Starbucks, Loyer")
    
    chat_history.append({"role": "assistant", "content": advice})
    return {"response": advice}

@router.post("/add-goal")
async def add_goal(payload: dict = Body(...)):
    new_goal = {
        "name": payload.get("name"),
        "target": float(payload.get("target")),
        "current": 0,
        "color": payload.get("color", "#6366F1")
    }
    USER_GOALS.append(new_goal)
    return {"status": "success", "goal": new_goal}

@router.post("/calculate-plan")
async def calculate_plan(payload: dict = Body(...)):
    goal_name = payload.get("name")
    target_amount = float(payload.get("target"))
    
    analysis = SerenityEngine.analyze_finances(MOCK_TRANSACTIONS)
    
    # Prompt optimisé pour le calcul financier par l'IA
    prompt = [
        {"role": "system", "content": "You are a precise financial advisor. Mirror the user's language."},
        {"role": "user", "content": f"Target: {target_amount}€ for {goal_name}. Current monthly spend: {analysis['total_spent']}€. Create a daily savings plan based on this budget."}
    ]
    
    plan_advice = coach.get_financial_advice(prompt, analysis["score"], "Netflix, Uber, Starbucks")
    return {"plan": plan_advice}

@router.delete("/delete-goal/{goal_name}")
async def delete_goal(goal_name: str):
    global USER_GOALS
    USER_GOALS = [goal for goal in USER_GOALS if goal["name"] != goal_name]
    return {"status": "success"}

# --- 3. ROUTES PAGES (RENDU HTML) ---

@router.get("/", response_class=HTMLResponse)
async def read_home(request: Request):
    # C'est ici que le nouveau SerenityEngine fait son vrai travail
    analysis = SerenityEngine.analyze_finances(MOCK_TRANSACTIONS)
    
    # --- SYSTÈME D'ALERTES DYNAMIQUES ---
    dynamic_alert = None
    if analysis["score"] < 50:
        dynamic_alert = "Attention Saleh, tes dépenses 'Plaisir' sont trop hautes ce mois-ci ! ⚠️"
    elif analysis["score"] > 85:
        dynamic_alert = "Ton score est excellent ! Tu gères tes finances comme un chef. 🏆"

    # On peut aussi calculer le montant restant réel
    total_spent = sum(t['amount'] for t in MOCK_TRANSACTIONS)
    remaining = 1500.00 - total_spent # Imaginons un budget de 1500€

    return templates.TemplateResponse("index.html", {
        "request": request,
        "name": "Saleh",
        "score": analysis["score"],
        "status": analysis["status"],
        "remaining":round(remaining,2), # 
        "transactions": MOCK_TRANSACTIONS[:3],
        "dynamic_alert": dynamic_alert
    })

@router.get("/goals", response_class=HTMLResponse)
async def read_goals(request: Request):
    return templates.TemplateResponse("goals.html", {
        "request": request,
        "goals": USER_GOALS 
    })

@router.get("/analytics", response_class=HTMLResponse)
async def read_analytics(request: Request):
    total_spent = sum(t['amount'] for t in MOCK_TRANSACTIONS)
    categories_data = {}
    for t in MOCK_TRANSACTIONS:
        cat = t['category']
        categories_data[cat] = categories_data.get(cat, 0) + t['amount']
        
    return templates.TemplateResponse("analytics.html", {
        "request": request, 
        "total_spent": round(total_spent, 2), 
        "categories": categories_data
    })

@router.get("/coach", response_class=HTMLResponse)
async def read_coach(request: Request):
    analysis = SerenityEngine.analyze_finances(MOCK_TRANSACTIONS)
    return templates.TemplateResponse("coach.html", {
        "request": request, 
        "analysis": analysis
    })