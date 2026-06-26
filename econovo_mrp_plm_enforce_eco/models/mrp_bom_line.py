# -*- coding: utf-8 -*-
from odoo import api, models
from .mixins import (
    check_bom_locked_on_create,
    raise_if_bom_locked,
    raise_if_bom_locked_write,
)

# User-driven structural fields of a component line. Auto-recomputed stored
# fields (manual_consumption) and technical/related fields (company_id) are
# intentionally excluded so that opening a form never trips the guard.
_LINE_STRUCTURAL_FIELDS = frozenset({
    'product_id', 'product_qty', 'product_uom_id', 'operation_id',
    'bom_product_template_attribute_value_ids', 'bom_id',
})


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    def write(self, vals):
        raise_if_bom_locked_write(self.env, self, vals, _LINE_STRUCTURAL_FIELDS)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        check_bom_locked_on_create(self.env, vals_list)
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_bom_locked(self):
        raise_if_bom_locked(self.env, self.mapped('bom_id'))
