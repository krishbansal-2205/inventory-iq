# models/enhanced_classic_eoq.py

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
from scipy import stats

from costs.cost_structure import (
    HoldingCostComponents,
    OrderingCostComponents,
    ProductionCostComponents,
)


@dataclass
class EnhancedEOQResult:
    item_id: str
    item_name: str
    model_type: str
    eoq: float
    total_cost: float
    order_frequency: float
    cycle_time: float
    unit_cost: float
    holding_cost_per_unit: float
    ordering_cost_per_order: float
    reorder_point: Optional[float] = None
    safety_stock: Optional[float] = None
    max_inventory: Optional[float] = None
    cost_breakdown: Optional[Dict] = None
    holding_breakdown: Optional[Dict] = None
    production_breakdown: Optional[Dict] = None
    ordering_breakdown: Optional[Dict] = None
    details: Optional[Dict] = None


def _validate_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be > 0. Got {value}.")


def _validate_non_negative(name: str, value: float) -> None:
    if value < 0:
        raise ValueError(f"{name} must be >= 0. Got {value}.")


def _round_optional(value: Optional[float], ndigits: int = 2) -> Optional[float]:
    return None if value is None else round(value, ndigits)


class _CostMixin:
    def _ordering_costs(
        self,
        ordering_components: Optional[OrderingCostComponents],
        ordering_cost_override: Optional[float],
        preview_qty: float = 1,
    ) -> Tuple[float, float, Dict]:
        """Return fixed S, per-unit variable ordering cost, and display breakdown."""
        if ordering_cost_override is not None:
            _validate_positive("ordering_cost_override",
                               ordering_cost_override)
            return (
                ordering_cost_override,
                0.0,
                {
                    "total_ordering_cost": round(ordering_cost_override, 4),
                    "fixed_component": round(ordering_cost_override, 4),
                    "variable_component": 0.0,
                    "source": "Manual Override",
                },
            )

        components = ordering_components or OrderingCostComponents()
        fixed = components.fixed_cost_per_order()
        variable = components.variable_cost_per_unit()
        _validate_positive("fixed ordering cost per order", fixed)
        return fixed, variable, components.calculate(max(preview_qty, 1))

    def _holding_costs(
        self,
        unit_cost_for_holding: float,
        holding_components: Optional[HoldingCostComponents],
        holding_cost_override: Optional[float],
    ) -> Tuple[float, Dict]:
        if holding_cost_override is not None:
            _validate_positive("holding_cost_override", holding_cost_override)
            return (
                holding_cost_override,
                {
                    "total_holding_cost": round(holding_cost_override, 4),
                    "source": "Manual Override",
                },
            )
        components = holding_components or HoldingCostComponents()
        breakdown = components.calculate(unit_cost_for_holding)
        H = breakdown["total_holding_cost"]
        _validate_positive("holding cost per unit per year", H)
        return H, breakdown


