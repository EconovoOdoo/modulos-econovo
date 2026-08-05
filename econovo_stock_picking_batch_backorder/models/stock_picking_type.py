# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    create_backorder_batch = fields.Boolean(
        'Batch Backorders', default=True,
        help="Value proposed on the backorder wizard when validating transfers "
             "belonging to a batch: the generated backorders are grouped into a "
             "new batch transfer.")
    backorder_batch_state = fields.Selection(
        [('draft', 'Draft'),
         ('in_progress', 'In Progress')],
        'Backorder Batch Status', default='draft', required=True,
        help="Status of the batch transfer created for the backorders.")
