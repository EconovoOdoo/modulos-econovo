{
    'name': 'Econovo Payment Approval',
    'version': '17.0.3.0.0',
    'category': 'Accounting/Payment',
    'summary': 'Activity-based approval workflow for outbound payments and journal entries',
    'description': """
Econovo Payment Approval
========================

Replaces Studio Approval Rules for ``account.payment`` and ``account.move``
with a lightweight, pure-Python approval workflow using ``mail.activity``.

Features
--------
* **Unified routing rules** (``econovo.approval.rule``) covering both outbound
  payments and manual journal entries.  Rules are evaluated in sequence order;
  every matching rule generates a separate activity (multiple approvers can be
  required for the same document).
* **Batch-aware amount routing** (``effective_approval_amount``): when a payment
  belongs to a Sumitec batch (``account.payment.batch.st``), approval rules are
  evaluated against the *batch total* rather than the individual payment amount.
  This prevents the edge case where each individual payment in a 5M batch is
  below the 1M threshold and would be routed to Nacho instead of Fabricio.
* **Priority stars** on payments and journal entries (Normal / Alta / Muy Alta /
  Urgente) so the tesorero / contable can flag urgency before approval.
* **Automatic activity creation** on ``action_post``:
  - ``account.payment`` → activity type "Revisar Pago" (warning)
  - ``account.move`` (move_type='entry') → activity type "Aprobar Asiento"
* **Approve / Reject buttons** in the form *and* list-view header (posted +
  pending activity, approvers group only).  "Aprobar" marks the activity done
  and records the approver.  "Rechazar" opens a wizard that posts a chatter
  note and creates a corrective activity for the document creator.
* **"Aprobado por"** read-only field; cleared automatically on reset to draft.
* No dependency on ``web_studio`` or ``base.automation``.

Routing rules — payments
------------------------
=====================  =========  =============================================
Rule                   Approver   Condition
=====================  =========  =============================================
10 — Mayores >1M ARS   Fabricio   effective_approval_amount > 1 000 000
20 — Menores ≤1M ARS   Nacho      effective_approval_amount ≤ 1 000 000
30 — Buenos Aires      Nacho      journal company = BA or created by Lourdes
40 — Exterior FX       Fabricio   currency != ARS
50 — Agrovial Comex    Fabricio   created by Barisone or Monastra
=====================  =========  =============================================

Routing rules — journal entries
--------------------------------
Applies only to ``move_type='entry'`` moves that touch one of 33 monitored
account codes (loans, municipal taxes, IIBB, VAT, payroll, union dues).

=====================  =========  =============================================
Rule                   Approver   Condition
=====================  =========  =============================================
60 — Mayores ≥1M ARS   Fabricio   amount_total >= 1 000 000
70 — Menores <1M ARS   Nacho      amount_total < 1 000 000
80 — Exterior FX       Fabricio   currency != ARS
=====================  =========  =============================================

Security groups
---------------
* **Aprobadores de Pagos** (``grp_aprobadores_pago``): can see and click the
  Aprobar / Rechazar buttons on posted payments and journal entries.

Configuration
-------------
Accounting → Configuration → Reglas de Aprobación

Technical notes — batch-aware routing (R5)
------------------------------------------
``account.payment.effective_approval_amount`` is a non-stored computed field::

    @api.depends('amount', 'batch_payment_st_id',
                 'batch_payment_st_id.payment_ids.amount',
                 'batch_payment_st_id.payment_ids.state')
    def _compute_effective_approval_amount(self):
        if payment.batch_payment_st_id:
            # sum of non-cancelled payments in the batch
        else:
            # individual payment amount

Rules 10 and 20 use ``effective_approval_amount`` in their domain and are
marked ``noupdate="0"`` so domain changes apply on every module upgrade.
Rules 30–80 are ``noupdate="1"`` to protect manual UI edits.
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
