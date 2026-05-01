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


st.set_page_config(page_title="Inventory Command Center",
                   page_icon="📦", layout="wide", initial_sidebar_state="expanded")


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
# Visual design system
# ─────────────────────────────────────────────────────────────────────────────
DESIGN_CSS = """
<style>
:root {
  --ink: #0f172a;
  --muted: #64748b;
  --panel: rgba(255, 255, 255, 0.86);
  --line: rgba(15, 23, 42, 0.10);
  --brand: #2563eb;
  --brand-2: #7c3aed;
  --accent: #14b8a6;
  --shadow: 0 20px 60px rgba(15, 23, 42, 0.10);
  --shadow-soft: 0 10px 28px rgba(15, 23, 42, 0.08);
}
.stApp {
  background:
    radial-gradient(circle at 10% 0%, rgba(37, 99, 235, 0.18), transparent 30%),
    radial-gradient(circle at 92% 8%, rgba(20, 184, 166, 0.16), transparent 32%),
    linear-gradient(180deg, #f8fafc 0%, #eef2ff 42%, #f8fafc 100%);
  color: var(--ink);
}
.block-container { padding-top: 1.4rem; padding-bottom: 5rem; max-width: 1450px; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0f172a 0%, #111827 52%, #172554 100%); border-right: 1px solid rgba(255,255,255,0.08); }
[data-testid="stSidebar"] * { color: rgba(255,255,255,0.92) !important; }
.hero-shell { position: relative; overflow: hidden; padding: 30px 34px; border-radius: 30px; background: linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(30, 41, 59, 0.92)); box-shadow: var(--shadow); border: 1px solid rgba(255,255,255,0.16); margin-bottom: 1.3rem; }
.hero-shell:after { content: ""; position: absolute; right: -80px; top: -120px; width: 360px; height: 360px; border-radius: 50%; background: linear-gradient(135deg, rgba(37,99,235,0.42), rgba(20,184,166,0.28)); filter: blur(4px); }
.hero-kicker { position: relative; z-index: 2; display: inline-flex; gap: 10px; align-items: center; padding: 7px 12px; border-radius: 999px; background: rgba(255, 255, 255, 0.10); border: 1px solid rgba(255, 255, 255, 0.18); color: #bfdbfe; font-size: 0.78rem; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }
.hero-title { position: relative; z-index: 2; margin: 14px 0 8px 0; font-size: clamp(2.1rem, 4vw, 4.1rem); line-height: 0.98; color: white; letter-spacing: -0.055em; font-weight: 900; }
.hero-copy { position: relative; z-index: 2; max-width: 780px; color: #cbd5e1; font-size: 1.04rem; line-height: 1.65; margin-bottom: 0; }
.hero-grid { position: relative; z-index: 2; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 22px; max-width: 840px; }
.hero-chip { padding: 13px 15px; border-radius: 18px; background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.14); color: #e2e8f0; font-size: 0.88rem; }
.hero-chip b { color: #fff; display: block; margin-bottom: 2px; }
.section-kicker { display: inline-flex; align-items: center; gap: 9px; color: var(--brand); font-weight: 900; font-size: 0.78rem; letter-spacing: 0.08em; text-transform: uppercase; margin-top: 0.45rem; }
.section-title { font-size: 1.55rem; font-weight: 900; letter-spacing: -0.04em; color: var(--ink); margin: 0.15rem 0 0.2rem; }
.section-copy { color: var(--muted); font-size: 0.95rem; margin: 0 0 0.9rem; }
.metric-card { border-radius: 22px; padding: 18px 18px 16px; background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.92)); border: 1px solid rgba(15,23,42,0.08); box-shadow: 0 12px 30px rgba(15,23,42,0.07); min-height: 118px; }
.metric-label { color: var(--muted); font-weight: 800; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.07em; }
.metric-value { margin-top: 8px; color: var(--ink); font-weight: 900; font-size: 1.7rem; letter-spacing: -0.045em; line-height: 1.05; }
.metric-detail { margin-top: 8px; color: #475569; font-size: 0.86rem; }
.result-banner { padding: 20px 22px; border-radius: 24px; background: linear-gradient(135deg, rgba(37,99,235,0.12), rgba(20,184,166,0.10)); border: 1px solid rgba(37,99,235,0.14); margin: 1.1rem 0 0.8rem; }
.result-title { color: var(--ink); font-size: 1.35rem; font-weight: 900; letter-spacing: -0.035em; margin: 0; }
.result-meta { color: var(--muted); font-size: 0.9rem; margin-top: 5px; }
.badge { display: inline-flex; align-items: center; padding: 6px 11px; border-radius: 999px; font-size: 0.76rem; font-weight: 900; letter-spacing: 0.04em; text-transform: uppercase; background: rgba(37,99,235,0.10); color: #1d4ed8; border: 1px solid rgba(37,99,235,0.16); }
.badge.teal { background: rgba(20,184,166,0.12); color: #0f766e; border-color: rgba(20,184,166,0.18); }
.badge.purple { background: rgba(124,58,237,0.11); color: #6d28d9; border-color: rgba(124,58,237,0.16); }
.sidebar-brand { padding: 20px 8px 16px; border-bottom: 1px solid rgba(255,255,255,0.12); margin-bottom: 18px; }
.sidebar-brand h2 { color: #fff !important; margin: 0; font-size: 1.25rem; letter-spacing: -0.03em; }
.sidebar-brand p { color: rgba(226,232,240,0.72) !important; font-size: 0.82rem; line-height: 1.45; margin-top: 6px; }
.workflow-step { padding: 11px 12px; border-radius: 16px; background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.10); margin: 8px 0; font-size: 0.86rem; }
[data-testid="stMetric"] { background: rgba(255,255,255,0.70); border: 1px solid rgba(15,23,42,0.08); padding: 14px 16px; border-radius: 18px; box-shadow: 0 8px 22px rgba(15,23,42,0.06); }
[data-testid="stMetricLabel"] p { font-size: 0.78rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; font-weight: 800; }
[data-testid="stMetricValue"] div { color: var(--ink); font-weight: 900; letter-spacing: -0.04em; }
.stButton > button, .stDownloadButton > button { border: none !important; border-radius: 999px !important; padding: 0.72rem 1.2rem !important; background: linear-gradient(135deg, #2563eb, #14b8a6) !important; color: white !important; font-weight: 900 !important; box-shadow: 0 14px 30px rgba(37, 99, 235, 0.25) !important; }
.stButton > button:hover, .stDownloadButton > button:hover { transform: translateY(-1px); box-shadow: 0 18px 36px rgba(37, 99, 235, 0.30) !important; }
.stTabs [data-baseweb="tab-list"] { gap: 8px; background: rgba(255,255,255,0.58); padding: 8px; border-radius: 18px; border: 1px solid rgba(15,23,42,0.08); }
.stTabs [data-baseweb="tab"] { border-radius: 13px; padding: 10px 16px; font-weight: 800; }
.stTabs [aria-selected="true"] { background: #0f172a !important; color: white !important; }
hr { border-color: rgba(15,23,42,0.08); }
@media (max-width: 900px) { .hero-grid { grid-template-columns: 1fr; } .hero-shell { padding: 24px; } }

/* ── Contrast hardening for Streamlit widgets and generated content ───────── */
.stApp, .main, .block-container, [data-testid="stAppViewContainer"] { color: var(--ink) !important; }
.block-container .stMarkdown,
.block-container .stMarkdown p,
.block-container [data-testid="stMarkdownContainer"],
.block-container [data-testid="stMarkdownContainer"] p { color: var(--ink) !important; }
.block-container [data-testid="stWidgetLabel"] p,
.block-container [data-testid="stWidgetLabel"] label,
.block-container [data-testid="stWidgetLabel"] span { color: #0f172a !important; font-weight: 750; }
.block-container input,
.block-container textarea,
.block-container [contenteditable="true"],
.block-container [data-baseweb="input"] input,
.block-container [data-baseweb="textarea"] textarea {
  color: #0f172a !important; -webkit-text-fill-color: #0f172a !important; background-color: rgba(255,255,255,0.96) !important;
}
.block-container input::placeholder,
.block-container textarea::placeholder { color: #64748b !important; -webkit-text-fill-color: #64748b !important; }
.block-container [data-baseweb="select"] > div,
.block-container [data-baseweb="select"] span,
.block-container [data-baseweb="select"] input,
.block-container [data-baseweb="popover"] *,
.block-container [role="listbox"] *,
.block-container [role="option"] * { color: #0f172a !important; -webkit-text-fill-color: #0f172a !important; }
.block-container [data-baseweb="radio"] label,
.block-container [data-baseweb="radio"] div,
.block-container [data-baseweb="checkbox"] label,
.block-container [data-baseweb="checkbox"] div { color: #0f172a !important; }
.stTabs [data-baseweb="tab"] p,
.stTabs [data-baseweb="tab"] span { color: #334155 !important; }
.stTabs [aria-selected="true"] p,
.stTabs [aria-selected="true"] span,
.stTabs [aria-selected="true"] div { color: #ffffff !important; }
[data-testid="stMetricLabel"] p,
[data-testid="stMetricLabel"] label,
[data-testid="stMetricLabel"] span { color: #64748b !important; }
[data-testid="stMetricValue"] div,
[data-testid="stMetricValue"] span { color: #0f172a !important; }
[data-testid="stMetricDelta"] div,
[data-testid="stMetricDelta"] span { color: #0f766e !important; }
.stAlert,
.stAlert p,
.stAlert div,
.stAlert span { color: #0f172a !important; }
[data-testid="stDataFrame"] *,
[data-testid="stTable"] * { color: #0f172a !important; }
.hero-title { color: #ffffff !important; }
.hero-copy { color: #cbd5e1 !important; }
.hero-kicker { color: #bfdbfe !important; }
.hero-chip { color: #e2e8f0 !important; }
.hero-chip b { color: #ffffff !important; }
.metric-label { color: #64748b !important; }
.metric-value { color: #0f172a !important; }
.metric-detail { color: #475569 !important; }
.result-title { color: #0f172a !important; }
.result-meta { color: #64748b !important; }
.badge { color: #1d4ed8 !important; }
.badge.teal { color: #0f766e !important; }
.badge.purple { color: #6d28d9 !important; }

/* Sidebar keeps its premium dark look, while white input boxes remain readable. */
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .workflow-step,
[data-testid="stSidebar"] .workflow-step * { color: rgba(255,255,255,0.92) !important; }
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] [data-baseweb="input"] input,
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] input {
  color: #0f172a !important; -webkit-text-fill-color: #0f172a !important; background-color: #ffffff !important;
}
[data-testid="stSidebar"] [data-baseweb="slider"] *,
[data-testid="stSidebar"] [role="slider"] * { color: rgba(255,255,255,0.92) !important; }
</style>
"""


