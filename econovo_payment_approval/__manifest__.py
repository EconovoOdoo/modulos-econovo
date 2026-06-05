{
    'name': 'Econovo Payment Approval',
    'version': '17.0.2.0.0',
    'category': 'Accounting/Payment',
    'summary': 'Activity-based approval workflow for outbound payments and journal entries',
    'description': """
Econovo Payment Approval
========================

Replaces Studio Approval Rules for ``account.payment`` and ``account.move``
with a lightweight, pure-Python approval workflow using ``mail.activity``.

Features
--------
* **Unified routing rules** (model: ``econovo.approval.rule``) covering both
  outbound payments and manual journal entries.  Rules are evaluated in
  sequence order; every matching rule generates a separate activity (multiple
  approvers can be required for the same document).
* **Priority stars** on payments and journal entries (Normal / Alta / Muy Alta /
  Urgente) so the tesorero / contable can flag urgency before approval.
* **Automatic activity creation** on ``action_post``:
  - ``account.payment`` → activity type "Aprobar Pago"
  - ``account.move`` (move_type='entry') → activity type "Aprobar Asiento"
* **Approve / Reject buttons** on the form view (posted + pending activity,
  approvers group only).  "Aprobar" marks the activity done and records the
  approver in a read-only field.  "Rechazar" opens a wizard that posts a
  chatter note and creates a corrective activity for the document creator.
* **Mass approve** from the list view Action dropdown (server action bound to
  the list, restricted to approvers group) — select multiple records and
  approve all in one click.
* **"Aprobado por"** read-only field on both payments and journal entries;
  cleared automatically when the document is reset to draft.
* No dependency on ``web_studio``, ``base.automation``, or batch-payment modules.

Security groups
---------------
* **Aprobadores de Pagos** (``grp_aprobadores_pago``): can see and click the
  "Rechazar Pago" button on posted payments.

Configuration
-------------
Accounting → Configuration → Reglas de Aprobación
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'account',
        'mail',
        'account_payment_batch_st',
    ],
    'data': [
        'security/econovo_payment_approval_groups.xml',
        'security/ir.model.access.csv',
        'data/mail_activity_data.xml',
        'data/approval_rules.xml',
        'wizard/econovo_payment_reject_wizard_views.xml',
        'views/econovo_approval_rule_views.xml',
        'views/account_payment_views.xml',
        'views/account_move_views.xml',
        'views/account_payment_batch_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
