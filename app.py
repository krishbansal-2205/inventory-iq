# app.py

import datetime
from numbers import Number

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analysis.cost_optimizer import CostOptimizer
from analysis.sensitivity import SensitivityAnalyzer
from analysis.visualizations import SensitivityVisualizer
from costs.cost_structure import HoldingCostComponents, OrderingCostComponents, ProductionCostComponents
from models.enhanced_classic_eoq import EnhancedClassicEOQ, EnhancedPOQ, EnhancedStochasticEOQ
from reports.pdf_generator import EOQPDFGenerator


st.set_page_config(page_title="Multi-Item EOQ System",
                   page_icon="📦", layout="wide")


ANNUAL_COST_KEYS = {
    "annual_ordering_cost",
    "annual_holding_cost",
    "annual_purchase_cost",
    "annual_variable_ordering_cost",
    "annual_stockout_cost",
    "annual_deterioration_cost",
    "annual_backorder_cost",
    "setup_cost_annual",
    "holding_cost_annual",
    "production_cost_annual",
    "cycle_holding_cost",
    "safety_stock_holding_cost",
}


def annual_cost_keys(cost_breakdown: dict):
    """Return only annual-dollar components for composition charts."""
    return [
        k for k, v in (cost_breakdown or {}).items()
        if k in ANNUAL_COST_KEYS and isinstance(v, Number) and v > 0
    ]


# ─────────────────────────────────────────────────────────────────────────────
# UI helpers
# ─────────────────────────────────────────────────────────────────────────────

def holding_cost_ui(prefix: str, unit_cost: float):
    st.markdown("#### 🏪 Holding Cost Components")
    mode = st.radio(
        "Input Mode",
        ["Component-Based (Detailed)", "Single Value (Simple)"],
        key=f"{prefix}_hc_mode",
        horizontal=True,
    )

    if mode == "Single Value (Simple)":
        h_val = st.number_input(
            "Holding Cost ($/unit/year)",
            min_value=0.01,
            value=2.50,
            step=0.10,
            key=f"{prefix}_h_single",
            help="Total holding cost per unit per year.",
        )
        return None, h_val

    col1, col2 = st.columns(2)
    with col1:
        capital_rate = st.slider(
            "Capital Cost Rate (%/year)", 0.0, 30.0, 10.0, 0.5, key=f"{prefix}_capital") / 100
        storage_rate = st.number_input(
            "Storage Rate ($/m²/year)", 0.0, 500.0, 50.0, key=f"{prefix}_storage_rate")
        unit_area = st.number_input(
            "Unit Storage Area (m²/unit)", 0.0, 10.0, 0.05, 0.01, key=f"{prefix}_unit_area")
        insurance_rate = st.slider(
            "Insurance Rate (%/year)", 0.0, 5.0, 1.0, 0.1, key=f"{prefix}_insurance") / 100
    with col2:
        obsolescence_rate = st.slider(
            "Obsolescence Rate (%/year)", 0.0, 20.0, 2.0, 0.5, key=f"{prefix}_obsolescence") / 100
        spoilage_rate = st.slider(
            "Spoilage/Damage Rate (%/year)", 0.0, 10.0, 0.0, 0.5, key=f"{prefix}_spoilage") / 100
        handling_cost = st.number_input(
            "Handling Cost ($/unit/year)", 0.0, 100.0, 0.5, key=f"{prefix}_handling")
        utility_cost = st.number_input(
            "Utility Cost ($/unit/year)", 0.0, 50.0, 0.0, key=f"{prefix}_utility")
        custom_hc = st.number_input(
            "Custom Holding Cost ($/unit/year)", 0.0, 100.0, 0.0, key=f"{prefix}_custom_hc")

    components = HoldingCostComponents(
        capital_cost_rate=capital_rate,
        storage_rate_per_sqm=storage_rate,
        unit_storage_area=unit_area,
        insurance_rate=insurance_rate,
        obsolescence_rate=obsolescence_rate,
        spoilage_rate=spoilage_rate,
        handling_cost_per_unit=handling_cost,
        utility_cost_per_unit=utility_cost,
        custom_holding_cost=custom_hc,
    )
    breakdown = components.calculate(unit_cost)
    st.success(
        f"Computed holding cost: **${breakdown['total_holding_cost']:.4f}/unit/year**")
    with st.expander("View Holding Cost Breakdown"):
        df = pd.DataFrame([
            {"Component": k.replace("_", " ").title(), "Cost ($/unit/year)": v}
            for k, v in breakdown.items()
            if k != "total_holding_cost"
        ])
        st.dataframe(df, hide_index=True, use_container_width=True)
    return components, None


