# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from . import models


def _post_init_hook(env):
    """Post-installation hook to set up default COMEX locations."""
    # Ensure COMEX location hierarchy is properly configured
    comex_root = env.ref('econovo_l10n_ar_comex.comex_location_root', raise_if_not_found=False)
    if comex_root:
        # Ensure parent locations don't have company restriction
        comex_root.write({'company_id': False})
        child_views = env['stock.location'].search([
            ('location_id', 'child_of', comex_root.id),
            ('usage', '=', 'view'),
        ])
        child_views.write({'company_id': False})
