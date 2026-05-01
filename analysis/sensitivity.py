from dataclasses import dataclass
from numbers import Number
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class SensitivityResult:
    parameter: str
    base_value: float
    base_eoq: float
    base_cost: float
    variations: List[float]
    eoq_values: List[float]
    cost_values: List[float]
    elasticity: float          # EOQ elasticity
    critical_range: Tuple[float, float]
    sensitivity_rank: int
    cost_elasticity: float = 0.0


class SensitivityAnalyzer:
    """Sensitivity analysis for enhanced EOQ results.

    Uses the same cost logic as the enhanced models:
    - POQ uses finite-production average inventory.
    - Stochastic EOQ includes safety stock holding and expected stockout cost.
    - Component-based holding costs are recalculated when unit cost changes.
    """

    def __init__(self, item_config: dict, result):
        self.cfg = item_config
        self.result = result
        self.base_eoq = float(result.eoq)
        self.base_cost = float(result.total_cost)
        self.D = float(item_config.get("demand", 0) or getattr(
            result, "order_frequency", 0) * self.base_eoq)
        self.C = float(getattr(result, "unit_cost",
                       item_config.get("unit_cost", 0)))
        self.H = float(result.holding_cost_per_unit)
        self.S = float(result.ordering_cost_per_order)
        self.production_rate = item_config.get("production_rate")
        self.model_type = str(getattr(result, "model_type", ""))
        self.is_stochastic = item_config.get(
            "type") == "stochastic" or "Stochastic" in self.model_type
        self.hc_components = item_config.get("hc_components")
        self.hc_override = item_config.get(
            "hc_override", item_config.get("holding_cost"))
        self.stockout_cost = float(item_config.get("stockout_cost", 0) or 0)
        self.demand_std = float(item_config.get("demand_std", 0) or 0)
        self.lead_time_days = float(item_config.get("lead_time", 0) or 0)
        self.lead_time_std = float(item_config.get("lead_time_std", 0) or 0)
        self.service_level = float(
            item_config.get("service_level", 0.95) or 0.95)
        if self.D <= 0 or self.H <= 0 or self.S <= 0:
            raise ValueError(
                "Sensitivity analysis requires demand, holding cost, and ordering cost to be > 0.")
        if self.is_stochastic and not 0 < self.service_level < 1:
            raise ValueError(
                "Stochastic sensitivity requires service_level between 0 and 1.")

    def _holding_cost_for_unit(self, unit_cost: float) -> float:
        """Recalculate H when detailed holding components are present.

        Simple-mode/manual holding-cost overrides intentionally stay fixed.
        """
        if self.hc_override is not None or self.hc_components is None:
            return self.H
        return float(self.hc_components.calculate(unit_cost)["total_holding_cost"])

    def _stochastic_terms(self, D: float) -> Tuple[float, float]:
        """Return safety stock and expected shortage units per cycle."""
        if not self.is_stochastic:
            return float(self.result.safety_stock or 0), 0.0
        daily_demand = D / 365
        sigma_lt = np.sqrt(
            self.lead_time_days * self.demand_std ** 2
            + daily_demand ** 2 * self.lead_time_std ** 2
        )
        z = stats.norm.ppf(self.service_level)
        safety_stock = z * sigma_lt
        expected_stockout = sigma_lt * \
            (stats.norm.pdf(z) - z * (1 - stats.norm.cdf(z)))
        return float(safety_stock), float(expected_stockout)

    def _eoq(self, D, S, H):
        if self.production_rate:
            P = float(self.production_rate)
            if P <= D:
                raise ValueError(
                    "production_rate must exceed demand during sensitivity analysis.")
            return np.sqrt((2 * D * S) / (H * (1 - D / P)))
        if self.is_stochastic:
            _, expected_stockout = self._stochastic_terms(D)
            effective_setup = S + expected_stockout * self.stockout_cost
            return np.sqrt((2 * D * effective_setup) / H)
        return np.sqrt((2 * D * S) / H)

    def _total_cost(self, D, S, H, C, Q=None):
        if Q is None:
            Q = self._eoq(D, S, H)
        if Q <= 0:
            return float("inf")
        if self.production_rate:
            P = float(self.production_rate)
            max_inventory = Q * (1 - D / P)
            return (D / Q) * S + (max_inventory / 2) * H + D * C
        safety_stock, expected_stockout = self._stochastic_terms(D)
        stockout_cost = (D / Q) * expected_stockout * \
            self.stockout_cost if self.is_stochastic else 0.0
        return (D / Q) * S + (Q / 2) * H + safety_stock * H + D * C + stockout_cost

    @staticmethod
    def _elasticity(x_vals, y_vals, base_x, base_y):
        x = np.array(x_vals, dtype=float)
        y = np.array(y_vals, dtype=float)
        if base_x == 0 or base_y == 0 or len(x) < 3:
            return 0.0
        idx = int(np.argmin(np.abs(x - base_x)))
        idx = max(1, min(idx, len(x) - 2))
        dx = (x[idx + 1] - x[idx - 1]) / base_x
        dy = (y[idx + 1] - y[idx - 1]) / base_y
        return round(float(dy / dx), 4) if dx != 0 else 0.0

    @staticmethod
    def _critical_range(x_vals, eoq_vals, base_eoq, tolerance=0.10):
        lower, upper = x_vals[0], x_vals[-1]
        for x, e in zip(x_vals, eoq_vals):
            if abs(e - base_eoq) / base_eoq <= tolerance:
                lower = x
                break
        for x, e in zip(reversed(x_vals), reversed(eoq_vals)):
            if abs(e - base_eoq) / base_eoq <= tolerance:
                upper = x
                break
        return (round(float(lower), 4), round(float(upper), 4))

    def _analyze(self, name, base, setter, pct_range=50, steps=100) -> SensitivityResult:
        if base < 0:
            raise ValueError(f"{name} base value must be >= 0.")
        low = max(base * (1 - pct_range / 100),
                  0.0001 if name != "Unit Cost (C)" else 0)
        high = base * (1 + pct_range / 100)
        variations = np.linspace(low, high, steps)
        eoq_vals, cost_vals = [], []
        for v in variations:
            D, S, H, C = self.D, self.S, self.H, self.C
            D, S, H, C = setter(v, D, S, H, C)
            eoq = self._eoq(D, S, H)
            cost = self._total_cost(D, S, H, C, eoq)
            eoq_vals.append(float(eoq))
            cost_vals.append(float(cost))
        return SensitivityResult(
            parameter=name,
            base_value=float(base),
            base_eoq=self.base_eoq,
            base_cost=self.base_cost,
            variations=list(map(float, variations)),
            eoq_values=eoq_vals,
            cost_values=cost_vals,
            elasticity=self._elasticity(
                variations, eoq_vals, base, self.base_eoq),
            cost_elasticity=self._elasticity(
                variations, cost_vals, base, self.base_cost),
            critical_range=self._critical_range(
                list(variations), eoq_vals, self.base_eoq),
            sensitivity_rank=0,
        )

    def analyze_demand(self, pct_range=50, steps=100):
        return self._analyze("Annual Demand (D)", self.D, lambda v, D, S, H, C: (v, S, H, C), pct_range, steps)

    def analyze_ordering_cost(self, pct_range=50, steps=100):
        return self._analyze("Ordering Cost (S)", self.S, lambda v, D, S, H, C: (D, v, H, C), pct_range, steps)

    def analyze_holding_cost(self, pct_range=50, steps=100):
        return self._analyze("Holding Cost (H)", self.H, lambda v, D, S, H, C: (D, S, v, C), pct_range, steps)

    def analyze_unit_cost(self, pct_range=50, steps=100):
        return self._analyze(
            "Unit Cost (C)",
            self.C,
            lambda v, D, S, H, C: (D, S, self._holding_cost_for_unit(v), v),
            pct_range,
            steps,
        )

    def analyze_holding_components(self) -> Dict[str, SensitivityResult]:
        hb = self.result.holding_breakdown or {}
        if not hb or "source" in hb:
            return {}
        components = {
            k: float(v) for k, v in hb.items()
            if k != "total_holding_cost" and isinstance(v, Number) and v > 0
        }
        out = {}
        for name, base_val in components.items():
            variations = np.linspace(0, base_val * 3, 100)
            eoq_vals, cost_vals = [], []
            for new_val in variations:
                new_H = max(self.H - base_val + new_val, 0.0001)
                eoq = self._eoq(self.D, self.S, new_H)
                cost = self._total_cost(self.D, self.S, new_H, self.C, eoq)
                eoq_vals.append(float(eoq))
                cost_vals.append(float(cost))
            out[name] = SensitivityResult(
                parameter=name.replace("_", " ").title(),
                base_value=base_val,
                base_eoq=self.base_eoq,
                base_cost=self.base_cost,
                variations=list(map(float, variations)),
                eoq_values=eoq_vals,
                cost_values=cost_vals,
                elasticity=self._elasticity(
                    variations, eoq_vals, base_val, self.base_eoq),
                cost_elasticity=self._elasticity(
                    variations, cost_vals, base_val, self.base_cost),
                critical_range=self._critical_range(
                    list(variations), eoq_vals, self.base_eoq),
                sensitivity_rank=0,
            )
        return out

    def analyze_ordering_components(self) -> Dict[str, SensitivityResult]:
        ob = self.result.ordering_breakdown or {}
        if not ob or "source" in ob:
            return {}
        skip = {"total_ordering_cost", "fixed_component",
                "variable_component", "freight_variable", "inspection_cost"}
        components = {k: float(v) for k, v in ob.items(
        ) if k not in skip and isinstance(v, Number) and v > 0}
        out = {}
        for name, base_val in components.items():
            variations = np.linspace(0, base_val * 3, 100)
            eoq_vals, cost_vals = [], []
            for new_val in variations:
                new_S = max(self.S - base_val + new_val, 0.0001)
                eoq = self._eoq(self.D, new_S, self.H)
                cost = self._total_cost(self.D, new_S, self.H, self.C, eoq)
                eoq_vals.append(float(eoq))
                cost_vals.append(float(cost))
            out[name] = SensitivityResult(
                parameter=name.replace("_", " ").title(),
                base_value=base_val,
                base_eoq=self.base_eoq,
                base_cost=self.base_cost,
                variations=list(map(float, variations)),
                eoq_values=eoq_vals,
                cost_values=cost_vals,
                elasticity=self._elasticity(
                    variations, eoq_vals, base_val, self.base_eoq),
                cost_elasticity=self._elasticity(
                    variations, cost_vals, base_val, self.base_cost),
                critical_range=self._critical_range(
                    list(variations), eoq_vals, self.base_eoq),
                sensitivity_rank=0,
            )
        return out

    def rank_parameters(self, pct_range=50) -> List[SensitivityResult]:
        analyses = [
            self.analyze_demand(pct_range=pct_range),
            self.analyze_ordering_cost(pct_range=pct_range),
            self.analyze_holding_cost(pct_range=pct_range),
            self.analyze_unit_cost(pct_range=pct_range),
        ]
        ranked = sorted(analyses, key=lambda x: abs(
            x.cost_elasticity), reverse=True)
        for rank, result in enumerate(ranked, 1):
            result.sensitivity_rank = rank
        return ranked

    def run_full_analysis(self, pct_range=50) -> Dict:
        ranked = self.rank_parameters(pct_range=pct_range)
        hc_components = self.analyze_holding_components()
        oc_components = self.analyze_ordering_components()
        tornado_data = []
        for r in ranked:
            cost_low = r.cost_values[0]
            cost_high = r.cost_values[-1]
            tornado_data.append({
                "Parameter": r.parameter,
                "Low Cost": min(cost_low, cost_high),
                "High Cost": max(cost_low, cost_high),
                "Range": abs(cost_high - cost_low),
                "Elasticity": r.cost_elasticity,
                "EOQ Elasticity": r.elasticity,
            })
        return {
            "ranked_parameters": ranked,
            "holding_components": hc_components,
            "ordering_components": oc_components,
            "tornado_data": pd.DataFrame(tornado_data).sort_values("Range", ascending=True),
            "base_eoq": self.base_eoq,
            "base_cost": self.base_cost,
        }

    def two_way_sensitivity(self, param1="demand", param2="holding_cost", steps=20) -> Dict:
        param_map = {
            "demand": self.D,
            "ordering_cost": self.S,
            "holding_cost": self.H,
            "unit_cost": self.C,
        }
        if param1 not in param_map or param2 not in param_map:
            raise ValueError(
                f"Parameters must be one of: {', '.join(param_map)}")
        if param1 == param2:
            raise ValueError("param1 and param2 must be different.")

        range1 = np.linspace(
            param_map[param1] * 0.5, param_map[param1] * 1.5, steps)
        range2 = np.linspace(
            param_map[param2] * 0.5, param_map[param2] * 1.5, steps)
        eoq_matrix = np.zeros((steps, steps))
        cost_matrix = np.zeros((steps, steps))

        for i, v1 in enumerate(range1):
            for j, v2 in enumerate(range2):
                params = {
                    "demand": self.D,
                    "ordering_cost": self.S,
                    "holding_cost": self.H,
                    "unit_cost": self.C,
                }
                params[param1] = max(
                    v1, 0.0001 if param1 != "unit_cost" else 0)
                params[param2] = max(
                    v2, 0.0001 if param2 != "unit_cost" else 0)
                if "unit_cost" in {param1, param2} and "holding_cost" not in {param1, param2}:
                    params["holding_cost"] = self._holding_cost_for_unit(
                        params["unit_cost"])
                eoq = self._eoq(
                    params["demand"], params["ordering_cost"], params["holding_cost"])
                cost = self._total_cost(
                    params["demand"], params["ordering_cost"], params["holding_cost"], params["unit_cost"], eoq)
                eoq_matrix[i, j] = eoq
                cost_matrix[i, j] = cost

        return {
            "param1": param1,
            "param2": param2,
            "range1": range1,
            "range2": range2,
            "eoq_matrix": eoq_matrix,
            "cost_matrix": cost_matrix,
        }
