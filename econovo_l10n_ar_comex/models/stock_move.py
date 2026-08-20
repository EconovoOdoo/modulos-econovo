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
    comex_product_line_id = fields.Many2one(
        'comex.operation.product.line',
        string="COMEX Product Line",
        copy=True,
        index='btree_not_null',
        ondelete='set null',
        help="COMEX product line these units belong to. Propagated through push rules "
             "so the stock can be located per line along the whole COMEX chain.",
    )

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------
    @api.model
    def _prepare_merge_moves_distinct_fields(self):
        """Never merge moves belonging to different COMEX product lines."""
        return super()._prepare_merge_moves_distinct_fields() + ['comex_product_line_id']

    def _action_done(self, cancel_backorder=False):
        """Refresh the located stock of the COMEX lines these units belong to."""
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        moves._refresh_comex_stock_position()
        return moves

    def _refresh_comex_stock_position(self):
        """Find the COMEX lines impacted by these moves and refresh their position.

        Lots are looked up as well, so a manual relocation through
        `stock.lot.location_id` or a delivery booked outside the COMEX chain is
        picked up too.
        """
        ProductLine = self.env['comex.operation.product.line'].sudo()
        lines = self.sudo().comex_product_line_id

        lots = self.sudo().move_line_ids.lot_id
        if lots and ProductLine.search_count([('product_id', 'in', lots.product_id.ids)], limit=1):
            tracked_move_lines = self.env['stock.move.line'].sudo().search([
                ('lot_id', 'in', lots.ids),
                ('move_id.comex_product_line_id', '!=', False),
            ])
            lines |= tracked_move_lines.move_id.comex_product_line_id

        if lines:
            lines._refresh_stock_position_cache()

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
