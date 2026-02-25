# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class StockPicking(models.Model):
    """Extend stock.picking with COMEX operation and shipment links."""

    _inherit = 'stock.picking'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    comex_operation_id = fields.Many2one(
        'comex.operation',
        string="COMEX Operation",
        tracking=True,
        copy=False,
        index=True,
    )
    comex_shipment_id = fields.Many2one(
        'comex.shipment',
        string="COMEX Shipment",
        tracking=True,
        copy=False,
        index=True,
    )
    is_comex = fields.Boolean(
        string="Is COMEX",
        compute='_compute_is_comex',
        store=True,
    )

    # Related fields from shipment (for COMEX tab in form view)
    comex_shipment_bl = fields.Char(
        string="BL/AWB Number",
        related='comex_shipment_id.name',
    )
    comex_shipment_transport = fields.Selection(
        string="Transport Mode",
        related='comex_shipment_id.transport_mode',
    )
    comex_shipment_vessel = fields.Char(
        string="Vessel/Flight",
        related='comex_shipment_id.vessel_name',
    )
    comex_shipment_origin_port = fields.Many2one(
        string="Origin Port",
        related='comex_shipment_id.origin_port_id',
    )
    comex_shipment_destination_port = fields.Many2one(
        string="Destination Port",
        related='comex_shipment_id.destination_port_id',
    )
    comex_shipment_departure = fields.Date(
        string="Departure Date",
        related='comex_shipment_id.date_departure',
    )
    comex_shipment_eta = fields.Date(
        string="ETA",
        related='comex_shipment_id.date_eta',
    )
    comex_shipment_carrier = fields.Many2one(
        string="Carrier",
        related='comex_shipment_id.carrier_id',
    )
    comex_shipment_container_count = fields.Integer(
        string="Containers",
        related='comex_shipment_id.container_count',
        help="Number of shipping containers in this shipment",
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('comex_operation_id')
    def _compute_is_comex(self):
        for picking in self:
            picking.is_comex = bool(picking.comex_operation_id)

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------
    def _get_downstream_pickings_and_moves(self):
        """Follow move_dest_ids from this picking to find all downstream pickings.

        Starting from the moves in this picking, recursively follows
        move_dest_ids to collect every downstream picking and move.
        Does NOT include self in the result.

        Returns:
            tuple(stock.picking recordset, stock.move recordset)
        """
        all_moves = self.env['stock.move']
        all_pickings = self.env['stock.picking']
        source_moves = self.move_ids

        moves_to_check = source_moves
        while moves_to_check:
            next_moves = moves_to_check.mapped('move_dest_ids') - source_moves - all_moves
            if not next_moves:
                break
            all_moves |= next_moves
            all_pickings |= next_moves.picking_id
            moves_to_check = next_moves

        return all_pickings, all_moves

    def _propagate_comex_shipment(self, shipment_id):
        """Propagate comex_shipment_id to all downstream pickings and moves.

        Called when comex_shipment_id is set or changed on a picking.
        Follows the move chain (move_dest_ids) to update all downstream
        pickings and moves with the same shipment.

        Args:
            shipment_id: int or False - the comex.shipment ID to set.
        """
        for picking in self.sudo():
            downstream_pickings, downstream_moves = picking._get_downstream_pickings_and_moves()
            if not downstream_pickings and not downstream_moves:
                continue

            if shipment_id:
                # Set shipment on downstream records that don't have it yet
                pickings_to_update = downstream_pickings.filtered(
                    lambda p: p.comex_shipment_id.id != shipment_id
                )
                if pickings_to_update:
                    pickings_to_update.write({'comex_shipment_id': shipment_id})
                moves_to_update = downstream_moves.filtered(
                    lambda m: m.comex_shipment_id.id != shipment_id
                )
                if moves_to_update:
                    moves_to_update.write({'comex_shipment_id': shipment_id})
            else:
                # Clear shipment from downstream records
                pickings_to_clear = downstream_pickings.filtered('comex_shipment_id')
                if pickings_to_clear:
                    pickings_to_clear.write({'comex_shipment_id': False})
                moves_to_clear = downstream_moves.filtered('comex_shipment_id')
                if moves_to_clear:
                    moves_to_clear.write({'comex_shipment_id': False})

            # Also update moves in the source picking itself
            if shipment_id:
                source_moves = picking.move_ids.filtered(
                    lambda m: m.comex_shipment_id.id != shipment_id
                )
                if source_moves:
                    source_moves.write({'comex_shipment_id': shipment_id})
            else:
                source_moves = picking.move_ids.filtered('comex_shipment_id')
                if source_moves:
                    source_moves.write({'comex_shipment_id': False})

    # -------------------------------------------------------------------------
    # OVERRIDE METHODS
    # -------------------------------------------------------------------------
    def write(self, vals):
        """Override to propagate comex_shipment_id through the move chain.

        When a user sets or changes comex_shipment_id on any picking,
        the value is propagated to all downstream pickings and moves
        via move_dest_ids, so the entire COMEX chain stays consistent.
        """
        res = super().write(vals)

        if 'comex_shipment_id' in vals and not self.env.context.get('skip_shipment_propagation'):
            shipment_id = vals['comex_shipment_id']
            self.with_context(skip_shipment_propagation=True)._propagate_comex_shipment(shipment_id)

        return res
