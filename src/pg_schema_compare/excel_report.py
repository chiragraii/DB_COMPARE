"""Excel difference report via openpyxl."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from pg_schema_compare.apply import PlannedStatement
from pg_schema_compare.models import CompareResult

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(color="FFFFFF", bold=True)
SAME_FILL = PatternFill("solid", fgColor="C6EFCE")
ONLY1_FILL = PatternFill("solid", fgColor="FCE4D6")
ONLY2_FILL = PatternFill("solid", fgColor="DDEBF7")
DIFF_FILL = PatternFill("solid", fgColor="FFC7CE")

STATUS_FILLS = {
    "SAME": SAME_FILL,
    "ONLY_IN_DB1": ONLY1_FILL,
    "ONLY_IN_DB2": ONLY2_FILL,
    "TYPE_DIFFERENCE": DIFF_FILL,
}


def write_excel_report(
    result: CompareResult,
    path: str | Path,
    *,
    planned: list[PlannedStatement] | None = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    _write_summary(wb.active, result)

    for name, cat in result.categories.items():
        ws = wb.create_sheet(_sheet_name(name))
        headers = ["Status", "Key", "DB-1 Detail", "DB-2 Detail"]
        _write_headers(ws, headers)
        row = 2
        for item in [*cat.same, *cat.only_db1, *cat.only_db2, *cat.type_diff]:
            values = [
                item.status.replace("_", " "),
                item.key,
                item.detail_db1,
                item.detail_db2,
            ]
            for col, value in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=value)
                fill = STATUS_FILLS.get(item.status)
                if fill and col == 1:
                    cell.fill = fill
            row += 1
        _autosize(ws, len(headers))

    if planned is not None:
        ws = wb.create_sheet("Apply Plan")
        headers = ["#", "Kind", "Table", "Constraint", "SQL", "Description"]
        _write_headers(ws, headers)
        for i, stmt in enumerate(planned, 1):
            ws.cell(row=i + 1, column=1, value=i)
            ws.cell(row=i + 1, column=2, value=stmt.kind)
            ws.cell(row=i + 1, column=3, value=stmt.table)
            ws.cell(row=i + 1, column=4, value=stmt.constraint_name)
            ws.cell(row=i + 1, column=5, value=stmt.sql)
            ws.cell(row=i + 1, column=6, value=stmt.description)
        _autosize(ws, len(headers))

    wb.save(path)
    return path


def _sheet_name(name: str) -> str:
    # Excel sheet name max 31 chars
    return name[:31]


def _write_summary(ws, result: CompareResult) -> None:
    ws.title = "Summary"
    ws["A1"] = "PostgreSQL Schema Comparison"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"DB-1: {result.db1_label}"
    ws["A3"] = f"DB-2: {result.db2_label}"

    headers = ["Category", "SAME", "ONLY IN DB-1", "ONLY IN DB-2", "TYPE DIFFERENCE"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=5, column=col, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT

    row = 6
    for name, same, o1, o2, td in result.summary_rows():
        ws.cell(row=row, column=1, value=name)
        ws.cell(row=row, column=2, value=same)
        ws.cell(row=row, column=3, value=o1)
        ws.cell(row=row, column=4, value=o2)
        ws.cell(row=row, column=5, value=td)
        row += 1

    ws.cell(row=row, column=1, value="Legend")
    ws.cell(row=row + 1, column=1, value="SAME").fill = SAME_FILL
    ws.cell(row=row + 2, column=1, value="ONLY IN DB-1").fill = ONLY1_FILL
    ws.cell(row=row + 3, column=1, value="ONLY IN DB-2").fill = ONLY2_FILL
    ws.cell(row=row + 4, column=1, value="TYPE DIFFERENCE").fill = DIFF_FILL
    _autosize(ws, len(headers))


def _write_headers(ws, headers: list[str]) -> None:
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(wrap_text=True)


def _autosize(ws, ncols: int) -> None:
    for col in range(1, ncols + 1):
        letter = get_column_letter(col)
        max_len = 10
        for cell in ws[letter]:
            if cell.value is not None:
                max_len = max(max_len, min(len(str(cell.value)), 80))
        ws.column_dimensions[letter].width = max_len + 2
