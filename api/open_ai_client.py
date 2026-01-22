import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class AICoach:
    def __init__(self):
        # Récupère la clé depuis ton fichier .env
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def get_financial_advice(self, user_message, score, transactions):
        # Le "System Prompt" définit la personnalité du Coach
        system_prompt = f"""
        Tu es SmartSave AI, un coach financier pro. 
         DONNÉES ACTUELLES : Score {score}/100, Transactions: {transactions}.
    
        RÈGLES :
         1. Si l'utilisateur veut fixer une limite (ex: "set limit"), propose-lui un montant précis basé sur ses transactions.
         2. Ne répète pas le score à chaque phrase s'il l'utilisateur ne le demande pas.
         3. Sois très bref (maximum 3 phrases).
         4. Réponds directement à la dernière question de l'utilisateur.
         5. Utilise un ton amical et encourageant."""

        completion = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile", # Modèle rapide et gratuit
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return completion.choices[0].message.content