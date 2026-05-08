# -*- coding: utf-8 -*-
"""HTTP controller: export MO Cost Summary to Excel (.xlsx).

Endpoint: GET /econovo/mo_cost_summary/export_xlsx
Params:   production_id (required)

Returns a .xlsx workbook with two sheets:
  Sheet 1 "Components by Category" — MO cost / Real cost grouped by product category.
  Sheet 2 "Operations by Work Center" — MO cost / Real cost grouped by work center.
"""

import io
import logging

from odoo import http
from odoo.http import content_disposition, request

_logger = logging.getLogger(__name__)

# ── Colour palette ────────────────────────────────────────────────────────────
_C = {
    "header_bg":  "1F4E79",
    "header_fg":  "FFFFFF",
    "cat_0":      "BDD7EE",
    "cat_1":      "DDEBF7",
    "cat_deep":   "EEF4FB",
    "product":    "F2F2F2",
    "usage":      "FFFFFF",
    "wc":         "E2EFDA",
    "op":         "F4F9F5",
    "subtotal":   "FFF2CC",
    "total":      "FFE082",
}


def _fill(hex_color):
    from openpyxl.styles import PatternFill
    return PatternFill("solid", fgColor=hex_color)


def _font(bold=False, color="000000", size=9):
    from openpyxl.styles import Font
    return Font(bold=bold, color=color, size=size)


def _align_right():
    from openpyxl.styles import Alignment
    return Alignment(horizontal="right", vertical="center")


def _align_left():
    from openpyxl.styles import Alignment
    return Alignment(horizontal="left", vertical="center")


def _flt(value):
    if value is None or value is False:
        return ""
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return ""


def _write_row(ws, row_idx, values, bg_color, bold=False, outline_level=0):
    fill = _fill(bg_color)
    row_font = _font(bold=bold)
    for col_idx, val in enumerate(values, start=1):
        cell = ws.cell(row=row_idx, column=col_idx, value=val)
        cell.font = row_font
        cell.fill = fill
        if isinstance(val, (int, float)) and col_idx > 3:
            cell.alignment = _align_right()
        else:
            cell.alignment = _align_left()
    if outline_level:
        ws.row_dimensions[row_idx].outline_level = min(outline_level, 7)


def _write_header(ws, row_idx, values, bg_color):
    fill = _fill(bg_color)
    for col_idx, val in enumerate(values, start=1):
        cell = ws.cell(row=row_idx, column=col_idx, value=val)
        cell.font = _font(bold=True, color=_C["header_fg"], size=9)
        cell.fill = fill
        cell.alignment = _align_left()


# ── Sheet 1: Components by Category ──────────────────────────────────────────

def _build_category_map(components, parent_name):
    """Build {categ_id: {...}} from a flat list of component summaries."""
    category_map = {}
    for comp in components:
        cat_id = comp.get("categ_id", 0)
        cat_name = comp.get("categ_name", "Uncategorized")
        ancestors = comp.get("categ_ancestors") or [{"id": cat_id, "name": cat_name}]
        if cat_id not in category_map:
            category_map[cat_id] = {
                "id": cat_id,
                "name": cat_name,
                "ancestors": ancestors,
                "mo_cost": 0.0,
                "real_cost": 0.0,
                "products": {},
            }
        cat = category_map[cat_id]
        cat["mo_cost"] += comp.get("mo_cost", 0.0)
        cat["real_cost"] += comp.get("real_cost", 0.0)

        prod_id = comp.get("product_id") or comp.get("id", 0)
        prod_name = comp.get("name", "")
        if prod_id not in cat["products"]:
            cat["products"][prod_id] = {
                "name": prod_name,
                "mo_cost": 0.0,
                "real_cost": 0.0,
                "usages": [],
            }
        prod = cat["products"][prod_id]
        prod["mo_cost"] += comp.get("mo_cost", 0.0)
        prod["real_cost"] += comp.get("real_cost", 0.0)
        prod["usages"].append({
            "parent_name": parent_name,
            "quantity": comp.get("quantity", 0.0),
            "uom_name": comp.get("uom_name", ""),
            "mo_cost": comp.get("mo_cost", 0.0),
            "real_cost": comp.get("real_cost", 0.0),
        })
    return category_map


