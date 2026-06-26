# -*- coding: utf-8 -*-
from odoo import api, models
from .mixins import check_bom_locked_on_create, raise_if_bom_locked


class MrpBomByproduct(models.Model):
    _inherit = 'mrp.bom.byproduct'

    def write(self, vals):
        raise_if_bom_locked(self.env, self.mapped('bom_id'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        check_bom_locked_on_create(self.env, vals_list)
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_bom_locked(self):
        raise_if_bom_locked(self.env, self.mapped('bom_id'))
