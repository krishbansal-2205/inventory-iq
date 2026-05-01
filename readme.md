<div align="center">

<br/>



### **Inventory IQ**
*A professional-grade, multi-model EOQ optimization platform with sensitivity analysis, cost intelligence, and automated PDF reporting.*

<br/>

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.10%2B-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![NumPy](https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white)](https://numpy.org)
[![SciPy](https://img.shields.io/badge/SciPy-8CAAE6?style=for-the-badge&logo=scipy&logoColor=white)](https://scipy.org)
[![Plotly](https://img.shields.io/badge/Plotly-3F4F75?style=for-the-badge&logo=plotly&logoColor=white)](https://plotly.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-gold?style=for-the-badge)](LICENSE)


</div>

---

##  Table of Contents

- [Overview](#-overview)
- [Why This Project](#-why-this-project)
- [Feature Showcase](#-feature-showcase)
- [Technical Architecture](#-technical-architecture)
- [The Math Behind It](#-the-math-behind-it)
- [Model Portfolio](#-model-portfolio)
- [Cost Intelligence Engine](#-cost-intelligence-engine)
- [Sensitivity Analysis Framework](#-sensitivity-analysis-framework)
- [Optimization Engine](#-optimization-engine)
- [Executive PDF Reports](#-executive-pdf-reports)
- [Project Structure](#-project-structure)
- [Quick Start](#-quick-start)
- [Configuration Guide](#-configuration-guide)
- [Design System](#-design-system)
- [Tech Stack Deep Dive](#-tech-stack-deep-dive)
- [Roadmap](#-roadmap)

---

##  Overview

**InventoryIQ** is a full-stack inventory optimization platform built entirely in Python. It implements and extends the classical Economic Order Quantity (EOQ) family of models with a production-grade software architecture — modular, testable, and extensible.

The platform allows supply chain analysts and operations teams to:

- Model purchased, manufactured, and stochastic inventory items simultaneously
- Decompose holding and ordering costs down to individual financial drivers
- Run one-way, two-way, and component-level sensitivity diagnostics
- Generate prioritized, overlap-aware cost-reduction recommendations
- Export polished, multi-section PDF reports for executive stakeholders

The entire application is powered by a single-page Streamlit interface with a custom dark-theme design system built from scratch — no UI templates, no component libraries.

---

##  Why This Project

Inventory optimization is a $1.1 trillion problem for global supply chains. Yet most practitioners still use Excel spreadsheets that:

- Treat holding and ordering costs as single magic numbers
- Ignore demand uncertainty and lead-time variability
- Provide no sensitivity analysis or "what if" capability
- Cannot handle mixed portfolios of manufactured and purchased items

InventoryIQ was built to close that gap. Every design decision — from the cost decomposition architecture to the overlap-aware savings estimator — was made to reflect how inventory decisions are actually made in practice, not just in textbooks.

---

##  Feature Showcase

###  Multi-Model Portfolio Analysis
Run **Classic EOQ**, **Production Order Quantity (POQ)**, and **Stochastic EOQ** models simultaneously across up to 8 SKUs in a single session. Each model uses a unified result contract (`EnhancedEOQResult`) so all downstream analytics — sensitivity, optimization, PDF — work identically regardless of model type.

###  Granular Cost Decomposition
Instead of asking "what is your holding cost?", InventoryIQ builds it from first principles:

| Holding Cost Component | Ordering Cost Component | Production Cost Component |
|------------------------|-------------------------|---------------------------|
| Capital cost rate      | Admin / processing      | Raw material              |
| Storage rate ($/m²)    | Fixed freight           | Labor (rate × hours)      |
| Insurance rate         | Variable freight        | Machine (rate × hours)    |
| Obsolescence rate      | Receiving cost          | Energy cost               |
| Spoilage / damage rate | Inspection cost         | Overhead rate             |
| Handling cost          | Communication cost      | Quality / inspection      |
| Utility cost           | Custom cost             | Scrap / defect rate       |

This decomposition is not cosmetic — it directly feeds the sensitivity analysis, which can isolate the impact of, say, raising warehouse insurance rates by 2%.

###  Sensitivity Analysis Engine
Four analysis modes, each mathematically consistent with the underlying model:

- **One-way analysis** — Sweep each parameter ±50% and observe EOQ and total-cost response curves
- **Tornado chart** — Rank parameters by their symmetric cost-impact range
- **Elasticity scoring** — Compute EOQ elasticity *and* cost elasticity for each parameter
- **Two-way heatmap** — Explore interaction effects between any two parameters simultaneously

###  Overlap-Aware Savings Optimizer
The optimizer generates actionable suggestions across three categories (Holding Cost, Ordering Cost, Strategic) and solves a real problem in savings reporting: **double-counting**. Suggestions that target the same underlying cost driver are grouped, and only the maximum saving within each group is counted toward the conservative planning estimate.

###  Automated Executive PDF Reports
One-click PDF generation using ReportLab, complete with:
- Cover page with executive KPI summary
- Auto-populated table of contents (real page numbers via multi-pass build)
- Per-item cost curves, inventory cycle charts, tornado charts, and scenario comparisons
- Consolidated action plan sorted by priority and saving potential
- EOQ model reference appendix and glossary

---

##  Technical Architecture

InventoryIQ is organized into six decoupled layers, each with a single responsibility:

```
┌─────────────────────────────────────────────────────────────────┐
│                        app.py  (Streamlit UI)                   │
│         Custom design system · Session state · Chart theming    │
└────────────────────────────────┬────────────────────────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│     models/     │   │    analysis/    │   │    reports/     │
│                 │   │                 │   │                 │
│  EnhancedEOQ    │   │  Sensitivity    │   │  PDF Generator  │
│  EnhancedPOQ    │   │  Analyzer       │   │  Chart Exporter │
│  StochasticEOQ  │   │  CostOptimizer  │   │  Report Styles  │
│  BackorderEOQ   │   │  Sensitivity    │   │  Report         │
│  DeteriorationEQ│   │  Visualizer     │   │  Sections       │
│  QuantityDisct  │   └─────────────────┘   └─────────────────┘
└────────┬────────┘
         │
         ▼
┌─────────────────┐   ┌─────────────────┐
│     costs/      │   │   optimizer/    │
│                 │   │                 │
│  HoldingCost    │   │  MultiItem      │
│  Components     │   │  Optimizer      │
│  OrderingCost   │   │  (SLSQP)        │
│  Components     │   └─────────────────┘
│  ProductionCost │
│  Components     │
└─────────────────┘
```

### Key Architectural Decisions

**1. Unified Result Contract**
Every model — Classic EOQ, POQ, Stochastic, Backorder, Deterioration, Quantity Discount — returns an `EnhancedEOQResult` dataclass. This means the sensitivity analyzer, cost optimizer, PDF generator, and Streamlit renderer are completely model-agnostic. Adding a new model requires zero changes to any downstream component.

**2. Cost Component Separation**
`OrderingCostComponents` explicitly separates *fixed-per-order* costs (which belong in the EOQ formula as *S*) from *variable-per-unit* costs (freight, inspection). Folding per-unit costs into *S* is a common modeling error that inflates EOQ — InventoryIQ prevents it by design.

**3. Stochastic Safety Stock Consistency**
The safety stock formula, the expected stockout penalty, and the EOQ formula are computed from the same `sigma_lt` variable in every context: `EnhancedStochasticEOQ`, `SensitivityAnalyzer`, `CostOptimizer`, and `MultiItemOptimizer`. There is no risk of the UI and the optimizer disagreeing on what the reorder point is.

**4. Batched Chart Export**
The PDF generator does not call `pio.to_image()` once per chart. It groups all figures by pixel dimensions and uses `pio.write_images()` for batch export, reducing Kaleido process startup overhead significantly on large portfolios.

---

##  The Math Behind It

### Classic EOQ

The Economic Order Quantity minimizes the sum of annual ordering cost and annual holding cost:

$$TC(Q) = \frac{D}{Q} \cdot S + \frac{Q}{2} \cdot H + D \cdot C$$

$$Q^* = \sqrt{\frac{2DS}{H}}$$

Where:
- $D$ = Annual demand (units/year)
- $S$ = Fixed ordering / setup cost ($/order)
- $H$ = Holding cost ($/unit/year)
- $C$ = Unit purchase cost ($/unit)

### Production Order Quantity (POQ)

When inventory is produced internally at rate $P > D$, the maximum inventory is reduced by the consumption during the production run:

$$Q^*_{POQ} = \sqrt{\frac{2DS}{H\left(1 - \frac{D}{P}\right)}}$$

$$I_{max} = Q^* \left(1 - \frac{D}{P}\right)$$

### Stochastic EOQ with Safety Stock

Under normally distributed demand and variable lead time, the safety stock required to achieve a target service level $\alpha$ is:

$$\sigma_{LT} = \sqrt{L \cdot \sigma_d^2 + d^2 \cdot \sigma_L^2}$$

$$SS = z_\alpha \cdot \sigma_{LT}$$

$$ROP = \bar{d} \cdot L + SS$$

The expected stockout units per cycle (using the unit normal loss function):

$$E[S] = \sigma_{LT}\left[\phi(z) - z\left(1 - \Phi(z)\right)\right]$$

The EOQ formula is adjusted to account for the stockout penalty as an effective per-cycle setup cost:

$$Q^*_{stoch} = \sqrt{\frac{2D(S + E[S] \cdot B)}{H}}$$

Where $B$ is the stockout penalty per unit and $\phi$, $\Phi$ are the standard normal PDF and CDF.

### Sensitivity Elasticity

Parameter elasticity is computed numerically using a centered finite difference around the base value:

$$\varepsilon_{EOQ,\theta} = \frac{\Delta EOQ / EOQ_0}{\Delta \theta / \theta_0} \approx \frac{EOQ(\theta^+) - EOQ(\theta^-)}{EOQ_0} \cdot \frac{\theta_0}{\theta^+ - \theta^-}$$

Analytically, for the classic EOQ:
- $\varepsilon_{EOQ,D} = +0.5$ (always)
- $\varepsilon_{EOQ,S} = +0.5$ (always)
- $\varepsilon_{EOQ,H} = -0.5$ (always)
- $\varepsilon_{TC,D} \approx +1.0$ for large $D$ (purchase cost dominates)

---

##  Model Portfolio

| Model | Class | Use Case | Key Parameters |
|---|---|---|---|
| **Classic EOQ** | `EnhancedClassicEOQ` | Purchased items, deterministic demand | D, S, H, C, lead time |
| **Production Order Qty** | `EnhancedPOQ` | Manufactured items, finite production rate | D, P, S, H, C |
| **Stochastic EOQ** | `EnhancedStochasticEOQ` | Variable demand / lead time, service-level targets | D, σ_d, L, σ_L, z_α, B |
| **EOQ with Backorders** | `BackorderEOQ` | Planned shortage allowed, back-order cost known | D, S, H, B, C |
| **Deterioration EOQ** | `DeteriorationEOQ` | Perishable / expiring goods | D, S, H, θ, C |
| **Quantity Discount EOQ** | `QuantityDiscountEOQ` | All-units tiered supplier pricing | D, S, I, price breaks |

All six models return `EnhancedEOQResult` and are plug-and-play with the rest of the system.

---

##  Cost Intelligence Engine

### HoldingCostComponents

```python
from costs.cost_structure import HoldingCostComponents

hc = HoldingCostComponents(
    capital_cost_rate=0.12,        # 12% cost of capital
    storage_rate_per_sqm=60.0,     # $/m²/year warehouse rent
    unit_storage_area=0.08,        # m² per unit
    insurance_rate=0.015,          # 1.5% of unit value
    obsolescence_rate=0.03,        # 3% annual write-off risk
    spoilage_rate=0.005,           # 0.5% damage/waste
    handling_cost_per_unit=0.75,   # $/unit/year labor
)

breakdown = hc.calculate(unit_cost=25.00)
# Returns: capital_cost, storage_cost, insurance_cost,
#          obsolescence_cost, spoilage_cost, handling_cost,
#          total_holding_cost — all in $/unit/year
```

### OrderingCostComponents

```python
from costs.cost_structure import OrderingCostComponents

oc = OrderingCostComponents(
    admin_cost=85.0,           # Purchase order processing
    freight_fixed=55.0,        # Fixed freight per shipment
    freight_per_unit=0.0,      # Variable freight — NOT folded into S
    receiving_cost=25.0,       # Dock labor per order
    communication_cost=12.0,   # EDI / email / phone per order
)

# fixed_cost_per_order() → the S used in the EOQ formula
# variable_cost_per_unit() → added to landed unit cost, not S
```

---

##  Sensitivity Analysis Framework

The `SensitivityAnalyzer` class is model-aware. When analyzing a stochastic item, it correctly re-computes safety stock and expected stockout at each parameter value. When analyzing a POQ item, it uses the finite-production average inventory formula.

```python
from analysis.sensitivity import SensitivityAnalyzer

analyzer = SensitivityAnalyzer(item_config, eoq_result)

# One-way analysis for any of the four core parameters
demand_result    = analyzer.analyze_demand(pct_range=50)
ordering_result  = analyzer.analyze_ordering_cost(pct_range=50)
holding_result   = analyzer.analyze_holding_cost(pct_range=50)
unit_cost_result = analyzer.analyze_unit_cost(pct_range=50)

# Component-level analysis (requires detailed cost input mode)
holding_components = analyzer.analyze_holding_components()
# → {'capital_cost': SensitivityResult, 'storage_cost': ..., ...}

# Two-way interaction heatmap
two_way = analyzer.two_way_sensitivity('demand', 'holding_cost', steps=25)
# → {'eoq_matrix': np.ndarray(25x25), 'cost_matrix': np.ndarray(25x25)}

# Full ranked analysis with tornado data
full = analyzer.run_full_analysis(pct_range=50)
# → {ranked_parameters, holding_components, ordering_components, tornado_data}
```

Each `SensitivityResult` carries:
- `elasticity` — EOQ elasticity at base point
- `cost_elasticity` — Cost elasticity at base point
- `critical_range` — Parameter range where EOQ stays within ±10% of optimal
- `sensitivity_rank` — 1-4 ranking by cost-elasticity magnitude

---

##  Optimization Engine

### Per-Item Recommendations

`CostOptimizer` generates `OptimizationSuggestion` objects with full implementation detail:

```python
from analysis.cost_optimizer import CostOptimizer

optimizer = CostOptimizer(item_config, eoq_result)
suggestions = optimizer.generate_all_suggestions()

for s in suggestions:
    print(f"[{s.priority}] {s.title}")
    print(f"  Save ${s.estimated_saving:,.2f} ({s.saving_pct:.1f}%)")
    print(f"  Difficulty: {s.difficulty} | Timeframe: {s.timeframe}")
    print(f"  Steps: {' → '.join(s.implementation)}")
```

**Suggestion categories:**

| Category | Example Triggers | Typical Actions |
|---|---|---|
| Holding Cost | Capital cost > 40% of H; storage > 25% of H | VMI, consignment, warehouse slotting |
| Ordering Cost | Admin > 30% of S; freight > 25% of S | EDI automation, carrier contracts, blanket POs |
| Strategic | Current qty differs from EOQ by >15%; high annual spend | EOQ alignment, A-class protocol, qty discount negotiation |

### Overlap-Aware Savings Aggregation

A critical feature: suggestions targeting the same underlying driver are grouped before reporting conservative savings.

```python
from analysis.cost_optimizer import summarize_suggestions

summary = summarize_suggestions(suggestions, base_cost=total_cost)
# Returns:
# {
#   "conservative_total": 4820.00,   ← max per overlap group, non-additive
#   "gross_identified_saving": 7340.00,  ← raw sum, for reference only
#   "saving_pct_conservative": 8.3,
#   "num_overlap_groups": 4,
#   "overlap_note": "Conservative total uses the largest saving..."
# }
```

### Multi-Item Constrained Optimization

The `MultiItemOptimizer` uses **SciPy SLSQP** to minimize total portfolio cost under real-world constraints:

```python
from optimizer.multi_item_optimizer import MultiItemOptimizer

optimizer = MultiItemOptimizer(items)  # list of item dicts

# Unconstrained benchmark
baseline = optimizer.unconstrained_eoq()

# Constrain maximum cash tied up in a single order cycle
result = optimizer.order_value_constrained_optimize(max_order_value=50_000)

# Constrain total warehouse footprint
result = optimizer.storage_constrained_optimize(max_space=1200)  # m²

# Both simultaneously
result = optimizer.dual_constrained_optimize(
    max_order_value=50_000, max_space=1200
)
```

The optimizer is model-aware: POQ items compute peak inventory as $Q(1 - D/P)$, stochastic items add safety stock to their footprint, and all cost functions are the same as those used in `EnhancedStochasticEOQ` and `EnhancedPOQ`.

---

##  Executive PDF Reports

Generated with **ReportLab** using a custom multi-pass build (`EOQDocTemplate` extends `SimpleDocTemplate`) that populates a real table of contents with live page numbers.

**Report structure:**

```
Cover Page
├── Company / analyst metadata
├── Executive KPI summary table
└── Confidentiality footer

Table of Contents  (auto-populated, real page numbers)

1. Executive Summary
   ├── Portfolio KPI row
   ├── Key findings per item
   └── Top 6 high-priority recommendations

2–N. Item Analysis (one section per SKU)
   ├── Item overview + model parameters
   ├── EOQ results KPI row
   ├── Cost breakdown table
   ├── Cost curve chart + Inventory cycle chart (side-by-side)
   ├── Cost composition pie chart
   ├── Sensitivity ranking table
   ├── Tornado chart + Sensitivity curves
   ├── What-if scenario table + bar chart
   └── Optimization recommendations table

N+1. Multi-Item Portfolio Summary
   └── Cross-item comparison table + grouped bar chart

N+2. Consolidated Action Plan
   └── All suggestions sorted by priority × saving, with conservative total

Appendix: EOQ Model Reference
   ├── Formula reference table
   └── Glossary
```

Charts are batch-exported at 150 DPI × 2x scale using `plotly.io.write_images()` grouped by pixel dimensions, avoiding repeated Kaleido process restarts.

---

##  Project Structure

```
inventoryiq/
│
├── app.py                          # Streamlit UI — design system, routing, render helpers
├── main.py                         # CLI entry point — demo run with three sample SKUs
├── requirements.txt
│
├── models/                         # EOQ model implementations
│   ├── enhanced_classic_eoq.py     # EnhancedClassicEOQ, EnhancedPOQ, EnhancedStochasticEOQ
│   ├── backorder_eoq.py            # Planned backorder model
│   ├── deterioration_eoq.py        # Perishable/deteriorating items
│   ├── quantity_discount.py        # All-units tiered discount EOQ
│   ├── classic_eoq.py              # Backwards-compat wrapper → EnhancedClassicEOQ
│   ├── poq_model.py                # Backwards-compat wrapper → EnhancedPOQ
│   └── stochastic_eoq.py           # Backwards-compat wrapper → EnhancedStochasticEOQ
│
├── costs/
│   └── cost_structure.py           # HoldingCostComponents, OrderingCostComponents,
│                                   # ProductionCostComponents — full decomposition
│
├── analysis/
│   ├── sensitivity.py              # SensitivityAnalyzer — 1-way, 2-way, component-level
│   ├── cost_optimizer.py           # CostOptimizer, summarize_suggestions,
│   │                               # summarize_portfolio_savings
│   └── visualizations.py          # SensitivityVisualizer — Plotly chart builders
│
├── optimizer/
│   └── multi_item_optimizer.py     # MultiItemOptimizer — SLSQP constrained optimization
│
├── reports/
│   ├── pdf_generator.py            # EOQPDFGenerator — orchestrates full report build
│   ├── chart_exporter.py           # ChartExporter — batched Plotly→PNG→ReportLab
│   ├── report_sections.py          # ReportSections — all flowable builders
│   └── report_styles.py            # ReportColors, ReportStyles — design tokens
│
└── visualization/
    └── dashboard.py                # EOQDashboard — legacy Matplotlib charts (CLI use)
```

---

##  Quick Start

### Prerequisites

- Python 3.9 or higher
- pip

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/inventoryiq.git
cd inventoryiq

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

### Run the Streamlit app

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`.

### Run the CLI demo

```bash
python main.py
```

This runs a three-item portfolio (Classic EOQ, POQ, Stochastic) with sample data and prints the results table to the terminal.

### Minimal programmatic usage

```python
from models.enhanced_classic_eoq import EnhancedClassicEOQ
from costs.cost_structure import HoldingCostComponents, OrderingCostComponents

# Build cost components
hc = HoldingCostComponents(capital_cost_rate=0.10, insurance_rate=0.01)
oc = OrderingCostComponents(admin_cost=80, freight_fixed=50, receiving_cost=20)

# Create and calculate the model
model = EnhancedClassicEOQ(
    item_id="SKU001",
    item_name="Steel Bolts",
    demand=5000,
    unit_cost=5.00,
    lead_time_days=7,
    holding_components=hc,
    ordering_components=oc,
)

result = model.calculate()

print(f"EOQ:              {result.eoq:,.0f} units")
print(f"Total Annual Cost: ${result.total_cost:,.2f}")
print(f"Orders / Year:    {result.order_frequency:.1f}")
print(f"Reorder Point:    {result.reorder_point:.0f} units")
```

---

##  Configuration Guide

### Item types

| Type string | Class used | Required config keys |
|---|---|---|
| `"classic"` | `EnhancedClassicEOQ` | `demand`, `unit_cost`, `lead_time` |
| `"poq"` | `EnhancedPOQ` | `demand`, `production_rate`, `lead_time` |
| `"stochastic"` | `EnhancedStochasticEOQ` | `demand`, `demand_std`, `lead_time`, `service_level` |

### Cost input modes

Each cost type supports two input modes:

| Mode | Keys used | When to use |
|---|---|---|
| Simple | `hc_override` (float) | Quick analysis, benchmarking |
| Component-based | `hc_components` (object) | Full cost decomposition, sensitivity to components |

When `hc_override` is set, component-based analysis is skipped and the override value is used directly as $H$. When `hc_components` is set, the total holding cost is computed from the breakdown and will update dynamically when unit cost changes (e.g., during unit-cost sensitivity analysis).

### Stochastic parameters

```python
{
    "type": "stochastic",
    "demand": 3000,           # Annual demand (units/year)
    "demand_std": 10,         # Daily demand standard deviation
    "lead_time": 14,          # Mean lead time (days)
    "lead_time_std": 2,       # Lead time standard deviation (days)
    "service_level": 0.98,    # Cycle service level (0 < SL < 1)
    "stockout_cost": 50,      # Penalty per unit short ($/unit)
    "unit_cost": 25,
}
```

---

##  Tech Stack Deep Dive

| Layer | Library | Version | Role |
|---|---|---|---|
| UI Framework | Streamlit | ≥1.10 | Application shell, session state, widgets |
| Numerical Core | NumPy | ≥1.21 | Array math, EOQ formulas, sensitivity grids |
| Scientific Computing | SciPy | ≥1.7 | Normal distribution (safety stock), SLSQP optimizer |
| Data Wrangling | Pandas | ≥1.3 | Summary tables, scenario DataFrames, CSV export |
| Interactive Charts | Plotly | ≥5.0 | Sensitivity curves, tornado, heatmaps, scenarios |
| PDF Generation | ReportLab | ≥4.0 | Full report layout, table of contents, styles |
| Chart Export | Kaleido | ≥0.2.1 | Plotly → PNG for PDF embedding |
| Image Processing | Pillow | ≥9.0 | Image handling in report pipeline |

### Why these choices?

**Streamlit over Dash/Flask** — Streamlit's session state model and widget binding allow a reactive, multi-step configuration UI with minimal boilerplate. The tradeoff (less layout control) is addressed by the custom CSS override layer.

**ReportLab over WeasyPrint/pdfkit** — ReportLab gives pixel-perfect control over every element in the PDF, supports multi-pass builds for live TOC generation, and has no external binary dependencies (no wkhtmltopdf, no headless Chrome).

**SciPy SLSQP over cvxpy/PuLP** — The constrained portfolio problem has smooth, twice-differentiable objective and constraint functions. SLSQP converges in milliseconds for 8-item portfolios and requires no solver installation.

---


##  Sample Output

Running `python main.py` with the default demo data produces:

```
============================================================
MULTI-ITEM EOQ INVENTORY MANAGEMENT SYSTEM
============================================================

Steel Bolts (SKU001) — Classic EOQ
  EOQ: 547.72 units
  Total Annual Cost: $26,118.03
  Orders/Year: 9.13
  Cycle Time: 40.00 days
  Reorder Point: 95.89 units

Plastic Casing (SKU002) — Production Order Quantity (POQ)
  EOQ: 1,095.45 units
  Total Annual Cost: $99,109.05
  Orders/Year: 10.96
  Cycle Time: 33.32 days
  Reorder Point: 65.75 units

Chemical Solution (SKU003) — Stochastic EOQ
  EOQ: 273.86 units
  Total Annual Cost: $79,041.73
  Orders/Year: 10.95
  Cycle Time: 33.33 days
  Reorder Point: 286.48 units
  Safety Stock: 261.80 units
```

---

<br/>

*EOQ formula first published by Ford W. Harris, 1913. Still relevant, still optimizing.*

</div>