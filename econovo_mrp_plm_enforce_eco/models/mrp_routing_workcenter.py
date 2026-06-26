# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import UserError
from .mixins import check_bom_locked_on_create, raise_if_bom_locked


class MrpRoutingWorkcenter(models.Model):
    _inherit = 'mrp.routing.workcenter'

    # ------------------------------------------------------------------
    # Server-side protection
    # ------------------------------------------------------------------

    def write(self, vals):
        raise_if_bom_locked(self.env, self.mapped('bom_id'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        # Defence-in-depth: also caught by copy_to_bom() override below.
        check_bom_locked_on_create(self.env, vals_list)
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_bom_locked(self):
        raise_if_bom_locked(self.env, self.mapped('bom_id'))

    # ------------------------------------------------------------------
    # "Copy existing operations" flow — two interception points
    # ------------------------------------------------------------------

    def copy_existing_operations(self):
        """Block opening the 'Select Operations to Copy' popup on locked BoMs.

        This is the earliest and most reliable interception point: the user
        sees the error immediately when clicking the button, before any popup
        or data change occurs.  ``copy_to_bom()`` is also overridden as
        defence-in-depth in case the context reaches that method directly.
        """
        if not self.env.su and not self.env.user.has_group('mrp.group_mrp_manager'):
            bom_id = self.env.context.get('bom_id')
            if bom_id:
                target_bom = self.env['mrp.bom'].browse(bom_id)
                if target_bom._is_bom_locked():
                    raise UserError(_(
                        'Use an Engineering Change Order (ECO) to add '
                        'operations to: %s',
                        target_bom.display_name,
                    ))
        return super().copy_existing_operations()

    def copy_to_bom(self):
        """Override to block copying operations into a locked BoM.

        The standard ``copy_existing_operations`` / ``copy_to_bom`` flow
        calls ``operation.copy({'bom_id': target_id})``, which goes through
        the ORM ``copy()`` method.  Checking the target BoM lock here, at
        the action-method level, is the most reliable interception point.
        """
        if not self.env.su and not self.env.user.has_group('mrp.group_mrp_manager'):
            bom_id = self.env.context.get('bom_id')
            if bom_id:
                target_bom = self.env['mrp.bom'].browse(bom_id)
                if target_bom._is_bom_locked():
                    raise UserError(_(
                        'Use an Engineering Change Order (ECO) to add '
                        'operations to: %s',
                        target_bom.display_name,
                    ))
        return super().copy_to_bom()

