# optimizer/multi_item_optimizer.py

from typing import Dict, List, Tuple

import numpy as np
from scipy import stats
from scipy.optimize import minimize


class MultiItemOptimizer:
    """Constrained multi-item optimization with enhanced-model cost logic.

    Supported item types:
    - classic: classic EOQ cost
    - poq / Production Order Quantity: finite-production inventory factor
    - stochastic / Stochastic EOQ: safety-stock holding and expected stockout cost

    Constraint semantics:
    - max_order_value limits cash required for the order/run quantity Q.
    - max_space limits peak inventory footprint, not raw Q, so POQ and stochastic
      items use their model-specific maximum inventory.
    """

    def __init__(self, items: List[Dict]):
        if not items:
            raise ValueError("items cannot be empty.")
        self.items = items
        self.n = len(items)

    @staticmethod
    def _item_params(item: Dict) -> Tuple[float, float, float, float, float]:
        D = float(item["demand"])
        S = float(item.get("ordering_cost", item.get("setup_cost", 0)))
        H = float(item.get("holding_cost", item.get("holding_cost_per_unit", 0)))
        C = float(item.get("unit_cost", 0))
        space = float(item.get("storage_space", 0) or 0)
        if D <= 0 or S <= 0 or H <= 0 or C < 0 or space < 0:
            raise ValueError(
                f"Invalid optimization parameters for item {item.get('id', item.get('name', 'unknown'))}."
            )
        return D, S, H, C, space

    @staticmethod
    def _is_poq(item: Dict) -> bool:
        return item.get("type") == "poq" or "Production Order Quantity" in str(item.get("model_type", ""))

    @staticmethod
    def _is_stochastic(item: Dict) -> bool:
        return item.get("type") == "stochastic" or "Stochastic" in str(item.get("model_type", ""))

    def _production_factor(self, item: Dict, D: float) -> float:
        if not self._is_poq(item):
            return 1.0
        P = float(item.get("production_rate") or 0)
        if P <= D:
            raise ValueError(
                f"production_rate must exceed demand for item {item.get('id', item.get('name'))}.")
        return 1 - D / P

    def _stochastic_terms(self, item: Dict, D: float) -> Tuple[float, float]:
        if not self._is_stochastic(item):
            return 0.0, 0.0
        service_level = float(item.get("service_level", 0.95) or 0.95)
        if not 0 < service_level < 1:
            raise ValueError(
                "service_level must be between 0 and 1 for stochastic optimization.")
        daily_demand = D / 365
        demand_std = float(item.get("demand_std", 0) or 0)
        lead_time_days = float(item.get("lead_time", 0) or 0)
        lead_time_std = float(item.get("lead_time_std", 0) or 0)
        sigma_lt = np.sqrt(lead_time_days * demand_std **
                           2 + daily_demand ** 2 * lead_time_std ** 2)
        z = stats.norm.ppf(service_level)
        safety_stock = z * sigma_lt
        expected_stockout = sigma_lt * \
            (stats.norm.pdf(z) - z * (1 - stats.norm.cdf(z)))
        return float(safety_stock), float(expected_stockout)

    def _optimal_quantity(self, item: Dict) -> float:
        D, S, H, _, _ = self._item_params(item)
        if self._is_poq(item):
            factor = self._production_factor(item, D)
            return float(np.sqrt((2 * D * S) / (H * factor)))
        if self._is_stochastic(item):
            _, expected_stockout = self._stochastic_terms(item, D)
            stockout_cost = float(item.get("stockout_cost", 0) or 0)
            # The stochastic total-cost curve has (D/Q) * expected_stockout * B,
            # so expected stockout cost behaves like an added per-cycle setup term.
            return float(np.sqrt((2 * D * (S + expected_stockout * stockout_cost)) / H))
        return float(np.sqrt((2 * D * S) / H))

    def _annual_cost_for_quantity(self, item: Dict, Q: float) -> float:
        D, S, H, C, _ = self._item_params(item)
        if Q <= 0 or not np.isfinite(Q):
            return float("inf")
        if self._is_poq(item):
            factor = self._production_factor(item, D)
            max_inventory = Q * factor
            return float((D / Q) * S + (max_inventory / 2) * H + D * C)
        if self._is_stochastic(item):
            safety_stock, expected_stockout = self._stochastic_terms(item, D)
            stockout_cost = float(item.get("stockout_cost", 0) or 0)
            return float((D / Q) * S + (Q / 2) * H + safety_stock * H + D * C + (D / Q) * expected_stockout * stockout_cost)
        return float((D / Q) * S + (Q / 2) * H + D * C)

    def _peak_inventory_for_quantity(self, item: Dict, Q: float) -> float:
        D, _, _, _, _ = self._item_params(item)
        if self._is_poq(item):
            return float(Q * self._production_factor(item, D))
        if self._is_stochastic(item):
            safety_stock, _ = self._stochastic_terms(item, D)
            return float(Q + safety_stock)
        return float(Q)

    def _space_required(self, item: Dict, Q: float) -> float:
        *_, space = self._item_params(item)
        return self._peak_inventory_for_quantity(item, Q) * space

    def _order_value_required(self, item: Dict, Q: float) -> float:
        _, _, _, C, _ = self._item_params(item)
        return Q * C

    def unconstrained_eoq(self):
        results = []
        for item in self.items:
            q = self._optimal_quantity(item)
            results.append({
                **item,
                "eoq": round(q, 2),
                "total_cost": round(self._annual_cost_for_quantity(item, q), 2),
                "orders_per_year": round(self._item_params(item)[0] / q, 2),
                "order_value_required": round(self._order_value_required(item, q), 2),
                "space_required": round(self._space_required(item, q), 2),
                "peak_inventory": round(self._peak_inventory_for_quantity(item, q), 2),
            })
        return results

    def total_cost(self, quantities):
        total = 0.0
        for i, item in enumerate(self.items):
            total += self._annual_cost_for_quantity(item, float(quantities[i]))
        return total

    def _initial_quantities(self):
        return [max(1.0, self._optimal_quantity(item)) for item in self.items]

    def order_value_constrained_optimize(self, max_order_value: float):
        if max_order_value <= 0:
            return {"error": "max_order_value must be > 0."}
        min_required = sum(self._order_value_required(item, 1)
                           for item in self.items)
        if max_order_value < min_required:
            return {"error": f"Constraint infeasible: minimum order value at Q=1 is ${min_required:,.2f}."}
        constraints = {"type": "ineq", "fun": lambda Q: max_order_value -
                       sum(self._order_value_required(self.items[i], Q[i]) for i in range(self.n))}
        result = minimize(self.total_cost, self._initial_quantities(), method="SLSQP", bounds=[
                          (1, None)] * self.n, constraints=constraints, options={"ftol": 1e-9, "maxiter": 1000})
        return self._format_results(result, "Order-Value Constrained", max_order_value)

    def budget_constrained_optimize(self, budget: float):
        return self.order_value_constrained_optimize(budget)

    def storage_constrained_optimize(self, max_space: float):
        if max_space <= 0:
            return {"error": "max_space must be > 0."}
        min_required = sum(self._space_required(item, 1)
                           for item in self.items)
        if max_space < min_required:
            return {"error": f"Constraint infeasible: minimum model-aware peak space at Q=1 is {min_required:,.2f}."}
        constraints = {"type": "ineq", "fun": lambda Q: max_space -
                       sum(self._space_required(self.items[i], Q[i]) for i in range(self.n))}
        result = minimize(self.total_cost, self._initial_quantities(), method="SLSQP", bounds=[
                          (1, None)] * self.n, constraints=constraints, options={"ftol": 1e-9, "maxiter": 1000})
        return self._format_results(result, "Space Constrained", max_space)

    def dual_constrained_optimize(self, max_order_value: float, max_space: float):
        if max_order_value <= 0 or max_space <= 0:
            return {"error": "max_order_value and max_space must be > 0."}
        min_value = sum(self._order_value_required(item, 1)
                        for item in self.items)
        min_space = sum(self._space_required(item, 1) for item in self.items)
        if max_order_value < min_value or max_space < min_space:
            return {"error": "Constraints infeasible even at minimum quantity Q=1 for each item."}
        constraints = [
            {"type": "ineq", "fun": lambda Q: max_order_value -
                sum(self._order_value_required(self.items[i], Q[i]) for i in range(self.n))},
            {"type": "ineq", "fun": lambda Q: max_space -
                sum(self._space_required(self.items[i], Q[i]) for i in range(self.n))},
        ]
        result = minimize(self.total_cost, self._initial_quantities(), method="SLSQP", bounds=[
                          (1, None)] * self.n, constraints=constraints, options={"ftol": 1e-9, "maxiter": 1000})
        return self._format_results(result, "Dual Constrained", {"max_order_value": max_order_value, "max_space": max_space})

    def _format_results(self, result, constraint_type, constraint_value):
        if not result.success:
            return {"error": str(result.message), "converged": False}
        item_results = []
        for i, item in enumerate(self.items):
            Q = float(result.x[i])
            D = self._item_params(item)[0]
            item_results.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "model_type": item.get("model_type", item.get("type", "classic")),
                "optimal_qty": round(Q, 2),
                "orders_per_year": round(D / Q, 2),
                "annual_cost": round(self._annual_cost_for_quantity(item, Q), 2),
                "order_value_used": round(self._order_value_required(item, Q), 2),
                "space_used": round(self._space_required(item, Q), 2),
                "peak_inventory": round(self._peak_inventory_for_quantity(item, Q), 2),
            })
        return {
            "constraint_type": constraint_type,
            "constraint_value": constraint_value,
            "total_cost": round(float(result.fun), 2),
            "items": item_results,
            "converged": True,
        }
