# analysis/visualizations.py

from typing import Dict

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class SensitivityVisualizer:
    @staticmethod
    def plot_sensitivity_curves(sensitivity_results: list, item_name: str) -> go.Figure:
        n = len(sensitivity_results)
        if n == 0:
            return go.Figure()
        subplot_titles = []
        for r in sensitivity_results:
            subplot_titles.extend([f"{r.parameter} → EOQ", f"{r.parameter} → Total Cost"])
        fig = make_subplots(rows=n, cols=2, subplot_titles=subplot_titles, vertical_spacing=0.08)
        for idx, r in enumerate(sensitivity_results, 1):
            x_pct = [(v - r.base_value) / r.base_value * 100 if r.base_value else 0 for v in r.variations]
            fig.add_trace(go.Scatter(x=x_pct, y=r.eoq_values, mode="lines", name=r.parameter, showlegend=False), row=idx, col=1)
            fig.add_trace(go.Scatter(x=[0], y=[r.base_eoq], mode="markers", name="Base", showlegend=False), row=idx, col=1)
            fig.add_hrect(y0=r.base_eoq * 0.9, y1=r.base_eoq * 1.1, fillcolor="green", opacity=0.08, line_width=0, row=idx, col=1)
            fig.add_trace(go.Scatter(x=x_pct, y=r.cost_values, mode="lines", showlegend=False), row=idx, col=2)
            fig.add_trace(go.Scatter(x=[0], y=[r.base_cost], mode="markers", showlegend=False), row=idx, col=2)
            axis_num = idx * 2 - 1
            # Plotly names the first subplot axes as "x"/"y", not "x1"/"y1".
            # Later axes are "x2", "x3", etc. Build valid domain refs for all rows.
            xref = "x domain" if axis_num == 1 else f"x{axis_num} domain"
            yref = "y domain" if axis_num == 1 else f"y{axis_num} domain"
            fig.add_annotation(
                x=0.02, y=0.95, xref=xref, yref=yref,
                text=f"EOQ ε={r.elasticity:.3f}<br>Cost ε={r.cost_elasticity:.3f}",
                showarrow=False, bgcolor="lightyellow", font=dict(size=10),
            )
        fig.update_layout(height=max(320, 280 * n), title=f"Sensitivity Analysis — {item_name}", template="plotly_white")
        for row in range(1, n + 1):
            fig.update_xaxes(title_text="% Change from Base", row=row, col=1)
            fig.update_xaxes(title_text="% Change from Base", row=row, col=2)
        return fig

    @staticmethod
    def plot_tornado_chart(tornado_data: pd.DataFrame, base_cost: float, item_name: str) -> go.Figure:
        if tornado_data is None or tornado_data.empty:
            return go.Figure()
        df = tornado_data.sort_values("Range", ascending=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Low", y=df["Parameter"], x=df["Low Cost"] - base_cost, orientation="h", opacity=0.8))
        fig.add_trace(go.Bar(name="High", y=df["Parameter"], x=df["High Cost"] - base_cost, orientation="h", opacity=0.8))
        fig.add_vline(x=0, line_width=2, line_color="black")
        for _, row in df.iterrows():
            fig.add_annotation(
                x=max(abs(row["Low Cost"] - base_cost), abs(row["High Cost"] - base_cost)),
                y=row["Parameter"], text=f"cost ε={row['Elasticity']:.3f}", showarrow=False, xanchor="left", font=dict(size=9),
            )
        fig.update_layout(
            title=f"Tornado Chart — Parameter Impact on Cost<br><sub>{item_name} | Base Cost: ${base_cost:,.2f}</sub>",
            barmode="overlay", xaxis_title="Change in Total Cost ($) vs Base", yaxis_title="Parameter",
            height=420, template="plotly_white", legend=dict(x=0.75, y=0.05),
        )
        return fig

    @staticmethod
    def plot_two_way_heatmap(two_way: Dict, item_name: str) -> go.Figure:
        fig = make_subplots(rows=1, cols=2, subplot_titles=["EOQ Heatmap", "Total Cost Heatmap"])
        p1 = two_way["param1"].replace("_", " ").title()
        p2 = two_way["param2"].replace("_", " ").title()
        x_labels = [f"{v:.1f}" for v in two_way["range2"]]
        y_labels = [f"{v:.1f}" for v in two_way["range1"]]
        fig.add_trace(go.Heatmap(z=two_way["eoq_matrix"], x=x_labels, y=y_labels, colorbar=dict(title="EOQ", x=0.46)), row=1, col=1)
        fig.add_trace(go.Heatmap(z=two_way["cost_matrix"], x=x_labels, y=y_labels, colorbar=dict(title="Cost ($)", x=1.02)), row=1, col=2)
        fig.update_layout(title=f"Two-Way Sensitivity: {p1} vs {p2} — {item_name}", height=520, template="plotly_white")
        fig.update_xaxes(title_text=p2, row=1, col=1)
        fig.update_xaxes(title_text=p2, row=1, col=2)
        fig.update_yaxes(title_text=p1, row=1, col=1)
        return fig

    @staticmethod
    def plot_component_sensitivity(component_results: Dict, component_type: str, item_name: str) -> go.Figure:
        if not component_results:
            return go.Figure()
        labels = [k.replace("_", " ").title() for k in component_results]
        values = [abs(v.cost_elasticity) for v in component_results.values()]
        fig = go.Figure(go.Scatterpolar(r=values + [values[0]], theta=labels + [labels[0]], fill="toself", name=component_type))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, title="Cost Elasticity |ε|")), title=f"{component_type} Component Sensitivity — {item_name}", height=450, template="plotly_white")
        return fig

    @staticmethod
    def plot_scenarios(scenarios_df: pd.DataFrame, item_name: str) -> go.Figure:
        if scenarios_df is None or scenarios_df.empty:
            return go.Figure()
        fig = make_subplots(rows=1, cols=2, subplot_titles=["Total Cost by Scenario", "Savings vs Baseline"])
        fig.add_trace(go.Bar(x=scenarios_df["Scenario"], y=scenarios_df["Total Annual Cost"], text=[f"${v:,.0f}" for v in scenarios_df["Total Annual Cost"]], textposition="outside", name="Total Cost"), row=1, col=1)
        fig.add_trace(go.Bar(x=scenarios_df["Scenario"], y=scenarios_df["Saving vs Baseline"], text=[f"${v:,.0f}" for v in scenarios_df["Saving vs Baseline"]], textposition="outside", name="Savings"), row=1, col=2)
        fig.update_layout(title=f"What-If Scenario Analysis — {item_name}", height=520, template="plotly_white", showlegend=False)
        fig.update_xaxes(tickangle=35)
        return fig

    @staticmethod
    def plot_optimization_summary(suggestions: list, item_name: str) -> go.Figure:
        if not suggestions:
            fig = go.Figure()
            fig.update_layout(title=f"No Optimization Opportunities Identified — {item_name}", template="plotly_white")
            return fig
        size_map = {"Easy": 18, "Medium": 28, "Hard": 38}
        fig = go.Figure()
        for s in suggestions:
            fig.add_trace(go.Scatter(
                x=[s.saving_pct], y=[s.estimated_saving], mode="markers+text",
                marker=dict(size=size_map.get(s.difficulty, 24), line=dict(width=1)),
                text=[s.title[:28] + ("..." if len(s.title) > 28 else "")], textposition="top center",
                name=s.title,
                hovertemplate=(f"<b>{s.title}</b><br>Priority: {s.priority}<br>Saving: ${s.estimated_saving:,.2f}<br>Saving %: {s.saving_pct:.1f}%<br>Difficulty: {s.difficulty}<br>Timeframe: {s.timeframe}<extra></extra>"),
            ))
        fig.update_layout(title=f"Optimization Opportunities — {item_name}<br><sub>Bubble size = implementation difficulty</sub>", xaxis_title="Saving (%)", yaxis_title="Annual Saving ($)", height=500, template="plotly_white", showlegend=False)
        return fig
