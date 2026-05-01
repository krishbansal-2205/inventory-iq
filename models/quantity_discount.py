# models/quantity_discount.py

import numpy as np

from models.enhanced_classic_eoq import EnhancedEOQResult


class QuantityDiscountEOQ:
    """All-units quantity discount EOQ, returning EnhancedEOQResult."""

    def __init__(self, item_id, item_name, demand, ordering_cost, holding_cost_pct, price_breaks, lead_time=0):
        if demand <= 0 or ordering_cost <= 0 or holding_cost_pct <= 0:
            raise ValueError("demand, ordering_cost, and holding_cost_pct must be > 0.")
        if lead_time < 0:
            raise ValueError("lead_time must be >= 0.")
        if not price_breaks:
            raise ValueError("price_breaks must contain at least one tier.")
        for min_qty, price in price_breaks:
            if min_qty < 0 or price <= 0:
                raise ValueError("Each price break must have min_qty >= 0 and price > 0.")
        self.item_id = item_id
        self.item_name = item_name
        self.D = float(demand)
        self.S = float(ordering_cost)
        self.I = float(holding_cost_pct)
        self.price_breaks = sorted(price_breaks, key=lambda x: x[0])
        self.L_days = float(lead_time)

    def _price_for_qty(self, qty: float) -> float:
        price = self.price_breaks[0][1]
        for min_qty, tier_price in self.price_breaks:
            if qty >= min_qty:
                price = tier_price
            else:
                break
        return price

    def calculate(self) -> EnhancedEOQResult:
        candidates = set()
        # Add every price-break threshold and each feasible EOQ at each tier price.
        for min_qty, price in self.price_breaks:
            candidates.add(float(min_qty if min_qty > 0 else 1))
            H = self.I * price
            eoq = np.sqrt((2 * self.D * self.S) / H)
            if eoq >= min_qty:
                candidates.add(float(eoq))

        options = []
        for qty in sorted(candidates):
            if qty <= 0:
                continue
            price = self._price_for_qty(qty)
            H = self.I * price
            purchase_cost = self.D * price
            ordering_cost = (self.D / qty) * self.S
            holding_cost = (qty / 2) * H
            total_cost = purchase_cost + ordering_cost + holding_cost
            options.append({
                "qty": qty,
                "price": price,
                "holding_cost_per_unit": H,
                "total_cost": total_cost,
                "ordering_cost": ordering_cost,
                "holding_cost": holding_cost,
                "purchase_cost": purchase_cost,
                "price_break_used": max(q for q, _ in self.price_breaks if qty >= q),
            })

        best = min(options, key=lambda x: x["total_cost"])
        rop = (self.D / 365) * self.L_days
        return EnhancedEOQResult(
            item_id=self.item_id,
            item_name=self.item_name,
            model_type="EOQ with Quantity Discounts",
            eoq=round(best["qty"], 2),
            total_cost=round(best["total_cost"], 2),
            order_frequency=round(self.D / best["qty"], 2),
            cycle_time=round((best["qty"] / self.D) * 365, 2),
            unit_cost=round(best["price"], 4),
            holding_cost_per_unit=round(best["holding_cost_per_unit"], 4),
            ordering_cost_per_order=round(self.S, 4),
            reorder_point=round(rop, 2),
            cost_breakdown={
                "annual_ordering_cost": round(best["ordering_cost"], 2),
                "annual_holding_cost": round(best["holding_cost"], 2),
                "annual_purchase_cost": round(best["purchase_cost"], 2),
                "total_cost": round(best["total_cost"], 2),
                "cost_per_unit": round(best["total_cost"] / self.D, 4),
            },
            holding_breakdown={"total_holding_cost": round(best["holding_cost_per_unit"], 4), "source": "Price-tier percentage"},
            ordering_breakdown={"total_ordering_cost": round(self.S, 4), "fixed_component": round(self.S, 4), "source": "Manual Override"},
            details={
                "optimal_price": best["price"],
                "price_break_used": best["price_break_used"],
                "all_options": [{**o, "qty": round(o["qty"], 2), "total_cost": round(o["total_cost"], 2)} for o in options],
            },
        )
