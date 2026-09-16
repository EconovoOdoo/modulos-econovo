# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit
#
################################################################################

import logging
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ADMSDeviceCommand(models.Model):
    """Queue of commands to be sent to ADMS-connected devices.
    Devices poll /iclock/getrequest and pick up pending commands."""
    _name = 'adms.device.command'
    _description = 'ADMS Device Command Queue'
    _order = 'create_date asc'

    # Re-queue a command if the device hasn't acknowledged it within this many
    # minutes (e.g. it received the command then lost power/network).
    _STALE_SENT_MINUTES = 10
    # After this many dispatch attempts with no acknowledgement, give up (failed).
    _MAX_DISPATCH_ATTEMPTS = 5

    device_id = fields.Many2one(
        'biometric.device.details', string='Device',
        required=True, ondelete='cascade', index=True)
    command_id = fields.Integer(
        string='Command Sequence',
        help='Auto-incremented per device, sent as C:{id}:...')
    command_type = fields.Selection([
        ('info', 'Request Info'),
        ('reboot', 'Reboot Device'),
        ('set_time', 'Set Time'),
        ('sync_user', 'Sync User'),
        ('delete_user', 'Delete User'),
        ('enroll_fp', 'Enroll Fingerprint'),
        ('enroll_bio', 'Enroll Face (Unified Template)'),
        ('clear_data', 'Clear Data'),
        ('sync_template', 'Sync Biometric Template'),
        ('custom', 'Custom Command'),
    ], string='Command Type', required=True)
    command_body = fields.Text(
        string='Command Body',
        help='Raw command string sent to device. '
             'Auto-generated from command_type or manually set for custom.')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent to Device'),
        ('done', 'Executed'),
        ('failed', 'Failed'),
    ], string='Status', default='pending', required=True)
    result = fields.Text(string='Device Response')
    sent_time = fields.Datetime(string='Sent Time')
    done_time = fields.Datetime(string='Completed Time')
    dispatch_attempts = fields.Integer(
        string='Dispatch Attempts', default=0, copy=False,
        help='Times this command was handed to the device via getrequest. '
             'Used by the stale-command sweeper to retry or give up.')

    # For fingerprint enrollment
    employee_id = fields.Many2one('hr.employee', string='Employee')
    finger_index = fields.Integer(string='Biometric Index/FID', default=0,
        help='0-9 for fingers (FID param, ENROLL_FP only). Not used by '
             'ENROLL_BIO, which has no FID/Index parameter.')
    template_id = fields.Many2one('biometric.fp.template', string='Biometric Template to Sync')
    card_no = fields.Char(string='Card Number',
        help='Optional card number for ENROLL_BIO (CardNo param). Leave empty if not using a card.')
    retry_count = fields.Integer(string='Retry Count', default=3,
        help='Capture attempts before enrollment fails (RETRY param, ENROLL_FP/ENROLL_BIO).')
    overwrite = fields.Boolean(string='Overwrite Existing', default=True,
        help='Overwrite the biometric template if one already exists for this user (OVERWRITE param).')

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-assign command_id per device."""
        for vals in vals_list:
            if 'command_id' not in vals or not vals.get('command_id'):
                device_id = vals.get('device_id')
                last = self.search(
                    [('device_id', '=', device_id)],
                    order='command_id desc', limit=1)
                vals['command_id'] = (last.command_id + 1) if last else 1
            # Auto-generate command_body from command_type
            if not vals.get('command_body'):
                vals['command_body'] = self._build_command_body(vals)
        return super().create(vals_list)

    def _build_command_body(self, vals):
        """Generate the raw command string from type and parameters."""
        cmd_type = vals.get('command_type', '')
        if cmd_type == 'reboot':
            return 'REBOOT'
        elif cmd_type == 'info':
            return 'INFO'
        elif cmd_type == 'clear_data':
            return 'CLEAR LOG'
        elif cmd_type == 'set_time':
            import pytz
            from datetime import datetime as dt
            # Use the device's configured timezone, not the server's local time
            device = self.env['biometric.device.details'].browse(vals.get('device_id', 0))
            tz_str = 'UTC'
            if device.exists():
                # Must use the same timezone as _get_device_timezone_for_adms() in the controller.
                # effective_timezone is excluded — it is a PyZK concept and must NOT be used
                # for ADMS time sync (would cause ServerLocalTime to differ from ATTLOG interpretation).
                tz_str = (device.custom_timezone
                          or device.company_id.partner_id.tz
                          or 'UTC')
            try:
                local_tz = pytz.timezone(tz_str)
            except pytz.UnknownTimeZoneError:
                local_tz = pytz.UTC
            now = dt.now(pytz.utc).astimezone(local_tz).strftime('%Y-%m-%d %H:%M:%S')
            return f'SET OPTION ServerLocalTime={now}'
        elif cmd_type == 'enroll_fp':
            # PIN from employee's zk_user_id, finger index
            employee = self.env['hr.employee'].browse(vals.get('employee_id', 0))
            if not employee or not employee.device_id_num:
                # Without this guard, a falsy device_id_num renders as the
                # literal text 'PIN=False' — the device then rejects it.
                raise UserError(_(
                    "Set the 'ZK Device User ID' on employee %s before enrolling.",
                    employee.name if employee else vals.get('employee_id')))
            pin = employee.device_id_num
            fid = vals.get('finger_index', 0)
            retry = vals.get('retry_count', 3) or 3
            overwrite = 1 if vals.get('overwrite', True) else 0
            return f'ENROLL_FP PIN={pin}\tFID={fid}\tRETRY={retry}\tOVERWRITE={overwrite}'
        elif cmd_type == 'enroll_bio':
            # Remote face enrollment (Section 12.6.3 "Enrolling Face, Palm
            # Print (Unified Templates)"). This is a Remote Enrollment
            # Command, NOT a Data Command: no 'DATA' prefix, and no FID/Index
            # param (that only exists on ENROLL_FP). Type=9 = Visible light
            # face per Appendix 10 "Biometric Type Index Definition".
            employee = self.env['hr.employee'].browse(vals.get('employee_id', 0))
            if not employee or not employee.device_id_num:
                raise UserError(_(
                    "Set the 'ZK Device User ID' on employee %s before enrolling.",
                    employee.name if employee else vals.get('employee_id')))
            pin = employee.device_id_num
            card_no = vals.get('card_no') or ''
            retry = vals.get('retry_count', 3) or 3
            overwrite = 1 if vals.get('overwrite', True) else 0
            return f'ENROLL_BIO TYPE=9\tPIN={pin}\tCardNo={card_no}\tRETRY={retry}\tOVERWRITE={overwrite}'
        elif cmd_type == 'sync_user':
            employee = self.env['hr.employee'].browse(vals.get('employee_id', 0))
            if employee:
                pin = employee.device_id_num or ''
                name = employee.name or ''
                return f'DATA UPDATE USERINFO PIN={pin}\tName={name}\tPri=0'
            return ''
        elif cmd_type == 'delete_user':
            employee = self.env['hr.employee'].browse(vals.get('employee_id', 0))
            if employee:
                pin = employee.device_id_num or ''
                return f'DATA DELETE USERINFO PIN={pin}'
            return ''
        elif cmd_type == 'sync_template':
            template = self.env['biometric.fp.template'].browse(vals.get('template_id', 0))
            if template and template.employee_id.device_id_num:
                pin = template.employee_id.device_id_num
                valid = 1
                fid = template.finger_index or 0
                no = template.bio_no or 0
                duress = 1 if template.duress else 0
                major_ver = template.algorithm_major_version or 0
                minor_ver = template.algorithm_minor_version or 0
                tmpl_format = template.template_format or 0
                temp_data = template.template_data
                
                # Biometric types mapping in ADMS (Appendix 10 "Biometric
                # Type Index Definition"): Type=1 (Finger), Type=9 (Visible
                # light face), Type=8 (Palm vein).
                if template.template_type == 'face':
                    bio_type = 9
                elif template.template_type == 'palm':
                    bio_type = 8
                else:
                    bio_type = 1
                    
                # Field names/order per Section 12.1.1.6 "Unified Templates" —
                # there is no 'Size' field in this schema (that belongs to the
                # old, non-unified FP/FACE upload commands, 12.1.1.3/12.1.1.4).
                return (f'DATA UPDATE BIODATA PIN={pin}\tNo={no}\tIndex={fid}\tValid={valid}'
                        f'\tDuress={duress}\tType={bio_type}\tMajorVer={major_ver}'
                        f'\tMinorVer={minor_ver}\tFormat={tmpl_format}\tTMP={temp_data}')
            return ''
        return vals.get('command_body', '')

    def format_for_device(self):
        """Format command for ADMS protocol: C:{id}:{body}"""
        self.ensure_one()
        return f'C:{self.command_id}:{self.command_body}'

    @api.model
    def _cron_requeue_stale_commands(self):
        """Re-queue commands stuck in 'sent' past the stale threshold.

        getrequest marks a command 'sent' the instant it hands it to the device.
        If the device then loses power/network before reporting back via
        /iclock/devicecmd, the command would stay 'sent' forever. This sweeper
        returns it to 'pending' so the next poll re-dispatches it, up to
        _MAX_DISPATCH_ATTEMPTS, after which it is marked 'failed'.
        """
        from datetime import timedelta
        cutoff = fields.Datetime.now() - timedelta(minutes=self._STALE_SENT_MINUTES)
        stale = self.search([
            ('status', '=', 'sent'),
            ('sent_time', '<', cutoff),
        ])
        requeued = failed = 0
        for cmd in stale:
            if cmd.dispatch_attempts >= self._MAX_DISPATCH_ATTEMPTS:
                cmd.write({
                    'status': 'failed',
                    'result': 'No device acknowledgement after %d dispatch attempt(s).'
                              % cmd.dispatch_attempts,
                })
                failed += 1
            else:
                cmd.write({'status': 'pending'})
                requeued += 1
        if requeued or failed:
            _logger.info(
                "ADMS stale-command sweeper: re-queued %d, failed %d command(s) "
                "stuck >%d min in 'sent'.",
                requeued, failed, self._STALE_SENT_MINUTES)
        return True


class BiometricFpTemplate(models.Model):
    """Store biometric templates received from ADMS devices."""
    _name = 'biometric.fp.template'
    _description = 'Biometric Storage Template'
    _order = 'employee_id, template_type, finger_index'

    employee_id = fields.Many2one('hr.employee', string='Employee',
                                   required=True, ondelete='cascade')
    device_id = fields.Many2one('biometric.device.details', string='Source Device')
    template_type = fields.Selection([
        ('finger', 'Fingerprint'),
        ('face', 'Face Recognition'),
        ('palm', 'Palm Print'),
    ], string='Biometric Type', default='finger', required=True)
    finger_index = fields.Integer(string='Index / FID', default=0,
        help="Maps to the protocol's 'Index=' field (Section 11.12). For "
             "face this is normally 0 (a single template per user).")
    bio_no = fields.Integer(string='Bio No.', default=0,
        help="Maps to the protocol's 'No=' field — sub-identifier for the "
             "biometric type (e.g. 0=left/1=right for palm; always 0 for face).")
    duress = fields.Boolean(string='Duress Template',
        help="Maps to the protocol's 'Duress=' field — True if this template "
             "is registered as a duress/panic template.")
    algorithm_major_version = fields.Integer(string='Algorithm Major Version',
        help="Maps to the protocol's 'MajorVer=' field.")
    algorithm_minor_version = fields.Integer(string='Algorithm Minor Version',
        help="Maps to the protocol's 'MinorVer=' field.")
    template_format = fields.Integer(string='Template Format', default=0,
        help="Maps to the protocol's 'Format=' field (0=ZK for all biometric types).")
    template_data = fields.Text(string='Template Data',
        help='Base64-encoded biometric template from device')
    template_size = fields.Integer(string='Template Size')
    template_version = fields.Char(string='Template Version')
    capture_time = fields.Datetime(string='Captured At', default=fields.Datetime.now)

    def action_sync_to_adms_devices(self):
        """Queue this template to be pushed to all hybrid/adms devices"""
        devices = self.env['biometric.device.details'].search([
            ('connection_mode', 'in', ['adms', 'hybrid']),
            ('company_id', '=', self.employee_id.company_id.id if self.employee_id.company_id else False)
        ])
        
        commands = []
        for device in devices:
            # Skip the device it was captured on, unless you want to force sync
            commands.append({
                'device_id': device.id,
                'command_type': 'sync_template',
                'template_id': self.id,
                'employee_id': self.employee_id.id,
            })
            
        if commands:
            self.env['adms.device.command'].create(commands)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sync Queued',
                    'message': f'Queued syncing for {len(commands)} device(s) via ADMS.',
                    'type': 'success',
                    'sticky': False,
                }
            }
