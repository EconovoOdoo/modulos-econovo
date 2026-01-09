# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import models


class StockRule(models.Model):
    """Extend stock.rule to propagate COMEX fields in push rules."""

    _inherit = 'stock.rule'

    def _push_prepare_move_copy_values(self, move_to_copy, new_date):
        """Override to propagate COMEX fields to chained moves/pickings."""
        values = super()._push_prepare_move_copy_values(move_to_copy, new_date)
        
        # Propagate COMEX shipment and operation from source picking
        if move_to_copy.picking_id:
            source_picking = move_to_copy.picking_id
            if source_picking.comex_shipment_id:
                values['comex_shipment_id'] = source_picking.comex_shipment_id.id
            if source_picking.comex_operation_id:
                values['comex_operation_id'] = source_picking.comex_operation_id.id

        return values