class EnhancedClassicEOQ(_CostMixin):
    """Classic EOQ with variable cost components. Lead time is in days."""

    def __init__(
        self,
        item_id: str,
        item_name: str,
        demand: float,
        unit_cost: float,
        lead_time_days: float = 0,
        holding_components: HoldingCostComponents = None,
        ordering_components: OrderingCostComponents = None,
        holding_cost_override: float = None,
        ordering_cost_override: float = None,
    ):
        _validate_positive("demand", demand)
        _validate_non_negative("unit_cost", unit_cost)
        _validate_non_negative("lead_time_days", lead_time_days)
        self.item_id = item_id
        self.item_name = item_name
        self.D = float(demand)
        self.base_unit_cost = float(unit_cost)
        self.L_days = float(lead_time_days)
        self.holding_components = holding_components
        self.ordering_components = ordering_components
        self.H_override = holding_cost_override
        self.S_override = ordering_cost_override

    def calculate(self) -> EnhancedEOQResult:
        S, variable_order_unit, _ = self._ordering_costs(
            self.ordering_components, self.S_override
        )
        landed_unit_cost = self.base_unit_cost + variable_order_unit
        H, h_breakdown = self._holding_costs(
            landed_unit_cost, self.holding_components, self.H_override
        )

        eoq = np.sqrt((2 * self.D * S) / H)
        # Rebuild ordering breakdown at the actual EOQ for honest display.
        _, _, o_breakdown = self._ordering_costs(
            self.ordering_components, self.S_override, preview_qty=eoq
        )

        annual_ordering_cost = (self.D / eoq) * S
        annual_holding_cost = (eoq / 2) * H
        annual_purchase_cost = self.D * self.base_unit_cost
        annual_variable_ordering_cost = self.D * variable_order_unit
        total_cost = (
            annual_ordering_cost + annual_holding_cost
            + annual_purchase_cost + annual_variable_ordering_cost
        )
        rop = (self.D / 365) * self.L_days

        return EnhancedEOQResult(
            item_id=self.item_id,
            item_name=self.item_name,
            model_type="Classic EOQ",
            eoq=round(eoq, 2),
            total_cost=round(total_cost, 2),
            order_frequency=round(self.D / eoq, 2),
            cycle_time=round((eoq / self.D) * 365, 2),
            unit_cost=round(landed_unit_cost, 4),
            holding_cost_per_unit=round(H, 4),
            ordering_cost_per_order=round(S, 4),
            reorder_point=round(rop, 2),
            cost_breakdown={
                "annual_ordering_cost": round(annual_ordering_cost, 2),
                "annual_holding_cost": round(annual_holding_cost, 2),
                "annual_purchase_cost": round(annual_purchase_cost, 2),
                "annual_variable_ordering_cost": round(annual_variable_ordering_cost, 2),
                "total_cost": round(total_cost, 2),
                "cost_per_unit": round(total_cost / self.D, 4),
                "base_unit_cost": round(self.base_unit_cost, 4),
                "landed_unit_cost": round(landed_unit_cost, 4),
            },
            holding_breakdown=h_breakdown,
            ordering_breakdown=o_breakdown,
            details={"avg_inventory": round(eoq / 2, 2)},
        )


