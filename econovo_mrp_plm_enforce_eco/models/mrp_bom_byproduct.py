# -*- coding: utf-8 -*-
from odoo import api, models


class MrpBomByproduct(models.Model):
    _inherit = ['mrp.bom.byproduct', 'econovo.bom.locked.child.mixin']

    def write(self, vals):
        self._raise_if_bom_locked()
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        self._check_bom_locked_on_create(vals_list)
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_bom_locked(self):
        self._raise_if_bom_locked()
