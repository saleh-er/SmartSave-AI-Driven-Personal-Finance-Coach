from datetime import datetime

class BudgetAnalyzer:
    @staticmethod
    def get_category_insights(tx_list, total_spent):
        icons = {
            "Food": "fa-utensils", "Transport": "fa-car", "Housing": "fa-house",
            "Shopping": "fa-bag-shopping", "Health": "fa-heart-pulse", 
            "Entertainment": "fa-gamepad", "Bills": "fa-file-invoice-dollar"
        }
        
        cat_totals = {}
        for t in tx_list:
            name = t.category if hasattr(t, 'category') else t['category']
            amt = float(t.amount if hasattr(t, 'amount') else t['amount'])
            cat_totals[name] = cat_totals.get(name, 0) + amt

        insights = []
        for name, amt in sorted(cat_totals.items(), key=lambda x: x[1], reverse=True):
            percentage = int((amt / total_spent * 100)) if total_spent > 0 else 0
            is_high = percentage > 30
            
            insights.append({
                "name": name,
                "amount": round(amt, 2),
                "percentage": percentage,
                "icon": icons.get(name, "fa-tag"),
                "color": "#EF4444" if is_high else "#10B981",
                "status": "High Spending" if is_high else "On track"
            })
        return insights