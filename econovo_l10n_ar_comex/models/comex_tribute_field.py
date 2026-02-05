# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ComexTributeField(models.Model):
    """Master data for tribute field selection in configurations.
    
    This model provides a catalog of available tribute fields that can be
    used in invoice line configuration for customs clearance tribute invoices.
    """
    
    _name = 'comex.tribute.field'
    _description = 'COMEX Tribute Field Definition'
    _order = 'sequence, name'
    
    sequence = fields.Integer(
        default=10,
        help="Display order in lists and selections",
    )
    
    technical_name = fields.Selection(
        selection=[
            ('amount_duties', 'Import Duties (DIE)'),
            ('amount_statistics', 'Statistics Fee'),
            ('amount_vat', 'VAT'),
            ('amount_vat_additional', 'Additional VAT'),
            ('amount_income_tax', 'Income Tax Perception'),
            ('amount_gross_income', 'Gross Income Perception'),
            ('amount_taxes', 'Other Taxes'),
            ('amount_fees', 'Other Fees'),
        ],
        string="Field Name",
        required=True,
        help="Technical field name in comex.customs.clearance model",
    )
    
    name = fields.Char(
        string="Display Name",
        compute='_compute_name',
        store=True,
        help="Human-readable name for the tribute field",
    )
    
    @api.depends('technical_name')
    def _compute_name(self):
        """Get display name from selection."""
        selection_dict = dict(self._fields['technical_name'].selection)
        for record in self:
            record.name = selection_dict.get(record.technical_name, record.technical_name)
