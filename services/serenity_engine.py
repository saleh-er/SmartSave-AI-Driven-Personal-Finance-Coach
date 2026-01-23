class SerenityEngine:
    @staticmethod
    def analyze_finances(transactions):
        if not transactions:
            return {"score": 100, "status": "Stable"}

        total_spent = sum(t['amount'] for t in transactions)
        # On calcule ce qui n'est PAS essentiel (is_essential: False)
        wants_spent = sum(t['amount'] for t in transactions if not t.get('is_essential', True))
        
        # Calcul du ratio : quel pourcentage du budget part dans le plaisir ?
        wants_ratio = (wants_spent / total_spent) if total_spent > 0 else 0
        
        # SCORE RÉEL : On part de 100. 
        # Si tes "plaisirs" dépassent 30%, le score chute lourdement.
        if wants_ratio <= 0.30:
            score = 100
        else:
            # On retire 2 points pour chaque 1% au-dessus de la limite
            excess = (wants_ratio - 0.30) * 100
            score = 100 - (excess * 2)

        score = max(0, min(100, int(score)))

        # Déterminer le statut
        if score >= 80: status = "Excellent"
        elif score >= 50: status = "Warning"
        else: status = "Critical"

        return {"score": score, "status": status}