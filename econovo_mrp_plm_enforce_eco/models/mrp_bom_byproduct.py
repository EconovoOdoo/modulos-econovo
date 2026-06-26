# -*- coding: utf-8 -*-
from odoo import api, models
from .mixins import (
    check_bom_locked_on_create,
    raise_if_bom_locked,
    raise_if_bom_locked_write,
)

# User-driven structural fields of a by-product line. Auto-recomputed stored
# fields (product_uom_id via _compute_product_uom_id) and related/technical
# fields (company_id) are excluded to avoid tripping on form open.
_BYPRODUCT_STRUCTURAL_FIELDS = frozenset({
    'product_id', 'product_qty', 'operation_id',
    'bom_product_template_attribute_value_ids', 'bom_id', 'cost_share',
})


class MrpBomByproduct(models.Model):
    _inherit = 'mrp.bom.byproduct'

    def write(self, vals):
        raise_if_bom_locked_write(self.env, self, vals, _BYPRODUCT_STRUCTURAL_FIELDS)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        check_bom_locked_on_create(self.env, vals_list)
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_bom_locked(self):
        raise_if_bom_locked(self.env, self.mapped('bom_id'))
