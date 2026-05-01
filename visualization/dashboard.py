# visualization/dashboard.py

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


class EOQDashboard:
    """Legacy Matplotlib dashboard with enhanced-result compatibility.

    The chart math is model-aware so POQ and stochastic charts reconcile with
    their enhanced EOQ result objects instead of falling back to classic EOQ.
    """

    def __init__(self, results, items):
        self.results = results
        self.items = items
        try:
            plt.style.use("seaborn-v0_8-darkgrid")
        except OSError:
            plt.style.use("default")

    def _result_for_item(self, item_idx=0, model="classic"):
        item_result = self.results[item_idx]
        if isinstance(item_result, tuple) and len(item_result) == 2:
            return item_result[1]
        if isinstance(item_result, dict):
            models = item_result.get("models", {})
            return models.get(model) or next(iter(models.values()), None)
        return item_result

    @staticmethod
    def _is_poq(item, result):
        return item.get("type") == "poq" or "Production Order Quantity" in str(getattr(result, "model_type", ""))

    @staticmethod
    def _is_stochastic(item, result):
        return item.get("type") == "stochastic" or "Stochastic" in str(getattr(result, "model_type", ""))

    def _cost_inputs(self, item_idx=0, model="classic"):
        item = self.items[item_idx]
        result = self._result_for_item(item_idx, model)
        D = float(item.get("demand", getattr(
            result, "order_frequency", 0) * getattr(result, "eoq", 0)))
        if result is not None and hasattr(result, "ordering_cost_per_order"):
            S = float(result.ordering_cost_per_order)
            H = float(result.holding_cost_per_unit)
            C = float(getattr(result, "unit_cost", item.get("unit_cost", 0)))
            eoq = float(result.eoq)
            item_name = getattr(result, "item_name", item.get(
                "name", f"Item {item_idx + 1}"))
        else:
            S = float(item["ordering_cost"])
            H = float(item["holding_cost"])
            C = float(item.get("unit_cost", 0))
            eoq = np.sqrt(2 * D * S / H)
            item_name = item.get("name", f"Item {item_idx + 1}")
        if D <= 0 or S <= 0 or H <= 0 or eoq <= 0:
            raise ValueError(
                "demand, ordering/setup cost, holding cost, and EOQ must be > 0.")
        return item, result, D, S, H, C, eoq, item_name

    def _stochastic_terms(self, item, D):
        if not (item.get("type") == "stochastic"):
            return 0.0, 0.0
        service_level = float(item.get("service_level", 0.95) or 0.95)
        if not 0 < service_level < 1:
            return 0.0, 0.0
        daily_d = D / 365
        sigma_lt = np.sqrt(
            float(item.get("lead_time", 0) or 0) *
            float(item.get("demand_std", 0) or 0) ** 2
            + daily_d ** 2 * float(item.get("lead_time_std", 0) or 0) ** 2
        )
        z = stats.norm.ppf(service_level)
        ss = z * sigma_lt
        expected_stockout = sigma_lt * \
            (stats.norm.pdf(z) - z * (1 - stats.norm.cdf(z)))
        return float(ss), float(expected_stockout)

    def _optimal_qty_for(self, item, result, D, S, H):
        if self._is_poq(item, result):
            P = float(item.get("production_rate") or 0)
            if P <= D:
                raise ValueError(
                    "production_rate must exceed demand for POQ charts.")
            return np.sqrt((2 * D * S) / (H * (1 - D / P)))
        if self._is_stochastic(item, result):
            _, expected_stockout = self._stochastic_terms(item, D)
            return np.sqrt((2 * D * (S + expected_stockout * float(item.get("stockout_cost", 0) or 0))) / H)
        return np.sqrt(2 * D * S / H)

    def _annual_relevant_cost(self, item, result, D, S, H, Q):
        if self._is_poq(item, result):
            P = float(item.get("production_rate") or 0)
            return (D / Q) * S + (Q * (1 - D / P) / 2) * H
        if self._is_stochastic(item, result):
            ss, expected_stockout = self._stochastic_terms(item, D)
            return (D / Q) * S + (Q / 2) * H + ss * H + (D / Q) * expected_stockout * float(item.get("stockout_cost", 0) or 0)
        return (D / Q) * S + (Q / 2) * H

    def plot_cost_curves(self, item_idx=0, model="classic"):
        item, result, D, S, H, C, eoq, item_name = self._cost_inputs(
            item_idx, model)
        q_star = float(self._optimal_qty_for(item, result, D, S, H))
        Q = np.linspace(max(1, q_star * 0.1), q_star * 3, 500)
        ordering = (D / Q) * S
        if self._is_poq(item, result):
            P = float(item.get("production_rate") or 0)
            holding = (Q * (1 - D / P) / 2) * H
        elif self._is_stochastic(item, result):
            ss, expected_stockout = self._stochastic_terms(item, D)
            holding = (Q / 2) * H + ss * H
            stockout = (D / Q) * expected_stockout * \
                float(item.get("stockout_cost", 0) or 0)
        else:
            holding = (Q / 2) * H
            stockout = 0
        relevant = ordering + holding + \
            (stockout if self._is_stochastic(item, result) else 0)
        total = relevant + D * C

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(Q, total, linewidth=2, label="Total Cost")
        ax.plot(Q, relevant, linewidth=2, label="Relevant Cost")
        ax.plot(Q, ordering, linestyle="--",
                linewidth=1.5, label="Ordering/Setup Cost")
        ax.plot(Q, holding, linestyle="--",
                linewidth=1.5, label="Holding Cost")
        if self._is_stochastic(item, result) and np.any(stockout):
            ax.plot(Q, stockout, linestyle=":", linewidth=1.5,
                    label="Expected Stockout Cost")
        ax.axvline(x=q_star, linestyle=":", linewidth=2,
                   label=f"Q* = {q_star:.0f}")
        ax.set_xlabel("Order Quantity (units)")
        ax.set_ylabel("Annual Cost ($)")
        ax.set_title(f"Cost Curves - {item_name}")
        ax.legend()
        fig.tight_layout()
        return fig

    def plot_inventory_cycle(self, item_idx=0, model="classic"):
        item, result, D, _, _, _, eoq, item_name = self._cost_inputs(
            item_idx, model)
        if result is None:
            return None
        cycle_days = float(result.cycle_time)
        if cycle_days <= 0:
            raise ValueError("cycle time must be > 0.")
        t = np.linspace(0, cycle_days * 3, 1000)
        daily_d = D / 365
        base = result.safety_stock or 0
        if self._is_poq(item, result):
            P = float(item.get("production_rate") or 0)
            daily_p = P / 365
            prod_days = eoq / daily_p
            peak = result.max_inventory if result.max_inventory is not None else eoq * \
                (1 - D / P)
            inventory = []
            for time in t:
                pos = time % cycle_days
                if pos <= prod_days:
                    inv = (daily_p - daily_d) * pos
                else:
                    inv = peak - daily_d * (pos - prod_days)
                inventory.append(base + max(0, inv))
        else:
            inventory = [
                base + max(0, eoq - daily_d * (time % cycle_days)) for time in t]

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(t, inventory, linewidth=2)
        ax.fill_between(t, inventory, alpha=0.3)
        for i in range(4):
            ax.axvline(x=i * cycle_days, linestyle="--", alpha=0.5)
        if result.reorder_point is not None:
            ax.axhline(y=result.reorder_point, linestyle=":",
                       linewidth=2, label=f"ROP = {result.reorder_point:.0f}")
        if result.safety_stock is not None and result.safety_stock > 0:
            ax.axhline(y=result.safety_stock, linestyle=":", linewidth=2,
                       label=f"Safety Stock = {result.safety_stock:.0f}")
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("Inventory Level (units)")
        ax.set_title(f"Inventory Cycle - {item_name}")
        ax.legend()
        fig.tight_layout()
        return fig

    def plot_model_comparison(self):
        data = []
        for item_result in self.results:
            if isinstance(item_result, tuple) and len(item_result) == 2:
                models = {"result": item_result[1]}
            elif isinstance(item_result, dict):
                models = item_result.get("models", {})
            else:
                models = {"result": item_result}
            for _, result in models.items():
                data.append({"Item": result.item_name, "Model": result.model_type,
                            "EOQ": result.eoq, "Cost": result.total_cost})
        df = pd.DataFrame(data)
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        df.pivot_table(values="EOQ", index="Item", columns="Model",
                       fill_value=0).plot(kind="bar", ax=axes[0], width=0.8)
        axes[0].set_title("EOQ by Item and Model")
        axes[0].set_ylabel("Order Quantity (units)")
        df.pivot_table(values="Cost", index="Item", columns="Model",
                       fill_value=0).plot(kind="bar", ax=axes[1], width=0.8)
        axes[1].set_title("Total Annual Cost by Item and Model")
        axes[1].set_ylabel("Annual Cost ($)")
        fig.tight_layout()
        return fig

    def plot_sensitivity_analysis(self, item_idx=0, param="demand", model="classic"):
        item, result, D, S, H, _, base_eoq, item_name = self._cost_inputs(
            item_idx, model)
        if param not in {"demand", "ordering_cost", "holding_cost"}:
            raise ValueError(
                "param must be one of: demand, ordering_cost, holding_cost")
        base_tc = self._annual_relevant_cost(item, result, D, S, H, base_eoq)
        variation = np.linspace(0.5, 1.5, 100)
        eoq_vals, tc_vals = [], []
        for v in variation:
            d, s, h = D, S, H
            if param == "demand":
                d = D * v
            elif param == "ordering_cost":
                s = S * v
            else:
                h = H * v
            e = self._optimal_qty_for(item, result, d, s, h)
            t = self._annual_relevant_cost(item, result, d, s, h, e)
            eoq_vals.append((e - base_eoq) / base_eoq * 100)
            tc_vals.append((t - base_tc) / base_tc * 100)
        fig, ax = plt.subplots(figsize=(10, 6))
        pct_change = (variation - 1) * 100
        ax.plot(pct_change, eoq_vals, linewidth=2, label="% Change in EOQ")
        ax.plot(pct_change, tc_vals, linewidth=2,
                label="% Change in Relevant Cost")
        ax.axhline(y=0, linewidth=0.8)
        ax.axvline(x=0, linewidth=0.8)
        ax.set_xlabel(f"% Change in {param.replace('_', ' ').title()}")
        ax.set_ylabel("% Change in Output")
        ax.set_title(f"Sensitivity Analysis - {item_name}")
        ax.legend()
        fig.tight_layout()
        return fig
