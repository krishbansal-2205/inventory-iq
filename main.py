# main.py

import pandas as pd

from costs.cost_structure import HoldingCostComponents, OrderingCostComponents, ProductionCostComponents
from models.enhanced_classic_eoq import EnhancedClassicEOQ, EnhancedPOQ, EnhancedStochasticEOQ
from optimizer.multi_item_optimizer import MultiItemOptimizer


class InventoryManagementSystem:
    """Central system using enhanced EOQ models only."""

    def __init__(self):
        self.items = []
        self.results = []

    def add_item(self, item_config: dict):
        self.items.append(item_config)

    @staticmethod
    def _model_for_item(item):
        item_type = item.get("type", "classic")
        if item_type == "classic":
            return EnhancedClassicEOQ(
                item_id=item["id"],
                item_name=item["name"],
                demand=item["demand"],
                unit_cost=item["unit_cost"],
                lead_time_days=item.get("lead_time", 0),
                holding_components=item.get("hc_components"),
                ordering_components=item.get("oc_components"),
                holding_cost_override=item.get(
                    "hc_override", item.get("holding_cost")),
                ordering_cost_override=item.get(
                    "oc_override", item.get("ordering_cost")),
            )
        if item_type == "poq":
            # Preserve detailed production-component breakdowns when supplied.
            # Overrides are only used for simple/manual POQ costs.
            is_simple_poq_cost = item.get("pc_components") is None
            return EnhancedPOQ(
                item_id=item["id"],
                item_name=item["name"],
                demand=item["demand"],
                production_rate=item["production_rate"],
                lead_time_days=item.get("lead_time", 0),
                holding_components=item.get("hc_components"),
                production_components=item.get("pc_components"),
                holding_cost_override=item.get(
                    "hc_override", item.get("holding_cost")),
                setup_cost_override=(item.get("setup_cost", item.get("oc_override", item.get("ordering_cost")))
                                     if is_simple_poq_cost else None),
                unit_cost_override=item.get(
                    "unit_cost") if is_simple_poq_cost else None,
            )
        if item_type == "stochastic":
            return EnhancedStochasticEOQ(
                item_id=item["id"],
                item_name=item["name"],
                avg_daily_demand=item["demand"] / 365,
                demand_std=item.get("demand_std", 0),
                lead_time_days=item.get("lead_time", 0),
                unit_cost=item["unit_cost"],
                service_level=item.get("service_level", 0.95),
                holding_components=item.get("hc_components"),
                ordering_components=item.get("oc_components"),
                holding_cost_override=item.get(
                    "hc_override", item.get("holding_cost")),
                ordering_cost_override=item.get(
                    "oc_override", item.get("ordering_cost")),
                stockout_cost_per_unit=item.get("stockout_cost", 0),
                lead_time_std=item.get("lead_time_std", 0),
            )
        raise ValueError(f"Unknown item type: {item_type}")

    def run_all_models(self):
        self.results = []
        for item in self.items:
            result = self._model_for_item(item).calculate()
            self.results.append((item, result))
        return self.results

    def run_constrained_optimization(self, max_order_value=None, max_space=None):
        # Convert enhanced item configs into model-aware optimizer parameters.
        # Keep model type and stochastic/production fields so constrained
        # optimization uses the same cost structure as the enhanced EOQ models.
        opt_items = []
        for cfg, result in (self.results or self.run_all_models()):
            opt_items.append({
                "id": cfg["id"],
                "name": cfg["name"],
                "type": cfg.get("type", "classic"),
                "model_type": result.model_type,
                "demand": cfg.get("demand", result.order_frequency * result.eoq),
                "ordering_cost": result.ordering_cost_per_order,
                "holding_cost": result.holding_cost_per_unit,
                "unit_cost": result.unit_cost,
                "storage_space": cfg.get("storage_space", 0),
                "production_rate": cfg.get("production_rate"),
                "demand_std": cfg.get("demand_std", 0),
                "lead_time": cfg.get("lead_time", 0),
                "lead_time_std": cfg.get("lead_time_std", 0),
                "service_level": cfg.get("service_level", 0.95),
                "stockout_cost": cfg.get("stockout_cost", 0),
            })
        optimizer = MultiItemOptimizer(opt_items)
        results = {"unconstrained": optimizer.unconstrained_eoq()}
        if max_order_value is not None and max_space is None:
            results["order_value_constrained"] = optimizer.order_value_constrained_optimize(
                max_order_value)
        elif max_space is not None and max_order_value is None:
            results["space_constrained"] = optimizer.storage_constrained_optimize(
                max_space)
        elif max_order_value is not None and max_space is not None:
            results["dual_constrained"] = optimizer.dual_constrained_optimize(
                max_order_value, max_space)
        return results

    @staticmethod
    def generate_summary_table(results):
        rows = []
        for cfg, result in results:
            rows.append({
                "Item ID": result.item_id,
                "Item Name": result.item_name,
                "Model": result.model_type,
                "EOQ": result.eoq,
                "Total Annual Cost": result.total_cost,
                "Orders/Year": result.order_frequency,
                "Cycle Time (days)": result.cycle_time,
                "ROP": result.reorder_point,
                "Safety Stock": result.safety_stock,
                "Holding Cost/Unit/Yr": result.holding_cost_per_unit,
                "Order Cost/Order": result.ordering_cost_per_order,
                "Unit Cost": result.unit_cost,
            })
        return pd.DataFrame(rows)


if __name__ == "__main__":
    system = InventoryManagementSystem()

    common_oc = OrderingCostComponents(
        admin_cost=80, freight_fixed=50, receiving_cost=20, communication_cost=10)
    system.add_item({
        "type": "classic",
        "id": "SKU001",
        "name": "Steel Bolts",
        "demand": 5000,
        "unit_cost": 5,
        "lead_time": 7,
        "holding_cost": 2.5,
        "ordering_cost": 150,
        "storage_space": 0.01,
    })
    system.add_item({
        "type": "poq",
        "id": "SKU002",
        "name": "Plastic Casing",
        "demand": 12000,
        "unit_cost": 8,
        "lead_time": 2,
        "production_rate": 50000,
        "holding_cost": 3.0,
        "ordering_cost": 200,
        "storage_space": 0.05,
    })
    system.add_item({
        "type": "stochastic",
        "id": "SKU003",
        "name": "Chemical Solution",
        "demand": 3000,
        "unit_cost": 25,
        "lead_time": 3,
        "demand_std": 10,
        "service_level": 0.99,
        "stockout_cost": 50,
        "holding_cost": 8.0,
        "ordering_cost": 100,
        "storage_space": 0.2,
    })

    print("=" * 60)
    print("MULTI-ITEM EOQ INVENTORY MANAGEMENT SYSTEM")
    print("=" * 60)
    results = system.run_all_models()
    for _, result in results:
        print(f"\n{result.item_name} ({result.item_id}) — {result.model_type}")
        print(f"  EOQ: {result.eoq:,.2f} units")
        print(f"  Total Annual Cost: ${result.total_cost:,.2f}")
        print(f"  Orders/Year: {result.order_frequency:,.2f}")
        print(f"  Cycle Time: {result.cycle_time:,.2f} days")
        if result.reorder_point is not None:
            print(f"  Reorder Point: {result.reorder_point:,.2f} units")
        if result.safety_stock is not None:
            print(f"  Safety Stock: {result.safety_stock:,.2f} units")

    print("\nSummary Table:")
    print(system.generate_summary_table(results).to_string(index=False))
