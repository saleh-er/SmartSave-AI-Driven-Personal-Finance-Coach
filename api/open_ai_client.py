import os
from groq import Groq
from dotenv import load_dotenv
load_dotenv()

class AICoach:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def get_financial_advice(self, chat_input, score, transactions):
        system_instructions = (
            f"You are SmartSave AI, Saleh's personal financial coach. "
            f"Context: Serenity Score is {score}/100. Recent activity: {transactions}. "
            "STRICT RULE: Always respond in the SAME LANGUAGE as the user's last message. "
            "If the user speaks English, reply in English. If they speak French, reply in French. "
            "If the user speaks Arabic, reply in Arabic. "
            "Keep your advice practical, short, and motivating."
        )

        messages = [{"role": "system", "content": system_instructions}]

        if isinstance(chat_input, list):
            messages.extend(chat_input)
        else:
            messages.append({"role": "user", "content": str(chat_input)})

        try:
            completion = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"Erreur API Groq : {e}")
            return "Désolé, j'ai eu un petit souci technique. Peux-tu reformuler ?"
