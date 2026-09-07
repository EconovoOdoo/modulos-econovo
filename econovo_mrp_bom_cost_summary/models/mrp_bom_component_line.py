# -*- coding: utf-8 -*-
from odoo import api, fields, models

#: Same gate as the Excel export / interactive Cost Summary panel.
GROUP_SHOW_COST = (
    "hide_product_price_cost.hide_product_price_cost_group_user_show_product_cost"
)


class MrpBomComponentLine(models.TransientModel):
    """Flat, one-row-per-usage breakdown of a BOM's components.

    Populated on demand by ``mrp.bom.action_open_component_detail`` from the
    same ``cost_summary`` the interactive Cost Summary panel, the PDF and the
    Excel export already share (single source of truth), so this native tree
    view always agrees with the other three surfaces.

    Being transient, records are session-scoped and garbage-collected by the
    framework; the action recreates them fresh on every click.
    """

    _name = "mrp.bom.component.line"
    _description = "BOM Component Detail (flat)"
    _order = "bom_cost desc"

    bom_id = fields.Many2one("mrp.bom", string="Bill of Materials", required=True)
    categ_id = fields.Many2one("product.category", string="Category")
    product_id = fields.Many2one("product.product", string="Component")
    parent_product_id = fields.Many2one(
        "product.product", string="Used In (Parent)",
    )
    quantity = fields.Float(string="Quantity", digits="Product Unit of Measure")
    uom_name = fields.Char(string="UoM")
    percentage = fields.Float(string="% of Components", digits=(16, 2))
    currency_id = fields.Many2one("res.currency", string="Currency")
    secondary_currency_id = fields.Many2one(
        "res.currency", string="Secondary Currency",
    )
    bom_cost = fields.Monetary(
        string="BOM Cost", currency_field="currency_id",
        groups=GROUP_SHOW_COST,
    )
    bom_cost_usd = fields.Monetary(
        string="BOM Cost (Secondary)", currency_field="secondary_currency_id",
        groups=GROUP_SHOW_COST,
    )
    prod_cost = fields.Monetary(
        string="Product Cost", currency_field="currency_id",
        groups=GROUP_SHOW_COST,
    )
    prod_cost_usd = fields.Monetary(
        string="Product Cost (Secondary)", currency_field="secondary_currency_id",
        groups=GROUP_SHOW_COST,
    )
    lead_time = fields.Float(string="Lead Time (days)")
    route_name = fields.Char(string="Route")
    route_detail = fields.Char(string="Route Detail")
    route_type = fields.Char(string="Route Type")
    quantity_available = fields.Float(string="Free to Use")
    quantity_on_hand = fields.Float(string="On Hand")
    availability_display = fields.Char(string="Availability")

    @api.model
    def _prepare_from_bom(self, bom):
        """Build create-ready vals for every usage row of ``bom``.

        Reuses the exact ``cost_summary`` computation shared with the
        interactive UI/PDF/Excel, so this view can never drift from them.
        Cost fields are left at 0 for users without "Show Product Cost" -
        the field-level ``groups`` above additionally blocks reading them,
        this just avoids populating a value nobody is allowed to see.
        """
        bom.ensure_one()
        report = self.env["report.mrp.report_bom_structure"]
        report_model = self.env[
            "report.econovo_mrp_bom_cost_summary.report_cost_summary"
        ]
        raw = report.get_html(bom_id=bom.id, searchQty=bom.product_qty or 1)
        bom_lines = raw.get("lines", {})
        cs = bom_lines.get("cost_summary")
        if cs is None:
            cs = report_model._compute_cost_summary(
                bom_lines, raw.get("secondary_currency", False),
            )
        if not cs:
            return []

        show_costs = cs.get("show_costs")
        currency = bom.company_id.currency_id
        secondary = raw.get("secondary_currency") or {}
        secondary_currency = (
            self.env["res.currency"].browse(secondary["id"])
            if secondary.get("id") else currency
        )

        vals_list = []
        for row in report_model._iter_component_usages(cs):
            vals_list.append({
                "bom_id": bom.id,
                "categ_id": row["categ_id"],
                "product_id": row["product_id"],
                "parent_product_id": row["parent_product_id"],
                "quantity": row["quantity"] or 0.0,
                "uom_name": row["uom_name"] or "",
                "percentage": row["percentage"] or 0.0,
                "currency_id": currency.id,
                "secondary_currency_id": secondary_currency.id,
                "bom_cost": row["bom_cost"] if show_costs else 0.0,
                "bom_cost_usd": row["bom_cost_usd"] if show_costs else 0.0,
                "prod_cost": row["prod_cost"] if show_costs else 0.0,
                "prod_cost_usd": row["prod_cost_usd"] if show_costs else 0.0,
                "lead_time": row["lead_time"] or 0.0,
                "route_name": row["route_name"] or "",
                "route_detail": row["route_detail"] or "",
                "route_type": row["route_type"] or "",
                "quantity_available": row["quantity_available"] or 0.0,
                "quantity_on_hand": row["quantity_on_hand"] or 0.0,
                "availability_display": row["availability_display"] or "",
            })
        return vals_list
