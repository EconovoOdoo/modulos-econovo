# -*- coding: utf-8 -*-

from odoo import http
from odoo.addons.stock_barcode.controllers.stock_barcode import StockBarcodeController


class StockBarcodeControllerInherit(StockBarcodeController):

    def _get_groups_data(self):
        groups = super()._get_groups_data()
        groups['show_quantity_to_count'] = http.request.env.company.show_quantity_to_count
        return groups
