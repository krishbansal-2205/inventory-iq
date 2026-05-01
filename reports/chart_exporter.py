# reports/chart_exporter.py

import io
import os
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from reportlab.lib.units import inch
from reportlab.platypus import Image as RLImage


ChartSpec = Tuple[str, go.Figure, float, float]


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


class ChartExporter:
    """
    Converts Plotly figures to ReportLab-compatible images.

    Performance note:
    - Single-chart export is kept for compatibility.
    - Multi-chart PDF generation should use figs_to_images(), which batches
      exports with plotly.io.write_images when available. That avoids repeatedly
      starting/tearing down Kaleido work for every chart.
    - DPI and scale are intentionally kept high; speed comes from batching and
      disabled validation, not from lowering resolution or skipping charts.
    """

    def __init__(self, dpi: int = 150, default_width: float = 6.5, default_height: float = 3.5, scale: int = 2):
        self.dpi = dpi
        self.default_width = default_width
        self.default_height = default_height
        self.scale = scale

    def _px(self, inches_value: float) -> int:
        return int(round(inches_value * self.dpi))

    @staticmethod
    def _is_exportable(fig: go.Figure) -> bool:
        return fig is not None and hasattr(fig, "data") and len(fig.data) > 0

    @staticmethod
    def _image_from_bytes(img_bytes: bytes, width_in: float, height_in: float) -> RLImage:
        return RLImage(io.BytesIO(img_bytes), width=width_in * inch, height=height_in * inch)

    def fig_to_image(self, fig: go.Figure, width_in: float = None, height_in: float = None) -> RLImage:
        """Convert one Plotly figure to a ReportLab image. Used as fallback."""
        if not self._is_exportable(fig):
            raise ValueError("Cannot export an empty Plotly figure.")

        import plotly.io as pio

        w = width_in or self.default_width
        h = height_in or self.default_height
        img_bytes = pio.to_image(
            fig,
            format="png",
            width=self._px(w),
            height=self._px(h),
            scale=self.scale,
            validate=False,
        )
        return self._image_from_bytes(img_bytes, w, h)

    def figs_to_images(self, specs: Iterable[ChartSpec]) -> Dict[str, RLImage]:
        """
        Batch-export many Plotly figures to ReportLab images.

        specs: iterable of (key, figure, width_in, height_in)

        Returns a dict of key -> ReportLab Image. Empty figures or failed exports
        are skipped, so report generation continues even if one chart fails.
        """
        prepared: List[Tuple[str, go.Figure, float, float, int, int]] = []
        for key, fig, width_in, height_in in specs:
            if self._is_exportable(fig):
                w = width_in or self.default_width
                h = height_in or self.default_height
                prepared.append((key, fig, w, h, self._px(w), self._px(h)))

        if not prepared:
            return {}

        # Group by pixel dimensions because plotly.io.write_images accepts a
        # shared width/height for each batch on many Plotly versions.
        groups = defaultdict(list)
        for item in prepared:
            groups[(item[4], item[5])].append(item)

        images: Dict[str, RLImage] = {}

        try:
            import plotly.io as pio
        except Exception:
            pio = None

        with tempfile.TemporaryDirectory(prefix="eoq_pdf_charts_") as tmpdir:
            for (width_px, height_px), group_items in groups.items():
                paths = [
                    Path(tmpdir) / f"chart_{i}_{item[0]}.png" for i, item in enumerate(group_items)]
                figs = [item[1] for item in group_items]

                batch_ok = False
                if pio is not None and hasattr(pio, "write_images") and len(figs) > 1:
                    try:
                        pio.write_images(
                            figs,
                            paths,
                            format="png",
                            width=width_px,
                            height=height_px,
                            scale=self.scale,
                            validate=False,
                        )
                        batch_ok = True
                    except Exception:
                        batch_ok = False

                if not batch_ok:
                    # Compatibility fallback: still avoids validation overhead and
                    # keeps the same DPI/scale/resolution.
                    for item, path in zip(group_items, paths):
                        try:
                            img_bytes = pio.to_image(
                                item[1],
                                format="png",
                                width=width_px,
                                height=height_px,
                                scale=self.scale,
                                validate=False,
                            )
                            path.write_bytes(img_bytes)
                        except Exception:
                            continue

                for item, path in zip(group_items, paths):
                    if path.exists() and path.stat().st_size > 0:
                        try:
                            images[item[0]] = self._image_from_bytes(
                                path.read_bytes(), item[2], item[3])
                        except Exception:
                            continue

        return images

    @staticmethod
    def _is_poq_model(model_type=None, production_rate=None):
        return bool(production_rate) or "Production Order Quantity" in str(model_type or "") or str(model_type or "").lower() == "poq"

    @staticmethod
    def _is_stochastic_model(model_type=None):
        return "Stochastic" in str(model_type or "") or str(model_type or "").lower() == "stochastic"

    @staticmethod
    def _stochastic_terms(D, demand_std=0, lead_time_days=0, lead_time_std=0, service_level=0.95):
        if not 0 < float(service_level) < 1:
            return 0.0, 0.0
        from scipy import stats
        daily_demand = D / 365
        sigma_lt = np.sqrt(float(lead_time_days or 0) * float(demand_std or 0)
                           ** 2 + daily_demand ** 2 * float(lead_time_std or 0) ** 2)
        z = stats.norm.ppf(float(service_level))
        safety_stock = z * sigma_lt
        expected_stockout = sigma_lt * \
            (stats.norm.pdf(z) - z * (1 - stats.norm.cdf(z)))
        return float(safety_stock), float(expected_stockout)

    def cost_curve_chart(self, D, S, H, C, eoq, item_name, model_type=None,
                         production_rate=None, safety_stock=0,
                         demand_std=0, lead_time_days=0, lead_time_std=0,
                         service_level=0.95, stockout_cost=0) -> go.Figure:
        """Model-aware cost curve.

        Classic:      (D/Q)S + (Q/2)H + DC
        POQ:          (D/Q)S + (Q(1-D/P)/2)H + DC
        Stochastic:   classic cycle cost + safety-stock holding + expected stockout cost
        """
        if D <= 0 or S <= 0 or H <= 0 or eoq <= 0:
            return go.Figure()

        is_poq = self._is_poq_model(model_type, production_rate)
        is_stochastic = self._is_stochastic_model(model_type)
        q_star = float(eoq)
        if is_poq:
            P_for_q = float(production_rate or 0)
            if P_for_q <= D:
                return go.Figure()
            q_star = float(np.sqrt((2 * D * S) / (H * (1 - D / P_for_q))))
        elif is_stochastic:
            _, expected_stockout_for_q = self._stochastic_terms(
                D, demand_std, lead_time_days, lead_time_std, service_level
            )
            q_star = float(np.sqrt(
                (2 * D * (S + expected_stockout_for_q * float(stockout_cost or 0))) / H))

        if q_star <= 0 or not np.isfinite(q_star):
            return go.Figure()

        Q = np.linspace(max(1, q_star * 0.1), q_star * 3, 400)
        ordering = (D / Q) * S

        if is_poq:
            P = float(production_rate or 0)
            if P <= D:
                return go.Figure()
            production_factor = 1 - D / P
            max_inventory = Q * production_factor
            holding = (max_inventory / 2) * H
            relevant = ordering + holding
            total = relevant + D * C
            holding_name = "POQ Holding Cost"
        elif is_stochastic:
            ss, expected_stockout = self._stochastic_terms(
                D, demand_std, lead_time_days, lead_time_std, service_level)
            if safety_stock is not None:
                ss = float(safety_stock or ss)
            cycle_holding = (Q / 2) * H
            safety_holding = ss * H
            stockout = (D / Q) * expected_stockout * float(stockout_cost or 0)
            holding = cycle_holding + safety_holding
            relevant = ordering + holding + stockout
            total = relevant + D * C
            holding_name = "Cycle + Safety Holding"
        else:
            holding = (Q / 2) * H
            relevant = ordering + holding
            total = relevant + D * C
            holding_name = "Holding Cost"

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=Q, y=total, name="Total Cost"))
        fig.add_trace(go.Scatter(x=Q, y=relevant,
                      name="Relevant Cost", line=dict(dash="solid")))
        fig.add_trace(go.Scatter(x=Q, y=ordering,
                      name="Ordering/Setup Cost", line=dict(dash="dash")))
        fig.add_trace(go.Scatter(x=Q, y=holding,
                      name=holding_name, line=dict(dash="dot")))
        if is_stochastic and float(stockout_cost or 0) > 0:
            fig.add_trace(go.Scatter(
                x=Q, y=stockout, name="Expected Stockout Cost", line=dict(dash="dashdot")))
        fig.add_vline(x=q_star, line_dash="dot",
                      annotation_text=f"Q*={q_star:.0f}", annotation_position="top right")
        fig.update_layout(title=f"Cost Curves - {item_name}", xaxis_title="Order Quantity",
                          yaxis_title="Annual Cost ($)", template="plotly_white", margin=dict(l=40, r=20, t=40, b=40))
        return fig

    def inventory_cycle_chart(self, eoq, D, lead_time_days, safety_stock, rop, item_name,
                              model_type=None, production_rate=None, max_inventory=None) -> go.Figure:
        """Model-aware inventory cycle chart.

        For POQ, inventory ramps up during production at P-D and then depletes at D.
        For classic/stochastic purchased items, replenishment is instantaneous.
        """
        if D <= 0 or eoq <= 0:
            return go.Figure()
        daily_d = D / 365
        cycle = eoq / daily_d
        t = np.linspace(0, cycle * 3, 800)
        base = float(safety_stock or 0)

        if self._is_poq_model(model_type, production_rate):
            P = float(production_rate or 0)
            if P <= D:
                return go.Figure()
            daily_p = P / 365
            prod_days = eoq / daily_p
            peak = float(
                max_inventory) if max_inventory is not None else eoq * (1 - D / P)
            inv = []
            for ti in t:
                pos = ti % cycle
                if pos <= prod_days:
                    level = (daily_p - daily_d) * pos
                else:
                    level = peak - daily_d * (pos - prod_days)
                inv.append(base + max(0, level))
        else:
            inv = [base + max(0, eoq - daily_d * (ti % cycle)) for ti in t]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=t, y=inv, fill="tozeroy", name="Inventory Level"))
        for i in range(4):
            fig.add_vline(x=i * cycle, line_dash="dash", line_width=1)
        if rop is not None:
            fig.add_hline(y=rop, line_dash="dot",
                          annotation_text=f"ROP={rop:.0f}")
        if safety_stock is not None and safety_stock > 0:
            fig.add_hline(y=safety_stock, line_dash="dot",
                          annotation_text=f"SS={safety_stock:.0f}")
        fig.update_layout(title=f"Inventory Cycle - {item_name}", xaxis_title="Time (days)",
                          yaxis_title="Units", template="plotly_white", margin=dict(l=40, r=60, t=40, b=40))
        return fig

    def cost_breakdown_pie(self, cost_breakdown: dict, item_name: str) -> go.Figure:
        labels, values = [], []
        for k, v in (cost_breakdown or {}).items():
            if k in ANNUAL_COST_KEYS and isinstance(v, (int, float)) and v > 0:
                labels.append(k.replace("_", " ").title())
                values.append(v)
        if not values:
            return go.Figure()
        fig = go.Figure(go.Pie(labels=labels, values=values,
                        hole=0.45, textinfo="percent+label"))
        fig.update_layout(title=f"Cost Breakdown - {item_name}", template="plotly_white", margin=dict(
            l=10, r=10, t=40, b=10), showlegend=False)
        return fig

    def tornado_chart(self, tornado_data, base_cost: float, item_name: str) -> go.Figure:
        if tornado_data is None or len(tornado_data) == 0:
            return go.Figure()
        df = tornado_data.sort_values("Range", ascending=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Low", y=df["Parameter"], x=df["Low Cost"] - base_cost, orientation="h"))
        fig.add_trace(go.Bar(
            name="High", y=df["Parameter"], x=df["High Cost"] - base_cost, orientation="h"))
        fig.add_vline(x=0, line_color="black", line_width=1.5)
        fig.update_layout(title=f"Tornado Chart - {item_name}", barmode="overlay",
                          xaxis_title="Delta Total Cost vs Baseline ($)", template="plotly_white", margin=dict(l=120, r=20, t=40, b=40))
        return fig

    def scenario_bar_chart(self, scenarios_df, item_name: str) -> go.Figure:
        if scenarios_df is None or len(scenarios_df) == 0:
            return go.Figure()
        fig = go.Figure(go.Bar(x=scenarios_df["Scenario"], y=scenarios_df["Total Annual Cost"], text=[
                        f"${v:,.0f}" for v in scenarios_df["Total Annual Cost"]], textposition="outside"))
        fig.update_layout(title=f"What-If Scenarios - {item_name}", yaxis_title="Total Annual Cost ($)",
                          xaxis_tickangle=30, template="plotly_white", margin=dict(l=40, r=20, t=40, b=100))
        return fig

    def multi_item_comparison(self, summary_df) -> go.Figure:
        fig = make_subplots(rows=1, cols=2, subplot_titles=[
                            "EOQ by Item", "Annual Cost by Item"])
        fig.add_trace(go.Bar(
            x=summary_df["Item Name"], y=summary_df["EOQ"], name="EOQ"), row=1, col=1)
        fig.add_trace(go.Bar(
            x=summary_df["Item Name"], y=summary_df["Total Annual Cost"], name="Cost"), row=1, col=2)
        fig.update_layout(title="Multi-Item Comparison", template="plotly_white",
                          showlegend=False, margin=dict(l=40, r=20, t=50, b=60))
        fig.update_xaxes(tickangle=30)
        return fig

    def sensitivity_curves(self, ranked_results, item_name: str) -> go.Figure:
        top = ranked_results[:3]
        if not top:
            return go.Figure()
        fig = make_subplots(rows=1, cols=len(top), subplot_titles=[
                            r.parameter for r in top])
        for idx, r in enumerate(top, 1):
            x_pct = [(v - r.base_value) / r.base_value *
                     100 if r.base_value else 0 for v in r.variations]
            fig.add_trace(go.Scatter(x=x_pct, y=r.cost_values,
                          name=r.parameter, showlegend=False), row=1, col=idx)
            fig.add_vline(x=0, line_dash="dash", line_width=1, row=1, col=idx)
        fig.update_layout(title=f"Sensitivity Curves (Top 3) - {item_name}",
                          template="plotly_white", height=300, margin=dict(l=40, r=20, t=50, b=40))
        fig.update_xaxes(title_text="% Change")
        fig.update_yaxes(title_text="Total Cost ($)", col=1)
        return fig
