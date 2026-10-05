# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import _, fields, models


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    subcontracting_chain_id = fields.Many2one(
        'mrp.subcontracting.chain',
        string='Subcontracting Chain',
        readonly=True,
        copy=False,
        index=True,
    )

    def action_view_subcontracting_chain(self):
        self.ensure_one()
        return {
            'name': _('Subcontracting Chain'),
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.subcontracting.chain',
            'view_mode': 'form',
            'res_id': self.subcontracting_chain_id.id,
        }