def inject_design_system():
    st.markdown(DESIGN_CSS, unsafe_allow_html=True)


def hero():
    st.markdown("""
    <div class="hero-shell">
      <div class="hero-kicker">Inventory Intelligence Suite</div>
      <div class="hero-title">EOQ Command Center</div>
      <p class="hero-copy">A boardroom-grade workspace for order quantity decisions, cost architecture, sensitivity diagnostics, and action-ready inventory recommendations.</p>
      <div class="hero-grid">
        <div class="hero-chip"><b>01 · Configure</b> Build item-level demand and cost architecture.</div>
        <div class="hero-chip"><b>02 · Diagnose</b> Compare EOQ, sensitivity, and scenario behavior.</div>
        <div class="hero-chip"><b>03 · Act</b> Export recommendations and executive PDF reports.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def section_header(kicker: str, title: str, copy: str = ""):
    st.markdown(f"""
    <div class="section-kicker">{kicker}</div>
    <div class="section-title">{title}</div>
    <div class="section-copy">{copy}</div>
    """, unsafe_allow_html=True)


def metric_card(label: str, value: str, detail: str = ""):
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">{label}</div>
      <div class="metric-value">{value}</div>
      <div class="metric-detail">{detail}</div>
    </div>
    """, unsafe_allow_html=True)