def ordering_cost_ui(prefix: str):
    st.markdown("#### 🚚 Ordering Cost Components")
    mode = st.radio(
        "Input Mode",
        ["Component-Based (Detailed)", "Single Value (Simple)"],
        key=f"{prefix}_oc_mode",
        horizontal=True,
    )

    if mode == "Single Value (Simple)":
        s_val = st.number_input("Ordering Cost ($/order)", min_value=0.01,
                                value=150.0, step=5.0, key=f"{prefix}_s_single")
        return None, s_val

    col1, col2 = st.columns(2)
    with col1:
        admin_cost = st.number_input(
            "Admin/Processing Cost ($/order)", 0.0, 5000.0, 80.0, key=f"{prefix}_admin")
        freight_fixed = st.number_input(
            "Fixed Freight Cost ($/order)", 0.0, 5000.0, 50.0, key=f"{prefix}_freight_fixed")
        freight_per_unit = st.number_input("Variable Freight ($/unit)", 0.0, 100.0, 0.0,
                                           key=f"{prefix}_freight_var", help="Treated as a per-unit landed cost, not as EOQ setup cost S.")
    with col2:
        receiving_cost = st.number_input(
            "Receiving Cost ($/order)", 0.0, 500.0, 20.0, key=f"{prefix}_receiving")
        inspection_per_unit = st.number_input("Inspection Cost ($/unit)", 0.0, 10.0, 0.0,
                                              key=f"{prefix}_inspection", help="Treated as a per-unit landed cost, not as EOQ setup cost S.")
        comm_cost = st.number_input(
            "Communication Cost ($/order)", 0.0, 200.0, 10.0, key=f"{prefix}_comm")
        custom_oc = st.number_input(
            "Custom Ordering Cost ($/order)", 0.0, 500.0, 0.0, key=f"{prefix}_custom_oc")

    components = OrderingCostComponents(
        admin_cost=admin_cost,
        freight_fixed=freight_fixed,
        freight_per_unit=freight_per_unit,
        receiving_cost=receiving_cost,
        inspection_cost_per_unit=inspection_per_unit,
        communication_cost=comm_cost,
        custom_ordering_cost=custom_oc,
    )
    breakdown = components.calculate(order_qty=1)
    st.success(
        f"Fixed EOQ ordering cost: **${components.fixed_cost_per_order():.2f}/order**  |  "
        f"Variable landed cost: **${components.variable_cost_per_unit():.4f}/unit**"
    )
    with st.expander("View Ordering Cost Breakdown"):
        df = pd.DataFrame([
            {"Component": k.replace("_", " ").title(), "Cost": v}
            for k, v in breakdown.items()
        ])
        st.dataframe(df, hide_index=True, use_container_width=True)
    return components, None


