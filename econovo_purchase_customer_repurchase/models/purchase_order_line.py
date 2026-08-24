# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
from odoo import models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        # The move source is hardcoded separately from the picking one, so it needs its own override.
        vals = super()._prepare_stock_move_vals(picking, price_unit, product_uom_qty, product_uom)
        source_location = self.order_id._get_customer_repurchase_location()
        if source_location:
            vals['location_id'] = source_location.id
        return vals
