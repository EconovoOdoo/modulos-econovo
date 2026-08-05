# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockBackorderConfirmation(models.TransientModel):
    _inherit = 'stock.backorder.confirmation'

    create_backorder_batch = fields.Boolean(
        "Create a new batch with the backorders",
        compute='_compute_create_backorder_batch', store=True, readonly=False)
    show_create_backorder_batch = fields.Boolean(
        compute='_compute_show_create_backorder_batch')

    @api.depends('pick_ids')
    def _compute_create_backorder_batch(self):
        for confirmation in self:
            batched_pickings = confirmation.pick_ids.filtered('batch_id')
            confirmation.create_backorder_batch = any(
                picking.picking_type_id.create_backorder_batch for picking in batched_pickings)

    @api.depends('pick_ids')
    def _compute_show_create_backorder_batch(self):
        for confirmation in self:
            confirmation.show_create_backorder_batch = bool(confirmation.pick_ids.batch_id)

    def process(self):
        return super(StockBackorderConfirmation, self.with_context(
            econovo_create_backorder_batch=any(self.mapped('create_backorder_batch')),
        )).process()
