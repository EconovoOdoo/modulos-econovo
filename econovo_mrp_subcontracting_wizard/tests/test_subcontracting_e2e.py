# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSubcontractingE2E(TransactionCase):
    """Walk the real physical/document flow: manufacturing orders with real work orders,
    purchase orders, receipts and resupply deliveries — not just the engine's field state.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        cls.warehouse.subcontracting_to_resupply = True
        # Work orders only show up on a Manufacturing Order if this feature is enabled.
        cls.env.user.groups_id += cls.env.ref('mrp.group_mrp_routings')
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'E2E Subcontractor', 'is_company': True})
        cls.workcenter = cls.env['mrp.workcenter'].create({
            'name': 'E2E Work Center', 'company_id': cls.company.id})
        cls.category_cut = cls.env['mrp.routing.operation.category'].create({
            'name': 'E2E Cutting', 'code': 'E2ECL'})
        cls.category_bend = cls.env['mrp.routing.operation.category'].create({
            'name': 'E2E Bending', 'code': 'E2EPL'})

    def _create_product(self, name, code):
        return self.env['product.template'].create({
            'name': name, 'default_code': code, 'type': 'product'})

    def _create_two_step_bom(self, code):
        """A product made of one component through Cut then Bend, in that order."""
        final_product = self._create_product('E2E Final %s' % code, code)
        component = self._create_product('E2E Raw %s' % code, 'RAW%s' % code)
        self.env['stock.quant']._update_available_quantity(
            component.product_variant_id, self.warehouse.lot_stock_id, 10.0)
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': final_product.id,
            'product_qty': 1.0,
            'product_uom_id': final_product.uom_id.id,
            'type': 'normal',
            'company_id': self.company.id,
        })
        op_cut = self.env['mrp.routing.workcenter'].create({
            'bom_id': bom.id, 'name': 'Cut', 'workcenter_id': self.workcenter.id,
            'sequence': 10, 'operation_category_id': self.category_cut.id,
        })
        op_bend = self.env['mrp.routing.workcenter'].create({
            'bom_id': bom.id, 'name': 'Bend', 'workcenter_id': self.workcenter.id,
            'sequence': 20, 'operation_category_id': self.category_bend.id,
        })
        self.env['mrp.bom.line'].create({
            'bom_id': bom.id,
            'product_id': component.product_variant_id.id,
            'product_qty': 1.0,
            'operation_id': op_cut.id,
        })
        return final_product, bom, (op_cut, op_bend)

    def _run_workorders(self, production):
        production.action_confirm()
        for workorder in production.workorder_ids:
            workorder.button_start()
            workorder.qty_producing = production.product_qty
            workorder.button_finish()
        result = production.button_mark_done()
        if isinstance(result, dict) and result.get('res_model') == 'mrp.consumption.warning':
            # The default BoM consumption policy warns on any deviation from the theoretical
            # quantity; confirm it exactly like a user would instead of loosening the policy.
            self.env['mrp.consumption.warning'].with_context(
                result.get('context', {})).create({}).action_confirm()

    def _externalize_last_operation(self, bom, operation):
        wizard = self.env['mrp.subcontracting.externalization'].create({
            'company_id': self.company.id,
            'bom_id': bom.id,
            'operation_id': operation.id,
            'subcontractor_id': self.subcontractor.id,
            'warehouse_id': self.warehouse.id,
            'eco_type_id': self._create_eco_type().id,
            'eco_handling': 'validated',
        })
        wizard.action_next()
        action = wizard.action_confirm()
        return self.env['mrp.subcontracting.chain'].browse(action['res_id'])

    def _create_eco_type(self):
        stage_done = self.env['mrp.eco.stage'].create({
            'name': 'E2E Effective', 'sequence': 10,
            'allow_apply_change': True, 'final_stage': True,
        })
        return self.env['mrp.eco.type'].create({
            'name': 'E2E Process Change', 'stage_ids': [(6, 0, stage_done.ids)]})

    def test_e2e_externalization_full_physical_flow(self):
        """Cut happens in-house, Bend is subcontracted: produce, purchase, receive, resupply."""
        final_product, bom, (op_cut, op_bend) = self._create_two_step_bom('E2EEXT')
        chain = self._externalize_last_operation(bom, op_bend)

        # The ECO builds the chain on a Bill of Materials revision, never on the original record
        # (which "replace" mode archives once the ECO applies) — fetch the live subcontract one.
        subcontract_bom = chain._get_subcontracted_bom()
        pre_bom = chain.bom_ids.filtered(lambda b: b.type == 'normal')
        self.assertTrue(pre_bom, 'The in-house Cut stage must survive as its own Bill of Materials.')
        pre_phantom = pre_bom.product_tmpl_id
        self.assertFalse(bom.active, 'Replace mode must archive the original once applied.')
        self.assertEqual(chain.anchor_product_tmpl_id, final_product)

        # Produce the pre-phantom in-house, with a real work order.
        production_form = Form(self.env['mrp.production'])
        production_form.product_id = pre_phantom.product_variant_id
        production_form.bom_id = pre_bom
        production_form.product_qty = 1.0
        pre_production = production_form.save()
        self._run_workorders(pre_production)
        self.assertEqual(pre_production.state, 'done')
        self.assertEqual(pre_phantom.product_variant_id.qty_available, 1.0)

        # Purchase the final product from the subcontractor, the way a planner actually would.
        po_form = Form(self.env['purchase.order'])
        po_form.partner_id = self.subcontractor
        with po_form.order_line.new() as line:
            line.product_id = final_product.product_variant_id
            line.product_qty = 1.0
        purchase_order = po_form.save()
        purchase_order.button_confirm()

        receipt = purchase_order.picking_ids
        self.assertEqual(len(receipt), 1)
        hidden_production = self.env['mrp.production'].search(
            [('bom_id', '=', subcontract_bom.id)])
        self.assertTrue(hidden_production, 'Confirming the purchase order must auto-create the '
                                            'hidden subcontracted Manufacturing Order.')
        self.assertEqual(hidden_production.state, 'confirmed')

        resupply_picking = self.env['stock.picking'].search([
            ('partner_id', '=', self.subcontractor.id),
            ('picking_type_id', '=', self.warehouse.subcontracting_resupply_type_id.id),
        ])
        self.assertTrue(resupply_picking, 'Without the resupply route this delivery never '
                                          'appears, and the subcontractor never receives it — '
                                          'this is exactly the failure CA9 fixed.')
        self.assertEqual(resupply_picking.move_ids.product_id.product_tmpl_id, pre_phantom)

        # Ship the pre-phantom to the subcontractor, then receive the finished product back.
        resupply_picking.move_ids.quantity = 1.0
        resupply_picking.move_ids.picked = True
        resupply_picking.button_validate()

        receipt.move_ids.quantity = 1.0
        receipt.move_ids.picked = True
        receipt.button_validate()

        self.assertEqual(hidden_production.state, 'done',
                          'Receiving the goods must automatically close the hidden Manufacturing '
                          'Order — no separate "record components" step for an untracked product.')
        self.assertEqual(final_product.product_variant_id.qty_available, 1.0)

    def test_e2e_internalization_restores_a_fully_working_in_house_flow(self):
        """After internalizing, a brand new Manufacturing Order needs no purchase at all."""
        final_product, bom, (op_cut, op_bend) = self._create_two_step_bom('E2EINT')
        chain = self._externalize_last_operation(bom, op_bend)

        wizard = self.env['mrp.subcontracting.internalization'].create({
            'chain_id': chain.id,
            'workcenter_id': self.workcenter.id,
            'eco_type_id': self._create_eco_type().id,
            'eco_handling': 'validated',
        })
        wizard.action_next()
        wizard.action_confirm()

        merged_bom = chain.internalized_bom_id
        self.assertEqual(merged_bom.type, 'normal')
        self.assertEqual(len(merged_bom.operation_ids), 2)

        production_form = Form(self.env['mrp.production'])
        production_form.product_id = final_product.product_variant_id
        production_form.bom_id = merged_bom
        production_form.product_qty = 1.0
        production = production_form.save()
        self._run_workorders(production)

        self.assertEqual(production.state, 'done')
        self.assertEqual(len(production.workorder_ids), 2, 'Both operations must run in-house.')
        self.assertEqual(final_product.product_variant_id.qty_available, 1.0)
        self.assertEqual(
            self.env['purchase.order'].search_count([('partner_id', '=', self.subcontractor.id)]),
            0,
            'Producing through the internalized route must never involve the subcontractor.')
