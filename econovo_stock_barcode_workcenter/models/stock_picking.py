# -*- coding: utf-8 -*-

from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_fields_stock_barcode(self):
        """Add x_studio_workcenter_id to the fields sent to the barcode app."""
        fields = super()._get_fields_stock_barcode()
        if 'x_studio_workcenter_id' in self.env['stock.picking']._fields:
            fields.append('x_studio_workcenter_id')
        return fields

    def _get_stock_barcode_data(self):
        """Include mrp.workcenter and mrp.plan records in the barcode data cache."""
        data = super()._get_stock_barcode_data()
        if 'x_studio_workcenter_id' in self._fields:
            workcenter_ids = self.mapped('x_studio_workcenter_id')
            if workcenter_ids:
                data['records']['mrp.workcenter'] = workcenter_ids.read(
                    ['name', 'code'], load=False,
                )
            else:
                data['records']['mrp.workcenter'] = []
        plans = self.move_ids.production_plan_id
        data['records']['mrp.plan'] = plans.read(['name'], load=False) if plans else []
        return data