def _write_components_sheet(ws, data, currency_name):
    """Write Sheet 1: Components by Category."""
    parent_name = data.get("name", "")
    components = [c.get("summary", c) for c in data.get("components", [])]
    category_map = _build_category_map(components, parent_name)

    headers = ["Type", "Name", "Qty", "UoM",
               "MO Cost (%s)" % currency_name,
               "Real Cost (%s)" % currency_name,
               "Deviation"]
    col_count = len(headers)
    _write_header(ws, 1, headers, _C["header_bg"])

    # Freeze header
    ws.freeze_panes = "A2"

    # Column widths
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 42
    ws.column_dimensions["C"].width = 10
    ws.column_dimensions["D"].width = 10
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 18
    ws.column_dimensions["G"].width = 14

    row = 2
    total_mo = 0.0
    total_real = 0.0

    for cat in sorted(category_map.values(), key=lambda x: -x["mo_cost"]):
        # Category row
        dev = _flt(cat["real_cost"] - cat["mo_cost"]) if cat["mo_cost"] else ""
        _write_row(ws, row, [
            "Category",
            cat["name"],
            "", "",
            _flt(cat["mo_cost"]),
            _flt(cat["real_cost"]),
            dev,
        ], _C["cat_0"], bold=True, outline_level=0)
        row += 1
        total_mo += cat["mo_cost"]
        total_real += cat["real_cost"]

        for prod in sorted(cat["products"].values(), key=lambda p: -p["mo_cost"]):
            dev_p = _flt(prod["real_cost"] - prod["mo_cost"]) if prod["mo_cost"] else ""
            _write_row(ws, row, [
                "Product",
                "  " + prod["name"],
                "", "",
                _flt(prod["mo_cost"]),
                _flt(prod["real_cost"]),
                dev_p,
            ], _C["product"], bold=False, outline_level=1)
            row += 1

            for usage in prod["usages"]:
                qty_str = "%g %s" % (usage["quantity"], usage["uom_name"]) if usage.get("quantity") else ""
                _write_row(ws, row, [
                    "Usage",
                    "    " + usage["parent_name"],
                    _flt(usage["quantity"]),
                    usage["uom_name"],
                    _flt(usage["mo_cost"]),
                    _flt(usage["real_cost"]),
                    _flt(usage["real_cost"] - usage["mo_cost"]) if usage["mo_cost"] else "",
                ], _C["usage"], bold=False, outline_level=2)
                row += 1

    # Grand Total
    _write_row(ws, row, [
        "TOTAL", "", "", "",
        _flt(total_mo),
        _flt(total_real),
        _flt(total_real - total_mo) if total_mo else "",
    ], _C["total"], bold=True)


# ── Sheet 2: Operations by Work Center ───────────────────────────────────────

def _write_operations_sheet(ws, data, currency_name):
    """Write Sheet 2: Operations by Work Center."""
    operations_data = data.get("operations", {})
    details = operations_data.get("details", [])

    headers = ["Type", "Name",
               "Duration (min)",
               "MO Cost (%s)" % currency_name,
               "Real Cost (%s)" % currency_name,
               "Deviation"]
    _write_header(ws, 1, headers, _C["header_bg"])
    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 42
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 18
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 14

    # Group by workcenter
    wc_map = {}
    for op in details:
        wc_id = op.get("workcenter_id", 0)
        wc_name = op.get("workcenter_name", "Unknown")
        if wc_id not in wc_map:
            wc_map[wc_id] = {
                "name": wc_name,
                "mo_cost": 0.0,
                "real_cost": 0.0,
                "duration": 0.0,
                "items": [],
            }
        wc = wc_map[wc_id]
        wc["mo_cost"] += op.get("mo_cost", 0.0)
        wc["real_cost"] += op.get("real_cost", 0.0)
        wc["duration"] += op.get("quantity", 0.0)
        wc["items"].append(op)

    row = 2
    total_mo = 0.0
    total_real = 0.0

    for wc in sorted(wc_map.values(), key=lambda x: -x["mo_cost"]):
        _write_row(ws, row, [
            "Work Center",
            wc["name"],
            _flt(wc["duration"]),
            _flt(wc["mo_cost"]),
            _flt(wc["real_cost"]),
            _flt(wc["real_cost"] - wc["mo_cost"]) if wc["mo_cost"] else "",
        ], _C["wc"], bold=True, outline_level=0)
        row += 1
        total_mo += wc["mo_cost"]
        total_real += wc["real_cost"]

        for op in wc["items"]:
            _write_row(ws, row, [
                "Operation",
                "  " + op.get("name", ""),
                _flt(op.get("quantity", 0.0)),
                _flt(op.get("mo_cost", 0.0)),
                _flt(op.get("real_cost", 0.0)),
                _flt(op.get("real_cost", 0.0) - op.get("mo_cost", 0.0)) if op.get("mo_cost") else "",
            ], _C["op"], bold=False, outline_level=1)
            row += 1

    # Grand Total
    if wc_map:
        _write_row(ws, row, [
            "TOTAL", "",
            "",
            _flt(total_mo),
            _flt(total_real),
            _flt(total_real - total_mo) if total_mo else "",
        ], _C["total"], bold=True)


# ── Controller ────────────────────────────────────────────────────────────────

class MoCostSummaryXlsx(http.Controller):

    @http.route(
        "/econovo/mo_cost_summary/export_xlsx",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def export_xlsx(self, production_id=None, **kwargs):
        """Export the MO Cost Summary as an .xlsx workbook."""
        try:
            from openpyxl import Workbook
        except ImportError:
            return request.make_response(
                "openpyxl is required for Excel export. "
                "Install it with: pip install openpyxl",
                headers=[("Content-Type", "text/plain")],
            )

        if not production_id:
            return request.make_response(
                "Missing production_id parameter",
                headers=[("Content-Type", "text/plain")],
            )

        try:
            prod_id = int(production_id)
        except (TypeError, ValueError):
            return request.make_response(
                "Invalid production_id",
                headers=[("Content-Type", "text/plain")],
            )

        env = request.env
        report = env["report.mrp.report_mo_overview"]
        result = report.get_report_values(prod_id)
        data = result["data"]

        # Determine currency name
        production = env["mrp.production"].browse(prod_id)
        currency_name = production.currency_id.name or "ARS"

        # Build workbook
        wb = Workbook()
        ws1 = wb.active
        ws1.title = "Components by Category"
        _write_components_sheet(ws1, data, currency_name)

        ws2 = wb.create_sheet("Operations by Work Center")
        _write_operations_sheet(ws2, data, currency_name)

        # Stream as .xlsx download
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        filename = "mo_cost_summary_%d.xlsx" % prod_id
        headers = [
            ("Content-Type",
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("Content-Disposition", content_disposition(filename)),
        ]
        return request.make_response(buf.getvalue(), headers=headers)
