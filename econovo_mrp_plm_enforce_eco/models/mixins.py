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

# XML ID of the group that bypasses PLM lock restrictions.
# Centralised here so every guard in the module references the same constant.
# Changing this value must be accompanied by a matching change in groups.xml.
_BYPASS_GROUP = 'econovo_mrp_plm_enforce_eco.group_plm_system_operator'


def _is_plm_bypass(env):
    """Return True when the current session should bypass PLM lock checks."""
    return (
        env.su
        or env.user.has_group('mrp.group_mrp_manager')
        or env.user.has_group(_BYPASS_GROUP)
    )


def _will_change(record, vals, structural_fields):
    """Return True if *vals* changes the value of any structural field on *record*.

    Mirrors the spirit of ``account.move._field_will_change``: a write that
    re-sends the current value (or only touches non-structural / auto-computed
    fields such as ``manual_consumption`` or ``product_uom_id`` recomputations)
    must NOT be treated as a structural modification.
    """
    for fname in structural_fields:
        if fname not in vals:
            continue
        field = record._fields[fname]
        if field.type == 'many2one':
            if record[fname].id != (vals[fname] or False):
                return True
        elif field.type in ('one2many', 'many2many'):
            # x2many commands in vals always express intent to change.
            if vals[fname]:
                return True
        else:
            if record[fname] != vals[fname]:
                return True
    return False


def raise_if_bom_locked_write(env, records, vals, structural_fields):
    """Raise if a write changes a *structural* field on a record of a locked BoM.

    Only structural user-driven fields are considered; technical or
    auto-recomputed stored fields are ignored so that simply opening a form
    (which may flush stored computes or re-send unchanged values) never trips
    the guard.  Skips sudo sessions, MRP Administrators, and PLM System
    Operators.
    """
    if _is_plm_bypass(env):
        return
    if not (set(structural_fields) & set(vals)):
        return
    locked = records.filtered(
        lambda r: r.bom_id._is_bom_locked() and _will_change(r, vals, structural_fields)
    )
    if locked:
        raise UserError(_(
            'Use an Engineering Change Order (ECO) to modify '
            'the structure of:\n%s',
            '\n'.join('- %s' % name for name in locked.mapped('bom_id.display_name')),
        ))


def raise_if_bom_locked(env, bom_recordset):
    """Raise UserError if any BoM in *bom_recordset* is currently locked.

    Used by ``unlink`` guards where the operation itself (deleting a child
    record of a locked BoM) is always structural.

    :param env:           ``self.env`` of the calling model.
    :param bom_recordset: ``mrp.bom`` recordset (typically ``self.mapped('bom_id')``).
    """
    if _is_plm_bypass(env):
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
    if _is_plm_bypass(env):
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
