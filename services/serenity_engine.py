class SerenityEngine:
    @staticmethod
    def analyze_finances(transactions):
        if not transactions:
            return {"score": 100, "status": "No data", "total_spent": 0}

        # Cette ligne magique gère t['amount'] (dict) ET t.amount (objet SQL)
        total_spent = sum(
            t.amount if hasattr(t, 'amount') else t.get('amount', 0) 
            for t in transactions
        )
        
        # Idem pour les dépenses essentielles
        essential_spent = sum(
            t.amount if hasattr(t, 'amount') else t.get('amount', 0)
            for t in transactions 
            if (t.is_essential if hasattr(t, 'is_essential') else t.get('is_essential', False))
        )

        # Calcul du score (exemple de logique simple)
        if total_spent == 0:
            score = 100
        else:
            pleasure_ratio = (total_spent - essential_spent) / total_spent
            score = max(0, 100 - (pleasure_ratio * 100))

        status = "Good" if score > 70 else "Warning" if score > 40 else "Critical"
        
        return {
            "score": round(score, 0),
            "status": status,
            "total_spent": round(total_spent, 2)
        }