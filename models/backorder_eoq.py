# models/backorder_eoq.py

import numpy as np

from models.enhanced_classic_eoq import EnhancedEOQResult


class BackorderEOQ:
    """EOQ model with planned backorders, returning EnhancedEOQResult."""

    def __init__(self, item_id, item_name, demand, ordering_cost, holding_cost, backorder_cost, unit_cost, lead_time=0):
        if demand <= 0 or ordering_cost <= 0 or holding_cost <= 0 or backorder_cost <= 0:
            raise ValueError("demand, ordering_cost, holding_cost, and backorder_cost must be > 0.")
        if unit_cost < 0 or lead_time < 0:
            raise ValueError("unit_cost and lead_time must be >= 0.")
        self.item_id = item_id
        self.item_name = item_name
        self.D = float(demand)
        self.S = float(ordering_cost)
        self.H = float(holding_cost)
        self.B = float(backorder_cost)
        self.C = float(unit_cost)
        self.L_days = float(lead_time)

    def calculate(self) -> EnhancedEOQResult:
        eoq = np.sqrt((2 * self.D * self.S / self.H) * ((self.H + self.B) / self.B))
        max_backorder = eoq * (self.H / (self.H + self.B))
        max_inventory = eoq - max_backorder
        ordering_cost = (self.D / eoq) * self.S
        holding_cost = (max_inventory ** 2) / (2 * eoq) * self.H
        backorder_cost = (max_backorder ** 2) / (2 * eoq) * self.B
        purchase_cost = self.D * self.C
        total_cost = ordering_cost + holding_cost + backorder_cost + purchase_cost
        # Trigger earlier to allow planned backorder during lead-time demand.
        rop = max((self.D / 365) * self.L_days - max_backorder, 0)

        return EnhancedEOQResult(
            item_id=self.item_id,
            item_name=self.item_name,
            model_type="EOQ with Planned Backorders",
            eoq=round(eoq, 2),
            total_cost=round(total_cost, 2),
            order_frequency=round(self.D / eoq, 2),
            cycle_time=round((eoq / self.D) * 365, 2),
            unit_cost=round(self.C, 4),
            holding_cost_per_unit=round(self.H, 4),
            ordering_cost_per_order=round(self.S, 4),
            reorder_point=round(rop, 2),
            max_inventory=round(max_inventory, 2),
            cost_breakdown={
                "annual_ordering_cost": round(ordering_cost, 2),
                "annual_holding_cost": round(holding_cost, 2),
                "annual_backorder_cost": round(backorder_cost, 2),
                "annual_purchase_cost": round(purchase_cost, 2),
                "total_cost": round(total_cost, 2),
                "cost_per_unit": round(total_cost / self.D, 4),
            },
            holding_breakdown={"total_holding_cost": round(self.H, 4), "source": "Manual Override"},
            ordering_breakdown={"total_ordering_cost": round(self.S, 4), "fixed_component": round(self.S, 4), "source": "Manual Override"},
            details={"max_backorder": round(max_backorder, 2)},
        )
