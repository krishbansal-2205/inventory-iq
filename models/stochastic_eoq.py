# models/stochastic_eoq.py
# Compatibility wrapper: delegates to enhanced stochastic EOQ.

from models.enhanced_classic_eoq import EnhancedStochasticEOQ


class StochasticEOQ(EnhancedStochasticEOQ):
    def __init__(self, item_id, item_name, avg_daily_demand, demand_std, ordering_cost, holding_cost, unit_cost, lead_time, service_level=0.95, stockout_cost=None):
        super().__init__(
            item_id=item_id,
            item_name=item_name,
            avg_daily_demand=avg_daily_demand,
            demand_std=demand_std,
            lead_time_days=lead_time,
            unit_cost=unit_cost,
            service_level=service_level,
            holding_cost_override=holding_cost,
            ordering_cost_override=ordering_cost,
            stockout_cost_per_unit=stockout_cost or 0.0,
        )
