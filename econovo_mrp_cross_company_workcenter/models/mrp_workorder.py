# -*- coding: utf-8 -*-
from odoo import models


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    def button_start(self, bypass=False):
        """ Allow starting the work order when the user has no ``hr.employee``
        in the currently active company, as long as they have one in ANOTHER
        company they are already allowed into (``res.users.company_ids``).

        Core only looks for an employee in ``self.env.company`` (the active
        company: ``res.users.employee_id`` is ``@api.depends_context('company')``),
        so a user legitimately granted access to several companies still gets
        rejected here unless their employee record happens to live in
        whichever company is active at the moment.

        Rather than switching the active company for the whole call (which
        would also change which company's records are visible/writable for
        every OTHER multi-company check triggered by the same call, e.g. on
        the resulting stock moves), this only seeds the ORM cache for
        ``res.users.employee_id`` with an employee from another allowed
        company, for the duration of this one call, then restores it.
        """
        if not bypass and not self.env.context.get('mrp_display') and not self.env.user.employee_id:
            allowed_company_ids = self.env.user._get_company_ids()
            other_employee = self.env['hr.employee'].sudo().search([
                ('user_id', '=', self.env.uid),
                ('company_id', 'in', allowed_company_ids),
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
