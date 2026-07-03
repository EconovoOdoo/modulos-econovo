# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit
#
################################################################################
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BiometricLogCleanupWizard(models.TransientModel):
    """Wizard to delete old device logs."""
    _name = 'biometric.log.cleanup.wizard'
    _description = 'Biometric Log Cleanup Wizard'

    device_id = fields.Many2one('biometric.device.details', string='Device')
    cleanup_type = fields.Selection([
        ('all', 'All Logs'),
        ('failed', 'Failed Logs Only'),
        ('success', 'Success Logs Only'),
        ('warning', 'Warning Logs Only'),
        ('download', 'Download Logs Only'),
        ('live_capture', 'Live Capture Logs Only'),
    ], string='Cleanup Type', default='all', required=True)

    retention_days = fields.Integer(string='Delete Logs Older Than (Days)', default=30, required=True)
    log_count = fields.Integer(string='Logs to Delete', compute='_compute_log_count', readonly=True)
    confirm_delete = fields.Boolean(string='I understand this action cannot be undone', default=False)

    @api.depends('device_id', 'cleanup_type', 'retention_days')
    def _compute_log_count(self):
        """Count logs that will be deleted."""
        for wizard in self:
            domain = [('log_time', '<', fields.Datetime.now() - timedelta(days=wizard.retention_days))]
            if wizard.device_id:
                domain.append(('device_id', '=', wizard.device_id.id))
            if wizard.cleanup_type == 'failed':
                domain.append(('status', '=', 'failed'))
            elif wizard.cleanup_type == 'success':
                domain.append(('status', '=', 'success'))
            elif wizard.cleanup_type == 'warning':
                domain.append(('status', '=', 'warning'))
            elif wizard.cleanup_type == 'download':
                domain.append(('log_type', '=', 'download'))
            elif wizard.cleanup_type == 'live_capture':
                domain.append(('log_type', '=', 'live_capture'))
            wizard.log_count = self.env['biometric.device.log'].search_count(domain)

    def action_confirm_cleanup(self):
        """Delete old logs."""
        self.ensure_one()

        if not self.confirm_delete:
            raise UserError(_("Please confirm that you understand this action cannot be undone."))

        domain = [('log_time', '<', fields.Datetime.now() - timedelta(days=self.retention_days))]
        if self.device_id:
            domain.append(('device_id', '=', self.device_id.id))
        if self.cleanup_type == 'failed':
            domain.append(('status', '=', 'failed'))
        elif self.cleanup_type == 'success':
            domain.append(('status', '=', 'success'))
        elif self.cleanup_type == 'warning':
            domain.append(('status', '=', 'warning'))
        elif self.cleanup_type == 'download':
            domain.append(('log_type', '=', 'download'))
        elif self.cleanup_type == 'live_capture':
            domain.append(('log_type', '=', 'live_capture'))

        logs_to_delete = self.env['biometric.device.log'].search(domain)
        count = len(logs_to_delete)

        if count > 0:
            logs_to_delete.unlink()

        # Log the cleanup action
        if self.device_id:
            self.device_id.message_post(
                body=_("Cleaned up %d old %s logs (older than %d days)") % (
                    count, self.cleanup_type, self.retention_days
                ),
                message_type='notification'
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cleanup Complete'),
                'message': _('Successfully deleted %d old logs.') % count,
                'type': 'success',
                'sticky': False,
            }
        }
