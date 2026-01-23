import uvicorn
import models.models as models_file
from database import engine, Base
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from web.routes import router as web_router
from core.config import settings

# 1. Gestion du cycle de vie (Lifespan) - Remplace on_event("startup")
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=== SmartSave Engine Starting ===")
    
    # CRÉATION DES TABLES DANS POSTGRESQL
    # Cette ligne vérifie tes classes dans models.py et crée les tables dans pgAdmin
    Base.metadata.create_all(bind=engine)
    
    print(f"Environment: {settings.ENV}")
    print("Database: Connected & Tables Created")
    print("AI Coach: Ready")
    yield
    print("=== SmartSave Engine Shutting Down ===")

def create_app() -> FastAPI:
    """
    Initialisation de l'application SmartSave avec PostgreSQL et Lifespan.
    """
    app = FastAPI(
        title="SmartSave API",
        description="L'intelligence artificielle au service de votre sérénité financière.",
        version="1.0.0",
        lifespan=lifespan  # On lie le lifespan ici
    )

    # Configuration des fichiers statiques
    app.mount("/static", StaticFiles(directory="web/static"), name="static")

    # Inclusion des routes
    app.include_router(web_router)

    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)