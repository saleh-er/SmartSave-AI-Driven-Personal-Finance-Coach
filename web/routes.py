from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from services.serenity_engine import SerenityEngine

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

# Données simulées (Base de données)
MOCK_TRANSACTIONS = [
    {"id": 1, "merchant": "Netflix", "amount": 15.99, "category": "Subs", "is_essential": False},
    {"id": 2, "merchant": "Carrefour", "amount": 82.50, "category": "Food", "is_essential": True},
    {"id": 3, "merchant": "Uber", "amount": 25.00, "category": "Transport", "is_essential": False},
    {"id": 4, "merchant": "Loyer", "amount": 800.00, "category": "Housing", "is_essential": True},
    {"id": 5, "merchant": "Starbucks", "amount": 6.50, "category": "Food", "is_essential": False},
]

@router.get("/", response_class=HTMLResponse)
async def read_home(request: Request):
    # Utilisation du moteur pour obtenir une analyse complète
    analysis = SerenityEngine.analyze_finances(MOCK_TRANSACTIONS)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "name": "Julie",
        "score": analysis["score"],
        "status": analysis["status"],
        "remaining": 450.00,
        "transactions": MOCK_TRANSACTIONS[:3] # On n'affiche que les 3 dernières sur l'accueil
    })

@router.get("/analytics", response_class=HTMLResponse)
async def read_analytics(request: Request):
    # On calcule les stats pour les graphiques
    total_spent = sum(t['amount'] for t in MOCK_TRANSACTIONS)
    
    # Groupement par catégorie pour les barres de progression
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
    # On prépare un message de bienvenue dynamique
    analysis = SerenityEngine.analyze_finances(MOCK_TRANSACTIONS)
    return templates.TemplateResponse("coach.html", {
        "request": request,
        "analysis": analysis
    })

@router.get("/goals", response_class=HTMLResponse)
async def read_goals(request: Request):
    # On définit des objectifs statiques pour l'instant
    user_goals = [
        {"name": "Japan Trip", "current": 1300, "target": 2000, "color": "#6366F1"},
        {"name": "Emergency Fund", "current": 4500, "target": 5000, "color": "#10B981"}
    ]
    return templates.TemplateResponse("goals.html", {
        "request": request,
        "goals": user_goals
    })