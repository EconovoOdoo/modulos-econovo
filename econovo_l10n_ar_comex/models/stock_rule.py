# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import models


class StockRule(models.Model):
    """Extend stock.rule to propagate COMEX fields in push rules."""

    _inherit = 'stock.rule'

    def _push_prepare_move_copy_values(self, move_to_copy, new_date):
        """Override to propagate COMEX fields to chained moves/pickings.

        Reads comex_operation_id and comex_shipment_id from the source
        move first (set during _link_pickings_to_comex_operation), then
        falls back to the source picking.  This covers the case where
        comex_operation_id was set on moves but not yet on the picking
        (e.g. during button_confirm before _link_pickings finishes).
        """
        values = super()._push_prepare_move_copy_values(move_to_copy, new_date)

        # Use sudo() because COMEX fields may have groups= restriction,
        # but push rules can be triggered by any warehouse user.
        move_sudo = move_to_copy.sudo()
        source_picking = move_sudo.picking_id

        # Shipment: move first, then picking
        shipment = move_sudo.comex_shipment_id
        if not shipment and source_picking:
            shipment = source_picking.comex_shipment_id
        if shipment:
            values['comex_shipment_id'] = shipment.id

        # Operation: move first, then picking
        operation = move_sudo.comex_operation_id
        if not operation and source_picking:
            operation = source_picking.comex_operation_id
        if operation:
            values['comex_operation_id'] = operation.id

        return values
