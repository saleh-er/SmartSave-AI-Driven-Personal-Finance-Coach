from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from services.serenity_engine import SerenityEngine

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

@router.get("/", response_class=HTMLResponse)
async def read_home(request: Request):
    # Appel de la logique métier avancée
    mock_score = SerenityEngine.calculate_score(income=3000, expenses=1200, savings=800)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "name": "Julie",
        "score": mock_score,
        "status": "Excellente" if mock_score > 80 else "Stable"
    })