def production_cost_ui(prefix: str):
    st.markdown("#### 🏭 Production Cost Components")
    mode = st.radio(
        "Input Mode",
        ["Component-Based (Detailed)", "Single Value (Simple)"],
        key=f"{prefix}_pc_mode",
        horizontal=True,
    )

    if mode == "Single Value (Simple)":
        col1, col2 = st.columns(2)
        with col1:
            unit_cost = st.number_input(
                "Unit Production Cost ($/unit)", 0.01, 10000.0, 10.0, key=f"{prefix}_pc_unit")
        with col2:
            setup_cost = st.number_input(
                "Setup Cost ($/run)", 0.01, 50000.0, 200.0, key=f"{prefix}_pc_setup")
        return None, unit_cost, setup_cost

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Materials & Labor**")
        raw_material = st.number_input(
            "Raw Material Cost ($/unit)", 0.0, 1000.0, 5.0, key=f"{prefix}_raw")
        labor_rate = st.number_input(
            "Labor Rate ($/hour)", 0.0, 200.0, 25.0, key=f"{prefix}_labor_rate")
        labor_hours = st.number_input(
            "Labor Hours per Unit", 0.0, 10.0, 0.1, 0.01, key=f"{prefix}_labor_hrs")
    with col2:
        st.markdown("**Machine & Energy**")
        machine_rate = st.number_input(
            "Machine Rate ($/hour)", 0.0, 500.0, 30.0, key=f"{prefix}_machine_rate")
        machine_hrs = st.number_input(
            "Machine Hours per Unit", 0.0, 10.0, 0.05, 0.01, key=f"{prefix}_machine_hrs")
        energy_cost = st.number_input(
            "Energy Cost ($/unit)", 0.0, 50.0, 0.50, key=f"{prefix}_energy")
    with col3:
        st.markdown("**Overhead & Quality**")
        overhead_rate = st.slider(
            "Overhead Rate (%)", 0.0, 100.0, 20.0, 1.0, key=f"{prefix}_overhead") / 100
        quality_cost = st.number_input(
            "Quality/Inspection ($/unit)", 0.0, 50.0, 0.25, key=f"{prefix}_quality")
        scrap_rate = st.slider("Scrap/Defect Rate (%)",
                               0.0, 95.0, 2.0, 0.5, key=f"{prefix}_scrap") / 100
        tooling_cost = st.number_input(
            "Tooling Cost ($/unit)", 0.0, 50.0, 0.10, key=f"{prefix}_tooling")
        setup_cost = st.number_input(
            "Setup Cost per Run ($)", 0.01, 50000.0, 500.0, key=f"{prefix}_setup")
        custom_pc = st.number_input(
            "Custom Cost ($/unit)", 0.0, 100.0, 0.0, key=f"{prefix}_custom_pc")

    components = ProductionCostComponents(
        raw_material_cost=raw_material,
        labor_rate_per_hour=labor_rate,
        labor_hours_per_unit=labor_hours,
        setup_cost_per_run=setup_cost,
        machine_rate_per_hour=machine_rate,
        machine_hours_per_unit=machine_hrs,
        energy_cost_per_unit=energy_cost,
        overhead_rate=overhead_rate,
        quality_cost_per_unit=quality_cost,
        scrap_rate=scrap_rate,
        tooling_cost_per_unit=tooling_cost,
        custom_production_cost=custom_pc,
    )
    breakdown = components.calculate()
    st.success(
        f"Variable production cost: **${breakdown['variable_cost_per_unit']:.4f}/unit** | Setup: **${breakdown['setup_cost_per_run']:.2f}/run**")
    with st.expander("View Production Cost Breakdown"):
        df = pd.DataFrame([{"Component": k.replace(
            "_", " ").title(), "Value": v} for k, v in breakdown.items()])
        st.dataframe(df, hide_index=True, use_container_width=True)
    return components, breakdown["variable_cost_per_unit"], setup_cost


# ─────────────────────────────────────────────────────────────────────────────
# Model/report helpers
# ─────────────────────────────────────────────────────────────────────────────

def build_model(cfg: dict):
    if cfg["type"] == "classic":
        return EnhancedClassicEOQ(
            cfg["id"], cfg["name"], cfg["demand"], cfg["unit_cost"], cfg["lead_time"],
            holding_components=cfg["hc_components"],
            ordering_components=cfg["oc_components"],
            holding_cost_override=cfg["hc_override"],
            ordering_cost_override=cfg["oc_override"],
        )
    if cfg["type"] == "poq":
        # Preserve detailed production-component breakdowns. In detailed mode
        # pc_components is present and already carries both variable unit cost
        # and setup cost, so passing overrides would force EnhancedPOQ into its
        # manual-cost branch and discard the component breakdown.
        is_simple_poq_cost = cfg.get("pc_components") is None
        return EnhancedPOQ(
            cfg["id"], cfg["name"], cfg["demand"], cfg["production_rate"], cfg["lead_time"],
            holding_components=cfg["hc_components"],
            production_components=cfg["pc_components"],
            holding_cost_override=cfg["hc_override"],
            setup_cost_override=cfg.get(
                "setup_cost") if is_simple_poq_cost else None,
            unit_cost_override=cfg.get(
                "unit_cost") if is_simple_poq_cost else None,
        )
    if cfg["type"] == "stochastic":
        return EnhancedStochasticEOQ(
            cfg["id"], cfg["name"], cfg["demand"] /
            365, cfg["demand_std"], cfg["lead_time"], cfg["unit_cost"], cfg["service_level"],
            holding_components=cfg["hc_components"],
            ordering_components=cfg["oc_components"],
            holding_cost_override=cfg["hc_override"],
            ordering_cost_override=cfg["oc_override"],
            stockout_cost_per_unit=cfg["stockout_cost"],
            lead_time_std=cfg.get("lead_time_std", 0),
        )
    raise ValueError(f"Unsupported item type: {cfg['type']}")


