# reports/report_sections.py

import datetime

import pandas as pd

from analysis.cost_optimizer import summarize_portfolio_savings, summarize_suggestions
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.tableofcontents import TableOfContents

from .report_styles import ReportColors as RC, ReportStyles


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


class ReportSections:
    def __init__(self):
        self.S = ReportStyles.get_styles()

    def spacer(self, h=0.12):
        return Spacer(1, h * inch)

    def divider(self):
        return HRFlowable(width="100%", thickness=1.2, color=RC.DIVIDER, spaceBefore=4, spaceAfter=6)

    def h1(self, text, counter=None):
        if counter is not None:
            counter[0] += 1
            text = f"{counter[0]}. {text}"
        return [self.divider(), Paragraph(text, self.S["H1"])]

    def h2(self, text):
        return [Paragraph(text, self.S["H2"])]

    def body(self, text):
        return Paragraph(text, self.S["Body"])

    def callout(self, text, style="InfoBox"):
        return [Paragraph(text, self.S[style]), self.spacer(0.05)]

    def bullet_list(self, items):
        return [Paragraph(f"• &nbsp; {item}", self.S["Body"]) for item in items] + [self.spacer(0.05)]

    def kpi_row(self, metrics):
        # ReportLab tables cannot have zero cells. Keep the helper safe for
        # conditional sections that may occasionally have no metrics.
        if not metrics:
            metrics = [("No metrics", "—", None)]
        n = len(metrics)
        col_w = 6.5 / n
        table = Table(
            [[Paragraph(label, self.S["KPILabel"]) for label, _, _ in metrics],
             [Paragraph(str(value), self.S["KPIValue"])
              for _, value, _ in metrics],
             [Paragraph(delta or "", self.S["KPIDelta"]) for _, _, delta in metrics]],
            colWidths=[col_w * inch] * n,
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), RC.LIGHT_BLUE),
            ("BACKGROUND", (0, 1), (-1, 1), RC.WHITE),
            ("BOX", (0, 0), (-1, -1), 0.5, RC.SECONDARY),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, RC.MID_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        return table

    def styled_table(self, headers, rows, col_widths=None):
        data = [[Paragraph(h, self.S["TableHeader"]) for h in headers]]
        for row in rows:
            data.append([cell if hasattr(cell, "wrap") else Paragraph(
                str(cell), self.S["TableCell"]) for cell in row])
        if col_widths is None:
            col_widths = [6.5 / len(headers) * inch] * len(headers)
        table = Table(data, colWidths=col_widths, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), RC.TABLE_HEADER),
            ("TEXTCOLOR", (0, 0), (-1, 0), RC.WHITE),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.3, RC.MID_GRAY),
            ("BOX", (0, 0), (-1, -1), 0.8, RC.PRIMARY),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        for i in range(1, len(rows) + 1):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), RC.TABLE_ROW_ALT))
        table.setStyle(TableStyle(style))
        return table

    def saving_cell(self, value, is_positive=True):
        color = "green" if is_positive else "red"
        prefix = "+" if is_positive else ""
        return Paragraph(f"<font color='{color}'><b>{prefix}${value:,.2f}</b></font>", self.S["TableCellRight"])

    def cover_page(self, meta):
        elements = [self.spacer(2.0)]
        elements += [
            Paragraph("INVENTORY MANAGEMENT", self.S["CoverTitle"]),
            Paragraph("EOQ Analysis &amp; Optimization Report",
                      self.S["CoverTitle"]),
            self.spacer(0.3),
            HRFlowable(width="60%", thickness=2, color=RC.ACCENT,
                       spaceAfter=20, spaceBefore=10),
            Paragraph(
                f"Prepared for: <b>{meta.get('company', '—')}</b>", self.S["CoverMeta"]),
            Paragraph(f"Analyst: {meta.get('analyst', '—')}",
                      self.S["CoverMeta"]),
            Paragraph(
                f"Report Date: {datetime.date.today().strftime('%B %d, %Y')}", self.S["CoverMeta"]),
            Paragraph(
                f"Items Analysed: {meta.get('num_items', 0)}", self.S["CoverMeta"]),
            self.spacer(0.5),
            Paragraph("EXECUTIVE SUMMARY", self.S["CoverSubtitle"]),
            self.kpi_row([
                ("Total Annual Cost",
                 f"${meta.get('total_cost', 0):,.0f}", None),
                ("Conservative Savings",
                 f"${meta.get('total_savings', 0):,.0f}", f"{meta.get('savings_pct', 0):.1f}%"),
                ("Recommendations", str(meta.get('num_recommendations', 0)), None),
            ]),
            PageBreak(),
        ]
        return elements

    def table_of_contents(self, sections=None):
        """Real PDF table of contents populated by ReportLab multiBuild.

        The old implementation hard-coded the page column to an em dash.
        This flowable receives page numbers from EOQDocTemplate.afterFlowable
        during the multi-pass build.
        """
        toc = TableOfContents()
        toc.levelStyles = [self.S["TableCell"]]
        return [Paragraph("Table of Contents", self.S["H1"]), self.spacer(), toc, PageBreak()]

    def executive_summary(self, all_results, all_suggestions, meta, counter):
        elements = self.h1("Executive Summary", counter)
        total_cost = sum(r.total_cost for _, r in all_results)
        savings_summary = summarize_portfolio_savings(
            all_suggestions, total_cost)
        elements += [
            self.body(
                f"This report analyses <b>{len(all_results)} inventory items</b> using the enhanced EOQ model contract across all calculations. It includes cost breakdowns, sensitivity analysis, and optimization recommendations."),
            self.spacer(),
            self.kpi_row([
                ("Items Analysed", str(len(all_results)), None),
                ("Total Annual Cost", f"${total_cost:,.0f}", None),
                ("Conservative Savings", f"${savings_summary['conservative_total']:,.0f}",
                 f"{savings_summary['saving_pct_conservative']:.1f}%" if total_cost else None),
                ("Recommendations", str(sum(len(s)
                 for s in all_suggestions)), None),
            ]),
            self.spacer(),
        ]
        elements += self.h2("Key Findings")
        elements += self.bullet_list([
            f"<b>{r.item_name}</b>: EOQ <b>{r.eoq:,.0f}</b> units, annual cost <b>${r.total_cost:,.2f}</b>, order frequency {r.order_frequency:.1f}/year."
            for _, r in all_results
        ])
        high = [
            s for suggs in all_suggestions for s in suggs if s.priority == "High"][:6]
        if high:
            elements += self.h2("Top Priority Recommendations")
            rows = [[s.priority, s.title, s.category, self.saving_cell(
                s.estimated_saving), s.timeframe] for s in high]
            elements.append(self.styled_table(["Priority", "Recommendation", "Category", "Saving", "Timeframe"], rows, [
                            0.7*inch, 2.5*inch, 1.0*inch, 1.1*inch, 1.2*inch]))
        elements.append(PageBreak())
        return elements

    def item_analysis(self, cfg, result, sens, suggestions, scenarios_df, charts, counter):
        elements = self.h1(
            f"Item Analysis: {result.item_name} ({result.item_id})", counter)
        elements += self.h2("Item Overview")
        elements.append(self.kpi_row([
            ("Annual Demand", f"{cfg.get('demand', 0):,.0f}", None),
            ("Unit Cost", f"${result.unit_cost:.2f}", None),
            ("Holding Cost/Unit/Yr",
             f"${result.holding_cost_per_unit:.4f}", None),
            ("Order/Setup Cost",
             f"${result.ordering_cost_per_order:.2f}", None),
        ]))
        elements += [self.spacer(), *self.h2("EOQ Results")]
        elements.append(self.kpi_row([
            ("EOQ", f"{result.eoq:,.0f} units", None),
            ("Total Annual Cost", f"${result.total_cost:,.2f}", None),
            ("Orders per Year", f"{result.order_frequency:.1f}", None),
            ("Cycle Time", f"{result.cycle_time:.0f} days", None),
        ]))
        extra = []
        if result.reorder_point is not None:
            extra.append(
                ("Reorder Point", f"{result.reorder_point:,.0f} units", None))
        if result.safety_stock is not None:
            extra.append(
                ("Safety Stock", f"{result.safety_stock:,.0f} units", None))
        if result.max_inventory is not None:
            extra.append(
                ("Max Inventory", f"{result.max_inventory:,.0f} units", None))
        extra.append(("Model", result.model_type, None))
        elements += [self.spacer(0.08), self.kpi_row(extra), self.spacer()]

        cb = result.cost_breakdown or {}
        rows = [[k.replace("_", " ").title(), f"${v:,.2f}"] for k, v in cb.items(
        ) if k in ANNUAL_COST_KEYS and isinstance(v, (int, float)) and v > 0]
        if rows:
            elements += self.h2("Cost Breakdown")
            elements.append(self.styled_table(
                ["Component", "Amount"], rows, [4.2*inch, 2.3*inch]))
            elements.append(self.spacer())

        if "cost_curve" in charts and "inv_cycle" in charts:
            elements += self.h2("Visual Analysis")
            chart_table = Table([[charts["cost_curve"], charts["inv_cycle"]]], colWidths=[
                                3.3*inch, 3.3*inch])
            chart_table.setStyle(TableStyle(
                [("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            elements += [chart_table, Paragraph(
                "EOQ cost curve and inventory cycle", self.S["Caption"]), self.spacer()]
        if "cost_pie" in charts:
            elements += [charts["cost_pie"], Paragraph(
                "Annual cost component distribution", self.S["Caption"]), self.spacer()]

        ranked = sens.get("ranked_parameters", []) if sens else []
        if ranked:
            elements += self.h2("Sensitivity Analysis")
            elements += self.callout(
                f"Most cost-sensitive parameter: <b>{ranked[0].parameter}</b> (cost ε = {ranked[0].cost_elasticity:.3f}).")
            rows = [[r.sensitivity_rank, r.parameter, f"{r.base_value:,.4f}", f"{r.elasticity:+.4f}",
                     f"{r.cost_elasticity:+.4f}", f"{r.critical_range[0]:,.2f} – {r.critical_range[1]:,.2f}"] for r in ranked]
            elements.append(self.styled_table(["Rank", "Parameter", "Base", "EOQ ε", "Cost ε", "EOQ Safe Range"], rows, [
                            0.4*inch, 1.6*inch, 0.9*inch, 0.8*inch, 0.8*inch, 2.0*inch]))
            elements.append(self.spacer())
        if "tornado" in charts:
            elements += [charts["tornado"], Paragraph(
                "Parameter impact range on total cost", self.S["Caption"]), self.spacer()]
        if "sens_curves" in charts:
            elements += [charts["sens_curves"], Paragraph(
                "Sensitivity curves for top parameters", self.S["Caption"]), self.spacer()]

        if scenarios_df is not None and len(scenarios_df) > 0:
            elements += self.h2("What-If Scenario Analysis")
            rows = [[row["Scenario"], f"${row['Total Annual Cost']:,.2f}", f"${row['Saving vs Baseline']:,.2f}",
                     f"{row['Saving %']:.2f}%"] for _, row in scenarios_df.iterrows()]
            elements.append(self.styled_table(["Scenario", "Annual Cost", "Saving", "Saving %"], rows, [
                            3.0*inch, 1.2*inch, 1.2*inch, 1.1*inch]))
            if "scenarios" in charts:
                elements += [self.spacer(0.08), charts["scenarios"],
                             Paragraph("Scenario cost comparison", self.S["Caption"])]
            elements.append(self.spacer())

        elements += self.h2("Optimization Recommendations")
        if suggestions:
            savings_summary = summarize_suggestions(
                suggestions, result.total_cost)
            elements += self.callout(
                f"<b>{len(suggestions)} recommendations</b> identified. "
                f"Conservative non-overlapping planning saving: <b>${savings_summary['conservative_total']:,.2f}</b>/year. "
                f"Gross identified savings, not additive: <b>${savings_summary['gross_identified_saving']:,.2f}</b>/year.",
                "SuccessBox",
            )
            rows = [[s.priority, s.category, s.title,
                     f"${s.estimated_saving:,.2f}", s.difficulty, s.timeframe] for s in suggestions[:10]]
            elements.append(self.styled_table(["Priority", "Category", "Recommendation", "Saving", "Difficulty", "Timeframe"], rows, [
                            0.6*inch, 0.8*inch, 2.2*inch, 0.9*inch, 0.8*inch, 1.2*inch]))
        else:
            elements += self.callout(
                "No specific optimization opportunities were identified beyond maintaining current EOQ parameters.")
        elements.append(PageBreak())
        return elements

    def multi_item_summary(self, all_results, summary_df, multi_chart, counter):
        elements = self.h1("Multi-Item Portfolio Summary", counter)
        rows = [[row["Item Name"], row["Model"], f"{row['EOQ']:,.0f}", f"${row['Total Annual Cost']:,.2f}", f"{row['Orders/Year']:.1f}", f"{row['Cycle Time (days)']:.0f}", "—" if pd.isna(
            row["ROP"]) else f"{row['ROP']:,.0f}", "—" if pd.isna(row["Safety Stock"]) else f"{row['Safety Stock']:,.0f}"] for _, row in summary_df.sort_values("Total Annual Cost", ascending=False).iterrows()]
        elements.append(self.styled_table(["Item", "Model", "EOQ", "Annual Cost", "Orders/Yr", "Cycle", "ROP",
                        "Safety Stock"], rows, [1.1*inch, 1.2*inch, 0.6*inch, 0.9*inch, 0.7*inch, 0.7*inch, 0.6*inch, 0.8*inch]))
        if multi_chart:
            elements += [self.spacer(), multi_chart,
                         Paragraph("Multi-item EOQ and cost comparison", self.S["Caption"])]
        elements.append(PageBreak())
        return elements

    def action_plan(self, all_suggestions, all_results, counter):
        elements = self.h1("Consolidated Action Plan", counter)
        flat = [(s, r.item_name) for suggs, (_, r) in zip(
            all_suggestions, all_results) for s in suggs]
        flat.sort(key=lambda x: ({"High": 0, "Medium": 1, "Low": 2}.get(
            x[0].priority, 3), -x[0].estimated_saving))
        savings_summary = summarize_portfolio_savings(
            all_suggestions, sum(r.total_cost for _, r in all_results))
        elements += self.callout(
            f"<b>Conservative non-overlapping planning saving: ${savings_summary['conservative_total']:,.2f}/year</b> "
            f"across {len(flat)} recommendations. Gross identified savings, not additive: "
            f"${savings_summary['gross_identified_saving']:,.2f}/year.",
            "SuccessBox",
        )
        if flat:
            rows = [[s.priority, item, s.title, s.category,
                     f"${s.estimated_saving:,.2f}", s.timeframe] for s, item in flat]
            elements.append(self.styled_table(["Priority", "Item", "Action", "Category", "Saving", "Timeframe"], rows, [
                            0.6*inch, 1.0*inch, 2.2*inch, 0.9*inch, 0.9*inch, 0.9*inch]))
        elements.append(PageBreak())
        return elements

    def appendix(self, counter):
        elements = self.h1("Appendix: EOQ Model Reference", counter)
        rows = [
            ("Classic EOQ", "Q* = sqrt(2DS/H)",
             "D=demand, S=order cost, H=holding cost"),
            ("POQ", "Q* = sqrt(2DS / (H(1-D/P)))", "P=annual production rate"),
            ("Stochastic EOQ", "ROP = dL + zσLT",
             "Safety stock accounts for demand and lead-time variation"),
            ("Quantity Discount", "Evaluate feasible EOQ and price-break candidates",
             "Choose minimum total cost"),
            ("Deterioration", "Effective H = H + θC", "θ=deterioration rate"),
        ]
        elements.append(self.styled_table(
            ["Model", "Formula", "Notes"], rows, [1.5*inch, 2.4*inch, 2.6*inch]))
        elements += self.h2("Glossary")
        glossary = [("EOQ", "Economic Order Quantity"), ("ROP", "Reorder Point"), ("Safety Stock",
                                                                                   "Buffer inventory for uncertainty"), ("Cost Elasticity", "% change in total cost for a 1% parameter change")]
        elements.append(self.styled_table(
            ["Term", "Definition"], glossary, [1.2*inch, 5.3*inch]))
        return elements
