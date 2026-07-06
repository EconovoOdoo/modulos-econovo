"""
Post-migration script for econovo_payment_approval 17.0.5.5.0

Changes applied:

  ir_model_data safety net for 'rule_pagos_mayores' (Rule 10):
    Production lost the original xmlid tracking for this record at some point
    (root cause unclear - likely a manual UI recreation after the record was
    deleted). If the xmlid is missing, this script re-attaches it to whatever
    econovo.approval.rule currently has sequence=10, so the upgrade does not
    create a SECOND duplicate "Pagos Mayores" rule from the XML data file.

  Excluded accounts (Fondo Fijo + Tarjetas de credito/debito, 46 codes):
    Sourced from finance-provided spreadsheets ("Cuentas a ignorar de
    aprobacion de pagos"), one per company (Agrovial, Oscar Scorza, HSS).
    These asset_cash accounts map 1:1 to a payment journal
    (journal.default_account_id). Payments/entries touching any of these
    accounts never require approval. Appended to every rule's domain
    (journal_id.default_account_id.code for payments, line_ids.account_id.code
    for entries).

  All 9 rules (10, 20, 25, 30, 40, 50, 60, 70, 80):
    Domains are re-applied directly via SQL as a safety net, since rules
    25/30/40/50/60/70/80 are noupdate=true in the DB (protected from plain
    XML reload) and rules 10/20 have shown drift in the past (a stale
    duplicate record in the XML file previously overwrote the intended
    Rule 20 domain on upgrade - now fixed at the source, but this script
    guarantees the correct value is in place immediately on this upgrade
    regardless of the DB's current (possibly drifted) state).
"""

import logging

_logger = logging.getLogger(__name__)

_EXCLUDED_ACCOUNTS = (
    "'1.1.1.01.0012', '1.1.1.01.0013', '1.1.1.01.007', '1.1.1.01.013',"
    "'1.1.1.01.014', '1.1.1.02.0023', '1.1.1.02.0024', '1.1.1.02.0025',"
    "'1.1.1.02.0026', '1.1.1.02.0027', '1.1.1.02.0028', '1.1.1.02.0029',"
    "'1.1.1.02.0030', '1.1.1.02.0031', '1.1.1.02.0032', '1.1.1.02.0033',"
    "'1.1.1.02.0034', '1.1.1.02.0035', '1.1.1.02.0036', '1.1.1.02.0037',"
    "'1.1.1.02.0038', '1.1.1.02.0039', '1.1.1.02.0040', '1.1.1.02.0041',"
    "'1.1.1.02.0042', '1.1.1.02.0043', '1.1.1.02.0044', '1.1.1.02.0045',"
    "'1.1.1.02.0046', '1.1.1.02.0047', '1.1.1.02.0048', '1.1.1.02.0049',"
    "'1.1.1.02.0050', '1.1.1.02.0051', '1.1.1.02.0052', '1.1.1.02.0054',"
    "'1.1.1.02.0055', '1.1.1.02.0056', '1.1.1.02.0057', '1.1.1.02.015',"
    "'1.1.1.02.030', '1.1.1.02.040', '1.1.1.02.045', '1.1.2.01.018',"
    "'1.1.2.01.019', '1.1.2.01.025'"
)

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

