# reports/pdf_generator.py

import datetime
import io

import pandas as pd

from analysis.cost_optimizer import summarize_portfolio_savings
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate

from .chart_exporter import ChartExporter
from .report_sections import ReportSections
from .report_styles import ReportColors as RC, ReportStyles


class EOQDocTemplate(SimpleDocTemplate):
    """SimpleDocTemplate with real table-of-contents notifications."""

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and getattr(flowable.style, "name", "") == "H1":
            text = flowable.getPlainText()
            if text and text != "Table of Contents":
                self.notify("TOCEntry", (0, text, self.page))


class ReportPageTemplate:
    def __init__(self, report_title: str, company: str):
        self.report_title = report_title
        self.company = company
        self.styles = ReportStyles.get_styles()

    def on_first_page(self, canvas_obj, doc):
        canvas_obj.saveState()
        w, h = doc.pagesize
        canvas_obj.setFillColor(RC.PRIMARY)
        canvas_obj.rect(0, 0, w, h, fill=1, stroke=0)
        canvas_obj.setFillColor(RC.ACCENT)
        canvas_obj.rect(0, h * 0.08, w, 6, fill=1, stroke=0)
        canvas_obj.setFillColor(RC.SECONDARY)
        canvas_obj.rect(0, 0, w, h * 0.07, fill=1, stroke=0)
        canvas_obj.setFillColor(RC.WHITE)
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.drawCentredString(
            w / 2, 20, f"CONFIDENTIAL - {self.company} - {datetime.date.today().year}")
        canvas_obj.restoreState()

    def on_later_pages(self, canvas_obj, doc):
        canvas_obj.saveState()
        w, h = doc.pagesize
        canvas_obj.setFillColor(RC.PRIMARY)
        canvas_obj.rect(0, h - 0.55 * inch, w, 0.55 * inch, fill=1, stroke=0)
        canvas_obj.setFillColor(RC.WHITE)
        canvas_obj.setFont("Helvetica-Bold", 9)
        canvas_obj.drawString(0.4 * inch, h - 0.35 * inch, self.report_title)
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.drawRightString(
            w - 0.4 * inch, h - 0.35 * inch, self.company)
        canvas_obj.setStrokeColor(RC.ACCENT)
        canvas_obj.setLineWidth(2)
        canvas_obj.line(0, h - 0.55 * inch, w, h - 0.55 * inch)
        canvas_obj.setStrokeColor(RC.MID_GRAY)
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(0.4 * inch, 0.45 * inch, w - 0.4 * inch, 0.45 * inch)
        canvas_obj.setFillColor(RC.MID_GRAY)
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.drawString(
            0.4 * inch, 0.28 * inch, f"Generated {datetime.date.today().strftime('%d %B %Y')}")
        canvas_obj.drawRightString(
            w - 0.4 * inch, 0.28 * inch, f"Page {doc.page}")
        canvas_obj.restoreState()


