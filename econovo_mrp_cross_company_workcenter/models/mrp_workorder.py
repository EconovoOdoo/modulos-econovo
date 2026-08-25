# -*- coding: utf-8 -*-
from contextlib import contextmanager

from odoo import models


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    @contextmanager
    def _cross_company_employee_cache(self):
        """ Make ``self.env.user.employee_id`` resolve to an employee HR
        already linked to this user in ANOTHER company, for the duration of
        the wrapped block, when none exists in the currently active company.

        Core (``mrp_workorder``) looks up the working employee this way in
        several places (``button_start()``, ``action_mark_as_done()``,
        ``_set_default_time_log()``): ``res.users.employee_id`` is
        ``@api.depends_context('company')``, so a user whose real/payroll
        employee record lives in a different company than the one they
        operate in gets rejected in ALL of them, not just the first button
        clicked.

        This deliberately does NOT rely on ``res.users.company_ids`` (granting
        the user multi-company access): that would also expose every OTHER
        record of that company the user's groups can read, and show the
        company switcher in the top bar, neither of which this needs. Neither
        ``mrp.workorder.employee_ids`` nor ``mrp.workcenter.productivity.employee_id``
        are ``check_company``-constrained (verified in core/``mrp_workorder``
        source), so recording a same-user employee from another company on
        these documents is not blocked at the ORM level either -- the only
        actual authorization fact that matters is that HR already linked
        that ``hr.employee`` to this user.

        Rather than switching the active company for the whole call (which
        would also change which company's records are visible/writable for
        every OTHER multi-company check triggered by the same call, e.g. on
        the resulting stock moves), this only seeds the ORM cache for
        ``res.users.employee_id`` with that employee, then restores it.

        ``hr.employee`` also carries its OWN global multi-company record rule
        (``hr.hr_employee_comp_rule``, ``[('company_id', 'in', company_ids +
        [False])]``), independent of any ``check_company`` field constraint.
        So once core code holds the bare id and does its own plain
        ``self.env['hr.employee'].browse(id)`` (not through ``sudo()``), the
        FIRST field access it makes on that record (e.g. ``button_start()``
        reading ``active`` while filtering ``wo.employee_ids |= browse(id)``)
        still hits that rule and still raises an ``AccessError``, even though
        the id itself came from a legitimate ``sudo()`` lookup above.
        ``Field.__get__`` only skips the rule-checked database fetch when the
        value is ALREADY in cache (a plain cache hit returns immediately,
        never calling ``fetch()``/``check_access_rule()`` at all), so this
        also warms that record's ``active`` field via the same ``sudo()``
        recordset -- the one field ``mrp_workorder`` is known to read
        directly off of it. This is narrower than ``sudo()``-ing the whole
        call: it only ever exposes the truthful value of one field on one
        specific record the user is already entitled to work with (their own
        linked employee), not a blanket bypass of every rule the rest of the
        method might otherwise trigger (e.g. on stock moves/production).
        """
        if self.env.context.get('mrp_display') or self.env.user.employee_id:
            yield
            return
        other_employee = self.env['hr.employee'].sudo().search([
            ('user_id', '=', self.env.uid),
        ], limit=1)
        if not other_employee:
            yield
            return
        other_employee.fetch(['active'])
        field = self.env.user._fields['employee_id']
        original_value = self.env.cache.get(self.env.user, field, default=False)
        self.env.cache.set(self.env.user, field, other_employee.id)
        try:
            yield
        finally:
            self.env.cache.set(self.env.user, field, original_value)

    def button_start(self, bypass=False):
        if bypass:
            return super().button_start(bypass=bypass)
        with self._cross_company_employee_cache():
            return super().button_start(bypass=bypass)

    def action_mark_as_done(self):
        # Same employee-in-active-company lookup as button_start(), used
        # here for the "Mark as Done"/finish action (desktop, non-tablet).
        with self._cross_company_employee_cache():
            return super().action_mark_as_done()

    def _set_default_time_log(self, loss_id):
        # Also called directly from do_finish(), independently of
        # action_mark_as_done() above, with the same employee lookup.
        with self._cross_company_employee_cache():
            return super()._set_default_time_log(loss_id)
