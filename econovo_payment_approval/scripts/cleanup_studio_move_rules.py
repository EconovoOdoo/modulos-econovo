"""
cleanup_studio_move_rules.py
============================
Removes Studio Approval Rules (studio.approval.rule) for account.move
from the production database. Run this AFTER the new econovo_payment_approval
module has been deployed to production and validated.

SAFETY:
  - Dry-run mode is ON by default (set DRY_RUN = False to actually delete).
  - Only deletes rules whose model is 'account.move'.
  - Does NOT touch rules for account.payment or any other model.

Usage:
    python cleanup_studio_move_rules.py
    # Review output, then set DRY_RUN = False and run again.
"""

import xmlrpc.client

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
URL = 'https://econovo.odoo.com'
DB  = 'econovoodoo-econovo1-econovo-15882591'
USER = 'admin'
PWD  = '9f17185b8cefab041c58e0fbd81ae55fee68ebf0'

DRY_RUN = True   # <-- set to False to actually delete
# --------------------------------------------------------------------------

common = xmlrpc.client.ServerProxy(URL + '/xmlrpc/2/common', allow_none=True)
uid    = common.authenticate(DB, USER, PWD, {})
if not uid:
    raise SystemExit('Authentication failed')

m = xmlrpc.client.ServerProxy(URL + '/xmlrpc/2/object', allow_none=True)

# 1. Find studio.approval.rule records for account.move
rules = m.execute_kw(DB, uid, PWD, 'studio.approval.rule', 'search_read',
    [[['model_id.model', '=', 'account.move']]],
    {'fields': ['id', 'name', 'domain', 'group_id', 'responsible_id', 'model_id']})

if not rules:
    print('No studio.approval.rule records found for account.move. Nothing to do.')
else:
    print(f'Found {len(rules)} Studio Approval Rule(s) for account.move:\n')
    for r in rules:
        print(f"  ID={r['id']}  Name={r['name']}")
        print(f"    model={r['model_id'][1] if r['model_id'] else '-'}")
        print(f"    group={r['group_id'][1] if r['group_id'] else '-'}")
        print(f"    responsible={r['responsible_id'][1] if r['responsible_id'] else '-'}")
        print(f"    domain={r['domain']}")
        print()

    if DRY_RUN:
        print('[DRY RUN] No records deleted. Set DRY_RUN = False to proceed.')
    else:
        ids_to_delete = [r['id'] for r in rules]
        ok = m.execute_kw(DB, uid, PWD, 'studio.approval.rule', 'unlink', [ids_to_delete])
        if ok:
            print(f'Deleted {len(ids_to_delete)} record(s): {ids_to_delete}')
        else:
            print('ERROR: unlink returned False. Check permissions.')
