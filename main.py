import uvicorn
import models.models as models_file
from database import engine, Base
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from web.routes import router as web_router
from web.auth import router as auth_router
from core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=== SmartSave Engine Starting ===")
    Base.metadata.create_all(bind=engine)
    print(f"Environment: {settings.ENV}")
    print("Database: Connected & Tables Created")
    print("AI Coach: Ready")
    yield
    print("=== SmartSave Engine Shutting Down ===")

def create_app() -> FastAPI:
    app = FastAPI(
        title="SmartSave API",
        description="L'intelligence artificielle au service de votre sérénité financière.",
        version="1.0.0",
        lifespan=lifespan
    )
    app.mount("/static", StaticFiles(directory="web/static"), name="static")
    app.include_router(auth_router)
    app.include_router(web_router)
    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
