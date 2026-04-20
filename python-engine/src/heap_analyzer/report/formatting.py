"""Italian number and date formatting helpers for the PDF report."""

from __future__ import annotations

from datetime import date, datetime


def fmt_it(value: float | int, decimals: int = 2) -> str:
    """Format a number using Italian conventions.

    Thousands separator: `.`  Decimal separator: `,`

    Args:
        value: Number to format.
        decimals: Number of decimal places.

    Returns:
        Formatted string (e.g. '1.234,50').
    """
    if isinstance(value, int) and decimals == 0:
        # Integer with no decimals
        formatted = f"{value:,}".replace(",", ".")
        return formatted

    # Format with decimals
    formatted = f"{value:,.{decimals}f}"
    # English uses ',' for thousands and '.' for decimal
    # Italian uses '.' for thousands and ',' for decimal
    # Step 1: replace ',' (thousands) with temp
    formatted = formatted.replace(",", "_THOU_")
    # Step 2: replace '.' (decimal) with ','
    formatted = formatted.replace(".", ",")
    # Step 3: replace temp with '.'
    formatted = formatted.replace("_THOU_", ".")
    return formatted


def fmt_date_it(d: date | datetime) -> str:
    """Format a date as GG/MM/AAAA.

    Args:
        d: Date or datetime to format.

    Returns:
        Italian date string (e.g. '20/04/2026').
    """
    return d.strftime("%d/%m/%Y")


def fmt_datetime_it(d: datetime) -> str:
    """Format a datetime as GG/MM/AAAA HH:MM.

    Args:
        d: Datetime to format.

    Returns:
        Italian datetime string (e.g. '20/04/2026 14:30').
    """
    return d.strftime("%d/%m/%Y %H:%M")
