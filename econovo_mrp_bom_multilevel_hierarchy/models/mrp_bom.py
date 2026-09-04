# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    has_sub_bom = fields.Boolean(
        string='Has Sub-BOMs',
        compute='_compute_has_sub_bom',
        help="Whether this BOM has at least one component with its own Bill of Materials.",
    )

    @api.depends('bom_line_ids.child_bom_id')
    def _compute_has_sub_bom(self):
        for bom in self:
            bom.has_sub_bom = bool(bom.bom_line_ids.child_bom_id)

    def action_view_bom_hierarchy_cascade(self):
        """Open the Bills of Materials list, in tree view, for this BOM and every sub-BOM used by its components, at any depth."""
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('mrp.mrp_bom_form_action')
        action['domain'] = [('id', 'in', self._get_multilevel_bom_ids())]
        return action
