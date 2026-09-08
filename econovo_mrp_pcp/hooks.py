# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.


def post_init_hook(env):
    """Backfill company_id on pre-existing mrp.plan records.

    company_id is required=True, but its Python default only knows the installing
    user's current company, which is wrong in a multi-company database. Correct it
    per plan from its own linked manufacturing orders' company.
    """
    plans = env['mrp.plan'].search([('manufacture_order_ids', '!=', False)])
    for plan in plans:
        plan.company_id = plan.manufacture_order_ids[0].company_id
