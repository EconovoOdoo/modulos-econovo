##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from collections import defaultdict

from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def do_print_voucher(self):
        """Override: when the book is digital, validate CAI, auto-assign one
        voucher number if none exists yet, and render the digital template.
        Falls through to the standard stack for non-digital books."""
        self.ensure_one()
        if not self.book_id or not self.book_id.is_digital:
            return super().do_print_voucher()

        book = self.book_id

        # Validate CAI expiry
        if book.l10n_ar_cai_due and book.l10n_ar_cai_due < fields.Date.today():
            raise UserError(_(
                'The CAI of book "%s" expired on %s. '
                'Please update the book before printing.',
                book.name,
                book.l10n_ar_cai_due,
            ))

        # Auto-assign one voucher number if not yet assigned (P3=B)
        if not self.voucher_ids:
            self.assign_numbers(1, book)

        return self.env.ref(
            'econovo_remito_digital.action_report_remito_digital'
        ).report_action(self)

    def _get_remito_digital_grouped_lines(self):
        """Return move lines grouped by product with lot data for the digital
        remito template.

        Each group dict contains:
          - product: product.product record
          - code: internal reference string
          - qty_total: total done/reserved quantity (float)
          - uom: unit of measure display name
          - lots: list of stock.lot records
          - lots_text: formatted lot string (with vehicle data if available)
        """
        self.ensure_one()
        grouped = defaultdict(lambda: {
            'product': None,
            'code': '',
            'qty_total': 0.0,
            'uom': '',
            'lots': [],
            'lots_text': '',
        })

        for ml in self.move_line_ids:
            pid = ml.product_id.id
            grouped[pid]['product'] = ml.product_id
            grouped[pid]['code'] = ml.product_id.default_code or ''
            grouped[pid]['qty_total'] += ml.quantity or 0.0
            grouped[pid]['uom'] = ml.product_uom_id.name if ml.product_uom_id else ''
            if ml.lot_id and ml.lot_id not in grouped[pid]['lots']:
                grouped[pid]['lots'].append(ml.lot_id)

        for group in grouped.values():
            if group['lots']:
                parts = []
                for lot in group['lots']:
                    # Defensive access: use extended name only if gg_lot_data is installed
                    if 'marca' in lot._fields:
                        extended = lot.get_product_extended_name()
                        parts.append(
                            'Serie: %s (%s)' % (lot.name, extended) if extended else 'Serie: %s' % lot.name
                        )
                    else:
                        parts.append('Serie: %s' % lot.name)
                group['lots_text'] = ', '.join(parts)

        return list(grouped.values())

    def _get_remito_digital_grouped_pages(self, max_lines=25):
        """Paginate grouped lines for multi-page rendering."""
        self.ensure_one()
        lines = self._get_remito_digital_grouped_lines()
        pages = []
        for i in range(0, max(len(lines), 1), max_lines):
            pages.append(lines[i:i + max_lines])
        return pages
