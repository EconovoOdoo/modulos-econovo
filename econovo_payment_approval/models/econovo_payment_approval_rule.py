from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval


class EconovoPaymentApprovalRule(models.Model):
    """Routing rules that map payment domain conditions to a responsible approver.

    Each rule specifies:
    - A domain (evaluated against account.payment) that selects which payments
      this rule applies to.
    - The user that receives the mail.activity when the domain matches.

    Rules are evaluated in sequence order; ALL matching rules generate an activity
    (multiple approvers can be required for a single payment).
    """

    _name = 'econovo.payment.approval.rule'
    _description = 'Payment Approval Routing Rule'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    domain = fields.Char(
        string='Payment Domain',
        default='[]',
        help=(
            'Odoo domain evaluated against account.payment records. '
            'The activity is created only when the payment matches this domain.'
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