class EnhancedPOQ(_CostMixin):
    """Production Order Quantity with variable production costs. Lead time is in days."""

    def __init__(
        self,
        item_id: str,
        item_name: str,
        demand: float,
        production_rate: float,
        lead_time_days: float = 0,
        holding_components: HoldingCostComponents = None,
        production_components: ProductionCostComponents = None,
        holding_cost_override: float = None,
        setup_cost_override: float = None,
        unit_cost_override: float = None,
    ):
        _validate_positive("demand", demand)
        _validate_positive("production_rate", production_rate)
        if production_rate <= demand:
            raise ValueError("production_rate must exceed annual demand.")
        _validate_non_negative("lead_time_days", lead_time_days)
        self.item_id = item_id
        self.item_name = item_name
        self.D = float(demand)
        self.P = float(production_rate)
        self.L_days = float(lead_time_days)
        self.holding_components = holding_components
        self.production_components = production_components or ProductionCostComponents()
        self.H_override = holding_cost_override
        self.S_override = setup_cost_override
        self.C_override = unit_cost_override

    def _unit_and_setup_costs(self) -> Tuple[float, float, Dict]:
        if self.C_override is not None:
            _validate_non_negative("unit_cost_override", self.C_override)
            C = float(self.C_override)
            p_breakdown = {
                "variable_cost_per_unit": round(C, 4),
                "source": "Manual Unit Cost Override",
            }
        else:
            p_breakdown = self.production_components.calculate(1)
            C = p_breakdown["variable_cost_per_unit"]

        if self.S_override is not None:
            _validate_positive("setup_cost_override", self.S_override)
            S = float(self.S_override)
        else:
            S = float(self.production_components.setup_cost_per_run)
            _validate_positive("setup_cost_per_run", S)
        return C, S, p_breakdown

    def calculate(self) -> EnhancedEOQResult:
        C, S, _ = self._unit_and_setup_costs()
        H, h_breakdown = self._holding_costs(
            C, self.holding_components, self.H_override)

        production_factor = 1 - self.D / self.P
        poq = np.sqrt((2 * self.D * S) / (H * production_factor))
        production_breakdown = (
            {"variable_cost_per_unit": round(
                C, 4), "source": "Manual Unit Cost Override"}
            if self.C_override is not None
            else self.production_components.calculate(poq)
        )

        max_inventory = poq * production_factor
        avg_inventory = max_inventory / 2
        setup_cost_annual = (self.D / poq) * S
        holding_cost_annual = avg_inventory * H
        production_cost_annual = self.D * C
        total_cost = setup_cost_annual + holding_cost_annual + production_cost_annual
        rop = (self.D / 365) * self.L_days
        production_run_time = (poq / self.P) * 365
        idle_time = ((poq / self.D) - (poq / self.P)) * 365

        return EnhancedEOQResult(
            item_id=self.item_id,
            item_name=self.item_name,
            model_type="Production Order Quantity (POQ)",
            eoq=round(poq, 2),
            total_cost=round(total_cost, 2),
            order_frequency=round(self.D / poq, 2),
            cycle_time=round((poq / self.D) * 365, 2),
            unit_cost=round(C, 4),
            holding_cost_per_unit=round(H, 4),
            ordering_cost_per_order=round(S, 4),
            reorder_point=round(rop, 2),
            max_inventory=round(max_inventory, 2),
            cost_breakdown={
                "setup_cost_annual": round(setup_cost_annual, 2),
                "holding_cost_annual": round(holding_cost_annual, 2),
                "production_cost_annual": round(production_cost_annual, 2),
                "total_cost": round(total_cost, 2),
                "production_run_time_days": round(production_run_time, 2),
                "idle_time_days": round(idle_time, 2),
                "utilization_rate_pct": round(self.D / self.P * 100, 2),
                "cost_per_unit": round(total_cost / self.D, 4),
            },
            holding_breakdown=h_breakdown,
            production_breakdown=production_breakdown,
            ordering_breakdown={
                "setup_cost_per_run": round(S, 4),
                "total_ordering_cost": round(S, 4),
                "fixed_component": round(S, 4),
                "variable_component": 0.0,
            },
            details={
                "avg_inventory": round(avg_inventory, 2),
                "production_factor": round(production_factor, 4),
            },
        )


