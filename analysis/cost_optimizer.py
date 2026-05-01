from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class OptimizationSuggestion:
    category: str
    priority: str
    title: str
    problem: str
    recommendation: str
    estimated_saving: float
    saving_pct: float
    implementation: List[str]
    difficulty: str
    timeframe: str
    kpi_impact: Dict


class CostOptimizer:
    """Generate actionable cost-reduction ideas for enhanced EOQ results.

    The internal cost model mirrors the enhanced EOQ classes so scenario and
    savings numbers reconcile with result.total_cost, including stochastic
    safety-stock and stockout costs.
    """

    def __init__(self, item_config: dict, result, sensitivity_analysis: dict = None):
        self.cfg = item_config
        self.result = result
        self.sensitivity = sensitivity_analysis or {}
        self.D = float(item_config.get("demand", 0)
                       or result.order_frequency * result.eoq)
        self.C = float(result.unit_cost)
        self.H = float(result.holding_cost_per_unit)
        self.S = float(result.ordering_cost_per_order)
        self.eoq = float(result.eoq)
        self.base_cost = float(result.total_cost)
        self.production_rate = item_config.get("production_rate")
        self.model_type = str(getattr(result, "model_type", ""))
        self.is_poq = item_config.get(
            "type") == "poq" or "Production Order Quantity" in self.model_type
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
        self.suggestions: List[OptimizationSuggestion] = []

    def _holding_cost_for_unit(self, unit_cost: float) -> float:
        if self.hc_override is not None or self.hc_components is None:
            return self.H
        return float(self.hc_components.calculate(unit_cost)["total_holding_cost"])

    def _stochastic_terms(self, D: float) -> Tuple[float, float]:
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

    def _optimal_qty(self, D, S, H):
        if self.production_rate:
            P = float(self.production_rate)
            if P <= D:
                return float("inf")
            return np.sqrt((2 * D * S) / (H * (1 - D / P)))
        if self.is_stochastic:
            _, expected_stockout = self._stochastic_terms(D)
            effective_setup = S + expected_stockout * self.stockout_cost
            return np.sqrt((2 * D * effective_setup) / H)
        return np.sqrt((2 * D * S) / H)

    def _annual_cost(self, D, S, H, C, Q=None):
        if Q is None:
            Q = self._optimal_qty(D, S, H)
        if Q <= 0 or not np.isfinite(Q):
            return float("inf")
        if self.production_rate:
            P = float(self.production_rate)
            max_inventory = Q * (1 - D / P)
            return (D / Q) * S + (max_inventory / 2) * H + D * C
        safety_stock, expected_stockout = self._stochastic_terms(D)
        stockout_cost = (D / Q) * expected_stockout * \
            self.stockout_cost if self.is_stochastic else 0.0
        return (D / Q) * S + (Q / 2) * H + safety_stock * H + D * C + stockout_cost

    def _unit_cost_scenario(self, new_C: float, h_multiplier: float = 1.0) -> Tuple[float, float]:
        base_H_for_C = self._holding_cost_for_unit(new_C)
        return new_C, max(base_H_for_C * h_multiplier, 0.0001)

    def _add_if_positive(self, suggestion: OptimizationSuggestion):
        if suggestion.estimated_saving > 0 and suggestion.saving_pct > 0:
            self.suggestions.append(suggestion)

    def analyze_holding_costs(self):
        hb = self.result.holding_breakdown or {}
        if not hb or "source" in hb:
            return
        total_H = self.H
        if total_H <= 0:
            return

        capital_cost = float(hb.get("capital_cost", 0) or 0)
        if capital_cost > 0 and capital_cost / total_H > 0.4:
            reduction = 0.15
            new_H = max(total_H - capital_cost * reduction, 0.0001)
            saving = self.base_cost - \
                self._annual_cost(self.D, self.S, new_H, self.C)
            self._add_if_positive(OptimizationSuggestion(
                category="Holding Cost",
                priority="High" if saving > self.base_cost * 0.05 else "Medium",
                title="Reduce Capital Cost Through Supplier Terms",
                problem=f"Capital cost (${capital_cost:.2f}/unit/year) is {capital_cost/total_H*100:.1f}% of holding cost.",
                recommendation="Negotiate extended payment terms, consignment inventory, VMI, or supply-chain financing to reduce working capital tied up in inventory.",
                estimated_saving=round(saving, 2),
                saving_pct=round(saving / self.base_cost * 100, 2),
                implementation=["Identify top suppliers by annual spend", "Request payment-term extension",
                                "Evaluate VMI or consignment for high-value items", "Monitor working-capital KPIs monthly"],
                difficulty="Medium",
                timeframe="Short-term (1-3 months)",
                kpi_impact={"Holding Cost": f"↓ ${capital_cost * reduction:.2f}/unit/year",
                            "Cash Flow": "Improved", "Annual Saving": f"${saving:,.2f}"},
            ))

        storage_cost = float(hb.get("storage_cost", 0) or 0)
        if storage_cost > 0 and storage_cost / total_H > 0.25:
            reduction = 0.20
            new_H = max(total_H - storage_cost * reduction, 0.0001)
            saving = self.base_cost - \
                self._annual_cost(self.D, self.S, new_H, self.C)
            self._add_if_positive(OptimizationSuggestion(
                category="Holding Cost",
                priority="High" if saving > self.base_cost * 0.03 else "Medium",
                title="Warehouse Space Optimization",
                problem=f"Storage cost (${storage_cost:.2f}/unit/year) is {storage_cost/total_H*100:.1f}% of holding cost.",
                recommendation="Improve slotting, vertical storage, packaging density, or shared/3PL warehouse use to lower per-unit storage cost.",
                estimated_saving=round(saving, 2),
                saving_pct=round(saving / self.base_cost * 100, 2),
                implementation=["Audit warehouse utilization", "Apply ABC slotting",
                                "Improve pallet/package dimensions", "Evaluate 3PL or shared storage options"],
                difficulty="Medium",
                timeframe="Short-term (1-6 months)",
                kpi_impact={"Storage Cost": f"↓ {reduction*100:.0f}%",
                            "Space Utilization": "Improved", "Annual Saving": f"${saving:,.2f}"},
            ))

        obs_cost = float(hb.get("obsolescence_cost", 0) or 0)
        if obs_cost > 0 and obs_cost / total_H > 0.15:
            reduction = 0.30
            new_H = max(total_H - obs_cost * reduction, 0.0001)
            saving = self.base_cost - \
                self._annual_cost(self.D, self.S, new_H, self.C)
            self._add_if_positive(OptimizationSuggestion(
                category="Holding Cost",
                priority="Medium",
                title="Reduce Obsolescence Risk",
                problem=f"Obsolescence cost (${obs_cost:.2f}/unit/year) is high relative to total holding cost.",
                recommendation="Tighten FIFO controls, forecasting, max-age alerts, and slow-moving inventory reviews.",
                estimated_saving=round(saving, 2),
                saving_pct=round(saving / self.base_cost * 100, 2),
                implementation=["Enforce FIFO inventory rules", "Set maximum shelf-age alerts",
                                "Review slow-moving stock quarterly", "Improve demand forecast cadence"],
                difficulty="Easy",
                timeframe="Immediate (< 1 month)",
                kpi_impact={"Obsolescence Rate": f"↓ {reduction*100:.0f}%",
                            "Annual Saving": f"${saving:,.2f}"},
            ))

    def analyze_ordering_costs(self):
        ob = self.result.ordering_breakdown or {}
        if not ob or "source" in ob:
            return
        total_S = self.S
        if total_S <= 0:
            return

        admin_cost = float(ob.get("admin_cost", 0) or 0)
        if admin_cost > 0 and admin_cost / total_S > 0.3:
            reduction = 0.50
            new_S = max(total_S - admin_cost * reduction, 0.0001)
            saving = self.base_cost - \
                self._annual_cost(self.D, new_S, self.H, self.C)
            self._add_if_positive(OptimizationSuggestion(
                category="Ordering Cost",
                priority="High" if saving > self.base_cost * 0.03 else "Medium",
                title="Automate Purchase Order Processing",
                problem=f"Administrative processing cost (${admin_cost:.2f}/order) is {admin_cost/total_S*100:.1f}% of ordering cost.",
                recommendation="Use automated reorder triggers, EDI/API supplier connections, blanket POs, and standardized approval workflows.",
                estimated_saving=round(saving, 2),
                saving_pct=round(saving / self.base_cost * 100, 2),
                implementation=["Configure automatic reorder triggers", "Integrate top suppliers via EDI/API",
                                "Use blanket POs for repeat purchases", "Train staff on exception-based procurement"],
                difficulty="Medium",
                timeframe="Short-term (2-4 months)",
                kpi_impact={"Admin Cost/Order": f"↓ {reduction*100:.0f}%",
                            "Processing Time": "Reduced", "Annual Saving": f"${saving:,.2f}"},
            ))

        freight = float(ob.get("freight_fixed", 0) or 0)
        if freight > 0 and freight / total_S > 0.25:
            reduction = 0.25
            new_S = max(total_S - freight * reduction, 0.0001)
            saving = self.base_cost - \
                self._annual_cost(self.D, new_S, self.H, self.C)
            self._add_if_positive(OptimizationSuggestion(
                category="Ordering Cost",
                priority="Medium",
                title="Freight Consolidation & Carrier Negotiation",
                problem=f"Fixed freight cost (${freight:.2f}/order) is {freight/total_S*100:.1f}% of ordering cost.",
                recommendation="Consolidate shipments, negotiate annual carrier contracts, or use 3PL/freight broker programs.",
                estimated_saving=round(saving, 2),
                saving_pct=round(saving / self.base_cost * 100, 2),
                implementation=["Analyze lanes and shipment frequency", "Issue carrier RFQ",
                                "Batch orders by supplier where feasible", "Implement freight-audit process"],
                difficulty="Easy",
                timeframe="Immediate (1-2 months)",
                kpi_impact={"Freight Cost": f"↓ {reduction*100:.0f}%",
                            "Annual Saving": f"${saving:,.2f}"},
            ))

        current_Q = self.cfg.get("current_order_qty")
        if current_Q and current_Q > 0:
            current_cost = self._annual_cost(
                self.D, self.S, self.H, self.C, current_Q)
            saving = current_cost - self.base_cost
            if abs(current_Q - self.eoq) / self.eoq > 0.15 and saving > 0:
                self._add_if_positive(OptimizationSuggestion(
                    category="Strategic",
                    priority="High",
                    title="Align Current Order Quantity to EOQ",
                    problem=f"Current order quantity ({current_Q:.0f}) differs from EOQ ({self.eoq:.0f}) by {abs(current_Q-self.eoq)/self.eoq*100:.1f}%.",
                    recommendation=f"Update the standard order quantity to approximately {self.eoq:.0f} units.",
                    estimated_saving=round(saving, 2),
                    saving_pct=round(saving / current_cost * 100, 2),
                    implementation=["Update ERP reorder quantity",
                                    "Notify purchasing/planning", "Review after one quarter"],
                    difficulty="Easy",
                    timeframe="Immediate (< 1 month)",
                    kpi_impact={"Order Quantity": f"{current_Q:.0f} → {self.eoq:.0f}",
                                "Annual Saving": f"${saving:,.2f}"},
                ))

    def analyze_strategic_opportunities(self):
        # Supplier quantity discounts are only appropriate for purchased items.
        if not self.is_poq and not self.cfg.get("price_breaks"):
            potential_discount = 0.05
            new_C, new_H = self._unit_cost_scenario(
                self.C * (1 - potential_discount))
            saving = self.base_cost - \
                self._annual_cost(self.D, self.S, new_H, new_C)
            if saving > self.S:
                threshold = self.eoq * 1.5
                self._add_if_positive(OptimizationSuggestion(
                    category="Strategic",
                    priority="Medium",
                    title="Negotiate Quantity Discount",
                    problem=f"Annual purchased spend is approximately ${self.D * self.C:,.2f}; small unit-cost reductions can materially affect total cost.",
                    recommendation=f"Negotiate a 5% supplier price discount for order quantities near {threshold:.0f}+ units, then re-run total-cost comparison including holding-cost effects.",
                    estimated_saving=round(saving, 2),
                    saving_pct=round(saving / self.base_cost * 100, 2),
                    implementation=["Prepare supplier volume data", "Request tiered price quotes",
                                    "Compare total landed cost by tier", "Update EOQ using accepted price break"],
                    difficulty="Medium",
                    timeframe="Short-term (1-3 months)",
                    kpi_impact={"Unit Cost": "↓ 5% target",
                                "Annual Saving": f"${saving:,.2f}"},
                ))

        current_safety_stock, _ = self._stochastic_terms(self.D)
        if current_safety_stock and current_safety_stock > self.eoq * 0.5:
            reduction_possible = current_safety_stock * 0.20
            saving = reduction_possible * self.H
            self._add_if_positive(OptimizationSuggestion(
                category="Strategic",
                priority="Medium",
                title="Optimize Safety Stock Level",
                problem=f"Safety stock ({current_safety_stock:.0f} units) is high relative to EOQ ({self.eoq:.0f} units).",
                recommendation="Reduce demand/lead-time uncertainty through supplier SLAs and better forecasting before lowering service targets.",
                estimated_saving=round(saving, 2),
                saving_pct=round(saving / self.base_cost * 100, 2),
                implementation=["Measure lead-time variability", "Set supplier lead-time SLA",
                                "Improve forecast model", "Recalculate safety stock quarterly"],
                difficulty="Hard",
                timeframe="Long-term (3-6 months)",
                kpi_impact={"Safety Stock": f"↓ {reduction_possible:.0f} units",
                            "Annual Saving": f"${saving:,.2f}"},
            ))

        annual_spend = self.D * self.C
        if annual_spend > 50000:
            saving = self.base_cost * 0.03
            self._add_if_positive(OptimizationSuggestion(
                category="Strategic",
                priority="High",
                title="Apply A-Class Item Management Protocol",
                problem=f"High annual spend item (${annual_spend:,.2f}/year) deserves tighter controls.",
                recommendation="Classify as A-class: weekly cycle counts, dedicated buyer/planner, supplier scorecard, and regular EOQ review.",
                estimated_saving=round(saving, 2),
                saving_pct=3.0,
                implementation=["Tag item as A-class in ERP/WMS", "Assign owner",
                                "Schedule weekly cycle counts", "Create supplier scorecard"],
                difficulty="Easy",
                timeframe="Immediate (< 1 month)",
                kpi_impact={"Inventory Accuracy": "Target 99%+",
                            "Estimated Saving": f"${saving:,.2f}/year"},
            ))

    def generate_scenarios(self) -> pd.DataFrame:
        discount_C, discount_H = self._unit_cost_scenario(self.C * 0.95)
        best_C, best_H_at_new_C = self._unit_cost_scenario(
            self.C * 0.95, h_multiplier=0.75)
        scenario_defs = [
            ("Baseline (Current)", self.D, self.S, self.H, self.C),
            ("15% Ordering Cost Reduction", self.D, self.S * 0.85, self.H, self.C),
            ("20% Holding Cost Reduction", self.D, self.S, self.H * 0.80, self.C),
            ("5% Unit Cost Reduction", self.D, self.S, discount_H, discount_C),
            ("10% Demand Increase", self.D * 1.10, self.S, self.H, self.C),
            ("Combined: Ordering + Holding", self.D,
             self.S * 0.85, self.H * 0.80, self.C),
            ("Best Case: All Optimizations", self.D,
             self.S * 0.80, best_H_at_new_C, best_C),
        ]

        rows = []
        for name, D, S, H, C in scenario_defs:
            if name == "Baseline (Current)":
                Q = self.eoq
                tc = self.base_cost
            else:
                Q = self._optimal_qty(D, S, H)
                tc = self._annual_cost(D, S, H, C, Q)
            saving = self.base_cost - tc
            rows.append({
                "Scenario": name,
                "EOQ (units)": round(Q, 1),
                "Ordering Cost/Order": round(S, 2),
                "Holding Cost/Unit/Yr": round(H, 4),
                "Unit Cost": round(C, 2),
                "Total Annual Cost": round(tc, 2),
                "Saving vs Baseline": round(saving, 2),
                "Saving %": round(saving / self.base_cost * 100, 2) if self.base_cost else 0,
                "Orders/Year": round(D / Q, 1),
            })
        return pd.DataFrame(rows)

    def generate_all_suggestions(self) -> List[OptimizationSuggestion]:
        self.suggestions = []
        self.analyze_holding_costs()
        self.analyze_ordering_costs()
        self.analyze_strategic_opportunities()
        priority_order = {"High": 0, "Medium": 1, "Low": 2}
        self.suggestions.sort(key=lambda s: (
            priority_order.get(s.priority, 3), -s.estimated_saving))
        return self.suggestions

    def total_potential_saving(self) -> Dict:
        if not self.suggestions:
            self.generate_all_suggestions()
        return summarize_suggestions(self.suggestions, self.base_cost)

