# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import re
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ComexTributeKeywordMapping(models.Model):
    """Configurable keyword-based fallback for tribute parsing.
    
    This model provides a text pattern matching fallback when invoice lines
    don't have a product or the product is not mapped.
    
    Example:
        Keyword "tasa estadística" (contains) → amount_statistics
        Keyword "perc.*iigg" (regex) → amount_income_tax
    
    Zero hardcoding - all keywords configurable from UI.
    """
    
    _name = 'comex.tribute.keyword.mapping'
    _description = 'COMEX Tribute Keyword Mapping'
    _order = 'priority desc, sequence, id'
    
    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Display order in list view.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, this mapping will not be used in parsing.",
    )
    priority = fields.Integer(
        string="Priority",
        default=10,
        help="Higher priority = checked first. Use for disambiguation when "
             "multiple patterns might match the same text.",
    )
    
    # Keyword/pattern to search
    name = fields.Char(
        string="Keyword/Pattern",
        required=True,
        help="Text to search in invoice line description (case-insensitive). "
             "Examples: 'DIE', 'Derecho de Importación', 'Tasa Estadística', "
             "'perc.*ganancias' (if using regex)",
    )
    
    # Match type
    match_type = fields.Selection(
        selection=[
            ('contains', 'Contains (anywhere in text)'),
            ('exact', 'Exact Match'),
            ('starts_with', 'Starts With'),
            ('ends_with', 'Ends With'),
            ('regex', 'Regular Expression'),
        ],
        string="Match Type",
        default='contains',
        required=True,
        help="How to match the keyword:\n"
             "- Contains: Keyword appears anywhere (most common)\n"
             "- Exact: Text must match exactly\n"
             "- Starts With: Text must start with keyword\n"
             "- Ends With: Text must end with keyword\n"
             "- Regex: Use Python regular expressions for complex patterns",
    )
    
    # Target field in customs_clearance
    tribute_field = fields.Selection(
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
        string="Tribute Field",
        required=True,
        help="Target field in Customs Clearance where amount will be accumulated.",
    )
    
    # Options
    stop_on_match = fields.Boolean(
        string="Stop on Match",
        default=True,
        help="If checked, stops checking other keywords after this one matches. "
             "Prevents double counting when multiple keywords might match.",
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
        help="Optional notes, examples, or documentation.",
    )
    
    # -------------------------------------------------------------------------
    # METHODS
    # -------------------------------------------------------------------------
    def check_match(self, text):
        """Check if text matches this keyword mapping.
        
        Args:
            text (str): Text to check (already lowercased)
            
        Returns:
            bool: True if matches, False otherwise
        """
        self.ensure_one()
        keyword = self.name.lower()
        
        if self.match_type == 'contains':
            return keyword in text
        elif self.match_type == 'exact':
            return text == keyword
        elif self.match_type == 'starts_with':
            return text.startswith(keyword)
        elif self.match_type == 'ends_with':
            return text.endswith(keyword)
        elif self.match_type == 'regex':
            try:
                return bool(re.search(keyword, text, re.IGNORECASE))
            except re.error:
                # Invalid regex - log warning and return False
                return False
        
        return False
    
    def name_get(self):
        """Display keyword → tribute field for better readability."""
        result = []
        for record in self:
            tribute_label = dict(self._fields['tribute_field'].selection).get(
                record.tribute_field, record.tribute_field
            )
            name = '"%s" (%s) → %s' % (
                record.name,
                record.match_type,
                tribute_label
            )
            result.append((record.id, name))
        return result
    
    @api.constrains('name', 'match_type')
    def _check_regex_valid(self):
        """Validate regex patterns."""
        for record in self:
            if record.match_type == 'regex':
                try:
                    re.compile(record.name, re.IGNORECASE)
                except re.error as e:
                    raise ValidationError(_(
                        "Invalid regular expression: %s\n\n"
                        "Error: %s"
                    ) % (record.name, str(e)))
