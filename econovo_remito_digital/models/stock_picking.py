##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import math
from collections import defaultdict

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import is_html_empty


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _has_remito_observations(self):
        """Return True when observations HTML has meaningful content."""
        self.ensure_one()
        return bool(self.observations and not is_html_empty(self.observations))

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
          - lots_text: list of formatted lot strings (e.g. ['N/S: ABC', 'N/S: XYZ'])
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
                tracking = group['product'].tracking if group['product'] else 'none'
                label = 'Serie' if tracking == 'serial' else 'Lote'
                entries = []
                for lot in group['lots']:
                    parts = ['<strong>%s:</strong> %s' % (label, lot.name)]
                    # Extra fields from gg_lot_data if installed
                    for fname, flabel in [
                        ('marca', 'Marca'),
                        ('tipo', 'Tipo'),
                        ('modelo', 'Modelo'),
                        ('motor', 'Marca Motor'),
                        ('nro_motor', 'Nro. Motor'),
                        ('chasis', 'Marca Chasis'),
                        ('nro_chasis', 'Nro. Chasis'),
                    ]:
                        if fname in lot._fields and getattr(lot, fname, False):
                            parts.append('<strong>%s:</strong> %s' % (flabel, getattr(lot, fname)))
                    if 'marca_equipo' in lot._fields and lot.marca_equipo:
                        parts.append('<strong>Marca de Equipo:</strong> %s' % lot.marca_equipo.name)
                    entries.append(', '.join(parts))
                group['lots_text'] = ';<br/>'.join(entries)

        return list(grouped.values())

    # Calibration constants for A4 at 8pt/96dpi with 4mm inner padding
    _REMITO_AVAILABLE_HEIGHT_MM = 118.0   # product rows area per page
    _REMITO_LINE_HEIGHT_MM = 5.5          # base row height (normal line)
    _REMITO_LOT_ENTRY_HEIGHT_MM = 3.5     # each extra lot entry beyond the first
    _REMITO_DETAIL_WRAP_CHARS = 50        # chars before product name wraps

    def _remito_line_visual_weight(self, group):
        """Estimate rendered height in mm for one product group row.

        Takes into account multiple lot entries and long product names
        that wrap to a second line.
        """
        base = self._REMITO_LINE_HEIGHT_MM
        # Extra height from lot entries beyond the first
        lot_count = len(group['lots'])
        if lot_count > 1:
            base += (lot_count - 1) * self._REMITO_LOT_ENTRY_HEIGHT_MM
        # Extra height if product name is long enough to wrap
        name_len = len(group['product'].name or '') if group['product'] else 0
        if name_len > self._REMITO_DETAIL_WRAP_CHARS:
            wrap_lines = math.ceil(name_len / self._REMITO_DETAIL_WRAP_CHARS)
            base = max(base, self._REMITO_LINE_HEIGHT_MM * wrap_lines)
        return base

    def _get_remito_digital_grouped_pages(self):
        """Paginate grouped lines using estimated visual height per row.

        Accumulates rows until the available height for the content area
        would be exceeded, then starts a new page.
        """
        self.ensure_one()
        lines = self._get_remito_digital_grouped_lines()
        if not lines:
            return [[]]
        pages = []
        current_page = []
        current_height = 0.0
        for group in lines:
            weight = self._remito_line_visual_weight(group)
            if current_page and current_height + weight > self._REMITO_AVAILABLE_HEIGHT_MM:
                pages.append(current_page)
                current_page = [group]
                current_height = weight
            else:
                current_page.append(group)
                current_height += weight
        if current_page:
            pages.append(current_page)
        return pages
