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
