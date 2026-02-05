# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AccountMove(models.Model):
    """Extend account.move to add COMEX operation and clearance links."""
    
    _inherit = 'account.move'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    comex_operation_ids = fields.Many2many(
        'comex.operation',
        string="COMEX Operations",
        help="COMEX operations linked to this invoice/bill",
        copy=False,
    )
    comex_clearance_ids = fields.One2many(
        'comex.customs.clearance',
        'vendor_bill_id',
        string="Customs Clearances",
        help="Customs clearances that use this vendor bill for tributes",
        copy=False,
    )
    comex_clearance_count = fields.Integer(
        string="Clearances Count",
        compute='_compute_comex_clearance_count',
        store=False,
    )
    is_comex_type_66 = fields.Boolean(
        string="Is Type 66 (Despacho)",
        compute='_compute_is_comex_type_66',
        store=False,
        help="True if this is a Document Type 66 (Despacho de Importación)",
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    def _compute_comex_clearance_count(self):
        """Count linked customs clearances."""
        for move in self:
            move.comex_clearance_count = len(move.comex_clearance_ids)

    def _compute_is_comex_type_66(self):
        """Check if document type is 66 (Despacho de Importación)."""
        for move in self:
            # Document Type 66 has code '66'
            move.is_comex_type_66 = (
                move.l10n_latam_document_type_id and 
                move.l10n_latam_document_type_id.code == '66'
            )

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------
    def action_view_comex_operations(self):
        """Open COMEX operations linked to this invoice."""
        self.ensure_one()
        action = self.env.ref('econovo_l10n_ar_comex.comex_operation_action').read()[0]
        if len(self.comex_operation_ids) > 1:
            action['domain'] = [('id', 'in', self.comex_operation_ids.ids)]
        elif len(self.comex_operation_ids) == 1:
            action['views'] = [(self.env.ref('econovo_l10n_ar_comex.comex_operation_view_form').id, 'form')]
            action['res_id'] = self.comex_operation_ids.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def action_view_comex_clearances(self):
        """Open customs clearances linked to this invoice."""
        self.ensure_one()
        action = self.env.ref('econovo_l10n_ar_comex.comex_customs_clearance_action').read()[0]
        if len(self.comex_clearance_ids) > 1:
            action['domain'] = [('id', 'in', self.comex_clearance_ids.ids)]
        elif len(self.comex_clearance_ids) == 1:
            action['views'] = [(self.env.ref('econovo_l10n_ar_comex.comex_customs_clearance_view_form').id, 'form')]
            action['res_id'] = self.comex_clearance_ids.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action
