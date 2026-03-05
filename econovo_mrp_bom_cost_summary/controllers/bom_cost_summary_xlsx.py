# -*- coding: utf-8 -*-
"""HTTP controller: export BOM Cost Summary to Excel (.xlsx).

Endpoint: GET /econovo/bom_cost_summary/export_xlsx
Params:   bom_id, quantity, variant, warehouse_id, costs, operations, lead_times

Returns a .xlsx workbook with two sheets:
  Sheet 1 "Cost Summary"       — hierarchical view with Excel row groups.
  Sheet 2 "Components Detail"  — flat pivot-ready list, one row per usage.
"""

import io
import logging

from odoo import http
from odoo.http import content_disposition, request

_logger = logging.getLogger(__name__)

# ── Colour palette ────────────────────────────────────────────────────────────
_C = {
    "header_bg": "1F4E79",  # section header background (dark blue)
    "header_fg": "FFFFFF",  # section header foreground (white)
    "info_bg":   "D9D9D9",  # BOM info rows
    "cat_0":     "BDD7EE",  # category depth 0
    "cat_1":     "DDEBF7",  # category depth 1
    "cat_deep":  "EEF4FB",  # category depth 2+
    "product":   "F2F2F2",  # product rows
    "usage":     "FFFFFF",  # usage rows
    "wc":        "E2EFDA",  # workcenter rows
    "op":        "F4F9F5",  # operation rows
    "subtotal":  "FFF2CC",  # subtotal rows
    "total":     "FFE082",  # grand total row
}


# ── Style helpers ─────────────────────────────────────────────────────────────

def _fill(hex_color):
    """Solid fill from a hex colour string."""
    from openpyxl.styles import PatternFill  # noqa: PLC0415
    return PatternFill("solid", fgColor=hex_color)


def _font(bold=False, color="000000", size=9):
    from openpyxl.styles import Font  # noqa: PLC0415
    return Font(bold=bold, color=color, size=size)


def _align_right():
    from openpyxl.styles import Alignment  # noqa: PLC0415
    return Alignment(horizontal="right", vertical="center")


def _align_left():
    from openpyxl.styles import Alignment  # noqa: PLC0415
    return Alignment(horizontal="left", vertical="center")


def _align_center():
    from openpyxl.styles import Alignment  # noqa: PLC0415
    return Alignment(horizontal="center", vertical="center")


# ── Value helpers ─────────────────────────────────────────────────────────────

def _flt(value):
    """Return a rounded float or empty string for False/None."""
    if value is None or value is False:
        return ""
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return ""


def _pct(value):
    """Return e.g. '45.2%' or '' for missing values."""
    if value is None or value is False:
        return ""
    try:
        return "%.1f%%" % float(value)
    except (TypeError, ValueError):
        return ""


def _str(value):
    """Return value as string, empty string for None/False."""
    if value is None or value is False:
        return ""
    return str(value)


# ── Low-level row writer ──────────────────────────────────────────────────────

def _write_row(ws, row_idx, values, bg_color, bold=False, outline_level=0):
    """Write a data row, applying background colour and optional outline."""
    fill = _fill(bg_color)
    row_font = _font(bold=bold)
    # Right-align numeric columns (indices 4-onward, but only if the value
    # is a float/int; text columns stay left-aligned).
    for col_idx, val in enumerate(values, start=1):
        cell = ws.cell(row=row_idx, column=col_idx, value=val)
        cell.font = row_font
        cell.fill = fill
        if isinstance(val, (int, float)) and col_idx > 3:
            cell.alignment = _align_right()
        else:
            cell.alignment = _align_left()
    # Cap at Excel's maximum outline depth of 7.
    if outline_level:
        ws.row_dimensions[row_idx].outline_level = min(outline_level, 7)


def _write_info(ws, row_idx, label, value, col_count):
    """Write a BOM-info banner row (label in col A, value in col B)."""
    fill = _fill(_C["info_bg"])
    c = ws.cell(row=row_idx, column=1, value=label)
    c.font = _font(bold=True)
    c.fill = fill
    c.alignment = _align_left()
    c2 = ws.cell(row=row_idx, column=2, value=value)
    c2.font = _font()
    c2.fill = fill
    c2.alignment = _align_left()
    for col_idx in range(3, col_count + 1):
        ws.cell(row=row_idx, column=col_idx).fill = fill


