# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        """Override to create COMEX picking types when a new company is created."""
        companies = super().create(vals_list)
        # Import here to avoid circular import
        from odoo.addons.econovo_l10n_ar_comex import _create_comex_picking_types_for_company
        for company in companies:
            _create_comex_picking_types_for_company(self.env, company)
        return companies
