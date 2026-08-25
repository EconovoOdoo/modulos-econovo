# -*- coding: utf-8 -*-
from odoo import models


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    def button_start(self, bypass=False):
        """ Allow starting the work order when the user has no ``hr.employee``
        in the currently active company, as long as HR already linked them to
        one in ANOTHER company (``hr.employee.user_id``).

        Core only looks for an employee in ``self.env.company`` (the active
        company: ``res.users.employee_id`` is ``@api.depends_context('company')``),
        so a user whose real/payroll employee record lives in a different
        company than the one they operate in gets rejected here.

        This deliberately does NOT rely on ``res.users.company_ids`` (granting
        the user multi-company access): that would also expose every OTHER
        record of that company the user's groups can read, and show the
        company switcher in the top bar, neither of which this needs. Neither
        ``mrp.workorder.employee_ids`` nor ``mrp.workcenter.productivity.employee_id``
        are ``check_company``-constrained (verified in core/``mrp_workorder``
        source), so recording a same-user employee from another company on
        these Oscar-Scorza-side (or any company's) documents is not blocked at
        the ORM level either -- the only actual authorization fact that
        matters is that HR already linked that ``hr.employee`` to this user.

        Rather than switching the active company for the whole call (which
        would also change which company's records are visible/writable for
        every OTHER multi-company check triggered by the same call, e.g. on
        the resulting stock moves), this only seeds the ORM cache for
        ``res.users.employee_id`` with that employee, for the duration of
        this one call, then restores it.
        """
        if not bypass and not self.env.context.get('mrp_display') and not self.env.user.employee_id:
            other_employee = self.env['hr.employee'].sudo().search([
                ('user_id', '=', self.env.uid),
            ], limit=1)
            if other_employee:
                field = self.env.user._fields['employee_id']
                original_value = self.env.cache.get(self.env.user, field, default=False)
                self.env.cache.set(self.env.user, field, other_employee.id)
                try:
                    return super().button_start(bypass=bypass)
                finally:
                    self.env.cache.set(self.env.user, field, original_value)
        return super().button_start(bypass=bypass)