def _write_section_header(ws, row_idx, title, col_count):
    """Write a full-width section header row."""
    fill = _fill(_C["header_bg"])
    for col_idx in range(1, col_count + 1):
        cell = ws.cell(row=row_idx, column=col_idx)
        cell.fill = fill
    c = ws.cell(row=row_idx, column=1, value=title)
    c.font = _font(bold=True, color=_C["header_fg"], size=10)
    c.alignment = _align_left()
    ws.row_dimensions[row_idx].height = 16


def _write_subtotal(ws, row_idx, label, col_count, ci,
                    bom_cost, bom_cost_usd, prod_cost, prod_cost_usd,
                    show_costs, has_usd, cur, usd):
    """Write a subtotal row."""
    vals = [""] * col_count
    vals[ci["Type"] - 1] = "Subtotal"
    vals[ci["Name"] - 1] = label
    if show_costs:
        vals[ci["BOM Cost (%s)" % cur] - 1] = _flt(bom_cost)
        if has_usd and "BOM Cost (%s)" % usd in ci:
            vals[ci["BOM Cost (%s)" % usd] - 1] = _flt(bom_cost_usd)
        if prod_cost is not None and "Product Cost (%s)" % cur in ci:
            vals[ci["Product Cost (%s)" % cur] - 1] = _flt(prod_cost)
        if prod_cost_usd is not None and has_usd and "Product Cost (%s)" % usd in ci:
            vals[ci["Product Cost (%s)" % usd] - 1] = _flt(prod_cost_usd)
    _write_row(ws, row_idx, vals, _C["subtotal"], bold=True, outline_level=0)
    return row_idx + 1


# ── Recursive category writer (Sheet 1) ──────────────────────────────────────