class EnhancedStochasticEOQ(_CostMixin):
    """Stochastic EOQ with safety stock. Lead time inputs are in days."""

    def __init__(
        self,
        item_id: str,
        item_name: str,
        avg_daily_demand: float,
        demand_std: float,
        lead_time_days: float,
        unit_cost: float,
        service_level: float = 0.95,
        holding_components: HoldingCostComponents = None,
        ordering_components: OrderingCostComponents = None,
        holding_cost_override: float = None,
        ordering_cost_override: float = None,
        stockout_cost_per_unit: float = 0.0,
        lead_time_std: float = 0.0,
    ):
        _validate_positive("avg_daily_demand", avg_daily_demand)
        _validate_non_negative("demand_std", demand_std)
        _validate_non_negative("lead_time_days", lead_time_days)
        _validate_non_negative("unit_cost", unit_cost)
        _validate_non_negative("stockout_cost_per_unit",
                               stockout_cost_per_unit)
        _validate_non_negative("lead_time_std", lead_time_std)
        if not 0 < service_level < 1:
            raise ValueError("service_level must be between 0 and 1.")

        self.item_id = item_id
        self.item_name = item_name
        self.d = float(avg_daily_demand)
        self.D = self.d * 365
        self.sigma_d = float(demand_std)
        self.L_days = float(lead_time_days)
        self.L_std = float(lead_time_std)
        self.base_unit_cost = float(unit_cost)
        self.SL = float(service_level)
        self.stockout_cost = float(stockout_cost_per_unit)
        self.holding_components = holding_components
        self.ordering_components = ordering_components
        self.H_override = holding_cost_override
        self.S_override = ordering_cost_override

    def calculate(self) -> EnhancedEOQResult:
        S, variable_order_unit, _ = self._ordering_costs(
            self.ordering_components, self.S_override
        )
        landed_unit_cost = self.base_unit_cost + variable_order_unit
        H, h_breakdown = self._holding_costs(
            landed_unit_cost, self.holding_components, self.H_override
        )

        sigma_lt = np.sqrt(
            self.L_days * self.sigma_d ** 2 + (self.d ** 2) * self.L_std ** 2
        )
        z = stats.norm.ppf(self.SL)
        safety_stock = z * sigma_lt
        avg_lt_demand = self.d * self.L_days
        rop = avg_lt_demand + safety_stock

        expected_stockout = sigma_lt * (
            stats.norm.pdf(z) - z * (1 - stats.norm.cdf(z))
        )

        # If stockout cost is included in the stochastic objective, the
        # expected shortage penalty behaves like an additional per-cycle setup
        # term.  Use the same effective setup cost everywhere so the model,
        # optimizer, sensitivity analysis, and charts agree on Q*.
        effective_setup_for_eoq = S + expected_stockout * self.stockout_cost
        eoq = np.sqrt((2 * self.D * effective_setup_for_eoq) / H)
        _, _, o_breakdown = self._ordering_costs(
            self.ordering_components, self.S_override, preview_qty=eoq
        )

        annual_ordering = (self.D / eoq) * S
        cycle_holding = (eoq / 2) * H
        safety_holding = safety_stock * H
        purchase_cost = self.D * self.base_unit_cost
        annual_variable_ordering_cost = self.D * variable_order_unit

        annual_stockout_cost = (self.D / eoq) * \
            expected_stockout * self.stockout_cost

        total_cost = (
            annual_ordering + cycle_holding + safety_holding + purchase_cost
            + annual_variable_ordering_cost + annual_stockout_cost
        )

        return EnhancedEOQResult(
            item_id=self.item_id,
            item_name=self.item_name,
            model_type="Stochastic EOQ",
            eoq=round(eoq, 2),
            total_cost=round(total_cost, 2),
            order_frequency=round(self.D / eoq, 2),
            cycle_time=round((eoq / self.D) * 365, 2),
            unit_cost=round(landed_unit_cost, 4),
            holding_cost_per_unit=round(H, 4),
            ordering_cost_per_order=round(S, 4),
            reorder_point=round(rop, 2),
            safety_stock=round(safety_stock, 2),
            cost_breakdown={
                "annual_ordering_cost": round(annual_ordering, 2),
                "cycle_holding_cost": round(cycle_holding, 2),
                "safety_stock_holding_cost": round(safety_holding, 2),
                "annual_purchase_cost": round(purchase_cost, 2),
                "annual_variable_ordering_cost": round(annual_variable_ordering_cost, 2),
                "annual_stockout_cost": round(annual_stockout_cost, 2),
                "total_cost": round(total_cost, 2),
                "cost_per_unit": round(total_cost / self.D, 4),
                "base_unit_cost": round(self.base_unit_cost, 4),
                "landed_unit_cost": round(landed_unit_cost, 4),
            },
            holding_breakdown=h_breakdown,
            ordering_breakdown=o_breakdown,
            details={
                "service_level": f"{self.SL * 100:.1f}%",
                "z_score": round(z, 3),
                "avg_lead_time_demand": round(avg_lt_demand, 2),
                "lead_time_demand_std": round(sigma_lt, 2),
                "expected_stockout_units_per_cycle": round(expected_stockout, 2),
                "effective_setup_cost_for_eoq": round(effective_setup_for_eoq, 4),
            },
        )
