##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from collections import defaultdict

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date, html_escape, is_html_empty


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    signature_date = fields.Datetime('Signature Date', copy=False)
    signature_date_display = fields.Char(compute='_compute_signature_date_display')
    signed_by = fields.Char('Signed By', copy=False, help='Name typed by the '
                             'person signing, captured from the Sign dialog.')

    @api.depends('signature_date')
    def _compute_signature_date_display(self):
        for picking in self:
            if picking.signature_date:
                picking.signature_date_display = format_date(
                    self.env, picking.signature_date, date_format='dd MMMM yyyy'
                )
            else:
                picking.signature_date_display = ''

    def write(self, vals):
        """Set signature_date automatically when a signature is captured."""
        if vals.get('signature') and 'signature_date' not in vals:
            vals['signature_date'] = fields.Datetime.now()
        return super().write(vals)

    @api.onchange('book_id')
    def _onchange_book_id_cai_alert(self):
        """Show a non-blocking toast when the assigned book is low on
        sequences or has a CAI near expiry."""
        if not self.book_id:
            return
        book = self.book_id
        alerts = []

        # Remaining sequences (sequence_end is a Char like '00000200')
        if book.sequence_end and book.next_number is not None:
            try:
                remaining = int(book.sequence_end) - book.next_number + 1
                if remaining <= 10:
                    alerts.append(_('Solo quedan %d secuencia(s) disponible(s).', remaining))
            except (ValueError, TypeError):
                pass

        # CAI expiry
        if book.l10n_ar_cai_due:
            days_left = (book.l10n_ar_cai_due - fields.Date.today()).days
            if days_left < 0:
                alerts.append(_(
                    'El CAI está VENCIDO (venció hace %d día(s)).',
                    abs(days_left),
                ))
            elif days_left <= 10:
                alerts.append(_(
                    'El CAI vence en %d día(s) (%s).',
                    days_left,
                    format_date(self.env, book.l10n_ar_cai_due, date_format='dd MMMM yyyy'),
                ))

        if alerts:
            return {
                'warning': {
                    'title': _('⚠ Alerta de Talonario: %s', book.name),
                    'message': '\n'.join(alerts),
                    'type': 'notification',
                }
            }

    def _attach_sign(self):
        """Override: for digital-book pickings, attach the remito instead of
        the native delivery slip."""
        self.ensure_one()
        if not (self.book_id and self.book_id.is_digital):
            return super()._attach_sign()
        report = self.env['ir.actions.report']._render_qweb_pdf(
            'econovo_remito_digital.action_report_remito_digital', self.id
        )
        filename = '%s_remito_firmado' % self.name
        if self.partner_id:
            message = _('Remito firmado por %s', self.partner_id.name)
        else:
            message = _('Remito firmado')
        self.message_post(
            attachments=[('%s.pdf' % filename, report[0])],
            body=message,
        )
        return True

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

    def assign_numbers(self, estimated_number_of_pages, book):
        """Block assigning voucher numbers beyond the AFIP-authorized range.

        stock_voucher's base implementation only pulls the next number(s)
        from book.sequence_id (a plain ir.sequence, which never stops on its
        own); it never checks book.sequence_end ("Nro. Hasta"). Without this
        guard, a book could silently keep emitting remito numbers past what
        AFIP actually authorized for that CAI/range.
        """
        if book.sequence_end:
            try:
                last_authorized = int(book.sequence_end)
            except (TypeError, ValueError):
                last_authorized = None
            if last_authorized is not None:
                first_number = book.next_number
                last_number = first_number + estimated_number_of_pages - 1
                if last_number > last_authorized:
                    raise UserError(_(
                        'Cannot assign voucher number(s) %(first)s to '
                        '%(last)s: book "%(book)s" is only authorized up to '
                        '%(limit)s (Nro. Hasta). Assign a new book/range '
                        'before continuing.',
                        first=first_number,
                        last=last_number,
                        book=book.name,
                        limit=last_authorized,
                    ))
        return super().assign_numbers(estimated_number_of_pages, book)

    def _remito_safe_text(self, value):
        """Escape a raw value and convert embedded newlines to <br/>, for
        safe interpolation into a hand-built HTML string later rendered
        via t-raw (lots_text below). Mirrors nl2br(escape(value)) in
        odoo/addons/base/models/ir_qweb_fields.py (the same helper Odoo's
        own t-field widget='text' uses internally), so a free-typed value
        (e.g. a lot's custom Marca/Chasis field) can never break out of the
        surrounding markup and any line breaks the user typed are kept.
        """
        return html_escape(value or '').replace('\n', Markup('<br/>'))

    def _get_remito_digital_grouped_lines(self):
        """Return move lines grouped by product with lot data for the digital
        remito template.

        Each group dict contains:
          - product: product.product record
          - code: internal reference string
          - qty_total: total done/reserved quantity (float)
          - uom: unit of measure display name
          - lots: list of stock.lot records
          - lots_text: pre-built HTML (joined by ';<br/>') for t-raw display
          - lots_entry_lengths: plain-text length of each lot entry (HTML
            tags excluded), used by _remito_line_visual_weight() to
            estimate how many visual lines each entry wraps into in the
            narrow lots column
        """
        self.ensure_one()
        grouped = defaultdict(lambda: {
            'product': None,
            'code': '',
            'qty_total': 0.0,
            'uom': '',
            'lots': [],
            'lots_text': '',
            'lots_entry_lengths': [],
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
                entry_lengths = []
                for lot in group['lots']:
                    plain_parts = ['%s: %s' % (label, lot.name or '')]
                    html_parts = ['<strong>%s:</strong> %s' % (label, self._remito_safe_text(lot.name))]
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
                            value = getattr(lot, fname)
                            plain_parts.append('%s: %s' % (flabel, value))
                            html_parts.append('<strong>%s:</strong> %s' % (flabel, self._remito_safe_text(value)))
                    if 'marca_equipo' in lot._fields and lot.marca_equipo:
                        plain_parts.append('Marca de Equipo: %s' % lot.marca_equipo.name)
                        html_parts.append('<strong>Marca de Equipo:</strong> %s' % self._remito_safe_text(lot.marca_equipo.name))
                    entries.append(', '.join(html_parts))
                    entry_lengths.append(len(', '.join(plain_parts)))
                group['lots_text'] = ';<br/>'.join(entries)
                group['lots_entry_lengths'] = entry_lengths

        return list(grouped.values())

    # Calibration constants for A4 at 11.5pt/96dpi with 4mm inner padding.
    # Derived from actual page geometry rather than trial and error:
    #   A4 height 297mm - margin_top 5mm - margin_bottom 55mm = 237mm usable.
    #   ~99mm of that is consumed, on EVERY page, by: header-block top
    #   padding (4mm) + the tallest header-table column (company info /
    #   R-badge+copy legend / REMITO Nº+barcode+page-num, ~31mm) + the
    #   DESTINATARIO table (4 field-rows, ~28mm at this font size) + the
    #   TRANSPORTE table (3 rows, ~19mm) + the products table <thead>
    #   (~9mm) + inter-table borders/safety buffer (~8mm).
    #   237mm - 99mm ~= 138mm; kept a bit under that as a safety margin.
    # This is a calibrated ESTIMATE, not a measurement — re-validate
    # visually against a real multi-page remito whenever fonts/layout
    # change again (a too-generous value risks rows colliding with the
    # fixed wkhtmltopdf footer; a too-conservative one just wastes space).
    _REMITO_AVAILABLE_HEIGHT_MM = 130.0       # product rows area per page
    _REMITO_LINE_HEIGHT_MM = 7.2              # base row height (normal line)
    _REMITO_LOT_ENTRY_HEIGHT_MM = 4.2          # height of one wrapped lot-entry line
    _REMITO_DETAIL_WRAP_CHARS = 42            # .col-detail chars/line, no lots column
    _REMITO_DETAIL_WRAP_CHARS_WITH_LOTS = 32  # .col-detail chars/line, lots column present
    _REMITO_LOT_WRAP_CHARS = 26               # .col-lots chars/line (narrow, ~25% width)

    def _remito_estimate_line_count(self, text, max_chars):
        """Estimate how many visual lines `text` wraps into at `max_chars`
        characters per line. Any embedded newline forces an extra break on
        top of natural character-width wrapping — matches what nl2br()
        actually renders (see _remito_safe_text() and the product name's
        t-field widget='text' in the template).
        """
        if not text:
            return 1
        return sum(
            max(1, math.ceil(len(segment) / max_chars)) if segment else 1
            for segment in text.split('\n')
        )

    def _remito_line_visual_weight(self, group):
        """Estimate rendered height in mm for one product group row.

        The code/qty/detail/lots columns render side by side in one <tr>,
        so the real row height is the MAX of whichever column wraps to the
        most lines (not a sum) — mirrors plain HTML table row behavior.
        The detail column's wrap threshold is narrower when the lots
        column is also present (it takes ~25% of the table width away from
        detail). Each lot entry is measured by its own plain-text length so
        a single long entry (e.g. several gg_lot_data attributes
        concatenated) that wraps to 2-3 lines is weighted accordingly,
        instead of assuming every entry is exactly one line.
        """
        has_lots = bool(group['lots'])
        detail_wrap_chars = (
            self._REMITO_DETAIL_WRAP_CHARS_WITH_LOTS if has_lots
            else self._REMITO_DETAIL_WRAP_CHARS
        )
        name = (group['product'].name or '') if group['product'] else ''
        name_lines = self._remito_estimate_line_count(name, detail_wrap_chars)
        height = self._REMITO_LINE_HEIGHT_MM * name_lines

        if has_lots:
            lots_lines = sum(
                max(1, math.ceil(length / self._REMITO_LOT_WRAP_CHARS))
                for length in group['lots_entry_lengths']
            )
            height = max(height, self._REMITO_LOT_ENTRY_HEIGHT_MM * lots_lines)

        return max(height, self._REMITO_LINE_HEIGHT_MM)

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
