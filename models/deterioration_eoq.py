# models/deterioration_eoq.py

import numpy as np

from models.enhanced_classic_eoq import EnhancedEOQResult


class DeteriorationEOQ:
    """
    EOQ model for deteriorating/perishable items.

    If shortage_allowed=False, uses deterioration-adjusted EOQ:
        H_eff = H + theta*C

    If shortage_allowed=True, uses a planned-backorder variant with H_eff.
    This makes shortage_allowed and backorder_cost active API inputs rather
    than silently ignored parameters.
    """

    def __init__(self, item_id, item_name, demand, ordering_cost, holding_cost, deterioration_rate, unit_cost, lead_time=0, shortage_allowed=False, backorder_cost=0):
        if demand <= 0 or ordering_cost <= 0 or holding_cost <= 0:
            raise ValueError(
                "demand, ordering_cost, and holding_cost must be > 0.")
        if deterioration_rate < 0 or unit_cost < 0 or lead_time < 0:
            raise ValueError(
                "deterioration_rate, unit_cost, and lead_time must be >= 0.")
        if shortage_allowed and backorder_cost <= 0:
            raise ValueError(
                "backorder_cost must be > 0 when shortage_allowed=True.")
        self.item_id = item_id
        self.item_name = item_name
        self.D = float(demand)
        self.S = float(ordering_cost)
        self.H = float(holding_cost)
        self.theta = float(deterioration_rate)
        self.C = float(unit_cost)
        self.L_days = float(lead_time)
        self.shortage_allowed = bool(shortage_allowed)
        self.B = float(backorder_cost)

    def calculate(self) -> EnhancedEOQResult:
        effective_H = self.H + self.theta * self.C
        if effective_H <= 0:
            raise ValueError("effective holding cost must be > 0.")

        if self.shortage_allowed:
            eoq = np.sqrt((2 * self.D * self.S) / effective_H) * \
                np.sqrt((effective_H + self.B) / self.B)
            max_backorder = eoq * (effective_H / (effective_H + self.B))
            max_inventory = eoq - max_backorder
            avg_inventory_area_factor = (max_inventory ** 2) / (2 * eoq)
            ordering_cost = (self.D / eoq) * self.S
            holding_cost = avg_inventory_area_factor * self.H
            deterioration_cost = avg_inventory_area_factor * self.theta * self.C
            backorder_cost = (max_backorder ** 2) / (2 * eoq) * self.B
            purchase_cost = self.D * self.C
            total_cost = ordering_cost + holding_cost + \
                deterioration_cost + backorder_cost + purchase_cost
            model_type = "EOQ with Deterioration and Backorders"
        else:
            eoq = np.sqrt((2 * self.D * self.S) / effective_H)
            max_backorder = None
            max_inventory = eoq
            ordering_cost = (self.D / eoq) * self.S
            holding_cost = (eoq / 2) * self.H
            deterioration_cost = (eoq / 2) * self.theta * self.C
            backorder_cost = 0.0
            purchase_cost = self.D * self.C
            total_cost = ordering_cost + holding_cost + deterioration_cost + purchase_cost
            model_type = "EOQ with Deterioration"

        lead_time_demand = (self.D / 365) * self.L_days
        rop = max(0.0, lead_time_demand - (max_backorder or 0))
        cycle_days = (eoq / self.D) * 365
        shelf_life_days = float("inf") if self.theta == 0 else 365 / self.theta
        warning = "Cycle > shelf life" if cycle_days > shelf_life_days else "OK"

        return EnhancedEOQResult(
            item_id=self.item_id,
            item_name=self.item_name,
            model_type=model_type,
            eoq=round(eoq, 2),
            total_cost=round(total_cost, 2),
            order_frequency=round(self.D / eoq, 2),
            cycle_time=round(cycle_days, 2),
            unit_cost=round(self.C, 4),
            holding_cost_per_unit=round(effective_H, 4),
            ordering_cost_per_order=round(self.S, 4),
            reorder_point=round(rop, 2),
            max_inventory=round(max_inventory, 2),
            cost_breakdown={
                "annual_ordering_cost": round(ordering_cost, 2),
                "annual_holding_cost": round(holding_cost, 2),
                "annual_deterioration_cost": round(deterioration_cost, 2),
                "annual_backorder_cost": round(backorder_cost, 2),
                "annual_purchase_cost": round(purchase_cost, 2),
                "total_cost": round(total_cost, 2),
                "cost_per_unit": round(total_cost / self.D, 4),
            },
            holding_breakdown={
                "base_holding_cost": round(self.H, 4),
                "deterioration_holding_equivalent": round(self.theta * self.C, 4),
                "total_holding_cost": round(effective_H, 4),
            },
            ordering_breakdown={"total_ordering_cost": round(
                self.S, 4), "fixed_component": round(self.S, 4), "source": "Manual Override"},
            details={
                "deterioration_rate": round(self.theta, 4),
                "shelf_life_days": round(shelf_life_days, 2) if np.isfinite(shelf_life_days) else "infinite",
                "shortage_allowed": self.shortage_allowed,
                "max_backorder": round(max_backorder, 2) if max_backorder is not None else None,
                "backorder_cost_per_unit_year": round(self.B, 4) if self.shortage_allowed else None,
                "warning": warning,
            },
        )
