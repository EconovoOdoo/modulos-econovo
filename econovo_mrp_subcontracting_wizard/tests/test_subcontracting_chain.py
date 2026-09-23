# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSubcontractingChain(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'Test Subcontractor',
            'is_company': True,
        })
        cls.category_laser = cls.env['mrp.routing.operation.category'].create({
            'name': 'Laser Cutting', 'code': 'CL'})
        cls.category_bending = cls.env['mrp.routing.operation.category'].create({
            'name': 'Bending', 'code': 'PL'})
        cls.category_plating = cls.env['mrp.routing.operation.category'].create({
            'name': 'Zinc Plating', 'code': 'ZN'})
        cls.workcenter = cls.env['mrp.workcenter'].create({
            'name': 'Test Work Center', 'company_id': cls.company.id})

    def _create_product(self, name, default_code):
        return self.env['product.template'].create({
            'name': name,
            'default_code': default_code,
            'type': 'product',
        })

    def _create_bom(self, product_tmpl, component_count=3, operation_categories=None):
        """Build a BoM with one component per operation plus one unassigned component."""
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': product_tmpl.id,
            'product_qty': 1.0,
            'product_uom_id': product_tmpl.uom_id.id,
            'type': 'normal',
            'company_id': self.company.id,
        })
        operations = self.env['mrp.routing.workcenter']
        for index, category in enumerate(operation_categories or []):
            operations |= self.env['mrp.routing.workcenter'].create({
                'bom_id': bom.id,
                'name': category.name,
                'workcenter_id': self.workcenter.id,
                'sequence': (index + 1) * 10,
                'operation_category_id': category.id,
            })
        for index in range(component_count):
            component = self._create_product('Component %s %s' % (product_tmpl.name, index),
                                             'CMP-%s-%s' % (product_tmpl.default_code, index))
            self.env['mrp.bom.line'].create({
                'bom_id': bom.id,
                'product_id': component.product_variant_id.id,
                'product_qty': 1.0,
                'operation_id': operations[index].id if index < len(operations) else False,
            })
        return bom, operations

    def test_operation_category_code_must_be_safe_for_product_codes(self):
        with self.assertRaises(ValidationError):
            self.env['mrp.routing.operation.category'].create({
                'name': 'Bad', 'code': 'zn 1'})

    def test_externalize_last_operation_creates_one_intermediate_product(self):
        product = self._create_product('Part Last', 'PARTLAST')
        bom, operations = self._create_bom(
            product, operation_categories=[self.category_laser, self.category_bending,
                                           self.category_plating])
        chain = self.env['mrp.subcontracting.chain']._externalize(
            bom, operations[2], self.subcontractor, self.warehouse)

        self.assertEqual(len(chain.bom_ids), 2)
        self.assertEqual(len(chain.phantom_product_tmpl_ids), 1)
        # The part handed over is named after the last in-house operation, not the external one.
        self.assertEqual(chain.phantom_product_tmpl_ids.default_code, 'PARTLAST-PL')
        # The subcontractor returns the real final product, so nothing else is generated.
        self.assertEqual(chain.anchor_product_tmpl_id, product)
        self.assertEqual(bom.type, 'subcontract')
        self.assertEqual(bom.subcontractor_ids, self.subcontractor)
        self.assertFalse(bom.operation_ids)

    def test_externalize_middle_operation_creates_two_intermediate_products(self):
        product = self._create_product('Part Middle', 'PARTMID')
        bom, operations = self._create_bom(
            product, operation_categories=[self.category_laser, self.category_bending,
                                           self.category_plating])
        chain = self.env['mrp.subcontracting.chain']._externalize(
            bom, operations[1], self.subcontractor, self.warehouse)

        self.assertEqual(len(chain.bom_ids), 3)
        codes = set(chain.phantom_product_tmpl_ids.mapped('default_code'))
        self.assertEqual(codes, {'PARTMID-CL', 'PARTMID-PL'})
        # The purchase order is placed for the state of the part when it comes back.
        self.assertEqual(chain.anchor_product_tmpl_id.default_code, 'PARTMID-PL')
        # The original BoM survives as the one producing the real final product.
        self.assertEqual(bom.product_tmpl_id, product)
        self.assertEqual(bom.type, 'normal')
        self.assertEqual(bom.operation_ids.operation_category_id, self.category_plating)

    def test_externalize_first_operation_creates_one_intermediate_product(self):
        product = self._create_product('Part First', 'PARTFIRST')
        bom, operations = self._create_bom(
            product, operation_categories=[self.category_laser, self.category_bending,
                                           self.category_plating])
        chain = self.env['mrp.subcontracting.chain']._externalize(
            bom, operations[0], self.subcontractor, self.warehouse)

        self.assertEqual(len(chain.bom_ids), 2)
        # No in-house step happens before, so the part is named after the external operation.
        self.assertEqual(chain.phantom_product_tmpl_ids.default_code, 'PARTFIRST-CL')
        self.assertEqual(bom.product_tmpl_id, product)
        self.assertEqual(len(bom.operation_ids), 2)

    def test_externalize_whole_product_generates_no_intermediate_product(self):
        product = self._create_product('Part Whole', 'PARTWHOLE')
        bom, dummy = self._create_bom(product, operation_categories=[])
        chain = self.env['mrp.subcontracting.chain']._externalize(
            bom, self.env['mrp.routing.workcenter'], self.subcontractor, self.warehouse)

        self.assertEqual(len(chain.bom_ids), 1)
        self.assertFalse(chain.phantom_product_tmpl_ids)
        self.assertEqual(bom.type, 'subcontract')

    def test_externalize_adds_resupply_route_to_delivered_components(self):
        product = self._create_product('Part Route', 'PARTROUTE')
        bom, operations = self._create_bom(
            product, operation_categories=[self.category_laser, self.category_bending])
        chain = self.env['mrp.subcontracting.chain']._externalize(
            bom, operations[1], self.subcontractor, self.warehouse)

        route = self.env['mrp.subcontracting.chain']._get_resupply_route()
        self.assertTrue(route, 'The global subcontractor resupply route must exist.')
        self.assertTrue(
            route.product_selectable,
            'Only a product selectable route is visible in product.template.route_ids.')
        self.assertTrue(chain.component_line_ids)
        for line in chain.component_line_ids:
            self.assertIn(route, line.product_tmpl_id.route_ids)
            self.assertEqual(line.state, 'ok')
        self.assertEqual(chain.warning_count, 0)

    def test_warehouse_resupply_route_is_never_written_on_a_component(self):
        # It is created with product_selectable=False, so it can never be read back and the
        # checklist would stay red forever.
        product = self._create_product('Part WH Route', 'PARTWHROUTE')
        bom, operations = self._create_bom(
            product, operation_categories=[self.category_laser, self.category_bending])
        chain = self.env['mrp.subcontracting.chain']._externalize(
            bom, operations[1], self.subcontractor, self.warehouse)

        products = chain.component_line_ids.product_tmpl_id
        self.assertFalse(self.env['product.template'].with_context(active_test=False).search([
            ('id', 'in', products.ids),
            ('route_ids', 'in', self.warehouse.subcontracting_route_id.ids),
        ]))

    def test_anchor_product_becomes_purchasable(self):
        product = self._create_product('Part Buy', 'PARTBUY')
        product.purchase_ok = False
        bom, operations = self._create_bom(
            product, operation_categories=[self.category_laser, self.category_bending])
        chain = self.env['mrp.subcontracting.chain']._externalize(
            bom, operations[1], self.subcontractor, self.warehouse)

        self.assertTrue(
            chain.anchor_product_tmpl_id.purchase_ok,
            'A purchase order line can only carry a purchasable product.')

    def test_internalized_chain_reports_no_missing_route(self):
        product = self._create_product('Part Quiet', 'PARTQUIET')
        bom, operations = self._create_bom(
            product, operation_categories=[self.category_laser, self.category_bending])
        chain = self.env['mrp.subcontracting.chain']._externalize(
            bom, operations[1], self.subcontractor, self.warehouse)
        chain.component_line_ids.product_tmpl_id.write({
            'route_ids': [(3, self.env['mrp.subcontracting.chain']._get_resupply_route().id)],
        })
        self.assertTrue(chain.warning_count)

        chain._internalize(self.workcenter)

        self.assertEqual(chain.state, 'internalized')
        self.assertEqual(
            chain.warning_count, 0,
            'Nothing is delivered any more, the checklist must stop warning.')

    def test_a_product_can_be_externalized_again_after_being_internalized(self):
        product = self._create_product('Part Again', 'PARTAGAIN')
        bom, operations = self._create_bom(
            product, operation_categories=[self.category_laser, self.category_bending])
        first_chain = self.env['mrp.subcontracting.chain']._externalize(
            bom, operations[1], self.subcontractor, self.warehouse)
        merged_bom = first_chain._internalize(self.workcenter)

        restored = merged_bom.operation_ids.filtered(
            lambda op: op.operation_category_id == self.category_bending)
        second_chain = self.env['mrp.subcontracting.chain']._externalize(
            merged_bom, restored, self.subcontractor, self.warehouse)

        self.assertNotEqual(second_chain, first_chain)
        self.assertEqual(first_chain.state, 'internalized')
        self.assertEqual(second_chain.state, 'externalized')
        self.assertEqual(
            second_chain.phantom_product_tmpl_ids, first_chain.phantom_product_tmpl_ids,
            'The intermediate product must be reused, never duplicated.')
        self.assertTrue(second_chain.phantom_product_tmpl_ids.active)

    def test_internalize_merges_everything_back_into_a_single_bom(self):
        product = self._create_product('Part Back', 'PARTBACK')
        bom, operations = self._create_bom(
            product, operation_categories=[self.category_laser, self.category_bending,
                                           self.category_plating])
        chain = self.env['mrp.subcontracting.chain']._externalize(
            bom, operations[1], self.subcontractor, self.warehouse)

        merged_bom = chain._internalize(self.workcenter)

        self.assertEqual(chain.state, 'internalized')
        self.assertEqual(merged_bom.type, 'normal')
        self.assertFalse(merged_bom.subcontractor_ids)
        self.assertEqual(len(merged_bom.operation_ids), 3)
        self.assertFalse(
            chain.phantom_product_tmpl_ids.filtered('active'),
            'Intermediate products must be archived once the route is back in-house.')
        self.assertFalse(
            merged_bom.bom_line_ids.filtered(
                lambda line: line.product_id.product_tmpl_id.is_subcontracting_phantom),
            'No intermediate product may remain as a component of the merged BoM.')

    def test_internalize_keeps_components_added_while_externalized(self):
        product = self._create_product('Part Kept', 'PARTKEPT')
        bom, operations = self._create_bom(
            product, operation_categories=[self.category_laser, self.category_bending,
                                           self.category_plating])
        chain = self.env['mrp.subcontracting.chain']._externalize(
            bom, operations[1], self.subcontractor, self.warehouse)

        # A component is added to the subcontracted stage after the externalization.
        late_component = self._create_product('Late Component', 'LATECMP')
        subcontract_bom = chain._get_subcontracted_bom()
        self.env['mrp.bom.line'].create({
            'bom_id': subcontract_bom.id,
            'product_id': late_component.product_variant_id.id,
            'product_qty': 2.0,
        })

        merged_bom = chain._internalize(self.workcenter)

        self.assertIn(
            late_component.product_variant_id,
            merged_bom.bom_line_ids.product_id,
            'Internalization must preserve the current content, not roll back to a snapshot.')

    def test_externalize_button_on_one_operation_opens_the_individual_assistant(self):
        product = self._create_product('Part Entry One', 'PARTENTRY1')
        bom, operations = self._create_bom(
            product, operation_categories=[self.category_laser, self.category_bending])

        action = operations[1].action_externalize_operation()

        self.assertEqual(action['res_model'], 'mrp.subcontracting.externalization')
        self.assertEqual(action['context']['default_bom_id'], bom.id)
        self.assertEqual(action['context']['default_operation_id'], operations[1].id)

    def test_externalize_button_on_many_operations_opens_the_bulk_assistant(self):
        first, dummy = self._create_bom(
            self._create_product('Part Entry A', 'PARTENTRYA'),
            operation_categories=[self.category_bending])
        second, dummy2 = self._create_bom(
            self._create_product('Part Entry B', 'PARTENTRYB'),
            operation_categories=[self.category_bending])
        operations = first.operation_ids | second.operation_ids

        action = operations.action_externalize_operation()

        self.assertEqual(action['res_model'], 'mrp.subcontracting.bulk')
        wizard = self.env['mrp.subcontracting.bulk'].browse(action['res_id'])
        self.assertEqual(wizard.mode, 'externalize')
        self.assertEqual(wizard.total_count, 2)
        self.assertEqual(wizard.line_ids.operation_id, operations)

    def test_externalize_button_refuses_a_bom_already_subcontracted(self):
        product = self._create_product('Part Busy', 'PARTBUSY')
        bom, operations = self._create_bom(
            product, operation_categories=[self.category_laser, self.category_bending])
        chain = self.env['mrp.subcontracting.chain']._externalize(
            bom, operations[1], self.subcontractor, self.warehouse)

        # The externalized operation no longer exists; what the user sees in the list is the
        # one that stayed in-house, and it belongs to a chain that is still live.
        with self.assertRaises(UserError):
            chain.bom_ids.operation_ids.action_externalize_operation()

    def test_internalize_button_finds_the_chain_from_the_operation(self):
        product = self._create_product('Part Return', 'PARTRETURN')
        bom, operations = self._create_bom(
            product, operation_categories=[self.category_laser, self.category_bending])
        chain = self.env['mrp.subcontracting.chain']._externalize(
            bom, operations[1], self.subcontractor, self.warehouse)

        action = chain.bom_ids.operation_ids.action_internalize_operation()

        self.assertEqual(action['res_model'], 'mrp.subcontracting.internalization')
        self.assertEqual(action['context']['default_chain_id'], chain.id)

    def test_operation_category_counts_its_operations(self):
        self._create_bom(
            self._create_product('Part Counted', 'PARTCOUNTED'),
            operation_categories=[self.category_plating])

        self.assertEqual(self.category_plating.operation_count, 1)
        action = self.category_plating.action_view_operations()
        self.assertEqual(action['res_model'], 'mrp.routing.workcenter')
