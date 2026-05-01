# reports/report_styles.py

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet


class ReportColors:
    PRIMARY = HexColor("#1a3a5c")
    SECONDARY = HexColor("#2980b9")
    ACCENT = HexColor("#27ae60")
    WARNING = HexColor("#f39c12")
    DANGER = HexColor("#e74c3c")
    LIGHT_BLUE = HexColor("#d6eaf8")
    LIGHT_GREEN = HexColor("#d5f5e3")
    LIGHT_ORANGE = HexColor("#fdebd0")
    LIGHT_RED = HexColor("#fadbd8")
    LIGHT_GRAY = HexColor("#f2f3f4")
    MID_GRAY = HexColor("#aab7b8")
    DARK_GRAY = HexColor("#566573")
    WHITE = HexColor("#ffffff")
    BLACK = HexColor("#000000")
    TABLE_HEADER = HexColor("#1a3a5c")
    TABLE_ROW_ALT = HexColor("#eaf4fc")
    DIVIDER = HexColor("#2980b9")


class ReportStyles:
    @staticmethod
    def get_styles():
        base = getSampleStyleSheet()
        RC = ReportColors
        custom = {
            "CoverTitle": ParagraphStyle("CoverTitle", fontName="Helvetica-Bold", fontSize=28, textColor=RC.WHITE, alignment=TA_CENTER, spaceAfter=12, leading=34),
            "CoverSubtitle": ParagraphStyle("CoverSubtitle", fontName="Helvetica", fontSize=16, textColor=RC.LIGHT_BLUE, alignment=TA_CENTER, spaceAfter=8, leading=20),
            "CoverMeta": ParagraphStyle("CoverMeta", fontName="Helvetica", fontSize=11, textColor=RC.WHITE, alignment=TA_CENTER, spaceAfter=6),
            "H1": ParagraphStyle("H1", fontName="Helvetica-Bold", fontSize=18, textColor=RC.PRIMARY, spaceBefore=16, spaceAfter=8, leading=22),
            "H2": ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=13, textColor=RC.SECONDARY, spaceBefore=10, spaceAfter=5, leading=16),
            "H3": ParagraphStyle("H3", fontName="Helvetica-Bold", fontSize=10, textColor=RC.DARK_GRAY, spaceBefore=8, spaceAfter=3, leading=12),
            "Body": ParagraphStyle("Body", fontName="Helvetica", fontSize=9, textColor=RC.BLACK, spaceAfter=4, leading=13, alignment=TA_JUSTIFY),
            "BodySmall": ParagraphStyle("BodySmall", fontName="Helvetica", fontSize=8, textColor=RC.DARK_GRAY, spaceAfter=2, leading=10),
            "Bold": ParagraphStyle("Bold", fontName="Helvetica-Bold", fontSize=9, textColor=RC.BLACK, spaceAfter=4, leading=13),
            "InfoBox": ParagraphStyle("InfoBox", fontName="Helvetica", fontSize=9, textColor=RC.PRIMARY, backColor=RC.LIGHT_BLUE, borderPad=7, spaceAfter=6, leading=13),
            "SuccessBox": ParagraphStyle("SuccessBox", fontName="Helvetica", fontSize=9, textColor=HexColor("#1a5c2a"), backColor=RC.LIGHT_GREEN, borderPad=7, spaceAfter=6, leading=13),
            "TableHeader": ParagraphStyle("TableHeader", fontName="Helvetica-Bold", fontSize=8, textColor=RC.WHITE, alignment=TA_CENTER, leading=10),
            "TableCell": ParagraphStyle("TableCell", fontName="Helvetica", fontSize=8, textColor=RC.BLACK, alignment=TA_LEFT, leading=10),
            "TableCellRight": ParagraphStyle("TableCellRight", fontName="Helvetica", fontSize=8, textColor=RC.BLACK, alignment=TA_RIGHT, leading=10),
            "Caption": ParagraphStyle("Caption", fontName="Helvetica-Oblique", fontSize=8, textColor=RC.DARK_GRAY, alignment=TA_CENTER, spaceAfter=6, leading=10),
            "KPILabel": ParagraphStyle("KPILabel", fontName="Helvetica", fontSize=8, textColor=RC.DARK_GRAY, alignment=TA_CENTER, leading=10),
            "KPIValue": ParagraphStyle("KPIValue", fontName="Helvetica-Bold", fontSize=13, textColor=RC.PRIMARY, alignment=TA_CENTER, leading=16),
            "KPIDelta": ParagraphStyle("KPIDelta", fontName="Helvetica-Bold", fontSize=8, textColor=RC.ACCENT, alignment=TA_CENTER, leading=10),
        }
        return {**base.byName, **custom}
