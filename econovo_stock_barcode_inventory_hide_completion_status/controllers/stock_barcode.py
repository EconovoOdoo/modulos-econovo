# -*- coding: utf-8 -*-

from odoo import http
from odoo.addons.stock_barcode.controllers.stock_barcode import StockBarcodeController


class StockBarcodeControllerInherit(StockBarcodeController):

    def _get_groups_data(self):
        data = super()._get_groups_data()
        data["show_completion_status"] = http.request.env.company.show_completion_status
        return data
