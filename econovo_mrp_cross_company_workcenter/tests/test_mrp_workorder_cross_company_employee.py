# -*- coding: utf-8 -*-
from unittest.mock import patch

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
            'company_ids': [(6, 0, (cls.env.company | cls.company_other).ids)],
            'groups_id': [(6, 0, groups.ids)],
        })
        # The operator has NO hr.employee in the session's active company
        # (cls.env.company): only in the other company they are also
        # allowed into.
        cls.employee_other_company = cls.env['hr.employee'].create({
            'name': 'Cross Company Operator',
            'user_id': cls.operator.id,
            'company_id': cls.company_other.id,
        })

        workcenter = cls.env['mrp.workcenter'].create({'name': 'Cross Company Employee Workcenter'})
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
        from the OTHER allowed company, instead of only ever looking for one
        in the session's active company. """
        workorder = self.production.workorder_ids[0]
        wo_as_operator = workorder.with_user(self.operator)
        # Core's employee check only runs within an actual HTTP request
        # (`not request` short-circuits it otherwise); simulate one being
        # active, like the real Shop Floor tablet/backend button click.
        with patch('odoo.addons.mrp_workorder.models.mrp_workorder.request', new=object()):
            wo_as_operator.button_start()
        self.assertIn(
            self.employee_other_company, workorder.employee_ids,
            "The workorder should record the operator's employee from the other allowed company.")
