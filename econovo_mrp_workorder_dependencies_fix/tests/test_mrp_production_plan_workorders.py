# -*- coding: utf-8 -*-
from odoo.addons.mrp.tests.common import TestMrpCommon
from odoo.tests import Form, tagged


@tagged('post_install', '-at_install')
class TestMrpProductionPlanWorkorders(TestMrpCommon):

    def test_plan_workorders_cross_production_dependency(self):
        """ A workorder that is the last step of its own Manufacturing Order,
        but also blocks a workorder of a DIFFERENT Manufacturing Order, must
        still be scheduled when planning its own production. Without the fix,
        it is never replanned, keeps no `leave_id`, and `_plan_workorders()`
        crashes comparing its empty leave against its sibling's real one.
        """
        mo_component = Form(self.env['mrp.production'])
        mo_component.bom_id = self.bom_3  # 2 operations: Cutting Machine, Weld Machine
        mo_component = mo_component.save()

        mo_assembly = Form(self.env['mrp.production'])
        mo_assembly.bom_id = self.bom_4  # 1 operation
        mo_assembly = mo_assembly.save()

        (mo_component | mo_assembly).write({'allow_workorder_dependencies': True})
        weld_workorder = mo_component.workorder_ids.filtered(lambda wo: wo.name == 'Weld Machine')
        mo_assembly.workorder_ids.blocked_by_workorder_ids = weld_workorder

        # Should not raise, even though `weld_workorder` blocks a workorder
        # belonging to `mo_assembly`, a completely different production.
        mo_component.button_plan()

        self.assertTrue(
            all(mo_component.workorder_ids.mapped('leave_id')),
            "Every workorder of the planned production should have a scheduled leave.")
        self.assertEqual(mo_component.date_start, min(mo_component.workorder_ids.mapped('leave_id.date_from')))
        self.assertEqual(mo_component.date_finished, max(mo_component.workorder_ids.mapped('leave_id.date_to')))
