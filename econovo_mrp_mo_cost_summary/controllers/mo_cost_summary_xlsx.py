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

def _collect_component_entries(comp_wrappers, parent_name, out):
    """Recursively collect flat component entries from the MO report tree.

    Each wrapper produced by _get_components_data has:
      - wrapper["summary"]: the native component dict (product_id, name,
        quantity, uom_name, mo_cost, real_cost, …)
      - wrapper["categ_id"], wrapper["categ_name"], wrapper["categ_ancestors"]:
        injected by our Python override to avoid polluting MoOverviewLine's
        strict OWL prop-shape validation on "summary".
      - wrapper["replenishments"]: list of replenishment dicts, where those
        with summary.model == "mrp.production" are sub-MOs carrying their own
        "components" list.

    The resulting flat entries are keyed with "_parent_name" so the sheet
    can show which MO consumed each component.
    """
    for wrapper in comp_wrappers:
        summary = wrapper.get("summary") or {}
        entry = dict(summary)
        # categ fields live on the wrapper, not on the summary
        entry["categ_id"] = wrapper["categ_id"] if "categ_id" in wrapper else entry.get("categ_id", 0)
        entry["categ_name"] = wrapper.get("categ_name") or entry.get("categ_name", "Uncategorized")
        entry["categ_ancestors"] = wrapper.get("categ_ancestors") or entry.get("categ_ancestors") or []
        entry["_parent_name"] = parent_name
        out.append(entry)

        # Recurse into sub-MO replenishments (each carries its own components list).
        for rep in (wrapper.get("replenishments") or []):
            rep_sum = rep.get("summary") or {}
            if rep_sum.get("model") == "mrp.production":
                sub_comps = rep.get("components") or []
                sub_name = rep_sum.get("name") or parent_name
                _collect_component_entries(sub_comps, sub_name, out)


def _build_category_map(flat_entries):
    """Aggregate a flat component entry list into {categ_id: {...}}."""
    category_map = {}
    for entry in flat_entries:
        cat_id = entry.get("categ_id") or 0
        cat_name = entry.get("categ_name") or "Uncategorized"
        ancestors = entry.get("categ_ancestors") or [{"id": cat_id, "name": cat_name}]

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
        mo_cost = float(entry.get("mo_cost") or 0)
        real_cost = float(entry.get("real_cost") or 0)
        cat["mo_cost"] += mo_cost
        cat["real_cost"] += real_cost

        prod_id = entry.get("product_id") or entry.get("id") or 0
        prod_name = entry.get("name") or ""
        if prod_id not in cat["products"]:
            cat["products"][prod_id] = {
                "name": prod_name,
                "mo_cost": 0.0,
                "real_cost": 0.0,
                "usages": [],
            }
        prod = cat["products"][prod_id]
        prod["mo_cost"] += mo_cost
        prod["real_cost"] += real_cost
        prod["usages"].append({
            "parent_name": entry.get("_parent_name") or "",
            "quantity": float(entry.get("quantity") or 0),
            "uom_name": entry.get("uom_name") or "",
            "mo_cost": mo_cost,
            "real_cost": real_cost,
        })
    return category_map


def _write_components_sheet(ws, data, currency_name):
    """Write Sheet 1: Components by Category."""
    # data["summary"] holds the MO-level summary; fall back to data["name"].
    parent_name = (data.get("summary") or {}).get("name") or data.get("name", "")
    flat_entries = []
    _collect_component_entries(data.get("components") or [], parent_name, flat_entries)
    category_map = _build_category_map(flat_entries)

    headers = ["Type", "Name", "Qty", "UoM",
               "MO Cost (%s)" % currency_name,
               "Real Cost (%s)" % currency_name,
               "Deviation"]
    _write_header(ws, 1, headers, _C["header_bg"])
    ws.freeze_panes = "A2"
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
        dev = _flt(cat["real_cost"] - cat["mo_cost"]) if cat["mo_cost"] else ""
        _write_row(ws, row, [
            "Category", cat["name"], "", "",
            _flt(cat["mo_cost"]), _flt(cat["real_cost"]), dev,
        ], _C["cat_0"], bold=True, outline_level=0)
        row += 1
        total_mo += cat["mo_cost"]
        total_real += cat["real_cost"]

        for prod in sorted(cat["products"].values(), key=lambda p: -p["mo_cost"]):
            dev_p = _flt(prod["real_cost"] - prod["mo_cost"]) if prod["mo_cost"] else ""
            _write_row(ws, row, [
                "Product", "  " + prod["name"], "", "",
                _flt(prod["mo_cost"]), _flt(prod["real_cost"]), dev_p,
            ], _C["product"], bold=False, outline_level=1)
            row += 1

            for usage in prod["usages"]:
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

    _write_row(ws, row, [
        "TOTAL", "", "", "",
        _flt(total_mo), _flt(total_real),
        _flt(total_real - total_mo) if total_mo else "",
    ], _C["total"], bold=True)


