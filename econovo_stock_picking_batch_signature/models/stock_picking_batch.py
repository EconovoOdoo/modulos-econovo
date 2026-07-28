# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools import format_date


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    signature = fields.Image(
        'Signature', copy=False, attachment=True,
        help="Signature of the person taking custody of this batch (e.g. "
             "the carrier picking up all its transfers), not a per-customer "
             "proof of delivery.")
    signed_by = fields.Char('Signed By', copy=False)
    signature_date = fields.Datetime('Signature Date', copy=False)
    signature_date_display = fields.Char(compute='_compute_signature_date_display')

    @api.depends('signature_date')
    def _compute_signature_date_display(self):
        for batch in self:
            if batch.signature_date:
                batch.signature_date_display = format_date(
                    self.env, batch.signature_date, date_format='dd MMMM yyyy'
                )
            else:
                batch.signature_date_display = ''

    def write(self, vals):
        """Auto-stamp signature_date, and cascade the signature to every
        transfer in the batch.

        A Batch Transfer has no single customer of its own (it can group
        deliveries for different partners), so this represents a single
        custody handoff (e.g. a carrier picking up the whole batch) copied
        to every underlying stock.picking, not a per-customer proof of
        delivery.
        """
        if vals.get('signature') and 'signature_date' not in vals:
            vals['signature_date'] = fields.Datetime.now()
        res = super().write(vals)
        cascade_vals = {
            field_name: vals[field_name]
            for field_name in ('signature', 'signed_by', 'signature_date')
            if field_name in vals
        }
        if cascade_vals:
            for batch in self:
                if batch.picking_ids:
                    batch.picking_ids.write(cascade_vals)
        return res