def _write_category_rows(ws, row, node, ci, cur, usd,
                         has_usd, show_costs, show_lead_times,
                         outline_base):
    """
    Recursively write category → product → usage rows for one tree node.

    :param outline_base: outline_level assigned to this category row.
                         Its products get outline_base+1, usages outline_base+2.
    """
    col_count = len(ci)
    depth = node.get("depth", 0)
    cat_colors = [_C["cat_0"], _C["cat_1"], _C["cat_deep"]]
    cat_color = cat_colors[min(depth, len(cat_colors) - 1)]
    indent = "    " * depth

    # Category row
    vals = [""] * col_count
    vals[ci["Level"] - 1] = depth
    vals[ci["Type"] - 1] = "Category"
    vals[ci["Name"] - 1] = indent + node["name"]
    vals[ci["%"] - 1] = _pct(node.get("percentage"))
    if show_costs:
        vals[ci["BOM Cost (%s)" % cur] - 1] = _flt(node.get("total"))
        if has_usd and "BOM Cost (%s)" % usd in ci:
            vals[ci["BOM Cost (%s)" % usd] - 1] = _flt(node.get("total_usd"))
        if "Product Cost (%s)" % cur in ci:
            vals[ci["Product Cost (%s)" % cur] - 1] = _flt(node.get("prod_cost_total"))
        if has_usd and "Product Cost (%s)" % usd in ci:
            vals[ci["Product Cost (%s)" % usd] - 1] = _flt(node.get("prod_cost_total_usd"))
    _write_row(ws, row, vals, cat_color, bold=True, outline_level=outline_base)
    row += 1

    # Recurse into child categories first
    for child in node.get("children", []):
        row = _write_category_rows(
            ws, row, child, ci, cur, usd,
            has_usd, show_costs, show_lead_times,
            outline_base=outline_base + 1,
        )

    # Products under this category
    for prod in node.get("products", []):
        usages = prod.get("usages", [])

        # Aggregate quantity (only if single UoM across all usages)
        uoms = {u.get("uom_name", "") for u in usages if u.get("uom_name")}
        if len(uoms) == 1:
            total_qty = _flt(sum(u.get("quantity", 0) for u in usages))
            uom_display = list(uoms)[0]
        elif len(uoms) > 1:
            total_qty = ""        # mixed UoMs → cannot aggregate
            uom_display = "—"
        else:
            total_qty = ""
            uom_display = ""

        prod_indent = "    " * (depth + 1)
        vals = [""] * col_count
        vals[ci["Level"] - 1] = depth + 1
        vals[ci["Type"] - 1] = "Product"
        vals[ci["Name"] - 1] = prod_indent + prod["name"]
        vals[ci["Qty / Duration"] - 1] = total_qty
        vals[ci["UoM"] - 1] = uom_display
        vals[ci["%"] - 1] = _pct(prod.get("percentage"))
        if show_costs:
            vals[ci["BOM Cost (%s)" % cur] - 1] = _flt(prod.get("total"))
            if has_usd and "BOM Cost (%s)" % usd in ci:
                vals[ci["BOM Cost (%s)" % usd] - 1] = _flt(prod.get("total_usd"))
            if "Product Cost (%s)" % cur in ci:
                vals[ci["Product Cost (%s)" % cur] - 1] = _flt(prod.get("prod_cost_total"))
            if has_usd and "Product Cost (%s)" % usd in ci:
                vals[ci["Product Cost (%s)" % usd] - 1] = _flt(prod.get("prod_cost_total_usd"))
        # Availability (always present columns)
        qa = prod.get("quantity_available")
        if qa is not False and qa is not None and "Free to Use" in ci:
            vals[ci["Free to Use"] - 1] = _flt(qa)
            vals[ci["On Hand"] - 1] = _flt(prod.get("quantity_on_hand"))
        if "Availability" in ci:
            vals[ci["Availability"] - 1] = _str(prod.get("availability_display"))

        _write_row(ws, row, vals, _C["product"], bold=False,
                   outline_level=outline_base + 1)
        row += 1

        # Usage rows
        for usage in usages:
            usage_indent = "    " * (depth + 2)
            parent_name = _str(usage.get("parent_name")) or "—"
            vals = [""] * col_count
            vals[ci["Level"] - 1] = depth + 2
            vals[ci["Type"] - 1] = "Usage"
            vals[ci["Name"] - 1] = usage_indent + parent_name
            vals[ci["Qty / Duration"] - 1] = _flt(usage.get("quantity"))
            vals[ci["UoM"] - 1] = _str(usage.get("uom_name"))
            vals[ci["%"] - 1] = _pct(usage.get("percentage"))
            if show_costs:
                vals[ci["BOM Cost (%s)" % cur] - 1] = _flt(usage.get("total"))
                if has_usd and "BOM Cost (%s)" % usd in ci:
                    vals[ci["BOM Cost (%s)" % usd] - 1] = _flt(usage.get("total_usd"))
                if "Product Cost (%s)" % cur in ci:
                    vals[ci["Product Cost (%s)" % cur] - 1] = _flt(usage.get("prod_cost"))
                if has_usd and "Product Cost (%s)" % usd in ci:
                    vals[ci["Product Cost (%s)" % usd] - 1] = _flt(usage.get("prod_cost_usd"))
            if show_lead_times:
                lt = usage.get("lead_time")
                vals[ci["Lead Time (days)"] - 1] = lt if lt is not False and lt is not None else ""
                route = _str(usage.get("route_name"))
                detail = _str(usage.get("route_detail"))
                if route and detail:
                    route = route + ": " + detail
                elif detail:
                    route = detail
                vals[ci["Route"] - 1] = route
            _write_row(ws, row, vals, _C["usage"], outline_level=outline_base + 2)
            row += 1

    return row


# ════════════════════════════ Sheet 1: Cost Summary ══════════════════════════