# ──────────────────────────────────────────────
# Savings aggregation helpers
# ──────────────────────────────────────────────


def _suggestion_overlap_group(suggestion: OptimizationSuggestion) -> str:
    """Return a conservative non-additivity group for a recommendation.

    Recommendations inside the same group usually act on the same baseline
    cost driver, so summing them overstates achievable savings. Portfolio and
    item-level summaries use the maximum saving within each group as a planning
    estimate while still exposing gross identified savings separately.
    """
    title = suggestion.title.lower()
    category = suggestion.category.lower()
    if "holding" in category:
        return "holding_cost_pool"
    if "safety stock" in title:
        return "safety_stock_pool"
    if "automate" in title or "admin" in title or "purchase order" in title:
        return "ordering_admin_pool"
    if "freight" in title or "carrier" in title:
        return "ordering_freight_pool"
    if "order quantity" in title or "align" in title:
        return "order_quantity_policy"
    if "quantity discount" in title or "unit cost" in title:
        return "unit_cost_negotiation"
    if "a-class" in title or "class item" in title:
        return "inventory_control_program"
    return category.replace(" ", "_") or "other"


def summarize_suggestions(suggestions: List[OptimizationSuggestion], base_cost: float = 0) -> Dict:
    """Summarize recommendation savings without double-counting overlaps."""
    gross_high = sum(
        s.estimated_saving for s in suggestions if s.priority == "High")
    gross_medium = sum(
        s.estimated_saving for s in suggestions if s.priority == "Medium")
    gross_low = sum(
        s.estimated_saving for s in suggestions if s.priority == "Low")
    gross_total = gross_high + gross_medium + gross_low

    grouped = {}
    for s in suggestions:
        group = _suggestion_overlap_group(s)
        if group not in grouped or s.estimated_saving > grouped[group].estimated_saving:
            grouped[group] = s

    conservative_total = sum(s.estimated_saving for s in grouped.values())
    return {
        "high_priority_saving": round(gross_high, 2),
        "medium_priority_saving": round(gross_medium, 2),
        "low_priority_saving": round(gross_low, 2),
        "gross_identified_saving": round(gross_total, 2),
        "optimistic_total": round(gross_total, 2),
        "conservative_total": round(conservative_total, 2),
        "saving_pct_conservative": round(conservative_total / base_cost * 100, 2) if base_cost else 0,
        "gross_saving_pct": round(gross_total / base_cost * 100, 2) if base_cost else 0,
        "num_suggestions": len(suggestions),
        "num_overlap_groups": len(grouped),
        "overlap_note": "Conservative total uses the largest saving in each overlapping cost-driver group; gross identified savings are not additive.",
    }


