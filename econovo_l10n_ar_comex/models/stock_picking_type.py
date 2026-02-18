# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockPickingType(models.Model):
    """Extend stock.picking.type with COMEX semantic flags."""

    _inherit = 'stock.picking.type'

    is_comex_import = fields.Boolean(
        string="COMEX Import",
        default=False,
        help="Mark this operation type as part of the COMEX import chain. "
             "Only flagged types appear in the COMEX default picking type setting.",
    )
    is_comex_export = fields.Boolean(
        string="COMEX Export",
        default=False,
        help="Mark this operation type as part of the COMEX export chain.",
    )
