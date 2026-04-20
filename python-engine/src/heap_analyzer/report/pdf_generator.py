"""Professional PDF report generator using reportlab.

Produces a peritale-grade PDF with:
  - Cover page
  - Table of Contents
  - Site overview map
  - Per-heap detail sheets
  - Summary table
  - Charts (histogram + pie)
  - Processing parameters
  - Optional notes
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from heap_analyzer import __version__
from heap_analyzer.processing.volume import HeapMetrics
from heap_analyzer.report.charts import render_category_pie, render_volume_histogram
from heap_analyzer.report.formatting import fmt_date_it, fmt_datetime_it, fmt_it
from heap_analyzer.report.map_renderer import (
    HeapDetailMetrics,
    HeapRenderInfo,
    MapRenderer,
)
from heap_analyzer.report.palette import category_color
from heap_analyzer.utils.logging import get_stderr_logger

logger = get_stderr_logger(__name__)

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN_LEFT = 18 * mm
MARGIN_RIGHT = 18 * mm
MARGIN_TOP = 20 * mm
MARGIN_BOTTOM = 20 * mm
USABLE_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class ReportConfig(BaseModel):
    """Configuration for report generation."""

    site_name: str = "Sito"
    company_name: str | None = None
    logo_path: str | None = None  # PNG/JPEG path
    operator_name: str | None = None
    additional_notes: str | None = None
    only_confirmed_heaps: bool = False
    include_comparison: bool = False  # placeholder for F6.S04
    software_name: str = "Heap Analyzer"
    software_version: str = __version__


class ReportProgress(NamedTuple):
    """Progress update during report generation."""

    phase: str
    percent: float
    message: str


# ---------------------------------------------------------------------------
# Heap data wrapper
# ---------------------------------------------------------------------------


class HeapReportData(BaseModel):
    """Combined heap data for the report."""

    heap_id: int
    label: str | None = None
    polygon_geojson: dict | None = None  # type: ignore[type-arg]
    volume_m3: float = 0.0
    planimetric_area_m2: float = 0.0
    surface_area_m2: float = 0.0
    max_height_m: float = 0.0
    mean_height_m: float = 0.0
    base_elevation_m: float = 0.0
    centroid_e: float = 0.0
    centroid_n: float = 0.0
    material_category: str | None = None
    material_confidence: float | None = None
    classified_by: str | None = None
    is_manually_confirmed: bool = False
    notes: str | None = None


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------


def _build_styles() -> dict[str, ParagraphStyle]:
    """Build custom paragraph styles for the report."""
    base = getSampleStyleSheet()
    return {
        "title_cover": ParagraphStyle(
            "title_cover",
            parent=base["Title"],
            fontSize=36,
            leading=42,
            alignment=TA_CENTER,
            fontName="Times-Bold",
            spaceAfter=12,
        ),
        "subtitle_cover": ParagraphStyle(
            "subtitle_cover",
            parent=base["Title"],
            fontSize=18,
            leading=24,
            alignment=TA_CENTER,
            fontName="Times-Roman",
            spaceAfter=30,
        ),
        "meta_cover": ParagraphStyle(
            "meta_cover",
            parent=base["Normal"],
            fontSize=12,
            leading=18,
            alignment=TA_CENTER,
            fontName="Helvetica",
        ),
        "footer_cover": ParagraphStyle(
            "footer_cover",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            fontName="Helvetica-Oblique",
            textColor=colors.grey,
        ),
        "section_title": ParagraphStyle(
            "section_title",
            parent=base["Heading1"],
            fontSize=18,
            leading=22,
            fontName="Times-Bold",
            spaceBefore=6,
            spaceAfter=12,
        ),
        "heap_title": ParagraphStyle(
            "heap_title",
            parent=base["Heading2"],
            fontSize=16,
            leading=20,
            fontName="Times-Bold",
            spaceBefore=4,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontSize=11,
            leading=14,
            fontName="Helvetica",
        ),
        "body_small": ParagraphStyle(
            "body_small",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            fontName="Helvetica",
        ),
        "body_italic_gray": ParagraphStyle(
            "body_italic_gray",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            fontName="Helvetica-Oblique",
            textColor=colors.grey,
        ),
        "toc_entry": ParagraphStyle(
            "toc_entry",
            parent=base["Normal"],
            fontSize=12,
            leading=20,
            fontName="Helvetica",
        ),
        "warning_text": ParagraphStyle(
            "warning_text",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            fontName="Helvetica-Oblique",
            textColor=colors.HexColor("#ea580c"),
        ),
    }


# ---------------------------------------------------------------------------
# Document templates
# ---------------------------------------------------------------------------


def _header_footer(canvas: object, doc: object, config: ReportConfig) -> None:
    """Draw header/footer on body pages."""
    canvas.saveState()

    # Footer
    footer_y = 12 * mm

    # Left: site name
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.grey)
    canvas.drawString(MARGIN_LEFT, footer_y, config.site_name)

    # Center: page number
    page_text = f"{doc.page}"
    canvas.drawCentredString(PAGE_WIDTH / 2, footer_y, page_text)

    # Right: software name + version
    sw_text = f"{config.software_name} v{config.software_version}"
    canvas.drawRightString(PAGE_WIDTH - MARGIN_RIGHT, footer_y, sw_text)

    canvas.restoreState()


def _build_doc(output_path: Path, config: ReportConfig) -> BaseDocTemplate:
    """Build a BaseDocTemplate with cover and body page templates."""
    frame_body = Frame(
        MARGIN_LEFT, MARGIN_BOTTOM,
        USABLE_WIDTH, PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM,
        id="body_frame",
    )

    frame_cover = Frame(
        MARGIN_LEFT, MARGIN_BOTTOM,
        USABLE_WIDTH, PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM,
        id="cover_frame",
    )

    def on_body_page(canvas: object, doc: object) -> None:
        _header_footer(canvas, doc, config)

    cover_template = PageTemplate(
        id="cover",
        frames=[frame_cover],
        onPage=lambda c, d: None,  # no header/footer on cover
    )

    body_template = PageTemplate(
        id="body",
        frames=[frame_body],
        onPage=on_body_page,
    )

    doc = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN_LEFT,
        rightMargin=MARGIN_RIGHT,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title="Report Volumetrico",
        author=f"{config.software_name} v{config.software_version}",
    )
    doc.addPageTemplates([cover_template, body_template])
    return doc


# ---------------------------------------------------------------------------
# Story builders
# ---------------------------------------------------------------------------


def _build_cover(
    config: ReportConfig,
    survey_date: date,
    styles: dict[str, ParagraphStyle],
) -> list:  # type: ignore[type-arg]
    """Build the cover page flowables."""
    story: list = []  # type: ignore[type-arg]

    # Logo
    if config.logo_path:
        logo_path = Path(config.logo_path)
        if logo_path.exists():
            # Limit height to 200 px ≈ ~53 mm at 96 dpi
            story.append(Spacer(1, 20 * mm))
            img = Image(str(logo_path), width=USABLE_WIDTH * 0.4, height=50 * mm, kind="bound")
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 30 * mm))
        else:
            story.append(Spacer(1, 80 * mm))
    else:
        story.append(Spacer(1, 80 * mm))

    # Title
    story.append(Paragraph("Report Volumetrico", styles["title_cover"]))
    story.append(Paragraph("Analisi cumuli di materiale", styles["subtitle_cover"]))

    # Metadata block
    story.append(Spacer(1, 10 * mm))
    meta_lines = [f"Sito: {config.site_name}"]
    meta_lines.append(f"Data rilievo: {fmt_date_it(survey_date)}")
    if config.operator_name:
        meta_lines.append(f"Operatore: {config.operator_name}")
    if config.company_name:
        meta_lines.append(f"Azienda: {config.company_name}")

    for line in meta_lines:
        story.append(Paragraph(line, styles["meta_cover"]))
        story.append(Spacer(1, 2 * mm))

    # Bottom: generation timestamp
    story.append(Spacer(1, 40 * mm))
    now_str = fmt_datetime_it(datetime.now())
    footer_text = (
        f"Generato da {config.software_name} "
        f"v{config.software_version} il {now_str}"
    )
    story.append(Paragraph(footer_text, styles["footer_cover"]))

    # Switch to body template for next pages
    story.append(NextPageTemplate("body"))
    story.append(PageBreak())
    return story


def _build_toc_placeholder(styles: dict[str, ParagraphStyle]) -> list:  # type: ignore[type-arg]
    """Build a simple TOC page (static — page numbers filled post-layout)."""
    story: list = []  # type: ignore[type-arg]
    story.append(Paragraph("Indice", styles["section_title"]))
    story.append(Spacer(1, 6 * mm))

    # We'll use a simple static TOC since reportlab's TableOfContents
    # requires specific heading tags. Static is acceptable given the
    # fixed structure of our report.
    toc_entries = [
        "Panoramica del sito",
        "Schede cumuli",
        "Tabella riepilogativa",
        "Analisi grafica",
        "Parametri di elaborazione",
    ]

    for entry in toc_entries:
        story.append(Paragraph(f"\u2022  {entry}", styles["toc_entry"]))

    story.append(PageBreak())
    return story


def _build_site_overview(
    overview_png_path: Path,
    heaps: list[HeapReportData],
    styles: dict[str, ParagraphStyle],
) -> list:  # type: ignore[type-arg]
    """Build the site overview page."""
    story: list = []  # type: ignore[type-arg]
    story.append(Paragraph("Panoramica del sito", styles["section_title"]))

    # Overview image
    if overview_png_path.exists():
        max_h = PAGE_HEIGHT * 0.55
        img = Image(str(overview_png_path), width=USABLE_WIDTH, height=max_h, kind="bound")
        img.hAlign = "CENTER"
        story.append(img)
        story.append(Spacer(1, 6 * mm))

    # Summary statistics
    n_heaps = len(heaps)
    total_volume = sum(h.volume_m3 for h in heaps)
    total_area = sum(h.planimetric_area_m2 for h in heaps)
    mean_height = (
        sum(h.mean_height_m for h in heaps) / n_heaps if n_heaps > 0 else 0
    )

    summary_data = [
        ["Numero cumuli", str(n_heaps)],
        ["Volume totale", f"{fmt_it(total_volume)} m\u00b3"],
        ["Area planimetrica totale", f"{fmt_it(total_area)} m\u00b2"],
        ["Altezza media complessiva", f"{fmt_it(mean_height)} m"],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[USABLE_WIDTH * 0.55, USABLE_WIDTH * 0.40],
    )
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.lightgrey),
        ("LINEBELOW", (0, -1), (-1, -1), 1, colors.grey),
    ]))
    story.append(summary_table)
    story.append(PageBreak())
    return story


def _build_heap_sheet(
    heap: HeapReportData,
    detail_png_path: Path | None,
    project_categories: list[str],
    styles: dict[str, ParagraphStyle],
) -> list:  # type: ignore[type-arg]
    """Build a single heap detail sheet."""
    story: list = []  # type: ignore[type-arg]

    display_label = heap.label or str(heap.heap_id)
    story.append(
        Paragraph(f"Cumulo #{display_label}", styles["heap_title"])
    )

    # Two-column layout: image (55%) + metrics (45%)
    left_elements: list = []  # type: ignore[type-arg]
    right_elements: list = []  # type: ignore[type-arg]

    # Left: detail image
    img_width = USABLE_WIDTH * 0.52
    if detail_png_path and detail_png_path.exists():
        img = Image(str(detail_png_path), width=img_width, height=PAGE_HEIGHT * 0.35, kind="bound")
        left_elements.append(img)
    else:
        left_elements.append(
            Paragraph("<i>Immagine non disponibile</i>", styles["body_small"])
        )

    # Right: metrics table
    metrics_data = [
        ["Volume", f"{fmt_it(heap.volume_m3)} m\u00b3"],
        ["Area planimetrica", f"{fmt_it(heap.planimetric_area_m2)} m\u00b2"],
        ["Area superficiale", f"{fmt_it(heap.surface_area_m2)} m\u00b2"],
        ["Altezza massima", f"{fmt_it(heap.max_height_m)} m"],
        ["Altezza media", f"{fmt_it(heap.mean_height_m)} m"],
        ["Quota base", f"{fmt_it(heap.base_elevation_m)} m s.l.m."],
        ["Centroide E", f"{fmt_it(heap.centroid_e, 2)} m"],
        ["Centroide N", f"{fmt_it(heap.centroid_n, 2)} m"],
    ]

    metrics_width = USABLE_WIDTH * 0.43
    metrics_table = Table(
        metrics_data,
        colWidths=[metrics_width * 0.55, metrics_width * 0.45],
    )
    metrics_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.lightgrey),
    ]))
    right_elements.append(metrics_table)

    # Combine into a two-column table
    layout_table = Table(
        [[left_elements, right_elements]],
        colWidths=[USABLE_WIDTH * 0.55, USABLE_WIDTH * 0.45],
    )
    layout_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(layout_table)
    story.append(Spacer(1, 4 * mm))

    # Classification block
    cat_text = heap.material_category or "Non classificato"
    color_hex = category_color(heap.material_category, project_categories)

    # Category with colored square (using reportlab inline drawing)
    cat_line = (
        f'<b>Categoria materiale:</b> '
        f'<font color="{color_hex}">\u25a0</font> {cat_text}'
    )
    story.append(Paragraph(cat_line, styles["body"]))

    if (
        heap.material_confidence is not None
        and heap.classified_by
        and heap.classified_by != "manual"
    ):
        conf_pct = f"{heap.material_confidence * 100:.0f}%"
        story.append(
            Paragraph(
                f"<b>Confidence VLM:</b> {conf_pct}",
                styles["body"],
            )
        )

    # Classified by
    if heap.classified_by:
        if heap.classified_by.startswith("vlm:"):
            class_by_text = f"VLM ({heap.classified_by})"
        elif heap.classified_by == "manual":
            class_by_text = "Manuale"
        else:
            class_by_text = heap.classified_by
    else:
        class_by_text = "\u2014"
    story.append(
        Paragraph(
            f"<b>Classificato da:</b> {class_by_text}",
            styles["body"],
        )
    )

    if heap.notes:
        story.append(
            Paragraph(f"<b>Note operatore:</b> {heap.notes}", styles["body"])
        )

    # Low confidence warning
    if (
        heap.material_confidence is not None
        and heap.material_confidence < 0.7
        and heap.classified_by
        and heap.classified_by != "manual"
    ):
        story.append(Spacer(1, 2 * mm))
        story.append(
            Paragraph(
                "\u26a0 Classificazione incerta \u2014 da verificare",
                styles["warning_text"],
            )
        )

    story.append(PageBreak())
    return story


def _build_summary_table(
    heaps: list[HeapReportData],
    project_categories: list[str],
    styles: dict[str, ParagraphStyle],
) -> list:  # type: ignore[type-arg]
    """Build the summary table page(s)."""
    story: list = []  # type: ignore[type-arg]
    story.append(Paragraph("Tabella riepilogativa", styles["section_title"]))
    story.append(Spacer(1, 4 * mm))

    # Header row
    header = [
        "ID", "Categoria", "Volume (m\u00b3)",
        "Area (m\u00b2)", "h max (m)", "h media (m)",
    ]

    # Data rows
    data = [header]
    for h in sorted(heaps, key=lambda x: x.heap_id):
        cat_text = h.material_category or "N/C"
        color_hex = category_color(h.material_category, project_categories)
        cat_para = Paragraph(
            f'<font color="{color_hex}">\u25a0</font> {cat_text}',
            styles["body_small"],
        )
        data.append([
            str(h.label or h.heap_id),
            cat_para,
            fmt_it(h.volume_m3),
            fmt_it(h.planimetric_area_m2),
            fmt_it(h.max_height_m),
            fmt_it(h.mean_height_m),
        ])

    col_widths = [
        USABLE_WIDTH * 0.07,  # ID
        USABLE_WIDTH * 0.28,  # Category
        USABLE_WIDTH * 0.17,  # Volume
        USABLE_WIDTH * 0.17,  # Area
        USABLE_WIDTH * 0.15,  # h max
        USABLE_WIDTH * 0.16,  # h mean
    ]

    table = Table(data, colWidths=col_widths, repeatRows=1)

    # Style
    style_cmds = [
        # Header
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        # Body
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        # General
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.grey),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.grey),
    ]

    # Alternating row shading
    for i in range(1, len(data)):
        if i % 2 == 1:
            style_cmds.append(
                ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f8fafc"))
            )

    table.setStyle(TableStyle(style_cmds))
    story.append(table)
    story.append(PageBreak())
    return story


def _build_charts_page(
    heaps: list[HeapReportData],
    project_categories: list[str],
    styles: dict[str, ParagraphStyle],
) -> list:  # type: ignore[type-arg]
    """Build the charts analysis page."""
    story: list = []  # type: ignore[type-arg]
    story.append(Paragraph("Analisi grafica", styles["section_title"]))
    story.append(Spacer(1, 4 * mm))

    # Volume histogram
    volumes = [h.volume_m3 for h in heaps if h.volume_m3 > 0]
    hist_bytes = render_volume_histogram(volumes)
    chart_w = USABLE_WIDTH * 0.9
    chart_h = PAGE_HEIGHT * 0.3
    hist_img = Image(BytesIO(hist_bytes), width=chart_w, height=chart_h, kind="bound")
    hist_img.hAlign = "CENTER"
    story.append(hist_img)
    story.append(Spacer(1, 8 * mm))

    # Category pie chart
    category_volumes: dict[str | None, float] = {}
    for h in heaps:
        cat = h.material_category
        category_volumes[cat] = category_volumes.get(cat, 0) + h.volume_m3

    has_classifications = any(k is not None for k in category_volumes)

    if has_classifications:
        pie_bytes = render_category_pie(category_volumes, project_categories)
        pie_img = Image(BytesIO(pie_bytes), width=chart_w, height=chart_h, kind="bound")
        pie_img.hAlign = "CENTER"
        story.append(pie_img)
    else:
        story.append(
            Paragraph(
                "<i>Nessuna classificazione disponibile</i>",
                styles["body_italic_gray"],
            )
        )

    story.append(PageBreak())
    return story


def _build_params_page(
    processing_params: dict,  # type: ignore[type-arg]
    styles: dict[str, ParagraphStyle],
) -> list:  # type: ignore[type-arg]
    """Build the processing parameters page."""
    story: list = []  # type: ignore[type-arg]
    story.append(Paragraph("Parametri di elaborazione", styles["section_title"]))
    story.append(Spacer(1, 4 * mm))

    config = processing_params.get("config", {})

    params_data = [
        [
            "Risoluzione DSM",
            f"{config.get('dsm_resolution', 0.1)} m/pixel",
        ],
        [
            "Soglia altezza minima",
            f"{config.get('height_threshold', 0.5)} m",
        ],
        [
            "Area minima cumulo",
            f"{config.get('min_heap_area', 50)} m\u00b2",
        ],
        ["Metodo stima base", "automatico"],
        [
            "Percentile DSM",
            f"{config.get('dsm_percentile', 95)}\u00b0",
        ],
        [
            "Kernel morphological",
            f"{config.get('morpho_kernel_size', 50)} pixel",
        ],
    ]

    params_table = Table(
        params_data,
        colWidths=[USABLE_WIDTH * 0.50, USABLE_WIDTH * 0.45],
    )
    params_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.lightgrey),
        ("LINEBELOW", (0, -1), (-1, -1), 1, colors.grey),
    ]))
    story.append(params_table)
    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph(
            "Questi parametri permettono la riproducibilit\u00e0 dell\u2019analisi.",
            styles["body_italic_gray"],
        )
    )
    story.append(PageBreak())
    return story


def _build_notes_page(
    notes: str,
    styles: dict[str, ParagraphStyle],
) -> list:  # type: ignore[type-arg]
    """Build the additional notes page."""
    story: list = []  # type: ignore[type-arg]
    story.append(Paragraph("Note", styles["section_title"]))
    story.append(Spacer(1, 4 * mm))

    # Preserve newlines
    for line in notes.split("\n"):
        story.append(Paragraph(line or "&nbsp;", styles["body"]))

    return story


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------


class ReportGenerator:
    """Generates professional PDF reports."""

    def __init__(self, config: ReportConfig) -> None:
        """Initialize the report generator.

        Args:
            config: Report configuration.
        """
        self.config = config
        self._renderer = MapRenderer()
        self._styles = _build_styles()

    def generate(
        self,
        results_path: Path,
        tiff_path: Path,
        output_path: Path,
        progress_cb: Callable[[ReportProgress], None] | None = None,
        heap_db_data: list[dict] | None = None,  # type: ignore[type-arg]
    ) -> Path:
        """Generate the complete PDF report.

        Args:
            results_path: Path to pipeline results.json.
            tiff_path: Path to the GeoTIFF ortophoto.
            output_path: Path for the output PDF.
            progress_cb: Optional progress callback.
            heap_db_data: Optional DB-sourced heap data with classification.
                Each dict: {heap_id, material_category, material_confidence,
                classified_by, is_manually_confirmed, notes}.

        Returns:
            Output path.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_dir = output_path.parent / ".report_temp"
        temp_dir.mkdir(exist_ok=True)

        def _progress(phase: str, pct: float, msg: str) -> None:
            if progress_cb:
                progress_cb(ReportProgress(phase, pct, msg))

        # --- Load data ---
        _progress("overview", 0, "Caricamento dati...")
        data = json.loads(results_path.read_text(encoding="utf-8"))
        metrics_raw = data["heap_metrics"]
        survey_metadata = data.get("survey_metadata", {})

        # Parse metrics
        metrics = [HeapMetrics(**hm) for hm in metrics_raw]

        # Parse survey date
        survey_date_str = survey_metadata.get("survey_date")
        survey_date = (
            date.fromisoformat(survey_date_str) if survey_date_str
            else date.today()
        )

        # Parse project categories
        project_categories: list[str] = survey_metadata.get(
            "project_categories", []
        )

        # Build HeapReportData combining metrics + DB data
        db_map: dict[int, dict] = {}  # type: ignore[type-arg]
        if heap_db_data:
            for hd in heap_db_data:
                db_map[hd["heap_id"]] = hd

        heaps: list[HeapReportData] = []
        for m in metrics:
            db = db_map.get(m.heap_id, {})
            h = HeapReportData(
                heap_id=m.heap_id,
                label=m.label,
                polygon_geojson=m.polygon_geojson,
                volume_m3=m.volume_m3,
                planimetric_area_m2=m.planimetric_area_m2,
                surface_area_m2=m.surface_area_m2,
                max_height_m=m.max_height_m,
                mean_height_m=m.mean_height_m,
                base_elevation_m=m.base_elevation_m,
                centroid_e=m.centroid_e,
                centroid_n=m.centroid_n,
                material_category=db.get("material_category"),
                material_confidence=db.get("material_confidence"),
                classified_by=db.get("classified_by"),
                is_manually_confirmed=bool(
                    db.get("is_manually_confirmed", False)
                ),
                notes=db.get("notes"),
            )
            heaps.append(h)

        # Filter if only_confirmed
        if self.config.only_confirmed_heaps:
            heaps = [
                h for h in heaps
                if h.is_manually_confirmed or h.material_category is not None
            ]

        # --- Render images ---
        _progress("overview", 10, "Generazione panoramica...")
        overview_png = temp_dir / "overview.png"
        render_infos = [
            HeapRenderInfo(
                heap_id=h.heap_id,
                label=h.label,
                polygon_geojson=h.polygon_geojson,
                category=h.material_category,
            )
            for h in heaps
        ]

        self._renderer.render_site_overview(
            tiff_path=tiff_path,
            heaps=render_infos,
            project_categories=project_categories,
            site_name=self.config.site_name,
            survey_date=survey_date,
            output_path=overview_png,
            dpi=150,
        )

        _progress("heap-sheets", 25, "Generazione schede cumuli...")
        detail_pngs: dict[int, Path] = {}
        for i, h in enumerate(heaps):
            pct = 25 + (i / max(len(heaps), 1)) * 30
            _progress(
                "heap-sheets", pct,
                f"Scheda cumulo {h.label or h.heap_id} "
                f"({i + 1}/{len(heaps)})",
            )
            png_path = temp_dir / f"heap_{h.heap_id}.png"
            ri = HeapRenderInfo(
                heap_id=h.heap_id,
                label=h.label,
                polygon_geojson=h.polygon_geojson,
                category=h.material_category,
            )
            dm = HeapDetailMetrics(
                volume_m3=h.volume_m3,
                max_height_m=h.max_height_m,
                mean_height_m=h.mean_height_m,
                planimetric_area_m2=h.planimetric_area_m2,
            )
            self._renderer.render_heap_detail(
                tiff_path=tiff_path,
                heap=ri,
                heap_metrics=dm,
                project_categories=project_categories,
                output_path=png_path,
                dpi=200,
            )
            detail_pngs[h.heap_id] = png_path

        # --- Build PDF story ---
        _progress("summary", 55, "Tabella riepilogativa...")

        story: list = []  # type: ignore[type-arg]

        # Cover
        story.extend(_build_cover(self.config, survey_date, self._styles))

        # TOC
        story.extend(_build_toc_placeholder(self._styles))

        # Site overview
        story.extend(
            _build_site_overview(overview_png, heaps, self._styles)
        )

        # Heap sheets
        for h in heaps:
            story.extend(
                _build_heap_sheet(
                    h, detail_pngs.get(h.heap_id),
                    project_categories, self._styles,
                )
            )

        # Summary table
        _progress("summary", 70, "Tabella riepilogativa...")
        story.extend(
            _build_summary_table(heaps, project_categories, self._styles)
        )

        # Charts
        _progress("charts", 75, "Grafici...")
        story.extend(
            _build_charts_page(heaps, project_categories, self._styles)
        )

        # Processing parameters
        _progress("params", 85, "Parametri di elaborazione...")
        story.extend(
            _build_params_page(survey_metadata, self._styles)
        )

        # Notes
        if self.config.additional_notes:
            story.extend(
                _build_notes_page(self.config.additional_notes, self._styles)
            )

        # --- Build PDF ---
        _progress("assemble", 90, "Assemblaggio PDF...")
        doc = _build_doc(output_path, self.config)
        doc.build(story)

        _progress("assemble", 100, "Report completato")
        logger.debug("PDF report saved: %s", output_path)

        # Cleanup temp files
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

        return output_path