def model_badge(model_type: str) -> str:
    lower = model_type.lower()
    css = "purple" if "production" in lower else "teal" if "stochastic" in lower else ""
    return f'<span class="badge {css}">{model_type}</span>'

# ─────────────────────────────────────────────────────────────────────────────
# UI helpers
# ─────────────────────────────────────────────────────────────────────────────


def holding_cost_ui(prefix: str, unit_cost: float):
    section_header("Cost architecture", "Holding cost",
                   "Choose a simple carrying charge or build it from capital, storage, insurance, risk, and handling components.")
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
    section_header("Procurement economics", "Ordering cost",
                   "Separate fixed setup/order costs from variable landed costs so the EOQ math stays clean.")
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
    section_header("Production economics", "Production cost",
                   "Model internal production with material, labor, machine, energy, overhead, quality, scrap, tooling, and setup costs.")
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
    st.markdown(
        f"""
        <div class="result-banner">
          <div style="display:flex; justify-content:space-between; gap:16px; align-items:flex-start; flex-wrap:wrap;">
            <div>
              <p class="result-title">{result.item_name} <span style="color:#64748b; font-weight:800;">({result.item_id})</span></p>
              <div class="result-meta">{model_badge(result.model_type)} &nbsp; Lead time: {cfg.get('lead_time', '—')} days &nbsp; Demand: {cfg.get('demand', 0):,.0f} units/year</div>
            </div>
            <div class="badge">Optimal Q · {result.eoq:,.0f}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Economic order quantity",
                    f"{result.eoq:,.0f}", "units per replenishment")
    with col2:
        metric_card("Total annual cost",
                    f"${result.total_cost:,.0f}", "purchase + ordering + holding")
    with col3:
        metric_card("Orders per year",
                    f"{result.order_frequency:,.1f}", "replenishment cadence")
    with col4:
        metric_card(
            "Cycle time", f"{result.cycle_time:,.0f}d", "average days per cycle")

    with st.expander("Cost architecture and operational details", expanded=False):
        col5, col6, col7 = st.columns(3)
        col5.metric("Holding Cost / Unit / Year",
                    f"${result.holding_cost_per_unit:.4f}")
        col6.metric("Order / Setup Cost",
                    f"${result.ordering_cost_per_order:.2f}")
        if result.reorder_point is not None:
            col7.metric("Reorder Point", f"{result.reorder_point} units")
        elif result.safety_stock is not None:
            col7.metric("Safety Stock", f"{result.safety_stock} units")

        cost_breakdown = result.cost_breakdown or {}
        cost_keys = annual_cost_keys(cost_breakdown)
        if cost_keys:
            fig_pie = px.pie(
                values=[cost_breakdown[k] for k in cost_keys],
                names=[k.replace("_", " ").title() for k in cost_keys],
                title=f"Annual Cost Composition — {result.item_name}",
                hole=0.48,
            )
            fig_pie.update_layout(margin=dict(
                l=10, r=10, t=50, b=10), legend_title_text="")
            st.plotly_chart(fig_pie, use_container_width=True)

        detail_tabs = st.tabs(["Holding", "Ordering", "Production"]
                              if result.production_breakdown else ["Holding", "Ordering"])
        with detail_tabs[0]:
            if result.holding_breakdown and "total_holding_cost" in result.holding_breakdown:
                hc_df = pd.DataFrame([
                    {"Component": k.replace(
                        "_", " ").title(), "Cost ($/unit/year)": v}
                    for k, v in result.holding_breakdown.items()
                    if isinstance(v, Number) and k != "total_holding_cost"
                ])
                st.dataframe(hc_df, hide_index=True, use_container_width=True)
            else:
                st.info(
                    "No component-level holding breakdown available for this item.")
        with detail_tabs[1]:
            if result.ordering_breakdown:
                oc_df = pd.DataFrame([
                    {"Component": k.replace("_", " ").title(), "Value": v}
                    for k, v in result.ordering_breakdown.items()
                    if k != "source"
                ])
                st.dataframe(oc_df, hide_index=True, use_container_width=True)
            else:
                st.info(
                    "No component-level ordering breakdown available for this item.")
        if result.production_breakdown:
            with detail_tabs[2]:
                pc_df = pd.DataFrame([{"Component": k.replace("_", " ").title(
                ), "Value": v} for k, v in result.production_breakdown.items()])
                st.dataframe(pc_df, hide_index=True, use_container_width=True)


def render_sensitivity_section(cfg, result):
    section_header("Diagnostic lab", "Sensitivity analysis",
                   "Stress-test demand, cost, and unit economics to understand which assumptions drive financial exposure.")
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

    section_header("Impact range", "Tornado chart",
                   "Visualizes which parameters create the widest swing in annual cost.")
    st.plotly_chart(SensitivityVisualizer.plot_tornado_chart(
        tornado_data, result.total_cost, result.item_name), use_container_width=True)

    section_header("Response curves", "Sensitivity curves",
                   "See how EOQ and total cost respond as each assumption moves away from baseline.")
    st.plotly_chart(SensitivityVisualizer.plot_sensitivity_curves(
        ranked, result.item_name), use_container_width=True)

    if show_two_way:
        section_header("Interaction view", "Two-way sensitivity",
                       "Explore how pairs of assumptions interact across the EOQ and total-cost surface.")
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
    section_header("Savings roadmap", "Optimization opportunities",
                   "Prioritized recommendations with implementation guidance and overlap-aware savings estimates.")
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

    section_header("Opportunity map", "Savings versus difficulty",
                   "Bubble position shows estimated impact; bubble size reflects implementation difficulty.")
    st.plotly_chart(SensitivityVisualizer.plot_optimization_summary(
        suggestions, result.item_name), use_container_width=True)

    section_header("Action detail", "Recommendation cards",
                   "Filter and inspect each opportunity before exporting the roadmap.")
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

    section_header("Scenario desk", "What-if scenarios",
                   "Compare targeted initiatives against the current baseline.")
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
    section_header("Report studio", "Executive PDF export",
                   "Generate a polished PDF packet with all model outputs, charts, recommendations, and appendices.")
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
    section_header("Portfolio dashboard", "Executive results",
                   "Scan optimal quantities, annual cost, replenishment cadence, and risk buffers across the modeled inventory portfolio.")
    summary_df = build_summary_df(results)
    total_cost = summary_df["Total Annual Cost"].sum()
    avg_cycle = summary_df["Cycle Time (days)"].mean()
    highest = summary_df.sort_values(
        "Total Annual Cost", ascending=False).iloc[0]

    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        metric_card("Portfolio annual cost",
                    f"${total_cost:,.0f}", f"{len(results)} item(s) modeled")
    with col_b:
        metric_card("Average cycle",
                    f"{avg_cycle:,.0f}d", "mean replenishment rhythm")
    with col_c:
        metric_card("Highest cost item", str(
            highest["Item Name"]), f"${highest['Total Annual Cost']:,.0f} annual cost")
    with col_d:
        metric_card(
            "Models active", f"{summary_df['Model'].nunique()}", "EOQ variants represented")

    for cfg, result in results:
        render_basic_result(cfg, result)

    section_header("Portfolio comparison", "Cost and replenishment summary",
                   "A compact cross-item view for comparing annual cost, order frequency, cycle time, and control points.")
    st.dataframe(summary_df, hide_index=True, use_container_width=True)

    chart_tab, cost_tab = st.tabs(["Annual cost", "Cost drivers"])
    with chart_tab:
        fig = px.bar(summary_df, x="Item Name", y="Total Annual Cost",
                     color="Model", barmode="group", title="Total Annual Cost Comparison")
        fig.update_layout(margin=dict(l=20, r=20, t=60, b=20),
                          legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)
    with cost_tab:
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(name="Holding ($/unit/year)",
                       x=summary_df["Item Name"], y=summary_df["Holding Cost/Unit/Yr"]))
        fig2.add_trace(go.Bar(name="Ordering ($/order)",
                       x=summary_df["Item Name"], y=summary_df["Ordering Cost/Order"]))
        fig2.update_layout(barmode="group", title="Holding vs Ordering Cost Comparison", margin=dict(
            l=20, r=20, t=60, b=20))
        st.plotly_chart(fig2, use_container_width=True)

    st.download_button("⬇️ Download Results CSV", summary_df.to_csv(
        index=False).encode("utf-8"), "eoq_results.csv", "text/csv")

    section_header("Deep dive", "Item diagnostics",
                   "Use the tabs below to inspect sensitivity, scenario behavior, and savings roadmaps for each item.")
    result_tabs = st.tabs([f"{r.item_name}" for _, r in results])
    for tab, (cfg, result) in zip(result_tabs, results):
        with tab:
            analysis_tabs = st.tabs(["Sensitivity lab", "Savings roadmap"])
            with analysis_tabs[0]:
                render_sensitivity_section(cfg, result)
            with analysis_tabs[1]:
                render_optimization_section(cfg, result)

    render_pdf_download(results, summary_df)


# ─────────────────────────────────────────────────────────────────────────────
# Main app
# ─────────────────────────────────────────────────────────────────────────────

inject_design_system()
hero()

with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">
      <h2>Inventory Studio</h2>
      <p>Configure models, run diagnostics, and export decision-ready reports.</p>
    </div>
    <div class="workflow-step"><b>1</b> · Select portfolio size</div>
    <div class="workflow-step"><b>2</b> · Configure demand + costs</div>
    <div class="workflow-step"><b>3</b> · Run EOQ analysis</div>
    """, unsafe_allow_html=True)
    num_items = st.slider("Portfolio items", 1, 8, 2)

all_items_config = []
tabs = st.tabs([f"Item {i + 1}" for i in range(num_items)])

for i, tab in enumerate(tabs):
    with tab:
        section_header(
            "Configuration", f"Item {i + 1}", "Define item identity, demand behavior, service targets, and cost architecture.")
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
        section_header("Model setup", "Cost model",
                       "Complete the cost inputs for the selected model type.")
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

section_header("Run", "Launch analysis",
               "Calculate enhanced EOQ outputs and unlock diagnostics, savings recommendations, and PDF export.")
if st.button("Run EOQ Analysis", type="primary"):
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
        st.success(
            f"Analysis completed for {len(results)} item(s). Scroll down for the executive dashboard.")

if "eoq_results" in st.session_state:
    render_full_results(st.session_state["eoq_results"])
