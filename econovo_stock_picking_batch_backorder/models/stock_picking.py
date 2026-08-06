# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import models

# States accepted by `stock.picking.batch._sanity_check` for a draft batch.
BACKORDER_BATCHABLE_STATES = ('assigned', 'confirmed', 'draft', 'waiting')


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        # Snapshot origins before `stock_picking_batch` clears `batch_id` on
        # both the transfers being validated and the ones it detaches untouched.
        detached_pickings = self._get_econovo_detached_pickings()
        origin_batch_ids = self._get_econovo_backorder_batch_origins(detached_pickings)
        res = super().button_validate()
        if origin_batch_ids and any(picking.state == 'done' for picking in self):
            self._create_econovo_backorder_batches(detached_pickings, origin_batch_ids)
        return res

    def _get_econovo_detached_pickings(self):
        """Transfers the batch is about to remove from itself WITHOUT validating
        them (nothing at all was picked on them): the same picking, not a
        backorder, so it is never seen by `_create_backorder`.
        """
        if not self.env.context.get('econovo_create_backorder_batch'):
            return self.browse()
        detached_ids = self.env.context.get('pickings_to_detach') or []
        return self.browse(detached_ids).filtered(
            lambda p: p.batch_id and p.state not in ('done', 'cancel'))

    def _get_econovo_backorder_batch_origins(self, detached_pickings):
        """Map the id of every transfer in `self` and in `detached_pickings` to
        its CURRENT origin batch id, before validation clears it.
        """
        if not self.env.context.get('econovo_create_backorder_batch'):
            return {}
        origins = {picking.id: picking.batch_id.id for picking in self if picking.batch_id}
        for picking in detached_pickings:
            origins.setdefault(picking.id, picking.batch_id.id)
        return origins

    def _create_econovo_backorder_batches(self, detached_pickings, origin_batch_ids):
        """Group this validation's new backorders AND the never-validated
        (empty) transfers per origin batch, so nothing from a partially
        processed batch is left out of the resulting consolidation batch.

        Assigning the batch here, right after validation, makes this grouping
        take precedence over the Automatic Batches feature: `_find_auto_batch`
        returns early on transfers that already have a batch.
        """
        pickings_per_origin = defaultdict(lambda: self.browse())
        for picking in self:
            origin_batch_id = origin_batch_ids.get(picking.id)
            if not origin_batch_id:
                continue
            backorders = picking.backorder_ids.filtered(lambda p: p.state in BACKORDER_BATCHABLE_STATES)
            pickings_per_origin[origin_batch_id] |= backorders
        for picking in detached_pickings.filtered(lambda p: p.state in BACKORDER_BATCHABLE_STATES):
            origin_batch_id = origin_batch_ids.get(picking.id)
            if origin_batch_id:
                pickings_per_origin[origin_batch_id] |= picking
        origin_batches = self.env['stock.picking.batch'].browse(pickings_per_origin.keys())
        for origin_batch in origin_batches:
            pickings = pickings_per_origin[origin_batch.id]
            if pickings:
                origin_batch._create_backorder_batch(pickings)
