# services/serenity_engine.py

class SerenityEngine:
    """
    Logique métier pour le calcul du Score de Sérénité.
    """
    
    @staticmethod
    def calculate_score(income: float, expenses: float, savings: float) -> float:
        """
        Calcule un score sur 100 basé sur les finances de l'utilisateur.
        """
        if income <= 0:
            return 0.0
        
        # Calcul du ratio d'épargne (50% du score)
        # Un bon ratio est de 20% (0.2)
        savings_ratio = savings / income
        savings_score = (savings_ratio / 0.2) * 50
        
        # Calcul du ratio de dépenses (50% du score)
        # On veut que les dépenses soient < 70% du revenu
        expense_ratio = expenses / income
        expense_score = (1 - expense_ratio) * 50
        
        # Somme des scores et limitation entre 0 et 100
        total_score = savings_score + expense_score
        return round(max(0.0, min(100.0, total_score)), 2)