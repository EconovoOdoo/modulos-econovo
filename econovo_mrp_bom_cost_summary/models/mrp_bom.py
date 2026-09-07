# -*- coding: utf-8 -*-
from odoo import _, models


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    def action_open_component_detail(self):
        """Open a flat, native list of every component usage in this BOM -
        one row per component x immediate parent, matching the Excel
        "Components Detail" sheet but filterable/groupable/sortable on
        screen instead of only in a downloaded file.
        """
        self.ensure_one()
        line_model = self.env["mrp.bom.component.line"]
        vals_list = line_model._prepare_from_bom(self)
        lines = line_model.create(vals_list) if vals_list else line_model

        action = self.env["ir.actions.actions"]._for_xml_id(
            "econovo_mrp_bom_cost_summary.action_mrp_bom_component_line"
        )
        action["domain"] = [("id", "in", lines.ids)]
        action["display_name"] = _("Components - %s", self.display_name)
        return action
