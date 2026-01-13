# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ComexPaymentTiming(models.Model):
    """Payment timing options for international trade (COMEX).
    
    Defines when payment is due relative to shipment or document presentation.
    Common timings: Advance, At Sight, 30/60/90/180 days after shipment/sight.
    """

    _name = 'comex.payment.timing'
    _description = 'COMEX Payment Timing'
    _order = 'sequence, name'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Timing Name",
        required=True,
        translate=True,
        help="When payment is due (e.g., At Sight, 180 days)",
    )
    code = fields.Char(
        string="Code",
        required=True,
        help="Short code for the timing (e.g., SIGHT, 30D, 180D)",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order in which timings appear in lists",
    )
    active = fields.Boolean(
        default=True,
        help="Set to False to hide this timing without deleting it",
    )
    days = fields.Integer(
        string="Days",
        default=0,
        help="Number of days for payment (0 for advance/sight, positive for deferred)",
    )
    timing_type = fields.Selection([
        ('advance', 'Advance Payment'),
        ('sight', 'At Sight'),
        ('days', 'Deferred (Days)'),
    ], string="Timing Type",
       required=True,
       default='days',
       help="Type of payment timing")
    
    description = fields.Text(
        string="Description",
        translate=True,
        help="Detailed description of this payment timing",
    )

    # BCRA compliance
    bcra_max_days = fields.Integer(
        string="BCRA Max Days",
        help="Maximum days allowed by BCRA for MULC access (may vary by NCM)",
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'The timing code must be unique!'),
        ('days_positive', 'CHECK(days >= 0)', 'Days must be zero or positive!'),
    ]

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        """Display format: Name (Days if applicable)"""
        result = []
        for timing in self:
            if timing.timing_type == 'days' and timing.days > 0:
                name = f"{timing.name} ({timing.days}d)"
            else:
                name = timing.name
            result.append((timing.id, name))
        return result
