import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from web.routes import router as web_router
from core.config import settings

def create_app() -> FastAPI:
    """
    Initialisation de l'application SmartSave avec une architecture modulaire.
    """
    app = FastAPI(
        title="SmartSave API",
        description="L'intelligence artificielle au service de votre sérénité financière.",
        version="1.0.0"
    )

    # 1. Configuration des fichiers statiques (CSS, JS, Images)
    app.mount("/static", StaticFiles(directory="web/static"), name="static")

    # 2. Inclusion des routes (Séparation des responsabilités)
    # Toutes les routes web et API sont définies dans le module web/routes.py
    app.include_router(web_router)

    @app.on_event("startup")
    async def startup_event():
        print("=== SmartSave Engine Started ===")
        print(f"Environment: {settings.ENV}")
        print("AI Coach: Ready")

    return app

app = create_app()

if __name__ == "__main__":
    # Lancement du serveur avec "Hot Reload" pour le développement
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)