def build_summary_df(results):
    return pd.DataFrame([
        {
            "Item ID": r.item_id,
            "Item Name": r.item_name,
            "Model": r.model_type,
            "EOQ": r.eoq,
            "Total Annual Cost": r.total_cost,
            "Orders/Year": r.order_frequency,
            "Cycle Time (days)": r.cycle_time,
            "ROP": r.reorder_point,
            "Safety Stock": r.safety_stock,
            "Holding Cost/Unit/Yr": r.holding_cost_per_unit,
            "Ordering Cost/Order": r.ordering_cost_per_order,
            "Unit Cost": r.unit_cost,
        }
        for _, r in results
    ])


def run_full_calculations(results, pct_range=50):
    all_sensitivity, all_suggestions, all_scenarios = [], [], []
    for cfg, result in results:
        sens = SensitivityAnalyzer(
            cfg, result).run_full_analysis(pct_range=pct_range)
        optimizer = CostOptimizer(cfg, result)
        suggestions = optimizer.generate_all_suggestions()
        scenarios = optimizer.generate_scenarios()
        all_sensitivity.append(sens)
        all_suggestions.append(suggestions)
        all_scenarios.append(scenarios)
    return all_sensitivity, all_suggestions, all_scenarios


def render_basic_result(cfg, result):
    with st.expander(
        f"📦 {result.item_name} | {result.model_type} | EOQ: {result.eoq} units | Cost: ${result.total_cost:,.2f}",
        expanded=True,
    ):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("EOQ", f"{result.eoq} units")
        col2.metric("Total Annual Cost", f"${result.total_cost:,.2f}")
        col3.metric("Orders/Year", result.order_frequency)
        col4.metric("Cycle Time", f"{result.cycle_time} days")

        col5, col6, col7 = st.columns(3)
        col5.metric("Holding Cost/Unit/Yr",
                    f"${result.holding_cost_per_unit:.4f}")
        col6.metric("Order/Setup Cost",
                    f"${result.ordering_cost_per_order:.2f}")
        if result.reorder_point is not None:
            col7.metric("Reorder Point", f"{result.reorder_point} units")

        cost_breakdown = result.cost_breakdown or {}
        cost_keys = annual_cost_keys(cost_breakdown)
        if cost_keys:
            fig_pie = px.pie(values=[cost_breakdown[k] for k in cost_keys], names=[k.replace(
                "_", " ").title() for k in cost_keys], title=f"Cost Breakdown - {result.item_name}")
            st.plotly_chart(fig_pie, use_container_width=True)

        if result.holding_breakdown and "total_holding_cost" in result.holding_breakdown:
            st.markdown("**Holding Cost Breakdown:**")
            hc_df = pd.DataFrame([
                {"Component": k.replace("_", " ").title(),
                 "Cost ($/unit/year)": v}
                for k, v in result.holding_breakdown.items()
                if isinstance(v, Number) and k != "total_holding_cost"
            ])
            st.dataframe(hc_df, hide_index=True, use_container_width=True)

        if result.ordering_breakdown:
            st.markdown("**Ordering Cost Breakdown:**")
            oc_df = pd.DataFrame([
                {"Component": k.replace("_", " ").title(), "Value": v}
                for k, v in result.ordering_breakdown.items()
                if k != "source"
            ])
            st.dataframe(oc_df, hide_index=True, use_container_width=True)

        if result.production_breakdown:
            st.markdown("**Production Cost Breakdown:**")
            pc_df = pd.DataFrame([{"Component": k.replace("_", " ").title(
            ), "Value": v} for k, v in result.production_breakdown.items()])
            st.dataframe(pc_df, hide_index=True, use_container_width=True)


