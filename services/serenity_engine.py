class SerenityEngine:
    @staticmethod
    def analyze_finances(transactions):
        # Si aucune transaction, on évite la division par zéro
        if not transactions:
            return {
                "score": 100, 
                "status": "Stable", 
                "total_spent": 0, 
                "wants_spent": 0
            }

        # 1. Calcul des totaux
        total_spent = sum(t['amount'] for t in transactions)
        # On calcule les dépenses "plaisir" (is_essential: False)
        wants_spent = sum(t['amount'] for t in transactions if not t.get('is_essential', True))
        
        # 2. Calcul du ratio (Règle des 30% max pour les envies)
        wants_ratio = (wants_spent / total_spent) if total_spent > 0 else 0
        
        # 3. Calcul du Score
        if wants_ratio <= 0.30:
            score = 100
        else:
            # On retire 2 points pour chaque 1% au-dessus de la limite de 30%
            excess = (wants_ratio - 0.30) * 100
            score = 100 - (excess * 2)

        # On verrouille entre 0 et 100
        score = max(0, min(100, int(score)))

        # 4. Détermination du statut
        if score >= 80: 
            status = "Excellent"
        elif score >= 50: 
            status = "Warning"
        else: 
            status = "Critical"

        # ON RETOURNE TOUTES LES CLÉS NÉCESSAIRES
        return {
            "score": score,
            "status": status,
            "total_spent": round(total_spent, 2),
            "wants_spent": round(wants_spent, 2)
        }