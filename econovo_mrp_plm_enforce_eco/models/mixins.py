# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import UserError


class BomLockedChildMixin(models.AbstractModel):
    """Mixin for child models of mrp.bom that must be protected from direct
    modification when the parent BoM is locked (in production without an open ECO).

    Inheriting models MUST have a Many2one field ``bom_id`` pointing to mrp.bom.

    Usage::

        class MrpBomLine(models.Model):
            _inherit = ['mrp.bom.line', 'econovo.bom.locked.child.mixin']

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
    """

    _name = 'econovo.bom.locked.child.mixin'
    _description = 'BoM Locked Child Mixin'

    def _get_locked_boms(self):
        """Return the subset of parent BoMs that are currently locked."""
        return self.mapped('bom_id').filtered(lambda b: b._is_bom_locked())

    def _raise_if_bom_locked(self):
        """Raise UserError if any record in self belongs to a locked BoM.

        Skips the check when running as sudo or as an MRP Administrator so
        that system operations (ECO apply flow, imports, etc.) are never blocked.
        """
        if self.env.su or self.env.user.has_group('mrp.group_mrp_manager'):
            return
        locked_boms = self._get_locked_boms()
        if locked_boms:
            raise UserError(_(
                'Use an Engineering Change Order (ECO) to modify the structure of:\n%s',
                '\n'.join('- %s' % name for name in locked_boms.mapped('display_name')),
            ))

    def _check_bom_locked_on_create(self, vals_list):
        """Pre-creation check: raise if any target BoM in vals_list is locked.

        Called before super().create() so no partial records are written.
        """
        if self.env.su or self.env.user.has_group('mrp.group_mrp_manager'):
            return
        bom_ids = {v['bom_id'] for v in vals_list if v.get('bom_id')}
        if not bom_ids:
            return
        locked = self.env['mrp.bom'].browse(bom_ids).filtered(
            lambda b: b._is_bom_locked()
        )
        if locked:
            raise UserError(_(
                'Use an Engineering Change Order (ECO) to add records to:\n%s',
                '\n'.join('- %s' % name for name in locked.mapped('display_name')),
            ))