def render_sensitivity_section(cfg, result):
    st.header("📉 Sensitivity Analysis")
    col1, col2, col3 = st.columns(3)
    with col1:
        pct_range = st.slider("Parameter Variation Range (±%)",
                              10, 80, 50, 5, key=f"range_{result.item_id}")
    with col2:
        show_two_way = st.checkbox(
            "Enable Two-Way Analysis", value=True, key=f"two_way_{result.item_id}")
    with col3:
        show_components = st.checkbox(
            "Show Component Analysis", value=True, key=f"components_{result.item_id}")

    full_analysis = SensitivityAnalyzer(
        cfg, result).run_full_analysis(pct_range=pct_range)
    ranked = full_analysis["ranked_parameters"]
    tornado_data = full_analysis["tornado_data"]

    st.subheader("📊 Parameter Sensitivity Ranking")
    summary_df = pd.DataFrame([
        {
            "Rank": r.sensitivity_rank,
            "Parameter": r.parameter,
            "Base Value": round(r.base_value, 4),
            "EOQ Elasticity (ε)": r.elasticity,
            "Cost Elasticity (ε)": r.cost_elasticity,
            "Impact Level": "High" if abs(r.cost_elasticity) > 0.4 else "Medium" if abs(r.cost_elasticity) > 0.2 else "Low",
            "EOQ Safe Range Low": r.critical_range[0],
            "EOQ Safe Range High": r.critical_range[1],
            f"Cost at -{pct_range}%": f"${r.cost_values[0]:,.2f}",
            f"Cost at +{pct_range}%": f"${r.cost_values[-1]:,.2f}",
        }
        for r in ranked
    ])
    st.dataframe(summary_df, hide_index=True, use_container_width=True)

    with st.expander("ℹ️ How to Read Elasticity"):
        st.markdown("""
        **EOQ elasticity** shows how EOQ changes when a parameter changes.  
        **Cost elasticity** shows how total annual cost changes when a parameter changes.  
        Parameters are ranked by cost elasticity because that is usually the business-impact view.
        """)

    st.subheader("🌪️ Tornado Chart — Parameter Impact")
    st.plotly_chart(SensitivityVisualizer.plot_tornado_chart(
        tornado_data, result.total_cost, result.item_name), use_container_width=True)

    st.subheader("📈 Sensitivity Curves")
    st.plotly_chart(SensitivityVisualizer.plot_sensitivity_curves(
        ranked, result.item_name), use_container_width=True)

    if show_two_way:
        st.subheader("🔁 Two-Way Sensitivity Analysis")
        col1, col2 = st.columns(2)
        options = ["demand", "ordering_cost", "holding_cost", "unit_cost"]
        with col1:
            param1 = st.selectbox("First Parameter", options, format_func=lambda x: x.replace(
                "_", " ").title(), key=f"p1_{result.item_id}")
        with col2:
            param2 = st.selectbox("Second Parameter", options, index=2, format_func=lambda x: x.replace(
                "_", " ").title(), key=f"p2_{result.item_id}")
        if param1 != param2:
            two_way = SensitivityAnalyzer(
                cfg, result).two_way_sensitivity(param1, param2, steps=25)
            st.plotly_chart(SensitivityVisualizer.plot_two_way_heatmap(
                two_way, result.item_name), use_container_width=True)
            st.info(
                f"EOQ ranges from **{two_way['eoq_matrix'].min():.0f}** to **{two_way['eoq_matrix'].max():.0f}** units across the selected combinations.")
        else:
            st.warning("Choose two different parameters.")

    if show_components:
        col1, col2 = st.columns(2)
        with col1:
            hc_comp = full_analysis.get("holding_components", {})
            if hc_comp:
                st.subheader("🏪 Holding Cost Component Sensitivity")
                st.plotly_chart(SensitivityVisualizer.plot_component_sensitivity(
                    hc_comp, "Holding Cost", result.item_name), use_container_width=True)
        with col2:
            oc_comp = full_analysis.get("ordering_components", {})
            if oc_comp:
                st.subheader("🚚 Ordering Cost Component Sensitivity")
                st.plotly_chart(SensitivityVisualizer.plot_component_sensitivity(
                    oc_comp, "Ordering Cost", result.item_name), use_container_width=True)


