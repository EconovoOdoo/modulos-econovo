from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    payment_priority = fields.Selection(
        selection=[
            ('low', 'Not a priority'),
            ('normal', 'Normal'),
            ('urgent', 'Urgent'),
        ],
        string='Payment Priority',
        default='normal',
        help="Urgency level used to prioritize payment processing.",
    )
