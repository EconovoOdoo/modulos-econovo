# -*- coding: utf-8 -*-

from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_fields_stock_barcode(self):
        """Add workcenter_id to the fields sent to the barcode app."""
        return super()._get_fields_stock_barcode() + ['workcenter_id']

    def _get_stock_barcode_data(self):
        """Include mrp.workcenter and mrp.plan records in the barcode data cache."""
        data = super()._get_stock_barcode_data()
        workcenters = self.mapped('workcenter_id')
        data['records']['mrp.workcenter'] = workcenters.read(['name', 'code'], load=False) if workcenters else []
        plans = self.move_ids._get_supply_production().plan_id
        data['records']['mrp.plan'] = plans.read(['name'], load=False) if plans else []
        return data


