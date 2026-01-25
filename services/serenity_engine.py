class SerenityEngine:
    @staticmethod
    def analyze_finances(transactions, budget=1500.0):
        if not transactions:
            return {"score": 100, "status": "Perfect", "total_spent": 0}

        # 1. Calcul du total dépensé
        total_spent = sum(float(t.amount if hasattr(t, 'amount') else t['amount']) for t in transactions)
        
        # 2. Logique du Score (Basée sur le budget réel)
        # Si on a dépensé 0, le score est 100. 
        # Plus on dépense, plus le score baisse.
        
        usage_ratio = total_spent / budget
        
        # Formule : On part de 100 et on retire des points selon l'utilisation du budget
        if usage_ratio <= 0.5:
            score = 100 - (usage_ratio * 40) # Entre 100 et 80
        elif usage_ratio <= 1.0:
            score = 80 - ((usage_ratio - 0.5) * 100) # Entre 80 et 30
        else:
            score = 30 - ((usage_ratio - 1.0) * 20) # En dessous de 30 si dépassement
            
        # On s'assure que le score reste entre 0 et 100
        score = max(0, min(100, int(score)))

        # 3. Détermination du statut
        if score > 80: status = "Excellent"
        elif score > 50: status = "Good"
        elif score > 20: status = "Warning"
        else: status = "Critical"

        return {
            "score": score,
            "status": status,
            "total_spent": round(total_spent, 2)
        }