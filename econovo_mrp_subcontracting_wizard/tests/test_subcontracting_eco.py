# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSubcontractingEco(TransactionCase):
    """Cover the full PLM round trip: create the ECO, build on its revision, apply, go live."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'ECO Subcontractor', 'is_company': True})
        cls.workcenter = cls.env['mrp.workcenter'].create({
            'name': 'ECO Work Center', 'company_id': cls.company.id})
        cls.category_cut = cls.env['mrp.routing.operation.category'].create({
            'name': 'Cutting', 'code': 'ECOCL'})
        cls.category_bend = cls.env['mrp.routing.operation.category'].create({
            'name': 'Bending', 'code': 'ECOPL'})
        cls.category_plate = cls.env['mrp.routing.operation.category'].create({
            'name': 'Plating', 'code': 'ECOZN'})

        # Mirrors the real staging setup: a blocking stage sits between the first stage and
        # the one that allows applying changes.
        Stage = cls.env['mrp.eco.stage']
        cls.stage_draft = Stage.create({'name': 'ECO Draft', 'sequence': 10})
        cls.stage_review = Stage.create({
            'name': 'ECO Review', 'sequence': 20, 'is_blocking': True})
        cls.stage_ready = Stage.create({
            'name': 'ECO Ready', 'sequence': 30, 'allow_apply_change': True})
        cls.stage_done = Stage.create({
            'name': 'ECO Effective', 'sequence': 40,
            'allow_apply_change': True, 'final_stage': True})
        cls.eco_type = cls.env['mrp.eco.type'].create({
            'name': 'ECO Process Change',
            'stage_ids': [(6, 0, (cls.stage_draft + cls.stage_review + cls.stage_ready
                                  + cls.stage_done).ids)],
        })

    def _create_bom_with_route(self, code):
        product = self.env['product.template'].create({
            'name': 'ECO Part %s' % code, 'default_code': code, 'type': 'product'})
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': product.id,
            'product_qty': 1.0,
            'product_uom_id': product.uom_id.id,
            'type': 'normal',
            'company_id': self.company.id,
        })
        operations = self.env['mrp.routing.workcenter']
        for index, category in enumerate(
                [self.category_cut, self.category_bend, self.category_plate]):
            operations |= self.env['mrp.routing.workcenter'].create({
                'bom_id': bom.id,
                'name': category.name,
                'workcenter_id': self.workcenter.id,
                'sequence': (index + 1) * 10,
                'operation_category_id': category.id,
            })
        component = self.env['product.template'].create({
            'name': 'ECO Component %s' % code, 'default_code': 'CMP%s' % code,
            'type': 'product'})
        self.env['mrp.bom.line'].create({
            'bom_id': bom.id,
            'product_id': component.product_variant_id.id,
            'product_qty': 1.0,
            'operation_id': operations[1].id,
        })
        return bom, operations

    def _externalize(self, bom, operation, eco_handling):
        wizard = self.env['mrp.subcontracting.externalization'].create({
            'company_id': self.company.id,
            'bom_id': bom.id,
            'operation_id': operation.id,
            'subcontractor_id': self.subcontractor.id,
            'warehouse_id': self.warehouse.id,
            'eco_type_id': self.eco_type.id,
            'eco_handling': eco_handling,
        })
        wizard.action_next()
        action = wizard.action_confirm()
        return self.env['mrp.subcontracting.chain'].browse(action['res_id'])

    def test_validated_eco_is_really_applied_and_records_go_live(self):
        bom, operations = self._create_bom_with_route('ECOVAL')
        chain = self._externalize(bom, operations[1], 'validated')

        eco = chain.eco_ids
        self.assertEqual(len(eco), 1)
        self.assertEqual(eco.state, 'done')
        self.assertTrue(eco.stage_id.final_stage)
        self.assertEqual(chain.validated_by_id, self.env.user)
        self.assertTrue(chain.validated_date)
        # Everything the chain generated must be usable straight away.
        self.assertTrue(chain.bom_ids)
        self.assertTrue(all(chain.bom_ids.mapped('active')))
        self.assertTrue(all(chain.phantom_product_tmpl_ids.mapped('active')))
        self.assertTrue(chain.bom_ids.filtered(lambda b: b.type == 'subcontract'))

    def test_pending_eco_keeps_generated_records_archived(self):
        bom, operations = self._create_bom_with_route('ECOPEND')
        chain = self._externalize(bom, operations[1], 'auto')

        eco = chain.eco_ids
        self.assertNotEqual(eco.state, 'done')
        self.assertEqual(eco.stage_id, self.stage_draft)
        # An ECO waiting for approval must not leave a half live chain behind.
        self.assertFalse(
            chain.bom_ids.filtered('active'),
            'No Bill of Materials of a pending chain may be active.')
        self.assertFalse(
            chain.phantom_product_tmpl_ids.filtered('active'),
            'No intermediate product of a pending chain may be active.')
        # The Bill of Materials still in production is untouched.
        self.assertEqual(bom.type, 'normal')
        self.assertEqual(len(bom.operation_ids), 3)

    def test_applying_a_pending_eco_activates_the_chain(self):
        bom, operations = self._create_bom_with_route('ECOWALK')
        chain = self._externalize(bom, operations[1], 'auto')
        eco = chain.eco_ids

        # Walk the approval circuit the way a user would, one stage at a time.
        eco.stage_id = self.stage_review.id
        eco.stage_id = self.stage_ready.id
        eco.action_apply()

        self.assertEqual(eco.state, 'done')
        self.assertTrue(all(chain.bom_ids.mapped('active')))
        self.assertTrue(all(chain.phantom_product_tmpl_ids.mapped('active')))

    def test_internalization_through_an_eco_merges_and_archives(self):
        bom, operations = self._create_bom_with_route('ECOBACK')
        chain = self._externalize(bom, operations[1], 'validated')

        wizard = self.env['mrp.subcontracting.internalization'].create({
            'chain_id': chain.id,
            'workcenter_id': self.workcenter.id,
            'eco_type_id': self.eco_type.id,
            'eco_handling': 'validated',
        })
        wizard.action_next()
        wizard.action_confirm()

        self.assertEqual(chain.state, 'internalized')
        merged_bom = chain.internalized_bom_id
        self.assertTrue(merged_bom.active)
        self.assertEqual(merged_bom.type, 'normal')
        self.assertEqual(len(merged_bom.operation_ids), 3)
        self.assertFalse(chain.phantom_product_tmpl_ids.filtered('active'))
        self.assertEqual(len(chain.eco_ids), 2)
