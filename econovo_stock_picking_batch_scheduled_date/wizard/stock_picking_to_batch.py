# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockPickingToBatch(models.TransientModel):
    _inherit = 'stock.picking.to.batch'

    scheduled_date = fields.Datetime(
        help="Scheduled date to set on the new batch transfer and on every "
             "transfer added to it. Leave empty to keep the batch's default "
             "(earliest scheduled date among its transfers).")

    def attach_pickings(self):
        res = super().attach_pickings()
        if self.mode == 'new' and self.scheduled_date:
            pickings = self.env['stock.picking'].browse(self.env.context.get('active_ids'))
            pickings.batch_id.scheduled_date = self.scheduled_date
            pickings.scheduled_date = self.scheduled_date
        return res
