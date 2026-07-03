# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit
#
################################################################################
import logging
from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AttendanceDownloadWizard(models.TransientModel):
    """Wizard to download attendance with mode selection and result summary.

    Lets the user choose a download window (Smart / Today / Week / Month / All)
    and shows a results summary sourced from the device operation log after the
    download completes.
    """
    _name = 'attendance.download.wizard'
    _description = 'Attendance Download Progress Wizard'

    device_id = fields.Many2one(
        'biometric.device.details', string='Device', required=True, readonly=True)
    download_mode = fields.Selection([
        ('smart', 'Smart (Auto-detect)'),
        ('today', 'Today Only'),
        ('weekly', 'Current Week'),
        ('current_month', 'Current Month'),
        ('all', 'All Records'),
    ], string='Download Mode', default='smart', required=True)

    # State
    state = fields.Selection([
        ('draft', 'Ready'),
        ('done', 'Completed'),
        ('error', 'Failed'),
    ], string='State', default='draft')

    # Result summary (populated after download)
    records_found = fields.Integer(string='Records Found', readonly=True)
    records_new = fields.Integer(string='New Records', readonly=True)
    records_duplicate = fields.Integer(string='Duplicates Skipped', readonly=True)
    records_failed = fields.Integer(string='Failed', readonly=True)
    duration = fields.Float(string='Duration (sec)', readonly=True)
    result_message = fields.Text(string='Result', readonly=True)

    def action_start_download(self):
        """Run the attendance download and show results."""
        self.ensure_one()

        if self.device_id.connection_mode == 'adms':
            self.write({
                'state': 'done',
                'result_message': _(
                    'Cloud (ADMS) devices push attendance data automatically — '
                    'no manual download is needed.\n\n'
                    'Check "Operation Logs" on the device to see the most recent syncs.'
                ),
            })
            return self._reload()

        try:
            self.device_id.action_download_attendance(download_mode=self.download_mode)
        except Exception as e:
            self.write({
                'state': 'error',
                'result_message': _('Download failed: %s') % str(e),
            })
            return self._reload()

        # Read the most recent log entry created by the download
        log = self.env['biometric.device.log'].sudo().search([
            ('device_id', '=', self.device_id.id),
            ('log_type', '=', 'download'),
        ], order='create_date desc', limit=1)

        if log:
            self.write({
                'state': 'done' if log.status != 'failed' else 'error',
                'records_found': log.records_found or 0,
                'records_new': log.records_new or 0,
                'records_duplicate': log.records_duplicate or 0,
                'records_failed': log.records_failed or 0,
                'duration': log.duration or 0.0,
                'result_message': log.details or '',
            })
        else:
            self.write({
                'state': 'done',
                'result_message': _('Download completed.'),
            })

        return self._reload()

    def _reload(self):
        """Return action to refresh wizard form in the same dialog."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'attendance.download.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}
