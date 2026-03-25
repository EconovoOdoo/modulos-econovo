{
    'name': 'Econovo Payment Batch Approval',
    'version': '17.0.1.1.0',
    'category': 'Accounting',
    'summary': 'Bridges Studio Approval Rules with the Sumitec payment batch module',
    'description': """
Fixes the incompatibility between Studio Approval Rules on account.payment.action_post
and the Sumitec payment batch module (account_payment_batch_st).

Features:
- Ensures payment batches are created before Studio intercepts action_post, so the
  batch persists in context even when the tesorera's posting is blocked by approval rules.
- Adds "Aprobar Lote" button to the batch form that propagates the approval to every
  draft payment in the batch (creates studio.approval.entry for each applicable rule),
  then confirms all payments in a single call.
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'account',
        'account_payment_batch_st',
        'web_studio',
    ],
    'data': [
        'security/econovo_payment_batch_approval_groups.xml',
        'views/account_payment_batch_st_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