# ── Sheet 2: Operations by Work Center ───────────────────────────────────────

def _collect_operation_entries(comp_wrappers, out):
    """Recursively collect operation entries from sub-MO replenishments.

    For each component wrapper, inspect its replenishments for sub-MOs and
    collect their workorders using the operations_workcenter_map stored at
    the replenishment level (our Python override moves it there from inside
    operations to avoid OWL prop-shape violations in MoOverviewComponentsBlock).

    Recurses into each sub-MO's own components to collect deeper levels.
    """
    for wrapper in comp_wrappers:
        summary = wrapper.get("summary") or {}
        for rep in (wrapper.get("replenishments") or []):
            rep_sum = rep.get("summary") or {}
            if rep_sum.get("model") != "mrp.production":
                continue
            ops_details = (rep.get("operations") or {}).get("details") or []
            # workcenter_map is at the replenishment level, not inside operations
            wc_map_rep = rep.get("operations_workcenter_map") or {}
            for op in ops_details:
                wc_info = wc_map_rep.get(op.get("id")) or {}
                out.append({
                    "name": op.get("name") or "",
                    "quantity": float(op.get("quantity") or 0),
                    "mo_cost": float(op.get("mo_cost") or 0),
                    "real_cost": float(op.get("real_cost") or 0),
                    "workcenter_id": wc_info.get("workcenter_id") or 0,
                    "workcenter_name": wc_info.get("workcenter_name") or "Unknown",
                })
            # Recurse into this sub-MO's own component wrappers for deeper levels.
            _collect_operation_entries(rep.get("components") or [], out)


def _write_operations_sheet(ws, data, currency_name):
    """Write Sheet 2: Operations by Work Center."""
    headers = ["Type", "Name", "Duration (min)",
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

    # ── Top-level operations ──────────────────────────────────────────────────
    # operations_workcenter_info is indexed in the same order as operations.details
    # (our _get_report_data override moves workcenter_map to this sibling key).
    top_details = (data.get("operations") or {}).get("details") or []
    top_wc_info = data.get("operations_workcenter_info") or []
    top_ops = []
    for i, op in enumerate(top_details):
        extra = top_wc_info[i] if i < len(top_wc_info) else {}
        top_ops.append({
            "name": op.get("name") or "",
            "quantity": float(op.get("quantity") or 0),
            "mo_cost": float(op.get("mo_cost") or 0),
            "real_cost": float(op.get("real_cost") or 0),
            "workcenter_id": extra.get("workcenter_id") or 0,
            "workcenter_name": extra.get("workcenter_name") or "Unknown",
        })

    # ── Sub-MO operations ─────────────────────────────────────────────────────
    sub_ops = []
    _collect_operation_entries(data.get("components") or [], sub_ops)

    # ── Group all operations by workcenter ────────────────────────────────────
    wc_map = {}
    for op in top_ops + sub_ops:
        wc_id = op["workcenter_id"]
        if wc_id not in wc_map:
            wc_map[wc_id] = {
                "name": op["workcenter_name"],
                "mo_cost": 0.0,
                "real_cost": 0.0,
                "duration": 0.0,
                "items": [],
            }
        wc = wc_map[wc_id]
        wc["mo_cost"] += op["mo_cost"]
        wc["real_cost"] += op["real_cost"]
        wc["duration"] += op["quantity"]
        wc["items"].append(op)

    row = 2
    total_mo = 0.0
    total_real = 0.0

    for wc in sorted(wc_map.values(), key=lambda x: -x["mo_cost"]):
        _write_row(ws, row, [
            "Work Center", wc["name"], _flt(wc["duration"]),
            _flt(wc["mo_cost"]), _flt(wc["real_cost"]),
            _flt(wc["real_cost"] - wc["mo_cost"]) if wc["mo_cost"] else "",
        ], _C["wc"], bold=True, outline_level=0)
        row += 1
        total_mo += wc["mo_cost"]
        total_real += wc["real_cost"]

        for op in wc["items"]:
            _write_row(ws, row, [
                "Operation", "  " + op["name"], _flt(op["quantity"]),
                _flt(op["mo_cost"]), _flt(op["real_cost"]),
                _flt(op["real_cost"] - op["mo_cost"]) if op["mo_cost"] else "",
            ], _C["op"], bold=False, outline_level=1)
            row += 1

    if wc_map:
        _write_row(ws, row, [
            "TOTAL", "", "",
            _flt(total_mo), _flt(total_real),
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

        # Determine currency name (mrp.production has no direct currency_id;
        # the currency comes from the production order's company).
        production = env["mrp.production"].browse(prod_id)
        currency_name = production.company_id.currency_id.name or "ARS"

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
