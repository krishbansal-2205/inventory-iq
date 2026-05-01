# costs/cost_structure.py

from dataclasses import dataclass
from typing import Dict


def _non_negative(name: str, value: float) -> None:
    if value < 0:
        raise ValueError(f"{name} must be >= 0. Got {value}.")


@dataclass
class HoldingCostComponents:
    """Variable holding cost structure. Rates are annual rates."""
    capital_cost_rate: float = 0.10
    storage_rate_per_sqm: float = 0.0
    unit_storage_area: float = 0.0
    insurance_rate: float = 0.01
    obsolescence_rate: float = 0.02
    spoilage_rate: float = 0.0
    handling_cost_per_unit: float = 0.0
    utility_cost_per_unit: float = 0.0
    custom_holding_cost: float = 0.0

    def calculate(self, unit_cost: float) -> Dict[str, float]:
        """Return holding cost breakdown in $/unit/year."""
        _non_negative("unit_cost", unit_cost)
        for name, value in self.__dict__.items():
            _non_negative(name, value)

        capital_cost = self.capital_cost_rate * unit_cost
        storage_cost = self.storage_rate_per_sqm * self.unit_storage_area
        insurance_cost = self.insurance_rate * unit_cost
        obsolescence_cost = self.obsolescence_rate * unit_cost
        spoilage_cost = self.spoilage_rate * unit_cost
        handling_cost = self.handling_cost_per_unit
        utility_cost = self.utility_cost_per_unit
        custom_cost = self.custom_holding_cost

        total = (
            capital_cost + storage_cost + insurance_cost + obsolescence_cost
            + spoilage_cost + handling_cost + utility_cost + custom_cost
        )

        return {
            "capital_cost": round(capital_cost, 4),
            "storage_cost": round(storage_cost, 4),
            "insurance_cost": round(insurance_cost, 4),
            "obsolescence_cost": round(obsolescence_cost, 4),
            "spoilage_cost": round(spoilage_cost, 4),
            "handling_cost": round(handling_cost, 4),
            "utility_cost": round(utility_cost, 4),
            "custom_cost": round(custom_cost, 4),
            "total_holding_cost": round(total, 4),
        }


@dataclass
class ProductionCostComponents:
    """Production cost structure. Setup cost is fixed per production run."""
    raw_material_cost: float = 0.0
    labor_rate_per_hour: float = 0.0
    labor_hours_per_unit: float = 0.0
    setup_cost_per_run: float = 0.0
    machine_rate_per_hour: float = 0.0
    machine_hours_per_unit: float = 0.0
    energy_cost_per_unit: float = 0.0
    overhead_rate: float = 0.0
    quality_cost_per_unit: float = 0.0
    scrap_rate: float = 0.0
    tooling_cost_per_unit: float = 0.0
    custom_production_cost: float = 0.0

    def calculate(self, production_qty: float = 1) -> Dict[str, float]:
        """Return per-unit and per-run production cost breakdown."""
        if production_qty <= 0:
            raise ValueError("production_qty must be > 0.")
        for name, value in self.__dict__.items():
            _non_negative(name, value)
        if self.scrap_rate >= 1:
            raise ValueError("scrap_rate must be less than 1.")

        labor_cost = self.labor_rate_per_hour * self.labor_hours_per_unit
        machine_cost = self.machine_rate_per_hour * self.machine_hours_per_unit

        direct_cost_per_unit = (
            self.raw_material_cost + labor_cost + machine_cost
            + self.energy_cost_per_unit + self.quality_cost_per_unit
            + self.tooling_cost_per_unit + self.custom_production_cost
        )
        overhead_per_unit = self.overhead_rate * direct_cost_per_unit

        # Cost per good unit: direct cost must be grossed up for expected scrap.
        scrap_adjustment = direct_cost_per_unit * (
            self.scrap_rate / (1 - self.scrap_rate)
        ) if self.scrap_rate else 0.0

        variable_cost_per_unit = direct_cost_per_unit + overhead_per_unit + scrap_adjustment
        setup_cost = self.setup_cost_per_run
        total_run_cost = setup_cost + variable_cost_per_unit * production_qty
        unit_cost_including_setup = variable_cost_per_unit + setup_cost / production_qty

        return {
            "raw_material_cost": round(self.raw_material_cost, 4),
            "labor_cost_per_unit": round(labor_cost, 4),
            "machine_cost_per_unit": round(machine_cost, 4),
            "energy_cost_per_unit": round(self.energy_cost_per_unit, 4),
            "quality_cost_per_unit": round(self.quality_cost_per_unit, 4),
            "tooling_cost_per_unit": round(self.tooling_cost_per_unit, 4),
            "overhead_per_unit": round(overhead_per_unit, 4),
            "scrap_cost_per_unit": round(scrap_adjustment, 4),
            "custom_cost": round(self.custom_production_cost, 4),
            "setup_cost_per_run": round(setup_cost, 4),
            "variable_cost_per_unit": round(variable_cost_per_unit, 4),
            "total_unit_cost_incl_setup": round(unit_cost_including_setup, 4),
            "total_run_cost": round(total_run_cost, 4),
        }


@dataclass
class OrderingCostComponents:
    """
    Ordering cost structure.

    Fixed components are valid EOQ setup/order cost S.
    Per-unit freight/inspection are variable landed costs and should not be
    folded into S, because EOQ assumes S is independent of order quantity.
    """
    admin_cost: float = 0.0
    freight_fixed: float = 0.0
    freight_per_unit: float = 0.0
    receiving_cost: float = 0.0
    inspection_cost_per_unit: float = 0.0
    communication_cost: float = 0.0
    custom_ordering_cost: float = 0.0

    def fixed_cost_per_order(self) -> float:
        for name, value in self.__dict__.items():
            _non_negative(name, value)
        return (
            self.admin_cost + self.freight_fixed + self.receiving_cost
            + self.communication_cost + self.custom_ordering_cost
        )

    def variable_cost_per_unit(self) -> float:
        for name, value in self.__dict__.items():
            _non_negative(name, value)
        return self.freight_per_unit + self.inspection_cost_per_unit

    def calculate(self, order_qty: float = 1) -> Dict[str, float]:
        """Return full ordering cost breakdown for display at a chosen order quantity."""
        if order_qty <= 0:
            raise ValueError("order_qty must be > 0.")
        fixed_costs = self.fixed_cost_per_order()
        freight_variable = self.freight_per_unit * order_qty
        inspection_cost = self.inspection_cost_per_unit * order_qty
        variable_costs = freight_variable + inspection_cost
        total = fixed_costs + variable_costs

        return {
            "admin_cost": round(self.admin_cost, 4),
            "freight_fixed": round(self.freight_fixed, 4),
            "freight_variable": round(freight_variable, 4),
            "receiving_cost": round(self.receiving_cost, 4),
            "inspection_cost": round(inspection_cost, 4),
            "communication_cost": round(self.communication_cost, 4),
            "custom_cost": round(self.custom_ordering_cost, 4),
            "fixed_component": round(fixed_costs, 4),
            "variable_component": round(variable_costs, 4),
            "total_ordering_cost": round(total, 4),
        }