_DOMAIN_10 = (
    "[('create_uid', '!=', 482), ('company_id', '!=', 1), "
    "('is_internal_transfer', '=', False), "
    "('effective_approval_amount', '>', 1000000), "
    "('journal_id.company_id', '!=', 3), "
    "('currency_id.name', '=', 'ARS'), ('payment_type', '=', 'outbound'), "
    "('journal_id.default_account_id.code', 'not in', [" + _EXCLUDED_ACCOUNTS + "])]"
)
_DOMAIN_20 = (
    "[('create_uid', '!=', 482), ('company_id', '!=', 1), "
    "('create_uid', 'not in', [370, 470]), "
    "('is_internal_transfer', '=', False), "
    "('journal_id.company_id', '!=', 3), "
    "('currency_id.name', '=', 'ARS'), ('payment_type', '=', 'outbound'), "
    "('journal_id.default_account_id.code', 'not in', [" + _EXCLUDED_ACCOUNTS + "])]"
)
_DOMAIN_25 = (
    "[('company_id', '=', 1), ('create_uid', 'not in', [370, 470, 482]), "
    "('is_internal_transfer', '=', False), ('currency_id.name', '=', 'ARS'), "
    "('payment_type', '=', 'outbound'), "
    "('journal_id.default_account_id.code', 'not in', [" + _EXCLUDED_ACCOUNTS + "])]"
)
_DOMAIN_30 = (
    "['|', ('journal_id.company_id', '=', 3), ('create_uid', '=', 482), "
    "('is_internal_transfer', '=', False), ('payment_type', '=', 'outbound'), "
    "('journal_id.default_account_id.code', 'not in', [" + _EXCLUDED_ACCOUNTS + "])]"
)
_DOMAIN_40 = (
    "[('is_internal_transfer', '=', False), ('currency_id.name', '!=', 'ARS'), "
    "('payment_type', '=', 'outbound'), "
    "('journal_id.default_account_id.code', 'not in', [" + _EXCLUDED_ACCOUNTS + "])]"
)
_DOMAIN_50 = (
    "[('company_id', '=', 1), ('create_uid', 'in', [370, 470]), "
    "('payment_type', '=', 'outbound'), ('is_internal_transfer', '=', False), "
    "('journal_id.default_account_id.code', 'not in', [" + _EXCLUDED_ACCOUNTS + "])]"
)
_DOMAIN_60 = (
    "[('move_type', '=', 'entry'), ('create_uid', 'not in', [366, 371]), "
    "('line_ids.account_id.code', 'not in', [" + _EXCLUDED_ACCOUNTS + "]), "
    "('currency_id.name', '=', 'ARS'), ('amount_total', '>=', 1000000), "
    "('line_ids.account_id.code', 'in', [" + _MONITORED_ACCOUNTS + "])]"
)
_DOMAIN_70 = (
    "[('move_type', '=', 'entry'), ('create_uid', 'not in', [366, 371]), "
    "('line_ids.account_id.code', 'not in', [" + _EXCLUDED_ACCOUNTS + "]), "
    "('currency_id.name', '=', 'ARS'), ('amount_total', '<', 1000000), "
    "('line_ids.account_id.code', 'in', [" + _MONITORED_ACCOUNTS + "])]"
)
_DOMAIN_80 = (
    "[('move_type', '=', 'entry'), ('create_uid', 'not in', [366, 371]), "
    "('line_ids.account_id.code', 'not in', [" + _EXCLUDED_ACCOUNTS + "]), "
    "('currency_id.name', '!=', 'ARS'), "
    "('line_ids.account_id.code', 'in', [" + _MONITORED_ACCOUNTS + "])]"
)

_UPDATES = {
    'rule_pagos_mayores':    _DOMAIN_10,
    'rule_pagos_menores':    _DOMAIN_20,
    'rule_pagos_agrovial_ars': _DOMAIN_25,
    'rule_pagos_ba':         _DOMAIN_30,
    'rule_pagos_fx':         _DOMAIN_40,
    'rule_pagos_agrovial_comex': _DOMAIN_50,
    'rule_asientos_mayores': _DOMAIN_60,
    'rule_asientos_menores': _DOMAIN_70,
    'rule_asientos_fx':      _DOMAIN_80,
}


def migrate(cr, version):
    # Safety net: re-attach ir_model_data for rule_pagos_mayores if it is
    # missing (seen in production - the xmlid tracking was lost while the
    # underlying record survived under a different id). Without this, the
    # next data load would create a SECOND "Pagos Mayores" rule.
    cr.execute("""
        SELECT id FROM ir_model_data
        WHERE module = 'econovo_payment_approval' AND name = 'rule_pagos_mayores'
    """)
    if not cr.fetchone():
        cr.execute("""
            SELECT id FROM econovo_approval_rule
            WHERE sequence = 10 AND target_model = 'account.payment'
            ORDER BY id LIMIT 1
        """)
        row = cr.fetchone()
        if row:
            rule_id = row[0]
            cr.execute("""
                INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
                VALUES ('rule_pagos_mayores', 'econovo_payment_approval',
                        'econovo.approval.rule', %s, false)
            """, (rule_id,))
            _logger.info(
                "econovo_payment_approval 17.0.5.5.0: re-attached missing "
                "ir_model_data for rule_pagos_mayores -> rule id %d", rule_id,
            )

    for xmlid, new_domain in _UPDATES.items():
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
            "econovo_payment_approval 17.0.5.5.0: updated domain for %s (%d row(s))",
            xmlid, rows,
        )
