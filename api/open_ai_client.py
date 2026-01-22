# api/open_ai_client.py
import os
from dotenv import load_dotenv

load_dotenv()

class AICoach:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")

    async def get_advice(self, score, status):
        # C'est ici qu'on appellera l'API
        # Pour l'instant on simule une réponse rapide
        return f"Votre score est {score}. En tant que coach, je vous conseille de réduire vos dépenses non-essentielles."