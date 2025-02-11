# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Saneen K (<https://www.cybrosys.com>)
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
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SecondaryUomLine(models.Model):
    """Model Class for Secondary Uom Line
    This class represents the secondary unit of measure (UOM) line in the
    system.
    It is designed to store information related to secondary UOMs."""
    _name = "secondary.uom.line"
    _description = "Secondary Uom Line"

    secondary_uom_id = fields.Many2one(
        'uom.uom',
        string='Secondary UoM',
        help="Select the Secondary UoM",
        required=True
    )
    product_id = fields.Many2one(
        'product.product',
        readonly=True,
        string="Product",
        help="Product having the Secondary UOM"
    )
    secondary_uom_ratio = fields.Float(
        string='Secondary UoM Ratio',
        help="Choose the ratio with the base Unit of Measure."
    )
    example_ratio = fields.Char(
        string='Ratio',
        compute="_compute_example_ratio",
        store=True,
        help="Ratio of base UOM and the secondary UOM"
    )

    @api.depends('secondary_uom_id', 'secondary_uom_ratio', 'product_id.uom_id')
    def _compute_example_ratio(self):
        """Compute the example ratio dynamically based on related fields."""
        for record in self:
            if record.secondary_uom_id and record.secondary_uom_ratio and record.product_id.uom_id:
                record.example_ratio = (
                    f"1 {record.secondary_uom_id.name} = "
                    f"{record.secondary_uom_ratio} {record.product_id.uom_id.name}"
                )
            else:
                record.example_ratio = ""

    @api.onchange('secondary_uom_id', 'secondary_uom_ratio')
    def _onchange_secondary_uom_id(self):
        """Check if the selected secondary UOM is already included in the UOM list."""
        if self._context.get('params'):
            sec_uom_ids = self.env['product.template'].browse(
                self._context.get('params').get('id')
            ).secondary_uom_ids.mapped('secondary_uom_id.id')
            if self.secondary_uom_id.id in sec_uom_ids:
                raise ValidationError(
                    _('This Unit of Measure already exists in the secondary UOM list. '
                      'Please select another UOM for secondary UOM.')
                )
