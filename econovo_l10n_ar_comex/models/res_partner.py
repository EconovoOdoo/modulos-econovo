# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models


class ResPartner(models.Model):
    """Extend res.partner with COMEX-related flags."""

    _inherit = 'res.partner'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    is_customs_broker = fields.Boolean(
        string="Is Customs Broker",
        default=False,
        help="Check if this partner is a customs broker (Despachante de Aduana).",
    )
    is_freight_forwarder = fields.Boolean(
        string="Is Freight Forwarder",
        default=False,
        help="Check if this partner is a freight forwarder.",
    )
    is_shipping_line = fields.Boolean(
        string="Is Shipping Line",
        default=False,
        help="Check if this partner is a shipping line or carrier.",
    )
    customs_broker_license = fields.Char(
        string="Customs Broker License",
        help="Official license number from ARCA.",
    )

    # COMEX operations where this partner is supplier/customer
    comex_operation_ids = fields.One2many(
        'comex.operation',
        'partner_id',
        string="COMEX Operations",
    )
    comex_operation_count = fields.Integer(
        string="COMEX Operation Count",
        compute='_compute_comex_operation_count',
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    def _compute_comex_operation_count(self):
        for partner in self:
            partner.comex_operation_count = len(partner.comex_operation_ids)

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------
    def action_view_comex_operations(self):
        """Open related COMEX operations."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('COMEX Operations'),
            'res_model': 'comex.operation',
            'view_mode': 'tree,kanban,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