def summarize_portfolio_savings(all_suggestions: List[List[OptimizationSuggestion]], total_cost: float = 0) -> Dict:
    """Portfolio version of summarize_suggestions, preserving item boundaries."""
    gross_total = 0.0
    conservative_total = 0.0
    high = medium = low = 0.0
    num = 0
    groups = 0
    for suggs in all_suggestions:
        summary = summarize_suggestions(suggs, 0)
        gross_total += summary["gross_identified_saving"]
        conservative_total += summary["conservative_total"]
        high += summary["high_priority_saving"]
        medium += summary["medium_priority_saving"]
        low += summary["low_priority_saving"]
        num += summary["num_suggestions"]
        groups += summary["num_overlap_groups"]
    return {
        "high_priority_saving": round(high, 2),
        "medium_priority_saving": round(medium, 2),
        "low_priority_saving": round(low, 2),
        "gross_identified_saving": round(gross_total, 2),
        "optimistic_total": round(gross_total, 2),
        "conservative_total": round(conservative_total, 2),
        "saving_pct_conservative": round(conservative_total / total_cost * 100, 2) if total_cost else 0,
        "gross_saving_pct": round(gross_total / total_cost * 100, 2) if total_cost else 0,
        "num_suggestions": num,
        "num_overlap_groups": groups,
        "overlap_note": "Portfolio conservative total sums each item's non-overlapping planning estimate; gross identified savings are not additive.",
    }
