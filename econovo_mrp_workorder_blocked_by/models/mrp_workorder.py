# -*- coding: utf-8 -*-

from odoo import _, models
from odoo.exceptions import UserError


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    def _check_blocked_by(self):
        """Raise UserError if any blocker workorder is not yet done/cancelled."""
        for wo in self:
            pending_blockers = wo.blocked_by_workorder_ids.filtered(
                lambda b: b.state not in ('done', 'cancel')
            )
            if pending_blockers:
                blocker_lines = '\n'.join(
                    '  • %s (%s)' % (b.name, b.production_id.name)
                    for b in pending_blockers
                )
                raise UserError(_(
                    'Cannot process "%s" (%s). The following operations must be completed first:\n%s',
                    wo.name,
                    wo.production_id.name,
                    blocker_lines,
                ))

    def button_start(self):
        self._check_blocked_by()
        return super().button_start()

    def button_finish(self):
        # Only enforce if the workorder was never started (state not progress).
        # If it is already in progress it already passed button_start validation.
        self.filtered(lambda wo: wo.state not in ('progress', 'done', 'cancel'))._check_blocked_by()
        return super().button_finish()
