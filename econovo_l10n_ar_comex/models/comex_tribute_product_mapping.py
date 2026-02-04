# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ComexTributeProductMapping(models.Model):
    """Configurable mapping between products and customs tribute fields.
    
    This model allows users to configure which products in Type 66 invoices
    should be parsed to which tribute amount fields in customs_clearance.
    
    Example:
        Product "DIE - Derecho de Importación" → amount_duties
        Product "Tasa de Estadística" → amount_statistics
    
    Zero hardcoding - all mappings configurable from UI.
    """
    
    _name = 'comex.tribute.product.mapping'
    _description = 'COMEX Tribute Product Mapping'
    _order = 'sequence, id'
    
    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order of processing. Lower sequence = higher priority.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, this mapping will not be used in parsing.",
    )
    
    # Product to recognize
    product_id = fields.Many2one(
        'product.product',
        string="Product",
        required=True,
        domain="[('detailed_type', '=', 'service')]",
        help="Product to identify in Type 66 invoice lines. "
             "Typically a service product like 'DIE', 'Tasa Estadística', etc.",
    )
    
    # Target field in customs_clearance
    tribute_field_id = fields.Many2one(
        'comex.tribute.field',
        string="Tribute Field",
        required=True,
        help="Target field in Customs Clearance where amount will be accumulated. "
             "Multiple products can map to the same field (amounts will be summed).",
    )
    
    # Multi-company support
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        default=lambda self: self.env.company,
        help="Leave empty to apply to all companies.",
    )
    
    # Documentation
    notes = fields.Text(
        string="Internal Notes",
        help="Optional notes for documentation purposes.",
    )
    
    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains('product_id', 'company_id')
    def _check_unique_product(self):
        """Ensure product is not duplicated within same company."""
        for record in self:
            domain = [
                ('product_id', '=', record.product_id.id),
                ('id', '!=', record.id),
            ]
            if record.company_id:
                domain.append(('company_id', '=', record.company_id.id))
            else:
                domain.append(('company_id', '=', False))
            
            if self.search_count(domain) > 0:
                raise ValidationError(_(
                    "Product '%s' is already mapped in this company. "
                    "Each product can only have one mapping per company."
                ) % record.product_id.display_name)
    
    # -------------------------------------------------------------------------
    # METHODS
    # -------------------------------------------------------------------------
    def name_get(self):
        """Display product name → tribute field for better readability."""
        result = []
        for record in self:
            name = '%s → %s' % (
                record.product_id.display_name,
                record.tribute_field_id.display_name if record.tribute_field_id else 'N/A'
            )
            result.append((record.id, name))
        return result
