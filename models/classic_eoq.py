# models/classic_eoq.py
# Compatibility wrapper: use the enhanced result contract everywhere.

from models.enhanced_classic_eoq import EnhancedClassicEOQ, EnhancedEOQResult

EOQResult = EnhancedEOQResult


class ClassicEOQ(EnhancedClassicEOQ):
    def __init__(self, item_id, item_name, demand, ordering_cost, holding_cost, unit_cost, lead_time=0):
        super().__init__(
            item_id=item_id,
            item_name=item_name,
            demand=demand,
            unit_cost=unit_cost,
            lead_time_days=lead_time,
            holding_cost_override=holding_cost,
            ordering_cost_override=ordering_cost,
        )
