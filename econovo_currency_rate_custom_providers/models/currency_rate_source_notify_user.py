# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class CurrencyRateSourceNotifyUser(models.Model):
    _name = 'currency.rate.source.notify.user'
    _description = 'Currency Rate Source Notification User'
    _order = 'sequence, id'

    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    source_id = fields.Many2one(
        'currency.rate.source',
        string='Source',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='cascade',
    )
    force_email = fields.Boolean(
        string='Force Email',
        default=False,
        help='Send email regardless of user notification preferences',
    )
    notes = fields.Char(
        string='Notes',
        help='Optional notes about this notification recipient',
    )
    
    # Related fields for display
    user_email = fields.Char(
        related='user_id.email',
        string='Email',
        readonly=True,
    )
    user_company_ids = fields.Many2many(
        related='user_id.company_ids',
        string='Companies',
        readonly=True,
    )

    _sql_constraints = [
        ('unique_source_user', 
         'UNIQUE(source_id, user_id)', 
         'Each user can only be added once per source!'),
    ]
