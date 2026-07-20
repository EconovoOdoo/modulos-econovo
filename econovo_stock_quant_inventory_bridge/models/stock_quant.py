# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    @api.model_create_multi
    def create(self, vals_list):
        quants = super().create(vals_list)
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        if active_model == 'stock.inventory' and active_id:
            inventory = self.env['stock.inventory'].browse(active_id)
            # stock_inventory's own create() override already refreshes
            # stock_quant_ids from _get_quants(), but our "preselected" mode
            # reads from preselected_quant_ids instead of a location/product
            # domain, so a quant created live from within an in-progress
            # "preselected" adjustment must be added to both fields
            # explicitly to show up immediately in that adjustment's count
            # screen.
            if inventory.exists() and inventory.product_selection == 'preselected':
                inventory.write({
                    'preselected_quant_ids': [(4, quant.id) for quant in quants],
                    'stock_quant_ids': [(4, quant.id) for quant in quants],
                })
        return quants
