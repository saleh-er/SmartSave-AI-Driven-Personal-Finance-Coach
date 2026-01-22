import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class AICoach:
    def __init__(self):
        # Récupère la clé depuis ton fichier .env
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def get_financial_advice(self, chat_input, score, transactions):
        # 1. On définit les instructions de base (System Prompt)
        system_instructions = f"""
        Tu es SmartSave AI, un coach financier expert.
        CONTEXTE : Score {score}/100. Transactions : {transactions}.
        
        TON STYLE :
        - Pas de blabla inutile. Pas de répétitions.
        - Si l'utilisateur dit "OK" ou "Oui", ne repose pas la question. Passe à l'action.
        - Sois force de proposition. Si l'utilisateur veut un téléphone, demande-lui son prix et propose un plan d'épargne sur 3 mois.
        - Utilise des emojis de manière pro (🎯, 📈, 📱).
        """

        # 2. On prépare la liste des messages pour l'API
        # On commence toujours par le message système
        messages = [{"role": "system", "content": system_instructions}]

        # 3. GESTION DE LA MÉMOIRE : 
        # Si chat_input est une liste (historique), on l'ajoute directement
        if isinstance(chat_input, list):
            messages.extend(chat_input)
        else:
            # Sinon, on crée un message utilisateur unique
            messages.append({"role": "user", "content": str(chat_input)})

        try:
            # 4. Envoi à l'API Groq
            completion = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"❌ Erreur API Groq : {e}")
            return "Désolé, j'ai eu un petit souci technique. Peux-tu reformuler ?"