def _build_summary_sheet(ws, cs, cur, usd,
                         show_costs, show_operations, show_lead_times,
                         bom_name, quantity):
    """
    Write Sheet 1: hierarchical Cost Summary with Excel row groups.

    Row group convention (summaryBelow=False means summary row is ABOVE
    its children, so collapse buttons appear above the grouped block):

      outline_level 0 → always visible (category depth 0, workcenter)
      outline_level 1 → child of level-0 (category depth 1, product of depth-0)
      outline_level 2 → child of level-1 (category depth 2, product of depth-1,
                                          usage under depth-0 product)
      …and so on.
    """
    from openpyxl.utils import get_column_letter  # noqa: PLC0415

    has_usd = bool(cs and usd and any(
        w.get("total_usd") for w in cs.get("workcenters", [])
    ) or any(
        n.get("total_usd") for n in cs.get("categories", [])
    ))

    # ── Build ordered column list ─────────────────────────────────────────────
    cols = ["Level", "Type", "Name", "Qty / Duration", "UoM", "%"]
    if show_costs:
        cols.append("BOM Cost (%s)" % cur)
        if has_usd:
            cols.append("BOM Cost (%s)" % usd)
        cols.append("Product Cost (%s)" % cur)
        if has_usd:
            cols.append("Product Cost (%s)" % usd)
    if show_lead_times:
        cols += ["Lead Time (days)", "Route"]
    cols += ["Free to Use", "On Hand", "Availability"]

    col_count = len(cols)
    # ci: column name → 1-based column index
    ci = {name: idx + 1 for idx, name in enumerate(cols)}

    # ── Column widths ─────────────────────────────────────────────────────────
    ws.column_dimensions["A"].width = 7    # Level
    ws.column_dimensions["B"].width = 13   # Type
    ws.column_dimensions["C"].width = 46   # Name
    ws.column_dimensions["D"].width = 15   # Qty/Duration
    ws.column_dimensions["E"].width = 8    # UoM
    ws.column_dimensions["F"].width = 8    # %
    for i in range(7, col_count + 1):
        ws.column_dimensions[get_column_letter(i)].width = 16

    # Collapse buttons appear ABOVE their group (not below).
    ws.sheet_properties.outlinePr.summaryBelow = False

    row = 1

    # ── BOM info banner ───────────────────────────────────────────────────────
    _write_info(ws, row, "BOM", bom_name, col_count)
    row += 1
    _write_info(ws, row, "Quantity", str(quantity), col_count)
    row += 1
    row += 1  # blank separator

    # ── Column-header row ─────────────────────────────────────────────────────
    header_row = row
    from openpyxl.styles import Alignment  # noqa: PLC0415
    for col_idx, h in enumerate(cols, start=1):
        c = ws.cell(row=row, column=col_idx, value=h)
        c.font = _font(bold=True, color=_C["header_fg"])
        c.fill = _fill(_C["header_bg"])
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 26
    ws.freeze_panes = ws.cell(row=row + 1, column=1)
    row += 1

    # ── Components section ────────────────────────────────────────────────────
    if cs["categories"]:
        _write_section_header(ws, row, "▶  Components by Product Category", col_count)
        row += 1

        for node in cs["categories"]:
            row = _write_category_rows(
                ws, row, node, ci, cur, usd,
                has_usd, show_costs, show_lead_times,
                outline_base=0,
            )

        row = _write_subtotal(
            ws, row, "Subtotal Components", col_count, ci,
            bom_cost=cs["totals"]["components"],
            bom_cost_usd=cs["totals"].get("components_usd"),
            prod_cost=cs["totals"].get("prod_cost"),
            prod_cost_usd=cs["totals"].get("prod_cost_usd"),
            show_costs=show_costs, has_usd=has_usd, cur=cur, usd=usd,
        )
        row += 1  # blank separator

    # ── Operations section ────────────────────────────────────────────────────
    if show_operations and cs["workcenters"]:
        _write_section_header(ws, row, "▶  Operations by Work Center", col_count)
        row += 1

        for wc in cs["workcenters"]:
            # Workcenter header row (always visible → outline_level 0)
            vals = [""] * col_count
            vals[ci["Level"] - 1] = 0
            vals[ci["Type"] - 1] = "Workcenter"
            vals[ci["Name"] - 1] = wc["name"]
            vals[ci["Qty / Duration"] - 1] = _flt(wc.get("total_duration"))
            vals[ci["%"] - 1] = _pct(wc.get("percentage"))
            if show_costs:
                vals[ci["BOM Cost (%s)" % cur] - 1] = _flt(wc.get("total"))
                if has_usd and "BOM Cost (%s)" % usd in ci:
                    vals[ci["BOM Cost (%s)" % usd] - 1] = _flt(wc.get("total_usd"))
            _write_row(ws, row, vals, _C["wc"], bold=True, outline_level=0)
            row += 1

            for op in wc.get("items", []):
                op_name = _str(op.get("name"))
                if op.get("parent_name"):
                    op_name += "  ← " + _str(op["parent_name"])
                vals = [""] * col_count
                vals[ci["Level"] - 1] = 1
                vals[ci["Type"] - 1] = "Operation"
                vals[ci["Name"] - 1] = "        " + op_name
                vals[ci["Qty / Duration"] - 1] = _flt(op.get("duration"))
                vals[ci["%"] - 1] = _pct(op.get("percentage"))
                if show_costs:
                    vals[ci["BOM Cost (%s)" % cur] - 1] = _flt(op.get("total"))
                    if has_usd and "BOM Cost (%s)" % usd in ci:
                        vals[ci["BOM Cost (%s)" % usd] - 1] = _flt(op.get("total_usd"))
                if show_lead_times:
                    lt = op.get("lead_time")
                    vals[ci["Lead Time (days)"] - 1] = lt if lt is not False and lt is not None else ""
                    vals[ci["Route"] - 1] = _str(op.get("route_name"))
                _write_row(ws, row, vals, _C["op"], outline_level=1)
                row += 1

        row = _write_subtotal(
            ws, row, "Subtotal Operations", col_count, ci,
            bom_cost=cs["totals"]["operations"],
            bom_cost_usd=cs["totals"].get("operations_usd"),
            prod_cost=None,
            prod_cost_usd=None,
            show_costs=show_costs, has_usd=has_usd, cur=cur, usd=usd,
        )
        row += 1  # blank separator

    # ── Grand Total ───────────────────────────────────────────────────────────
    vals = [""] * col_count
    vals[ci["Type"] - 1] = "TOTAL"
    vals[ci["Name"] - 1] = "Grand Total  (Components + Operations)"
    if show_costs:
        vals[ci["BOM Cost (%s)" % cur] - 1] = _flt(cs["totals"]["total"])
        if has_usd and "BOM Cost (%s)" % usd in ci:
            vals[ci["BOM Cost (%s)" % usd] - 1] = _flt(cs["totals"].get("total_usd"))
    _write_row(ws, row, vals, _C["total"], bold=True)
    ws.row_dimensions[row].height = 15
    total_row = row
    row += 1

    # ── Auto-filter on header row ─────────────────────────────────────────────
    ws.auto_filter.ref = (
        "A%d:%s%d" % (header_row, get_column_letter(col_count), total_row)
    )


