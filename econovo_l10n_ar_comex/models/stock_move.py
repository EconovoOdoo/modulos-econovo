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
        related='picking_id.comex_shipment_id',
        store=True,
        index=True,
    )
    comex_operation_id = fields.Many2one(
        'comex.operation',
        string="COMEX Operation",
        related='picking_id.comex_operation_id',
        store=True,
        index=True,
    )