def render_optimization_section(cfg, result):
    st.header("💡 Cost Optimization Suggestions")
    optimizer = CostOptimizer(cfg, result)
    suggestions = optimizer.generate_all_suggestions()
    scenarios_df = optimizer.generate_scenarios()
    savings_summary = optimizer.total_potential_saving()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Annual Cost", f"${result.total_cost:,.2f}")
    col2.metric("Conservative Planning Saving",
                f"${savings_summary['conservative_total']:,.2f}", f"{savings_summary['saving_pct_conservative']:.1f}%")
    col3.metric("Gross Identified (Not Additive)",
                f"${savings_summary['gross_identified_saving']:,.2f}")
    col4.metric("Suggestions Found", savings_summary["num_suggestions"])

    if savings_summary.get("gross_identified_saving", 0) > savings_summary.get("conservative_total", 0):
        st.caption(savings_summary.get(
            "overlap_note", "Gross identified savings may include overlapping recommendations and should not be treated as fully additive."))

    st.subheader("🗺️ Optimization Opportunity Map")
    st.plotly_chart(SensitivityVisualizer.plot_optimization_summary(
        suggestions, result.item_name), use_container_width=True)

    st.subheader("📋 Detailed Recommendations")
    if not suggestions:
        st.info("No specific optimization opportunities found for this item.")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            filter_priority = st.multiselect("Filter by Priority", ["High", "Medium", "Low"], default=[
                                             "High", "Medium", "Low"], key=f"fp_{result.item_id}")
        categories = sorted({s.category for s in suggestions})
        with col2:
            filter_category = st.multiselect(
                "Filter by Category", categories, default=categories, key=f"fc_{result.item_id}")
        with col3:
            filter_difficulty = st.multiselect("Filter by Difficulty", ["Easy", "Medium", "Hard"], default=[
                                               "Easy", "Medium", "Hard"], key=f"fd_{result.item_id}")
        filtered = [
            s for s in suggestions if s.priority in filter_priority and s.category in filter_category and s.difficulty in filter_difficulty]
        if not filtered:
            st.warning("No suggestions match the selected filters.")
        for i, s in enumerate(filtered):
            with st.expander(f"[{s.priority}] {s.title} | Save ${s.estimated_saving:,.2f} ({s.saving_pct:.1f}%) | {s.difficulty} | {s.timeframe}", expanded=(i == 0)):
                col_a, col_b = st.columns([3, 2])
                with col_a:
                    st.markdown("**Problem:**")
                    st.info(s.problem)
                    st.markdown("**Recommendation:**")
                    st.success(s.recommendation)
                    st.markdown("**Implementation Steps:**")
                    for step_num, step in enumerate(s.implementation, 1):
                        st.markdown(f"{step_num}. {step}")
                with col_b:
                    st.markdown("**KPI Impact:**")
                    st.dataframe(pd.DataFrame([{"KPI": k, "Impact": v} for k, v in s.kpi_impact.items(
                    )]), hide_index=True, use_container_width=True)

    st.subheader("🔮 What-If Scenario Analysis")
    st.plotly_chart(SensitivityVisualizer.plot_scenarios(
        scenarios_df, result.item_name), use_container_width=True)
    st.dataframe(scenarios_df, hide_index=True, use_container_width=True)

    if suggestions:
        report_df = pd.DataFrame([
            {
                "Priority": s.priority,
                "Category": s.category,
                "Title": s.title,
                "Problem": s.problem,
                "Recommendation": s.recommendation,
                "Est. Saving ($)": s.estimated_saving,
                "Saving (%)": s.saving_pct,
                "Difficulty": s.difficulty,
                "Timeframe": s.timeframe,
                "Implementation": " → ".join(s.implementation),
            }
            for s in suggestions
        ])
        st.download_button("📄 Download Optimization Report (CSV)", report_df.to_csv(
            index=False).encode("utf-8"), f"optimization_report_{result.item_id}.csv", "text/csv")


