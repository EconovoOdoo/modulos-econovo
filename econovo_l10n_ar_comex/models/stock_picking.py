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

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('comex_operation_id')
    def _compute_is_comex(self):
        for picking in self:
            picking.is_comex = bool(picking.comex_operation_id)
