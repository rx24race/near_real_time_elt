"""Render a portable HTML report using only the standard library."""

from html import escape
from decimal import Decimal
from pathlib import Path
from string import Template

from csv_etl import HEADERS


TEMPLATE = Path(__file__).resolve().parent / "templates" / "dashboard.html"
METRIC_LABELS = {
    "rows_read": "Rows read", "rows_accepted": "Rows accepted", "rows_written": "Rows written",
    "rows_rejected": "Rows rejected", "duplicates_removed": "Duplicates removed",
    "corrected_records": "Corrected records",
}


def text(value) -> str:
    return escape("Unavailable" if value is None else str(value), quote=True)


def category_chart(categories) -> str:
    if categories is None:
        return '<p class="muted">Category summary unavailable: transformation did not finish.</p>'
    if not categories:
        return '<p class="muted">No accepted category amounts.</p>'
    # Geometry must come from finite, nonnegative numbers, never CSV text or CSS.
    amounts = [row["net_amount"] for row in categories]
    if any(not isinstance(amount, (Decimal, int)) or not Decimal(amount).is_finite()
           or amount < 0 for amount in amounts):
        return '<p class="muted">Category summary unavailable: invalid numeric totals.</p>'
    maximum = max(amounts)
    bars = []
    for row, amount in zip(categories, amounts):
        tenths = int(Decimal(amount) * 1000 / Decimal(maximum)) if maximum else 0
        tenths = max(0, min(1000, tenths))
        width = f"{tenths // 10}.{tenths % 10}"
        bars.append(
            f'<div class="category" data-category="{text(row["category"])}" data-net-amount="{amount:.2f}">'
            f'<div class="category-label"><span>{text(row["category"])}</span><strong>{amount:.2f}</strong></div>'
            f'<div class="bar-track" aria-hidden="true"><div class="bar" style="width:{width}%"></div></div></div>'
        )
    return "".join(bars)


def quality_notes(issues) -> str:
    if issues is None:
        return '<p class="muted">Issue counts unavailable: classification did not finish.</p>'
    if not issues:
        return '<p class="muted">No rejected-row issues.</p>'
    return '<ul class="issue-list">' + "".join(
        f'<li><span>{text(issue["reason"])}</span><strong>{text(issue["row_count"])}</strong></li>'
        for issue in issues
    ) + '</ul>'


def preview_table(name: str, rows, total) -> str:
    if rows is None:
        return '<p class="muted">Preview unavailable: the required stage did not finish.</p>'
    if not rows:
        return f'<p class="muted">No {name} records.</p>'
    columns = ("source_record_number",) + HEADERS + (
        ("gross_amount", "net_amount") if name == "accepted" else ("rejection_reasons",)
    )
    visible = rows[:10]
    headers = "".join(f'<th scope="col">{text(column.replace("_", " ").title())}</th>' for column in columns)
    body = "".join(
        '<tr>' + "".join(f'<td>{text(row.get(column, ""))}</td>' for column in columns) + '</tr>'
        for row in visible
    )
    return (
        f'<div class="table-scroll" role="region" aria-label="{name.capitalize()} preview" tabindex="0">'
        f'<table id="{name}-preview"><caption>First {len(visible)} of {text(total)} {name} records '
        f'(up to 10), in source order. Record numbers exclude the header.</caption>'
        f'<thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table></div>'
    )


def render_report(result) -> str:
    metrics = "".join(
        f'<div class="metric" data-metric="{key}"><dt>{label}</dt>'
        f'<dd>{text(result.metrics.get(key))}</dd></div>'
        for key, label in METRIC_LABELS.items()
    )
    stages = "".join(
        '<li class="stage"><span class="stage-name">' + text(name.capitalize()) + '</span>'
        '<span class="stage-state ' + {"complete": "complete", "failed": "failed"}.get(state, "not-run")
        + '">' + text(state) + '</span></li>'
        for name, state in result.stages.items()
    )
    keys = ("rows_read", "rows_accepted", "duplicates_removed", "rows_rejected")
    values = [result.metrics.get(key) for key in keys]
    if all(value is not None for value in values):
        invariant = (f"Row accounting: {values[0]} read = {values[1]} accepted + "
                     f"{values[2]} duplicate copies + {values[3]} rejected.")
    else:
        invariant = "Row accounting unavailable: classification did not finish."
    error = (
        '<section class="panel error" role="alert"><h2>Run failed</h2><p>'
        + text(result.error) + '</p><p>No cleaned CSV was published for this attempt.</p></section>'
        if result.status == "Failed" else ""
    )
    return Template(TEMPLATE.read_text(encoding="utf-8")).substitute(
        source=text(result.source), run_id=text(result.run_id),
        status=text(result.status), status_class={"Success": "success", "Success with warnings": "warning"}.get(result.status, "failed"),
        started_at=text(result.started_at), ended_at=text(result.ended_at),
        duration=text(f"{result.duration_seconds:.3f} seconds"),
        metrics=metrics, stages=stages, invariant=text(invariant), error=error,
        categories=category_chart(result.categories), issues=quality_notes(result.issues),
        accepted_preview=preview_table("accepted", result.accepted_preview, result.metrics.get("rows_accepted")),
        rejected_preview=preview_table("rejected", result.rejected_preview, result.metrics.get("rows_rejected")),
    )
