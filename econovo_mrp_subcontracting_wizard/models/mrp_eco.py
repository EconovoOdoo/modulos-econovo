# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import fields, models


class MrpEco(models.Model):
    _inherit = 'mrp.eco'

    subcontracting_chain_id = fields.Many2one(
        'mrp.subcontracting.chain',
        string='Subcontracting Chain',
        readonly=True,
        copy=False,
        index=True,
        help='Chain whose externalization or internalization is registered by this '
             'Engineering Change Order.',
    )

    def action_apply(self):
        res = super().action_apply()
        # The chain is built on the BoM revision, so its extra records stay archived until
        # the change actually reaches production.
        self.filtered(
            lambda eco: eco.subcontracting_chain_id and eco.state == 'done'
        ).subcontracting_chain_id._on_eco_applied()
        return res
