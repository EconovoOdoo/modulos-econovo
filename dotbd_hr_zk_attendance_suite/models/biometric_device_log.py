# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit
#
################################################################################
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BiometricDeviceLog(models.Model):
    """Model to store per-device operation logs (download, connection, sync, etc.)"""
    _name = 'biometric.device.log'
    _description = 'Biometric Device Operation Log'
    _order = 'log_time desc'
    _rec_name = 'display_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    device_id = fields.Many2one(
        'biometric.device.details', string='Device',
        required=True, ondelete='cascade', index=True,
        help='The biometric device this log belongs to')

    log_type = fields.Selection([
        ('download', 'Attendance Download'),
        ('connection', 'Connection Test'),
        ('sync', 'User Sync'),
        ('live_capture', 'Live Capture'),
        ('info_refresh', 'Device Info Refresh'),
        ('other', 'Other'),
    ], string='Operation Type', required=True, default='download', index=True,
       tracking=True)

    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('warning', 'Warning'),
    ], string='Status', required=True, default='success', index=True,
       tracking=True)

    log_time = fields.Datetime(
        string='Time', required=True,
        default=fields.Datetime.now, index=True)

    # Download-specific fields
    records_found = fields.Integer(
        string='Records on Device', default=0,
        help='Total attendance records found on device')
    records_new = fields.Integer(
        string='New Records Imported', default=0,
        help='New records successfully imported')
    records_duplicate = fields.Integer(
        string='Duplicates Skipped', default=0,
        help='Records skipped because they already existed')
    records_failed = fields.Integer(
        string='Failed Records', default=0,
        help='Records that failed to import')
    employees_not_found = fields.Integer(
        string='Unknown Employees', default=0,
        help='Punches from device user IDs not linked to any employee')

    duration = fields.Float(
        string='Duration (sec)', digits=(10, 2), default=0.0,
        help='Time taken for the operation in seconds')

    error_message = fields.Text(
        string='Error Message',
        help='Error details if the operation failed')
    details = fields.Text(
        string='Details',
        help='Additional information about the operation')

    company_id = fields.Many2one(
        'res.company', string='Company',
        related='device_id.company_id', store=True)

    display_name = fields.Char(
        string='Name', compute='_compute_display_name', store=True)

    @api.depends('device_id', 'log_type', 'log_time', 'status')
    def _compute_display_name(self):
        type_labels = dict(self._fields['log_type'].selection)
        status_labels = dict(self._fields['status'].selection)
        for rec in self:
            device_name = rec.device_id.name or 'Unknown'
            log_type = type_labels.get(rec.log_type, rec.log_type)
            status = status_labels.get(rec.status, rec.status)
            time_str = fields.Datetime.to_string(rec.log_time) if rec.log_time else ''
            rec.display_name = f"{device_name} - {log_type} [{status}] {time_str}"

    def action_delete_all_logs(self):
        """Delete all logs for this device. Opens confirmation wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Delete All Logs - %s') % self.device_id.name,
            'res_model': 'biometric.log.cleanup.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_device_id': self.device_id.id},
        }

    def action_delete_all_device_logs(self):
        """Delete all logs across all devices. Opens confirmation wizard."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Delete All Device Logs'),
            'res_model': 'biometric.log.cleanup.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def cron_cleanup_old_logs(self):
        """Scheduled action to clean up old logs across all devices.
        Uses retention_days from each device's configuration."""
        from datetime import datetime, timedelta

        devices = self.env['biometric.device.details'].search([])
        total_cleaned = 0

        for device in devices:
            retention = 90  # Default 90 days
            cutoff_date = datetime.now() - timedelta(days=retention)
            old_logs = self.search([
                ('device_id', '=', device.id),
                ('log_time', '<', fields.Datetime.to_string(cutoff_date)),
            ])

            count = len(old_logs)
            if count > 0:
                old_logs.unlink()
                total_cleaned += count

        if total_cleaned > 0:
            _logger.info("Log cleanup complete: Deleted %d total old logs", total_cleaned)

        return True
