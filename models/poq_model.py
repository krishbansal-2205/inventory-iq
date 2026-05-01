# models/poq_model.py
# Compatibility wrapper: delegates to enhanced POQ.

from models.enhanced_classic_eoq import EnhancedPOQ


class ProductionOrderQuantity(EnhancedPOQ):
    def __init__(self, item_id, item_name, demand, ordering_cost, holding_cost, production_rate, unit_cost, lead_time=0):
        super().__init__(
            item_id=item_id,
            item_name=item_name,
            demand=demand,
            production_rate=production_rate,
            lead_time_days=lead_time,
            holding_cost_override=holding_cost,
            setup_cost_override=ordering_cost,
            unit_cost_override=unit_cost,
        )
