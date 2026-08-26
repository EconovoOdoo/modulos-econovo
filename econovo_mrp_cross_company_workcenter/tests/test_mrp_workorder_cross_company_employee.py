# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMrpWorkorderCrossCompanyEmployee(TransactionCase):
    # Deliberately does not build on odoo.addons.mrp.tests.common.TestMrpCommon:
    # its base setUpClass (via product.tests.common.ProductCommon) forces the
    # active company's currency to USD, which fails against a database whose
    # main company already has journal items. This test only needs one
    # product/workcenter/BOM/production, built directly instead.

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_other = cls.env['res.company'].create({'name': 'Cross Company Employee Co'})
        groups = cls.env.ref('mrp.group_mrp_user') + cls.env.ref('stock.group_stock_user')
        # This local database has a custom hr.employee field
        # ("device_id", from a biometric-attendance integration) that is
        # NOT mirrored onto hr.employee.public -- confirmed NOT the case in
        # production (checked via ir.model.fields there). Without hr access,
        # core's own "public employee profile" prefetch fallback then trips
        # on that stale local field when button_start()/action_mark_as_done()
        # read employee_ids. Real production operators don't have HR access
        # either, but don't hit this because production has no such gap.
        groups += cls.env.ref('hr.group_hr_user')
        # This local database also has econovo_user_warehouse_restriction
        # installed, which needs its own explicit bypass group; this module
        # does not depend on it, so only add it when actually present.
        warehouse_bypass_group = cls.env.ref(
            'econovo_user_warehouse_restriction.group_warehouse_unrestricted', raise_if_not_found=False)
        if warehouse_bypass_group:
            groups += warehouse_bypass_group
        cls.operator = cls.env['res.users'].create({
            'name': 'Cross Company Operator',
            'login': 'cross_company_operator',
            'company_id': cls.env.company.id,
            'groups_id': [(6, 0, groups.ids)],
        })
        # The operator has NO hr.employee in the session's active company
        # (cls.env.company), only in another company -- and deliberately no
        # company_ids access to it either (this must work without granting
        # multi-company access).
        cls.employee_other_company = cls.env['hr.employee'].create({
            'name': 'Cross Company Operator',
            'user_id': cls.operator.id,
            'company_id': cls.company_other.id,
        })

        workcenter = cls.env['mrp.workcenter'].create({'name': 'Cross Company Employee Workcenter'})
        cls.workcenter = workcenter
        product = cls.env['product.product'].create({
            'name': 'Cross Company Employee Test Product',
            'type': 'product',
        })
        bom = cls.env['mrp.bom'].create({
            'product_id': product.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'operation_ids': [
                (0, 0, {'name': 'Test Operation', 'workcenter_id': workcenter.id, 'time_cycle': 15, 'sequence': 1}),
            ],
        })
        # Explicit locations/picking type: this database's existing products
        # carry their own routes/warehouse setup, which a bare test product
        # does not have, so the usual compute-from-product-routes defaults
        # cannot be relied on here.
        picking_type = cls.env['stock.picking.type'].search([
            ('code', '=', 'mrp_operation'),
            ('company_id', '=', cls.env.company.id),
        ], limit=1)
        # This database's own econovo_user_warehouse_restriction module
        # (unrelated to this module) blocks stock.move writes unless the
        # user has a permission record for the move's warehouse.
        if 'warehouse.user.permission' in cls.env:
            cls.env['warehouse.user.permission'].create({
                'user_id': cls.operator.id,
                'warehouse_id': picking_type.warehouse_id.id,
                'full_control': True,
            })
        cls.production = cls.env['mrp.production'].create({
            'product_id': product.id,
            'product_qty': 1.0,
            'product_uom_id': product.uom_id.id,
            'bom_id': bom.id,
            'picking_type_id': picking_type.id,
            'location_src_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
        })
        cls.production.action_confirm()

    def test_button_start_finds_employee_in_another_allowed_company(self):
        """ button_start() must succeed and record the operator's employee
        from the OTHER company, instead of only ever looking for one in the
        session's active company -- without granting the operator any
        multi-company access (company_ids) to that other company. """
        self.assertEqual(
            self.operator.company_ids, self.env.company,
            "This must work without granting the operator company_ids access to the other company.")
        workorder = self.production.workorder_ids[0]
        wo_as_operator = workorder.with_user(self.operator)
        # Core's employee check only runs within an actual HTTP request
        # (`not request` short-circuits it otherwise); simulate one being
        # active, like the real Shop Floor tablet/backend button click.
        with patch('odoo.addons.mrp_workorder.models.mrp_workorder.request', new=object()):
            wo_as_operator.button_start()
        self.assertIn(
            self.employee_other_company, workorder.employee_ids,
            "The workorder should record the operator's employee from the other company.")

    def test_action_mark_as_done_finds_employee_in_another_allowed_company(self):
        """ action_mark_as_done() (the "Mark as Done"/finish action) does its
        own, separate active-company employee lookup -- not covered by
        fixing button_start() alone -- and must also work for the operator's
        employee from the other company. """
        workorder = self.production.workorder_ids[0]
        wo_as_operator = workorder.with_user(self.operator)
        with patch('odoo.addons.mrp_workorder.models.mrp_workorder.request', new=object()):
            wo_as_operator.button_start()
            wo_as_operator.action_mark_as_done()
        self.assertEqual(workorder.state, 'done')
        productivity = self.env['mrp.workcenter.productivity'].search([
            ('workorder_id', '=', workorder.id),
            ('employee_id', '=', self.employee_other_company.id),
        ])
        self.assertTrue(
            productivity,
            "The time log should record the operator's employee from the other company.")

    def test_planner_reads_employee_allowed_on_its_own_company_workcenter(self):
        """ Any OTHER user of the work center's company (a planner creating a
        manufacturing order, a supervisor opening a work order) must be able to
        read an employee listed on that work center, even though the employee
        belongs to another company and the planner has no access to it. """
        planner = self.env['res.users'].create({
            'name': 'Cross Company Planner',
            'login': 'cross_company_planner',
            'company_id': self.env.company.id,
            'groups_id': [(6, 0, (self.env.ref('mrp.group_mrp_user') + self.env.ref('stock.group_stock_user')).ids)],
        })
        self.assertEqual(
            planner.company_ids, self.env.company,
            "The planner must not be granted access to the employee's company.")
        self.workcenter.employee_ids = [(4, self.employee_other_company.id)]

        # read() rather than attribute access: the latter prefetches every
        # field of the same group, which on this local database includes a
        # biometric-integration field missing from hr.employee.public (a local
        # data quirk, verified absent in production). The record rule, which
        # is what this asserts, is applied either way.
        [employee_data] = self.employee_other_company.with_user(planner).read(['name'])
        self.assertEqual(employee_data['name'], self.employee_other_company.name)
        for model in ('hr.employee', 'hr.employee.public'):
            self.assertEqual(
                self.env[model].with_user(planner).search([('id', '=', self.employee_other_company.id)]).id,
                self.employee_other_company.id,
                "%s should be readable: the employee is allowed on a work center of the planner's company." % model)

    def test_employee_not_on_any_workcenter_stays_unreadable(self):
        """ The widened rule must grant no more than the work center
        configuration itself authorizes. """
        unrelated_employee = self.env['hr.employee'].create({
            'name': 'Unrelated Other Company Employee',
            'company_id': self.company_other.id,
        })
        planner = self.env['res.users'].create({
            'name': 'Cross Company Planner Negative',
            'login': 'cross_company_planner_negative',
            'company_id': self.env.company.id,
            'groups_id': [(6, 0, (self.env.ref('mrp.group_mrp_user') + self.env.ref('stock.group_stock_user')).ids)],
        })
        with self.assertRaises(AccessError):
            unrelated_employee.with_user(planner).read(['name'])
        for model in ('hr.employee', 'hr.employee.public'):
            self.assertFalse(
                self.env[model].with_user(planner).search([('id', '=', unrelated_employee.id)]),
                "%s of another company must stay hidden when not allowed on any work center." % model)

