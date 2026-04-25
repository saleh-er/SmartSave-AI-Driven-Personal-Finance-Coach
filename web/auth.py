from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models.models import User
from core.security import hash_password, verify_password, create_access_token, decode_token

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

# --- SCHEMAS ---
class SignupSchema(BaseModel):
    full_name: str
    email: str
    password: str
    monthly_income: float = 0.0
    situation: str = "employee"

class LoginSchema(BaseModel):
    email: str
    password: str

# --- HELPER : récupérer l'utilisateur connecté depuis le cookie ---
def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Non connecté")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token invalide")
    user = db.query(User).filter(User.id == payload.get("user_id")).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return user

# --- PAGE SIGNUP ---
@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

# --- PAGE LOGIN ---
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# --- API SIGNUP ---
@router.post("/api/signup")
async def signup(data: SignupSchema, db: Session = Depends(get_db)):
    # Vérifier si l'email existe déjà
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    
    # Créer le nouvel utilisateur
    new_user = User(
        full_name=data.full_name,
        email=data.email,
        hashed_password=hash_password(data.password),
        monthly_income=data.monthly_income,
        situation=data.situation
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Générer le token et le retourner
    token = create_access_token({"user_id": new_user.id, "email": new_user.email})
    return {"status": "success", "token": token, "name": new_user.full_name}

# --- API LOGIN ---
@router.post("/api/login")
async def login(data: LoginSchema, db: Session = Depends(get_db)):
    # Chercher l'utilisateur
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    
    # Vérifier le mot de passe
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    
    # Générer le token
    token = create_access_token({"user_id": user.id, "email": user.email})
    return {"status": "success", "token": token, "name": user.full_name}

# --- LOGOUT ---
@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response
