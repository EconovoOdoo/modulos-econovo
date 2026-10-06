from odoo import _
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStockBookCopy(TransactionCase):

    def setUp(self):
        super().setUp()
        sequence = self.env['ir.sequence'].create({
            'name': 'Test Stock Voucher Sequence',
            'code': 'stock.voucher',
            'prefix': 'TEST/',
            'company_id': self.env.company.id,
        })
        self.book = self.env['stock.book'].create({
            'name': 'Test Talonario',
            'sequence_id': sequence.id,
            'lines_per_voucher': 0,
        })

    def test_copy_adds_translated_suffix_to_stock_book(self):
        duplicate = self.book.copy()

        self.assertEqual(duplicate.name, _('%s (copy)', self.book.name))

    def test_copy_preserves_explicit_stock_book_name(self):
        duplicate = self.book.copy({'name': 'Custom Talonario'})

        self.assertEqual(duplicate.name, 'Custom Talonario')

    def test_stock_picking_copy_does_not_add_stock_book_suffix(self):
        picking_type = self.env.ref('stock.picking_type_in')
        picking = self.env['stock.picking'].create({
            'name': 'TEST/IN/00001',
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
            'company_id': self.env.company.id,
        })

        duplicate = picking.copy()

        self.assertNotEqual(
            duplicate.name,
            _('%s (copy)', picking.name),
        )