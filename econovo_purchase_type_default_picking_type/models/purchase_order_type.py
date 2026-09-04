# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PurchaseOrderType(models.Model):
    _inherit = 'purchase.order.type'

    picking_type_id = fields.Many2one(
        comodel_name='stock.picking.type',
        string='Deliver To',
        domain="[('code', '=', 'incoming'), ('company_id', '=', company_id)]",
        help="Receipt operation type preset onto every purchase order using this "
             "type. Left empty, the order keeps computing its usual default "
             "operation type.\n\n"
             "Only available on types restricted to a single Company, since an "
             "operation type always belongs to one company.")

    @api.constrains('company_id', 'picking_type_id')
    def _check_picking_type_company(self):
        for order_type in self:
            if not order_type.picking_type_id:
                continue
            if not order_type.company_id:
                raise ValidationError(_(
                    "Type %s cannot preset a Deliver To operation type while shared "
                    "across companies: restrict it to a single Company first.",
                    order_type.display_name))
            if order_type.picking_type_id.company_id != order_type.company_id:
                raise ValidationError(_(
                    "Type %s's preset Deliver To must belong to the same Company as "
                    "the type itself.",
                    order_type.display_name))
