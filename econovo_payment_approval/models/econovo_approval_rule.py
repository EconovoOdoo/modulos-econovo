from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval


class EconovoApprovalRule(models.Model):
    """Routing rules for activity-based approval of payments and journal entries.

    One rule set covers both account.payment and account.move (move_type='entry').
    The target_model field determines which records the rule applies to.

    Rules are evaluated in sequence order; ALL matching rules generate an activity
    (multiple approvers can be required for the same document).
    """

    _name = 'econovo.approval.rule'
    _description = 'Approval Routing Rule'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    target_model = fields.Selection(
        selection=[
            ('account.payment', 'Payment'),
            ('account.move', 'Journal Entry'),
        ],
        string='Applies To',
        required=True,
        default='account.payment',
        help='Model against which the domain is evaluated.',
    )
    domain = fields.Char(
        default='[]',
        help=(
            'Odoo domain evaluated against the target model records. '
            'The activity is created only when the record matches this domain.'
        ),
    )
    user_id = fields.Many2one(
        'res.users',
        string='Approver',
        required=True,
        help='User that receives the approval activity.',
    )
    note = fields.Text(
        string='Internal Notes',
        help='Optional explanation of the routing logic for this rule.',
    )

    @api.constrains('domain')
    def _check_domain(self):
        """Validate that the domain string is syntactically correct."""
        for rule in self:
            if rule.domain:
                try:
                    safe_eval(rule.domain, mode='eval')
                except Exception as e:
                    raise ValidationError(
                        _('Invalid domain for rule "%s": %s', rule.name, e)
                    ) from e