def render_pdf_download(results, summary_df):
    st.header("📄 PDF Report Generator")
    with st.expander("⚙️ Report Settings", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            company = st.text_input("Company Name", "ACME Corporation")
            analyst = st.text_input("Analyst Name", "Inventory Team")
        with col2:
            report_title = st.text_input(
                "Report Title", "EOQ Inventory Analysis Report")
            page_size_opt = st.selectbox("Page Size", ["A4", "Letter"])
        include_charts = st.checkbox(
            "Include charts in PDF",
            value=True,
            help=(
                "Exports every chart at full report resolution. The optimized generator batches "
                "Plotly/Kaleido image export so charts are faster without dropping chart count or DPI."
            ),
        )
    if st.button("🖨️ Generate PDF Report", type="primary"):
        from reportlab.lib.pagesizes import A4, letter
        page_size = A4 if page_size_opt == "A4" else letter
        spinner_text = "Generating charts and building PDF..." if include_charts else "Building PDF..."
        with st.spinner(spinner_text):
            try:
                all_sensitivity, all_suggestions, all_scenarios = run_full_calculations(
                    results)
                generator = EOQPDFGenerator(
                    page_size=page_size,
                    report_title=report_title,
                    company=company,
                    analyst=analyst,
                    include_charts=include_charts,
                )
                pdf_bytes = generator.generate(
                    all_configs=[cfg for cfg, _ in results],
                    all_results=results,
                    all_sensitivity=all_sensitivity,
                    all_suggestions=all_suggestions,
                    all_scenarios=all_scenarios,
                    summary_df=summary_df,
                )
                st.success(
                    f"Report generated successfully ({len(pdf_bytes)/1024:.0f} KB).")
                st.download_button(
                    label="⬇️ Download PDF Report",
                    data=pdf_bytes,
                    file_name=f"EOQ_Report_{datetime.date.today().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    type="primary",
                )
            except Exception as exc:
                st.error(f"Error generating PDF: {exc}")
                st.exception(exc)


def render_full_results(results):
    st.header("📊 Results")
    for cfg, result in results:
        render_basic_result(cfg, result)

    st.subheader("📈 Summary Comparison")
    summary_df = build_summary_df(results)
    st.dataframe(summary_df, hide_index=True, use_container_width=True)
    st.plotly_chart(px.bar(summary_df, x="Item Name", y="Total Annual Cost", color="Model",
                    barmode="group", title="Total Annual Cost Comparison"), use_container_width=True)

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(name="Holding ($/unit/year)",
                   x=summary_df["Item Name"], y=summary_df["Holding Cost/Unit/Yr"]))
    fig2.add_trace(go.Bar(name="Ordering ($/order)",
                   x=summary_df["Item Name"], y=summary_df["Ordering Cost/Order"]))
    fig2.update_layout(
        barmode="group", title="Holding vs Ordering Cost Comparison")
    st.plotly_chart(fig2, use_container_width=True)

    st.download_button("⬇️ Download Results CSV", summary_df.to_csv(
        index=False).encode("utf-8"), "eoq_results.csv", "text/csv")

    result_tabs = st.tabs([f"📦 {r.item_name}" for _, r in results])
    for tab, (cfg, result) in zip(result_tabs, results):
        with tab:
            analysis_tabs = st.tabs(
                ["📉 Sensitivity Analysis", "💡 Optimization Suggestions"])
            with analysis_tabs[0]:
                render_sensitivity_section(cfg, result)
            with analysis_tabs[1]:
                render_optimization_section(cfg, result)

    render_pdf_download(results, summary_df)


# ─────────────────────────────────────────────────────────────────────────────
# Main app
# ─────────────────────────────────────────────────────────────────────────────

st.title("📦 Multi-Item EOQ System with Variable Cost Control")
st.sidebar.header("⚙️ Configuration")
num_items = st.sidebar.slider("Number of Items", 1, 8, 2)

all_items_config = []
tabs = st.tabs([f"📦 Item {i + 1}" for i in range(num_items)])

