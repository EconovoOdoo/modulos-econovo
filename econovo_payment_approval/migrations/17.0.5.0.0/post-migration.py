"""
Post-migration script for econovo_payment_approval 17.0.5.0.0

Changes applied:

  Rules 10 + 20 (account.payment, amount threshold):
    Remove the partial COMEX exclusion ('|', company!=1, creator not in COMEX)
    and replace it with a flat ('company_id', '!=', 1). All Agrovial
    (company=1) ARS payments are now routed exclusively by rule 25 and rule 50,
    so rules 10/20 must not match company=1 at all.
    These rules are already noupdate=false in the DB (set by v17.0.3.0.0
    migration), so their domain is re-applied from XML on upgrade. This SQL
    update is an additional safety net.

  Rule 25 (account.payment, Agrovial ARS -> Nacho):
    New rule. Created by ORM from XML data on first upgrade. No SQL needed.

  Rules 60 + 70 + 80 (account.move, journal entries):
    Add ('create_uid', 'not in', [366, 371]) to exclude:
      366 = Demarchi Agustin  (all his entries skip approval)
      371 = Ruiz Agustina     (rechargeable card expenses skip approval)
    These rules are noupdate=true in the DB, so the XML change alone would not
    be applied. This script updates their domains directly via SQL and clears
    the noupdate flag so future XML changes are honoured.
"""

import logging

_logger = logging.getLogger(__name__)

_MONITORED_ACCOUNTS = (
    "'2.1.1.01.025', '2.1.2.02.001', '2.1.2.02.002', '2.1.2.02.003',"
    "'2.1.2.02.004', '2.1.2.02.005', '2.1.2.02.006', '2.1.2.02.017',"
    "'2.1.2.02.018', '2.1.2.02.019', '2.1.3.01.001', '2.1.3.01.002',"
    "'2.1.3.01.003', '2.1.3.01.010', '2.1.3.01.020', '2.1.3.02.010',"
    "'2.1.3.02.020', '2.1.3.02.021', '2.1.3.02.520', '2.1.3.03.020',"
    "'2.1.3.04.010', '2.1.4.01.010', '2.1.4.01.020', '2.1.4.01.030',"
    "'2.1.4.01.040', '2.1.4.01.051', '2.1.4.01.052', '2.1.4.01.053',"
    "'2.1.4.01.054', '2.1.4.01.056', '2.1.4.01.057', '2.1.4.01.060',"
    "'2.1.5.01.001'"
)

_DOMAIN_60 = (
    "[('move_type', '=', 'entry'), ('create_uid', 'not in', [366, 371]), "
    "('currency_id.name', '=', 'ARS'), ('amount_total', '>=', 1000000), "
    "('line_ids.account_id.code', 'in', [" + _MONITORED_ACCOUNTS + "])]"
)
_DOMAIN_70 = (
    "[('move_type', '=', 'entry'), ('create_uid', 'not in', [366, 371]), "
    "('currency_id.name', '=', 'ARS'), ('amount_total', '<', 1000000), "
    "('line_ids.account_id.code', 'in', [" + _MONITORED_ACCOUNTS + "])]"
)
_DOMAIN_80 = (
    "[('move_type', '=', 'entry'), ('create_uid', 'not in', [366, 371]), "
    "('currency_id.name', '!=', 'ARS'), "
    "('line_ids.account_id.code', 'in', [" + _MONITORED_ACCOUNTS + "])]"
)

_DOMAIN_10 = (
    "[('create_uid', '!=', 482), ('company_id', '!=', 1), "
    "('is_internal_transfer', '=', False), "
    "('effective_approval_amount', '>', 1000000), "
    "('journal_id.company_id', '!=', 3), "
    "('currency_id.name', '=', 'ARS'), ('payment_type', '=', 'outbound')]"
)
_DOMAIN_20 = (
    "[('create_uid', '!=', 482), ('company_id', '!=', 1), "
    "('is_internal_transfer', '=', False), "
    "('effective_approval_amount', '<=', 1000000), "
    "('journal_id.company_id', '!=', 3), "
    "('currency_id.name', '=', 'ARS'), ('payment_type', '=', 'outbound')]"
)

_UPDATES = {
    # xmlid: (new_domain, clear_noupdate)
    'rule_pagos_mayores':   (_DOMAIN_10, False),  # already noupdate=false
    'rule_pagos_menores':   (_DOMAIN_20, False),  # already noupdate=false
    'rule_asientos_mayores': (_DOMAIN_60, True),
    'rule_asientos_menores': (_DOMAIN_70, True),
    'rule_asientos_fx':      (_DOMAIN_80, True),
}


def migrate(cr, version):
    for xmlid, (new_domain, clear_noupdate) in _UPDATES.items():
        cr.execute("""
            UPDATE econovo_approval_rule ear
            SET domain = %s
            FROM ir_model_data imd
            WHERE imd.model = 'econovo.approval.rule'
              AND imd.res_id = ear.id
              AND imd.module = 'econovo_payment_approval'
              AND imd.name = %s
        """, (new_domain, xmlid))
        rows = cr.rowcount
        _logger.info(
            "econovo_payment_approval 17.0.5.0.0: updated domain for %s (%d row(s))",
            xmlid, rows,
        )
        if clear_noupdate:
            cr.execute("""
                UPDATE ir_model_data
                SET noupdate = false
                WHERE module = 'econovo_payment_approval'
                  AND name = %s
            """, (xmlid,))
