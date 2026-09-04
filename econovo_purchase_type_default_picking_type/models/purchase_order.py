# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.onchange('order_type')
    def onchange_order_type(self):
        super().onchange_order_type()
        for order in self:
            preset_picking_type = order.order_type.picking_type_id
            if preset_picking_type and preset_picking_type.company_id == order.company_id:
                order.picking_type_id = preset_picking_type.id