# ════════════════════════════ Sheet 2: Components Detail ═════════════════════

def _flatten_usages(cs):
    """
    Walk the category tree and yield one dict per component usage.

    :returns generator of dicts with keys:
        category_path, product_name, parent_name,
        quantity, uom_name, percentage,
        bom_cost, bom_cost_usd, prod_cost, prod_cost_usd,
        lead_time, route_name, route_detail, route_type,
        quantity_available, quantity_on_hand, availability_state, availability_display
    """
    def _walk(node, path_parts):
        path_parts = path_parts + [node["name"]]
        cat_path = " > ".join(path_parts)

        # Recurse into children first so rows are ordered depth-first
        for child in node.get("children", []):
            yield from _walk(child, path_parts)

        for prod in node.get("products", []):
            for usage in prod.get("usages", []):
                yield {
                    "category_path":       cat_path,
                    "product_name":        prod.get("name", ""),
                    "parent_name":         _str(usage.get("parent_name")),
                    "quantity":            _flt(usage.get("quantity")),
                    "uom_name":            _str(usage.get("uom_name")),
                    "percentage":          _pct(usage.get("percentage")),
                    "bom_cost":            _flt(usage.get("total")),
                    "bom_cost_usd":        _flt(usage.get("total_usd")),
                    "prod_cost":           _flt(usage.get("prod_cost")),
                    "prod_cost_usd":       _flt(usage.get("prod_cost_usd")),
                    "lead_time":           usage.get("lead_time"),
                    "route_name":          _str(usage.get("route_name")),
                    "route_detail":        _str(usage.get("route_detail")),
                    "route_type":          _str(usage.get("route_type")),
                    "quantity_available":  prod.get("quantity_available"),
                    "quantity_on_hand":    prod.get("quantity_on_hand"),
                    "availability_display": _str(prod.get("availability_display")),
                }

    for root_node in cs.get("categories", []):
        yield from _walk(root_node, [])


