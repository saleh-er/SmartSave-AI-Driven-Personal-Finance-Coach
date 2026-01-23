from fastapi import APIRouter, Request, Body
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from services.serenity_engine import SerenityEngine
from api.open_ai_client import AICoach  # On importe ton nouveau client Groq

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

# Initialisation du coach
coach = AICoach()

# Données simulées
MOCK_TRANSACTIONS = [
    {"id": 1, "merchant": "Netflix", "amount": 15.99, "category": "Subs", "is_essential": False},
    {"id": 2, "merchant": "Carrefour", "amount": 82.50, "category": "Food", "is_essential": True},
    {"id": 3, "merchant": "Uber", "amount": 25.00, "category": "Transport", "is_essential": False},
    {"id": 4, "merchant": "Loyer", "amount": 800.00, "category": "Housing", "is_essential": True},
    {"id": 5, "merchant": "Starbucks", "amount": 6.50, "category": "Food", "is_essential": False},
]

# --- ROUTE API POUR LE CHAT (GROQ) ---
chat_history = []
@router.post("/chat")
async def chat_with_coach(payload: dict = Body(...)):
    user_msg = payload.get("message")
    chat_history.append({"role": "user", "content": user_msg})
    
    # On ne garde que les 5 derniers messages pour ne pas saturer l'IA
    recent_history = chat_history[-5:]
    
    analysis = SerenityEngine.analyze_finances(MOCK_TRANSACTIONS)
    # On passe maintenant l'historique au coach au lieu d'un seul message
    advice = coach.get_financial_advice(recent_history, analysis["score"], "Netflix, Uber, etc.")
    
    chat_history.append({"role": "assistant", "content": advice})
    return {"response": advice}

# --- ROUTES DES PAGES HTML ---

@router.get("/", response_class=HTMLResponse)
async def read_home(request: Request):
    analysis = SerenityEngine.analyze_finances(MOCK_TRANSACTIONS)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "name": "Saleh",
        "score": analysis["score"],
        "status": analysis["status"],
        "remaining": 450.00,
        "transactions": MOCK_TRANSACTIONS[:3]
    })

@router.get("/analytics", response_class=HTMLResponse)
async def read_analytics(request: Request):
    total_spent = sum(t['amount'] for t in MOCK_TRANSACTIONS)
    categories = {}
    for t in MOCK_TRANSACTIONS:
        categories[t['category']] = categories.get(t['category'], 0) + t['amount']
    
    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "total_spent": round(total_spent, 2),
        "categories": categories
    })

@router.get("/coach", response_class=HTMLResponse)
async def read_coach(request: Request):
    analysis = SerenityEngine.analyze_finances(MOCK_TRANSACTIONS)
    return templates.TemplateResponse("coach.html", {
        "request": request,
        "analysis": analysis
    })

@router.get("/goals", response_class=HTMLResponse)
async def read_goals(request: Request):
    user_goals = [
        {"name": "Japan Trip", "current": 1300, "target": 2000, "color": "#6366F1"},
        {"name": "Emergency Fund", "current": 4500, "target": 5000, "color": "#10B981"}
    ]
    return templates.TemplateResponse("goals.html", {
        "request": request,
        "goals": user_goals
    })