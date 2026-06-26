# -*- coding: utf-8 -*-
"""
Plain Python helpers shared by child-model overrides (mrp.bom.line,
mrp.routing.workcenter, mrp.bom.byproduct).

These are intentionally NOT an Odoo AbstractModel: multi-``_inherit``
(e.g. ``['mrp.routing.workcenter', 'some.mixin']``) raises a
TypeError when the base model has a self-referential Many2many field
because the column-name is duplicated in the composed class.  Plain
imported functions sidestep that limitation entirely.
"""

from odoo import _
from odoo.exceptions import UserError


def raise_if_bom_locked(env, bom_recordset):
    """Raise UserError if any BoM in *bom_recordset* is currently locked.

    Skips the check for sudo sessions and MRP Administrators.

    :param env:           ``self.env`` of the calling model.
    :param bom_recordset: ``mrp.bom`` recordset (typically ``self.mapped('bom_id')``).
    """
    if env.su or env.user.has_group('mrp.group_mrp_manager'):
        return
    locked = bom_recordset.filtered(lambda b: b._is_bom_locked())
    if locked:
        raise UserError(_(
            'Use an Engineering Change Order (ECO) to modify '
            'the structure of:\n%s',
            '\n'.join('- %s' % name for name in locked.mapped('display_name')),
        ))


def check_bom_locked_on_create(env, vals_list):
    """Pre-creation guard for child-model ``create()`` overrides.

    Called *before* ``super().create()`` so that no partial records are
    written when the target BoM is locked.

    :param env:       ``self.env`` of the calling model.
    :param vals_list: list of dicts as received by ``create()``.
    """
    if env.su or env.user.has_group('mrp.group_mrp_manager'):
        return
    bom_ids = {v['bom_id'] for v in vals_list if v.get('bom_id')}
    if not bom_ids:
        return
    locked = env['mrp.bom'].browse(bom_ids).filtered(lambda b: b._is_bom_locked())
    if locked:
        raise UserError(_(
            'Use an Engineering Change Order (ECO) to add records to:\n%s',
            '\n'.join('- %s' % name for name in locked.mapped('display_name')),
        ))