def _build_detail_sheet(ws, cs, cur, usd, show_lead_times):
    """
    Write Sheet 2: flat, pivot-ready component usage list.
    One data row per usage (component × parent-product pair).
    """
    from openpyxl.styles import Alignment  # noqa: PLC0415
    from openpyxl.utils import get_column_letter  # noqa: PLC0415

    has_usd = bool(usd and any(
        n.get("total_usd") for n in cs.get("categories", [])
    ))

    # ── Column definitions ────────────────────────────────────────────────────
    cols = [
        "Category",
        "Product",
        "Used In (Parent)",
        "Quantity",
        "UoM",
        "% of Components",
        "BOM Cost (%s)" % cur,
    ]
    if has_usd:
        cols.append("BOM Cost (%s)" % usd)
    cols.append("Product Cost (%s)" % cur)
    if has_usd:
        cols.append("Product Cost (%s)" % usd)
    if show_lead_times:
        cols += ["Lead Time (days)", "Route", "Route Detail", "Route Type"]
    cols += ["Free to Use", "On Hand", "Availability"]

    col_count = len(cols)
    ci = {name: idx + 1 for idx, name in enumerate(cols)}

    # ── Column widths ─────────────────────────────────────────────────────────
    ws.column_dimensions["A"].width = 36
    ws.column_dimensions["B"].width = 36
    ws.column_dimensions["C"].width = 36
    ws.column_dimensions["D"].width = 12
    ws.column_dimensions["E"].width = 8
    ws.column_dimensions["F"].width = 10
    for i in range(7, col_count + 1):
        ws.column_dimensions[get_column_letter(i)].width = 16

    # ── Header row ────────────────────────────────────────────────────────────
    header_row = 1
    for col_idx, h in enumerate(cols, start=1):
        c = ws.cell(row=header_row, column=col_idx, value=h)
        c.font = _font(bold=True, color=_C["header_fg"])
        c.fill = _fill(_C["header_bg"])
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[header_row].height = 26
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

    # ── Data rows ─────────────────────────────────────────────────────────────
    row = header_row + 1
    for item in _flatten_usages(cs):
        vals = [""] * col_count
        vals[ci["Category"] - 1] = item["category_path"]
        vals[ci["Product"] - 1] = item["product_name"]
        vals[ci["Used In (Parent)"] - 1] = item["parent_name"]
        vals[ci["Quantity"] - 1] = item["quantity"]
        vals[ci["UoM"] - 1] = item["uom_name"]
        vals[ci["% of Components"] - 1] = item["percentage"]
        vals[ci["BOM Cost (%s)" % cur] - 1] = item["bom_cost"]
        if has_usd and "BOM Cost (%s)" % usd in ci:
            vals[ci["BOM Cost (%s)" % usd] - 1] = item["bom_cost_usd"]
        vals[ci["Product Cost (%s)" % cur] - 1] = item["prod_cost"]
        if has_usd and "Product Cost (%s)" % usd in ci:
            vals[ci["Product Cost (%s)" % usd] - 1] = item["prod_cost_usd"]
        if show_lead_times:
            lt = item.get("lead_time")
            vals[ci["Lead Time (days)"] - 1] = lt if lt is not False and lt is not None else ""
            vals[ci["Route"] - 1] = item["route_name"]
            vals[ci["Route Detail"] - 1] = item["route_detail"]
            vals[ci["Route Type"] - 1] = item["route_type"]
        qa = item.get("quantity_available")
        if qa is not False and qa is not None and "Free to Use" in ci:
            vals[ci["Free to Use"] - 1] = _flt(qa)
            vals[ci["On Hand"] - 1] = _flt(item.get("quantity_on_hand"))
        vals[ci["Availability"] - 1] = item["availability_display"]

        _write_row(ws, row, vals, _C["usage"])
        row += 1

    # ── Auto-filter ───────────────────────────────────────────────────────────
    if row > header_row + 1:
        ws.auto_filter.ref = (
            "A%d:%s%d" % (header_row, get_column_letter(col_count), row - 1)
        )


