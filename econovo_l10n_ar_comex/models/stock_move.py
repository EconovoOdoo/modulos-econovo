# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class StockMove(models.Model):
    """Extend stock.move with COMEX shipment link."""

    _inherit = 'stock.move'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    comex_shipment_id = fields.Many2one(
        'comex.shipment',
        string="COMEX Shipment",
        copy=True,
        index=True,
        help="COMEX shipment this move belongs to. Propagated through push rules.",
    )
    comex_operation_id = fields.Many2one(
        'comex.operation',
        string="COMEX Operation",
        copy=True,
        index=True,
        help="COMEX operation this move belongs to. Propagated through push rules.",
    )

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------
    def _assign_picking(self):
        """Override to propagate COMEX fields to the picking."""
        result = super()._assign_picking()
        # After picking is assigned, update COMEX fields on picking.
        # Use sudo() because COMEX fields have groups= restriction, but
        # this method can be called by any warehouse user processing moves.
        for move in self.sudo():
            if move.picking_id and (move.comex_shipment_id or move.comex_operation_id):
                vals = {}
                if move.comex_shipment_id and not move.picking_id.comex_shipment_id:
                    vals['comex_shipment_id'] = move.comex_shipment_id.id
                if move.comex_operation_id and not move.picking_id.comex_operation_id:
                    vals['comex_operation_id'] = move.comex_operation_id.id
                if vals:
                    move.picking_id.write(vals)
        return result