for i, tab in enumerate(tabs):
    with tab:
        st.subheader(f"Item {i + 1} Configuration")
        col1, col2 = st.columns(2)
        with col1:
            item_id = st.text_input(
                "Item ID", f"SKU{i + 1:03d}", key=f"id_{i}")
            item_name = st.text_input(
                "Item Name", f"Item {i + 1}", key=f"nm_{i}")
            demand = st.number_input(
                "Annual Demand (units)", 1, 500000, 5000, key=f"dm_{i}")
            lead_time = st.number_input(
                "Lead Time (days)", 0, 365, 7, key=f"lt_{i}")
        with col2:
            item_type = st.selectbox("Item Type", [
                                     "Purchased (Classic EOQ)", "Manufactured (POQ)", "Uncertain Demand (Stochastic)"], key=f"type_{i}")
            demand_std = st.number_input(
                "Demand Std Dev (daily)", 0.0, 1000.0, 0.0, key=f"std_{i}")
            service_level = st.slider(
                "Service Level", 0.80, 0.999, 0.95, key=f"sl_{i}")
            stockout_cost = st.number_input(
                "Stockout Cost ($/unit)", 0.0, 1000.0, 0.0, key=f"soc_{i}")
            current_order_qty = st.number_input(
                "Current Order Qty (optional)", 0.0, 1000000.0, 0.0, key=f"coq_{i}")

        st.divider()
        if item_type == "Purchased (Classic EOQ)":
            unit_cost = st.number_input(
                "Unit Purchase Cost ($)", 0.01, 10000.0, 10.0, key=f"uc_{i}")
            col_hc, col_oc = st.columns(2)
            with col_hc:
                hc_components, hc_override = holding_cost_ui(
                    f"item{i}", unit_cost)
            with col_oc:
                oc_components, oc_override = ordering_cost_ui(f"item{i}")
            all_items_config.append({
                "type": "classic", "id": item_id, "name": item_name, "demand": demand, "unit_cost": unit_cost,
                "lead_time": lead_time, "demand_std": demand_std, "service_level": service_level,
                "stockout_cost": stockout_cost, "current_order_qty": current_order_qty if current_order_qty > 0 else None,
                "hc_components": hc_components, "hc_override": hc_override, "oc_components": oc_components, "oc_override": oc_override,
            })
        elif item_type == "Manufactured (POQ)":
            production_rate = st.number_input(
                "Production Rate (units/year)", int(demand) + 1, 10000000, int(demand) * 3, key=f"pr_{i}")
            col_pc, col_hc = st.columns(2)
            with col_pc:
                pc_components, unit_cost, setup_cost = production_cost_ui(
                    f"item{i}")
            with col_hc:
                hc_components, hc_override = holding_cost_ui(
                    f"item{i}_h", unit_cost)
            all_items_config.append({
                "type": "poq", "id": item_id, "name": item_name, "demand": demand, "unit_cost": unit_cost,
                "lead_time": lead_time, "production_rate": production_rate, "current_order_qty": current_order_qty if current_order_qty > 0 else None,
                "hc_components": hc_components, "hc_override": hc_override, "pc_components": pc_components, "setup_cost": setup_cost,
            })
        else:
            unit_cost = st.number_input(
                "Unit Cost ($)", 0.01, 10000.0, 10.0, key=f"uc_s_{i}")
            lead_time_std = st.number_input(
                "Lead Time Std Dev (days)", 0.0, 30.0, 0.0, key=f"lts_{i}")
            col_hc, col_oc = st.columns(2)
            with col_hc:
                hc_components, hc_override = holding_cost_ui(
                    f"item{i}_s", unit_cost)
            with col_oc:
                oc_components, oc_override = ordering_cost_ui(f"item{i}_s")
            all_items_config.append({
                "type": "stochastic", "id": item_id, "name": item_name, "demand": demand, "unit_cost": unit_cost,
                "lead_time": lead_time, "demand_std": demand_std,
                "service_level": service_level, "stockout_cost": stockout_cost, "lead_time_std": lead_time_std,
                "current_order_qty": current_order_qty if current_order_qty > 0 else None,
                "hc_components": hc_components, "hc_override": hc_override, "oc_components": oc_components, "oc_override": oc_override,
            })

if st.button("🚀 Run EOQ Analysis", type="primary"):
    results, errors = [], []
    for cfg in all_items_config:
        try:
            results.append((cfg, build_model(cfg).calculate()))
        except Exception as exc:
            errors.append(f"{cfg['name']}: {exc}")
    if errors:
        for err in errors:
            st.error(err)
    if results:
        st.session_state["eoq_results"] = results
        st.success(f"Analysis completed for {len(results)} item(s).")

if "eoq_results" in st.session_state:
    render_full_results(st.session_state["eoq_results"])
