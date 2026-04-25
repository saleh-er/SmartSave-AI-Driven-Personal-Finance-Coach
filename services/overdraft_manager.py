import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class OverdraftManager:

    @staticmethod
    def detect_overdraft(current_balance: float, overdraft_limit: float) -> dict:
        """Détecte si l'utilisateur est en découvert et le niveau de gravité."""
        
        if current_balance >= 0:
            return {
                "in_overdraft": False,
                "severity": "none",
                "amount": 0,
                "message": "Solde positif"
            }
        
        overdraft_amount = abs(current_balance)
        
        if overdraft_limit > 0 and overdraft_amount <= overdraft_limit:
            severity = "warning"
            message = f"Découvert autorisé utilisé: {overdraft_amount}€ sur {overdraft_limit}€ autorisés"
        elif overdraft_amount < 200:
            severity = "moderate"
            message = f"Découvert de {overdraft_amount}€"
        elif overdraft_amount < 500:
            severity = "serious"
            message = f"Découvert important de {overdraft_amount}€"
        else:
            severity = "critical"
            message = f"Découvert critique de {overdraft_amount}€"
        
        return {
            "in_overdraft": True,
            "severity": severity,
            "amount": round(overdraft_amount, 2),
            "message": message
        }

    @staticmethod
    def generate_recovery_plan(user_name: str, current_balance: float, 
                                monthly_income: float, transactions: list,
                                situation: str) -> str:
        """Génère un plan de sortie de découvert personnalisé via Groq."""
        
        overdraft_amount = abs(current_balance) if current_balance < 0 else 0
        
        # Analyse des dépenses
        total_spent = sum(t.amount for t in transactions)
        non_essential = [(t.merchant, t.amount, t.category) 
                        for t in transactions if not t.is_essential]
        non_essential_total = sum(t.amount for t in transactions if not t.is_essential)
        
        non_essential_str = "\n".join([f"- {m}: {a}€ ({c})" 
                                        for m, a, c in non_essential[:10]])
        
        prompt = f"""
You are an emergency financial coach helping {user_name} get out of overdraft.

CRITICAL SITUATION:
- Current balance: {current_balance}€ (OVERDRAFT of {overdraft_amount}€)
- Monthly income: {monthly_income}€
- Situation: {situation}
- Total spent this month: {total_spent}€
- Non-essential spending: {non_essential_total}€

Non-essential expenses that could be reduced:
{non_essential_str}

Generate a CONCRETE and URGENT recovery plan with:
1. 🚨 Immediate actions (next 48 hours) — what to stop spending on RIGHT NOW
2. 📅 Weekly plan — exact amounts to save each week to exit overdraft
3. ✂️ Top 3 specific expenses to cut immediately with exact savings
4. 💡 One smart tip specific to their situation ({situation})
5. 🎯 Realistic date to exit overdraft based on their income

Be direct, specific, use real numbers from their data.
Reply in the SAME language as the user will use (detect from context, default French).
Use emojis. Keep it under 200 words but impactful.
"""
        
        try:
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=600
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"Groq overdraft plan error: {e}")
            return "Erreur lors de la génération du plan. Réessayez."

    @staticmethod
    def get_quick_savings_tips(transactions: list, overdraft_amount: float) -> list:
        """Retourne les 3 dépenses les plus faciles à couper immédiatement."""
        
        non_essential = [(t.merchant, t.amount, t.category) 
                        for t in transactions if not t.is_essential]
        non_essential.sort(key=lambda x: x[1], reverse=True)
        
        tips = []
        for merchant, amount, category in non_essential[:3]:
            tips.append({
                "merchant": merchant,
                "amount": round(amount, 2),
                "category": category,
                "impact": f"Économisez {round(amount, 2)}€ immédiatement"
            })
        
        return tips
