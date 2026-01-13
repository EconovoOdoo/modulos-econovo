# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ComexPaymentInstrument(models.Model):
    """Payment instruments for international trade (COMEX).
    
    Based on ICC standards and international trade practices.
    Common instruments: TT (Wire Transfer), L/C (Letter of Credit),
    D/P (Documents against Payment), D/A (Documents against Acceptance).
    """

    _name = 'comex.payment.instrument'
    _description = 'COMEX Payment Instrument'
    _order = 'sequence, name'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Instrument Name",
        required=True,
        translate=True,
        help="Name of the payment instrument (e.g., Letter of Credit, TT)",
    )
    code = fields.Char(
        string="Code",
        required=True,
        help="Short code for the instrument (e.g., LC, TT, DP)",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order in which instruments appear in lists",
    )
    active = fields.Boolean(
        default=True,
        help="Set to False to hide this instrument without deleting it",
    )
    description = fields.Text(
        string="Description",
        translate=True,
        help="Detailed description of when to use this payment instrument",
    )
    
    # Risk and cost indicators
    risk_level = fields.Selection([
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
    ], string="Risk Level",
       help="Risk level for the importer when using this instrument")
    
    bank_intervention = fields.Boolean(
        string="Bank Intervention",
        default=False,
        help="Whether a bank acts as intermediary/guarantor",
    )
    
    typical_cost_pct = fields.Float(
        string="Typical Cost (%)",
        digits=(5, 3),
        help="Typical bank commission as percentage of FOB value (e.g., 0.15% for L/C)",
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'The instrument code must be unique!'),
    ]

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        """Display format: Code - Name"""
        result = []
        for instrument in self:
            name = f"{instrument.code} - {instrument.name}"
            result.append((instrument.id, name))
        return result
