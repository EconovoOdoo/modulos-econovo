"""
Post-migration script for econovo_payment_approval 17.0.3.0.0

Updates approval rules 10 and 20 to use effective_approval_amount instead of
amount in their domain. This field returns the batch total when the payment
belongs to a Sumitec batch, ensuring the routing threshold is evaluated
against the full batch amount rather than each individual payment.

Also clears the noupdate flag on these two rules in ir.model.data so that
future XML domain changes are applied on subsequent upgrades.
"""


def migrate(cr, version):
    # Update rule domains: replace 'amount' with 'effective_approval_amount'
    # We match specifically on sequence 10 and 20 to be safe.
    cr.execute("""
        UPDATE econovo_approval_rule
        SET domain = REPLACE(domain, '''amount''', '''effective_approval_amount''')
        WHERE sequence IN (10, 20)
          AND target_model = 'account.payment'
          AND domain LIKE '%%''amount''%%';
    """)

    # Allow future upgrades to re-apply XML domains for these two rules
    # by clearing the noupdate flag on their ir.model.data entries.
    cr.execute("""
        UPDATE ir_model_data
        SET noupdate = false
        WHERE module = 'econovo_payment_approval'
          AND name IN ('rule_pagos_mayores', 'rule_pagos_menores');
    """)
