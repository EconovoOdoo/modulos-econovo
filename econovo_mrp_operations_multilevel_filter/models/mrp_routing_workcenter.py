# -*- coding: utf-8 -*-
from odoo import _, models


class MrpRoutingWorkcenter(models.Model):
    _inherit = 'mrp.routing.workcenter'

    def action_view_multilevel_operations(self):
        """Reopen the Operations list filtered to the selected BOM(s) and all their sub-BOMs, at any level."""
        boms = self.mapped('bom_id')
        bom_ids = boms._get_multilevel_bom_ids()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Multi-level Operations: %s', ', '.join(boms.mapped('display_name'))),
            'res_model': 'mrp.routing.workcenter',
            'view_mode': 'tree,form',
            'domain': [('bom_id', 'in', bom_ids)],
        }
