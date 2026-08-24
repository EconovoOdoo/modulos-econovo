# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    is_customer_repurchase = fields.Boolean(
        string="Repurchase from Customer",
        help="Source the receipts of this operation type from the customer location "
             "instead of the vendor location.\n\n"
             "Use it when buying back goods previously sold (for example equipment "
             "repurchased from a dealer), so the balance left by the original "
             "delivery is cleared and the serial number stops being recorded as "
             "delivered to a customer.")

    @api.constrains('code', 'is_customer_repurchase')
    def _check_is_customer_repurchase(self):
        for picking_type in self:
            if picking_type.is_customer_repurchase and picking_type.code != 'incoming':
                raise ValidationError(_(
                    "Operation type %s cannot be flagged as a repurchase from customer: "
                    "only receipts can take goods back from a customer location.",
                    picking_type.display_name))
