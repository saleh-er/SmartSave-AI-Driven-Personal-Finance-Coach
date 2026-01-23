from fastapi import APIRouter, Request, Body
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from services.serenity_engine import SerenityEngine
from api.open_ai_client import AICoach

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")
coach = AICoach()

# --- 1. DONNÉES GLOBALES (Mémoire du serveur) ---

# Liste des objectifs qui peut être modifiée par l'utilisateur
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

# --- 2. ROUTES API (LOGIQUE) ---

@router.post("/chat")
async def chat_with_coach(payload: dict = Body(...)):
    user_msg = payload.get("message")
    chat_history.append({"role": "user", "content": user_msg})
    recent_history = chat_history[-5:]
    analysis = SerenityEngine.analyze_finances(MOCK_TRANSACTIONS)
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

# --- 3. ROUTES PAGES (AFFICHAGE) ---

@router.get("/", response_class=HTMLResponse)
async def read_home(request: Request):
    analysis = SerenityEngine.analyze_finances(MOCK_TRANSACTIONS)
    dynamic_alert = None
    uber_total = sum(t['amount'] for t in MOCK_TRANSACTIONS if t['merchant'] == 'Uber')
    
    if uber_total > 20:
        dynamic_alert = f"Attention Saleh, tu as déjà dépensé {uber_total}€ en Uber. 🚕"
    elif analysis["score"] > 75:
        dynamic_alert = "Super boulot ! Ton score de sérénité est excellent. ✨"

    return templates.TemplateResponse("index.html", {
        "request": request, "name": "Saleh", "score": analysis["score"], 
        "status": analysis["status"], "remaining": 450.00, 
        "transactions": MOCK_TRANSACTIONS[:3], "dynamic_alert": dynamic_alert
    })

@router.get("/goals", response_class=HTMLResponse)
async def read_goals(request: Request):
    # On utilise UNIQUEBLENT la liste USER_GOALS définie en haut
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
        "request": request, "total_spent": round(total_spent, 2), "categories": categories_data
    })

@router.get("/coach", response_class=HTMLResponse)
async def read_coach(request: Request):
    analysis = SerenityEngine.analyze_finances(MOCK_TRANSACTIONS)
    return templates.TemplateResponse("coach.html", {"request": request, "analysis": analysis})

@router.post("/calculate-plan")
async def calculate_plan(payload: dict = Body(...)):
    goal_name = payload.get("name")
    target_amount = float(payload.get("target"))
    
    # On récupère l'analyse actuelle pour que l'IA connaisse le budget de Saleh
    analysis = SerenityEngine.analyze_finances(MOCK_TRANSACTIONS)
    
    # Prompt spécifique pour le plan d'épargne
    prompt = [
        {"role": "system", "content": "You are a financial math expert. Calculate a daily saving plan."},
        {"role": "user", "content": f"I want to save {target_amount}€ for '{goal_name}'. My current monthly spending is {analysis['total_spent']}€. Based on this, suggest how many days it will take and how much I should save per day. Be very concise."}
    ]
    
    plan_advice = coach.get_financial_advice(prompt, analysis["score"], "Netflix, Uber, Starbucks")
    return {"plan": plan_advice}