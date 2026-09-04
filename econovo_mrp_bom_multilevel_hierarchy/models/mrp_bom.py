# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


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

    def _get_descendant_bom_ids(self):
        """Return every sub-BOM used by this BOM's components, at any depth (this BOM itself is excluded)."""
        self.ensure_one()
        descendant_ids = set()
        boms_to_explode = self.bom_line_ids.child_bom_id
        while boms_to_explode:
            new_boms = boms_to_explode.filtered(lambda bom: bom.id != self.id and bom.id not in descendant_ids)
            descendant_ids.update(new_boms.ids)
            boms_to_explode = new_boms.bom_line_ids.child_bom_id
        return list(descendant_ids)

    def action_view_bom_hierarchy_cascade(self):
        """Open the Bills of Materials list, in tree view, for every sub-BOM used by this BOM's components, at any depth."""
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('mrp.mrp_bom_form_action')
        action['domain'] = [('id', 'in', self._get_descendant_bom_ids())]
        action['name'] = _('Sub-BOMs of %s', self.display_name)
        return action
