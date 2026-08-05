# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import models

# States accepted by `stock.picking.batch._sanity_check` for a draft batch.
BACKORDER_BATCHABLE_STATES = ('assigned', 'confirmed', 'draft', 'waiting')


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _create_backorder(self):
        backorders = super()._create_backorder()
        if self.env.context.get('econovo_create_backorder_batch'):
            backorders._create_backorder_batches()
        return backorders

    def _create_backorder_batches(self):
        """Group the backorders in `self` into a new batch per origin batch.

        Assigning the batch here, while the backorders are being created,
        makes this grouping take precedence over the Automatic Batches feature:
        `_find_auto_batch` returns early on transfers that already have a batch.
        """
        backorders_per_batch = defaultdict(lambda: self.env['stock.picking'])
        for backorder in self.filtered(lambda p: p.state in BACKORDER_BATCHABLE_STATES):
            origin_batch = backorder.backorder_id.batch_id
            if origin_batch:
                backorders_per_batch[origin_batch] |= backorder
        for origin_batch, backorders in backorders_per_batch.items():
            origin_batch._create_backorder_batch(backorders)
