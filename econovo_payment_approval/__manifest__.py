{
    'name': 'Econovo Payment Approval',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Payment',
    'summary': 'Activity-based approval workflow for outbound payments',
    'description': """
Replaces Studio Approval Rules for account.payment with a lightweight,
pure-Python approval workflow using mail.activity.

Features:
- Configurable routing rules (model: econovo.payment.approval.rule)
- One mail.activity per batch or per individual payment, assigned to the
  correct approver based on rule domain evaluation
- Automatic activity cleanup when payment is reset to draft or cancelled
- Rejection wizard: approver writes a reason, chatter is updated and the
  tesorero is notified via a new activity
- No dependency on web_studio, base.automation, or account_payment_batch_st
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'account',
        'mail',
    ],
    'data': [
        'security/econovo_payment_approval_groups.xml',
        'security/ir.model.access.csv',
        'data/mail_activity_data.xml',
        'data/payment_approval_rules.xml',
        'wizard/econovo_payment_reject_wizard_views.xml',
        'views/econovo_payment_approval_rule_views.xml',
        'views/account_payment_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