# ════════════════════════════ Controller ═════════════════════════════════════

class BomCostSummaryXlsxController(http.Controller):

    @http.route(
        "/econovo/bom_cost_summary/export_xlsx",
        type="http",
        auth="user",
    )
    def export_xlsx(
        self,
        bom_id,
        quantity=None,
        variant=None,
        warehouse_id=None,
        costs="true",
        operations="true",
        lead_times="true",
        **_kw,
    ):
        """Generate and return a .xlsx for the BOM Cost Summary."""
        try:
            from openpyxl import Workbook  # noqa: PLC0415
        except ImportError:
            _logger.error(
                "econovo_mrp_bom_cost_summary: openpyxl is not installed; "
                "cannot generate XLSX export."
            )
            return request.make_response(
                "openpyxl is required for Excel export.", status=500
            )

        # ── Validate bom_id ───────────────────────────────────────────────────
        try:
            bom_id = int(bom_id)
        except (TypeError, ValueError):
            return request.make_response("Invalid bom_id.", status=400)

        bom = request.env["mrp.bom"].browse(bom_id)
        if not bom.exists():
            return request.make_response("BOM not found.", status=404)

        # ── Parse parameters ──────────────────────────────────────────────────
        qty = (
            float(quantity)
            if quantity and quantity not in ("false", "null")
            else (bom.product_qty or 1.0)
        )
        show_costs = str(costs).lower() not in ("false", "0")
        show_operations = str(operations).lower() not in ("false", "0")
        show_lead_times = str(lead_times).lower() not in ("false", "0")

        # ── Fetch BOM data ────────────────────────────────────────────────────
        bom_report = request.env["report.mrp.report_bom_structure"]
        if warehouse_id and warehouse_id not in ("false", "null"):
            bom_report = bom_report.with_context(warehouse=int(warehouse_id))

        variant_id = (
            int(variant)
            if variant and variant not in ("false", "null", "0")
            else False
        )
        raw = bom_report.get_html(
            bom_id=bom_id,
            searchQty=qty,
            searchVariant=variant_id,
        )
        bom_lines = raw.get("lines", {})
        secondary = raw.get("secondary_currency", False)

        report_model = request.env[
            "report.econovo_mrp_bom_cost_summary.report_cost_summary"
        ]
        cost_summary = report_model._compute_cost_summary(bom_lines, secondary)
        if not cost_summary:
            return request.make_response(
                "No cost data available for this BOM.", status=204
            )

        currency_name = bom.company_id.currency_id.name
        usd_name = secondary.get("name", "USD") if secondary else ""

        # ── Build workbook ────────────────────────────────────────────────────
        wb = Workbook()

        ws1 = wb.active
        ws1.title = "Cost Summary"
        _build_summary_sheet(
            ws1, cost_summary, currency_name, usd_name,
            show_costs, show_operations, show_lead_times,
            bom.display_name, qty,
        )

        ws2 = wb.create_sheet("Components Detail")
        _build_detail_sheet(
            ws2, cost_summary, currency_name, usd_name, show_lead_times,
        )

        # ── Serialize ─────────────────────────────────────────────────────────
        output = io.BytesIO()
        wb.save(output)
        xlsx_data = output.getvalue()

        safe_name = (
            bom.display_name
            .replace("/", "-")
            .replace("\\", "-")
            .replace(" ", "_")[:60]
        )
        filename = "BOM_Cost_Summary_%s.xlsx" % safe_name

        headers = [
            (
                "Content-Type",
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet",
            ),
            ("Content-Disposition", content_disposition(filename)),
        ]
        return request.make_response(xlsx_data, headers=headers)
