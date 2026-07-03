# -*- coding: utf-8 -*-
from odoo import models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def _plan_workorders(self, replan=False):
        """ Plan all the production's workorders depending on the workcenters
        work schedule.

        Overrides the core implementation to fix a crash
        (``TypeError: '<' not supported between instances of 'bool' and
        'datetime.datetime'``) that occurs when a workorder is the last step of
        THIS production but also blocks (``needed_by_workorder_ids``) a
        workorder of a DIFFERENT production (a legitimate cross-production
        "Workorder Dependencies" setup, e.g. several component Manufacturing
        Orders feeding one assembly/welding Manufacturing Order):

        * The core ``final_workorders`` detection excludes any workorder whose
          ``needed_by_workorder_ids`` is not empty, regardless of which
          production those dependent workorders belong to, so such a workorder
          never gets (re)planned on its own production and keeps no scheduled
          ``leave_id``.
        * The final ``date_start``/``date_finished`` computation then runs
          ``min()``/``max()`` over every active workorder's
          ``leave_id.date_from``/``date_to`` without filtering out workorders
          that still have no scheduled leave, which crashes as soon as one of
          them is empty (``False``) while another has a real value.

        :param replan: If it is a replan, only ready and pending workorder will be taken into account
        :type replan: bool.
        """
        self.ensure_one()

        if not self.workorder_ids:
            return

        self._link_workorders_and_moves()

        # Plan workorders starting from final ones (those with no dependent
        # workorders WITHIN THE SAME PRODUCTION; a workorder blocking another
        # production's workorder must still be treated as final for its own
        # production's planning purposes).
        final_workorders = self.workorder_ids.filtered(
            lambda wo: not wo.needed_by_workorder_ids.filtered(lambda dep: dep.production_id == wo.production_id)
        )
        for workorder in final_workorders:
            workorder._plan_workorder(replan)

        workorders = self.workorder_ids.filtered(lambda w: w.state not in ('done', 'cancel'))
        if not workorders:
            return

        # Defensive guard: ignore workorders that still have no scheduled
        # leave instead of crashing on an unguarded min()/max() mixing False
        # and datetime values.
        planned_workorders = workorders.filtered('leave_id')
        if not planned_workorders:
            return

        self.with_context(force_date=True).write({
            'date_start': min(planned_workorders.mapped('leave_id.date_from')),
            'date_finished': max(planned_workorders.mapped('leave_id.date_to')),
        })
