# services/serenity_engine.py

class SerenityEngine:
    @staticmethod
    def analyze_finances(transactions: list):
        """Calcule le score et génère une analyse rapide pour l'IA."""
        if not transactions:
            return {"score": 50, "status": "No data", "warning": "No transactions found."}

        total_spent = sum(t['amount'] for t in transactions)
        essential = sum(t['amount'] for t in transactions if t.get('is_essential', False))
        
        # Calcul du score basé sur le ratio 50/30/20 (Besoin/Envie/Épargne)
        ratio = (essential / total_spent) if total_spent > 0 else 0
        score = 100 - (abs(0.5 - ratio) * 100) # Plus on est proche de 50% de besoins, plus le score est haut
        
        status = "Excellent" if score > 80 else "Stable" if score > 60 else "Critical"
        
        return {
            "score": round(score, 1),
            "status": status,
            "total_spent": round(total_spent, 2),
            "savings_potential": round(total_spent - essential, 2)
        }