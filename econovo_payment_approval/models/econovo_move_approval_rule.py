from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval


class EconovoMoveApprovalRule(models.Model):
    """Routing rules that map journal entry domain conditions to a responsible approver.

    Each rule specifies:
    - A domain (evaluated against account.move) that selects which entries
      this rule applies to.
    - The user that receives the mail.activity when the domain matches.

    Rules are evaluated in sequence order; ALL matching rules generate an activity.
    Only journal entries with move_type='entry' are considered.
    """

    _name = 'econovo.move.approval.rule'
    _description = 'Journal Entry Approval Routing Rule'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    domain = fields.Char(
        string='Entry Domain',
        default='[]',
        help=(
            'Odoo domain evaluated against account.move records. '
            'The activity is created only when the entry matches this domain. '
            'Include move_type="entry" to restrict to manual journal entries.'
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
