# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
from odoo import models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _prepare_picking(self):
        vals = super()._prepare_picking()
        source_location = self._get_customer_repurchase_location()
        if source_location:
            vals['location_id'] = source_location.id
        return vals

    def _get_customer_repurchase_location(self):
        """Customer location to take the goods back from, empty when not a repurchase.

        Core sources every purchase receipt from `property_stock_supplier`, which
        leaves the balance of the original delivery stranded in the customer
        location. Sourcing a repurchase from the customer location instead makes
        both sides net out.
        """
        self.ensure_one()
        if not self.picking_type_id.is_customer_repurchase:
            return self.env['stock.location']
        location = self.partner_id.property_stock_customer
        if not location:
            location, dummy = self.env['stock.warehouse']._get_partner_locations()
        return location