class EOQPDFGenerator:
    def __init__(self, page_size=A4, report_title="EOQ Inventory Analysis Report", company="Your Company", analyst="Inventory Team", include_charts: bool = True):
        self.page_size = page_size
        self.report_title = report_title
        self.company = company
        self.analyst = analyst
        self.include_charts = include_charts
        self.sections = ReportSections()
        # Print-quality export. Speed is improved by batching all chart exports,
        # not by reducing DPI, scale, or number of charts.
        self.exporter = ChartExporter(dpi=150, scale=2)
        self.page_template = ReportPageTemplate(report_title, company)

    def _item_chart_specs(self, item_index, cfg, result, sensitivity_analysis, scenarios_df):
        """Build Plotly figure specs for one item without exporting them yet."""
        exp = self.exporter
        D = cfg.get("demand", result.order_frequency * result.eoq)
        S = result.ordering_cost_per_order
        H = result.holding_cost_per_unit
        C = result.unit_cost
        prefix = f"item{item_index}"
        local_keys = {}
        specs = []

        def add(local_key, fig, width_in, height_in):
            global_key = f"{prefix}_{local_key}"
            local_keys[local_key] = global_key
            specs.append((global_key, fig, width_in, height_in))

        try:
            add("cost_curve", exp.cost_curve_chart(
                D, S, H, C, result.eoq, result.item_name,
                model_type=result.model_type,
                production_rate=cfg.get("production_rate"),
                safety_stock=result.safety_stock or 0,
                demand_std=cfg.get("demand_std", 0),
                lead_time_days=cfg.get("lead_time", 0),
                lead_time_std=cfg.get("lead_time_std", 0),
                service_level=cfg.get("service_level", 0.95),
                stockout_cost=cfg.get("stockout_cost", 0),
            ), 3.2, 2.8)
        except Exception:
            pass
        try:
            add("inv_cycle", exp.inventory_cycle_chart(
                result.eoq, D, cfg.get(
                    "lead_time", 0), result.safety_stock or 0,
                result.reorder_point, result.item_name,
                model_type=result.model_type,
                production_rate=cfg.get("production_rate"),
                max_inventory=result.max_inventory,
            ), 3.2, 2.8)
        except Exception:
            pass
        try:
            add("cost_pie", exp.cost_breakdown_pie(
                result.cost_breakdown or {}, result.item_name), 5.0, 2.8)
        except Exception:
            pass
        try:
            td = (sensitivity_analysis or {}).get("tornado_data")
            if td is not None and len(td) > 0:
                add("tornado", exp.tornado_chart(
                    td, result.total_cost, result.item_name), 6.5, 2.8)
        except Exception:
            pass
        try:
            ranked = (sensitivity_analysis or {}).get("ranked_parameters", [])
            if ranked:
                add("sens_curves", exp.sensitivity_curves(
                    ranked, result.item_name), 6.5, 2.5)
        except Exception:
            pass
        try:
            if scenarios_df is not None and len(scenarios_df) > 0:
                add("scenarios", exp.scenario_bar_chart(
                    scenarios_df, result.item_name), 6.5, 2.8)
        except Exception:
            pass

        return specs, local_keys

    def _build_all_chart_images(self, all_results, all_sensitivity, all_scenarios, summary_df):
        """Batch-export every report chart once, then map images back per item."""
        if not self.include_charts:
            return [{} for _ in all_results], None

        all_specs = []
        per_item_key_maps = []
        for idx, ((cfg, result), sens, scen_df) in enumerate(zip(all_results, all_sensitivity, all_scenarios)):
            specs, key_map = self._item_chart_specs(
                idx, cfg, result, sens, scen_df)
            all_specs.extend(specs)
            per_item_key_maps.append(key_map)

        multi_key = "portfolio_multi_item_comparison"
        try:
            all_specs.append(
                (multi_key, self.exporter.multi_item_comparison(summary_df), 6.5, 3.0))
        except Exception:
            pass

        exported = self.exporter.figs_to_images(all_specs)

        per_item_charts = []
        for key_map in per_item_key_maps:
            per_item_charts.append(
                {local: exported[global_key] for local, global_key in key_map.items() if global_key in exported})

        return per_item_charts, exported.get(multi_key)

    def generate(self, all_configs, all_results, all_sensitivity, all_suggestions, all_scenarios, summary_df: pd.DataFrame, output_path=None) -> bytes:
        if not all_results:
            raise ValueError("all_results cannot be empty.")
        if len(all_results) != len(all_sensitivity) or len(all_results) != len(all_suggestions) or len(all_results) != len(all_scenarios):
            raise ValueError(
                "Result, sensitivity, suggestion, and scenario lists must have the same length.")

        buf = io.BytesIO()
        doc = EOQDocTemplate(
            buf,
            pagesize=self.page_size,
            rightMargin=0.65 * inch,
            leftMargin=0.65 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.65 * inch,
            title=self.report_title,
            author=self.analyst,
            subject="EOQ Inventory Optimization",
            creator="Multi-Item EOQ System",
        )
        elements = []
        section_counter = [0]
        total_cost = sum(r.total_cost for _, r in all_results)
        savings_summary = summarize_portfolio_savings(
            all_suggestions, total_cost)
        meta = {
            "company": self.company,
            "analyst": self.analyst,
            "num_items": len(all_results),
            "total_cost": total_cost,
            "total_savings": savings_summary["conservative_total"],
            "gross_identified_saving": savings_summary["gross_identified_saving"],
            "savings_pct": savings_summary["saving_pct_conservative"],
            "gross_saving_pct": savings_summary["gross_saving_pct"],
            "num_recommendations": savings_summary["num_suggestions"],
            "savings_note": savings_summary["overlap_note"],
        }
        elements += self.sections.cover_page(meta)
        elements += self.sections.table_of_contents([
            "Executive Summary",
            *[f"Item Analysis: {r.item_name}" for _, r in all_results],
            "Multi-Item Portfolio Summary",
            "Consolidated Action Plan",
            "Appendix: EOQ Model Reference",
        ])
        elements += self.sections.executive_summary(
            all_results, all_suggestions, meta, section_counter)

        # Export all chart images in one batched pass before building flowables.
        # This keeps every chart at the original high resolution while avoiding
        # many repeated Kaleido calls.
        per_item_charts, multi_chart = self._build_all_chart_images(
            all_results, all_sensitivity, all_scenarios, summary_df
        )

        for idx, ((cfg, result), sens, suggs, scen_df) in enumerate(zip(all_results, all_sensitivity, all_suggestions, all_scenarios)):
            charts = per_item_charts[idx] if idx < len(per_item_charts) else {}
            elements += self.sections.item_analysis(
                cfg, result, sens, suggs, scen_df, charts, section_counter)

        elements += self.sections.multi_item_summary(
            all_results, summary_df, multi_chart, section_counter)
        elements += self.sections.action_plan(
            all_suggestions, all_results, section_counter)
        elements += self.sections.appendix(section_counter)
        doc.multiBuild(
            elements,
            onFirstPage=self.page_template.on_first_page,
            onLaterPages=self.page_template.on_later_pages,
        )
        pdf_bytes = buf.getvalue()
        buf.close()
        if output_path:
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)
        return pdf_bytes
