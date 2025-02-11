# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Saneen K (<https://www.cybrosys.com>), J. Leonett
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    """Inherits purchase.order.line to add support for secondary UoM."""
    _inherit = 'purchase.order.line'

    secondary_uom_ids = fields.Many2many(
        'uom.uom', string="Secondary UoM Ids",
        help="All the secondary UoMs available for this product"
    )
    secondary_product_uom_id = fields.Many2one(
        'uom.uom', string='Secondary UoM',
        compute='_compute_secondary_product_uom', store=True, readonly=False,
        help="Select the Secondary UoM",
        domain="[('id', 'in', secondary_uom_ids)]"
    )
    secondary_product_uom_qty = fields.Float(
        string='Secondary Quantity',
        help="Secondary UoM Quantity", default=1
    )
    is_secondary_readonly = fields.Boolean(
        string="Is Secondary UoM",
        help="Check if the selected UoM is secondary; if yes, make it readonly"
    )

    @api.onchange('secondary_product_uom_id', 'secondary_product_uom_qty')
    def _onchange_secondary_product_uom_id(self):
        """Update product_qty based on the secondary UoM quantity."""
        all_uom = []
        if self.product_id.is_need_secondary_uom:
            self.is_secondary_readonly = True
            for uom in self.product_id.secondary_uom_ids:
                all_uom.append(uom.secondary_uom_id.id)
        if self.is_secondary_readonly:
            if self.secondary_product_uom_id.id in all_uom:
                primary_uom_ratio = self.env['secondary.uom.line'].search(
                    [('secondary_uom_id', '=', self.secondary_product_uom_id.id),
                     ('product_id', '=', self.product_id.id)]
                ).mapped('secondary_uom_ratio')
                converted_qty = primary_uom_ratio[0] * self.secondary_product_uom_qty
                self.product_qty = converted_qty

    @api.depends('product_id')
    def _compute_secondary_product_uom(self):
        """Compute default secondary UoM."""
        for rec in self:
            if not rec.product_uom or rec.product_id.uom_id.id != rec.secondary_product_uom_id.id:
                rec.secondary_product_uom_id = rec.product_id.uom_id
            all_secondary_uoms = rec.product_id.secondary_uom_ids.mapped('secondary_uom_id')
            if rec.product_id.is_need_secondary_uom and all_secondary_uoms:
                rec.write({
                    'secondary_uom_ids': [(6, 0, all_secondary_uoms.ids)]
                })
