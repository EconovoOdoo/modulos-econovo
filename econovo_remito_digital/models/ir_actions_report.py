##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import io

from odoo import models, tools


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    _REMITO_DIGITAL_REPORT_NAME = 'econovo_remito_digital.report_remito_digital_document'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """Render one PDF per (picking, copy) pair for the digital remito
        report, then merge them together.

        The remito template no longer pre-splits pages in Python: each
        picking's product table flows naturally and wkhtmltopdf paginates
        it on its own (accurate, no height-estimation heuristics). To get
        an accurate "Hoja X de Y" counter that resets per copy (ORIGINAL/
        DUPLICADO/...) instead of running across the whole batch, each
        (picking, copy) pair is rendered as its own single-doc PDF - so
        wkhtmltopdf's native page counter naturally restarts at 1 - and all
        resulting PDFs are merged into one, in order, via the same
        _merge_pdfs() utility core itself uses for multi-doc batch printing.

        Every other report is untouched (falls through to super()
        immediately), and pickings whose book only needs a single ORIGINAL
        copy take the exact same single-pass path used before this override
        existed - zero extra wkhtmltopdf invocations for the common case.
        """
        report_sudo = self._get_report(report_ref)
        if report_sudo.report_name != self._REMITO_DIGITAL_REPORT_NAME:
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

        if isinstance(res_ids, int):
            res_ids = [res_ids]

        # Under Odoo's test runner, _render_qweb_pdf falls back to HTML
        # rendering (no real PDF bytes to merge yet) - let core handle that
        # exactly as it would for any other report.
        is_test_mode = (
            (tools.config['test_enable'] or tools.config['test_file'])
            and not self.env.context.get('force_report_rendering')
        )
        if not res_ids or is_test_mode:
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

        pickings = self.env['stock.picking'].browse(res_ids)
        needs_split = any(
            len(picking.book_id._get_remito_copies_labels()) > 1
            for picking in pickings
        )
        if not needs_split:
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

        streams = []
        for picking in pickings:
            for label in picking.book_id._get_remito_copies_labels():
                pdf_content, _report_type = super(
                    IrActionsReport, self.with_context(econovo_copy_label=label)
                )._render_qweb_pdf(report_ref, res_ids=[picking.id], data=data)
                streams.append(io.BytesIO(pdf_content))

        with self._merge_pdfs(streams) as merged_stream:
            return merged_stream.getvalue(), 'pdf'
