# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit
#
################################################################################

import base64
import bisect
import json
from markupsafe import Markup
import datetime
import logging
import pytz
import threading
import time as _time
from collections import defaultdict
from datetime import timedelta
from odoo import api, fields, models, registry as odoo_registry, _, SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError
from .zk_machine_attendance import ZkMachineAttendance

_logger = logging.getLogger(__name__)
try:
    from zk import ZK, const
except ImportError:
    try:
        # pyzk2 is a maintained fork published on PyPI; it imports as 'pyzk2'
        # and exposes the same ZK class + const submodule as pyzk.
        from pyzk2 import ZK, const
    except ImportError:
        _logger.error("Please install the 'pyzk' or 'pyzk2' library — "
                      "direct-TCP (PyZK) features are disabled; ADMS still works.")


class BiometricDeviceDetails(models.Model):
    """Enhanced Model for biometric device with full pyzk capabilities"""
    _name = 'biometric.device.details'
    _description = 'Biometric Device Details - Enhanced'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ==================== BASIC DEVICE INFORMATION ====================
    active = fields.Boolean(
        string='Active', default=True, tracking=True,
        help='Uncheck to archive this device. Archived devices are hidden from '
             'lists and excluded from scheduled downloads and ADMS processing.')

    name = fields.Char(string='Name', required=True, help='Device Name', tracking=True)
    device_ip = fields.Char(string='Device IP',
                            help='The IP address of the Device', tracking=True)
    port_number = fields.Integer(string='Port Number', default=4370,
                                 help="The Port Number of the Device (default: 4370)", tracking=True)
    device_password = fields.Char(string='Device Password',
                                   groups='dotbd_hr_zk_attendance_suite.group_attendance_manager',
                                   help='Password for the biometric device. Leave empty for default (0). '
                                        'Most ZKteco devices use password 0 by default.')
    address_id = fields.Many2one('res.partner', string='Working Address',
                                 help='Working address of the partner')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.user.company_id.id,
                                 help='Current Company')
    last_download_time = fields.Datetime(string='Last Download Time',
                                         help='The last time the attendance data was downloaded')

    # ==================== DEVICE INFORMATION (NEW - from pyzk) ====================
    firmware_version = fields.Char(string='Firmware Version', readonly=True, copy=False,
                                   help='Device firmware version retrieved from device')
    serial_number = fields.Char(string='Serial Number', readonly=True, copy=False,
                               help='Unique device serial number')
    platform = fields.Char(string='Platform', readonly=True, copy=False,
                          help='Device platform/model')
    mac_address = fields.Char(string='MAC Address', readonly=True, copy=False,
                             help='Device MAC address')
    device_name_from_device = fields.Char(string='Device Name (from Device)', readonly=True, copy=False,
                                          help='Device name stored in the device itself')
    face_version = fields.Char(string='Face Recognition Version', readonly=True, copy=False,
                               help='Face recognition module version')
    fp_version = fields.Char(string='Fingerprint Version', readonly=True, copy=False,
                            help='Fingerprint module version')
    pin_width = fields.Integer(string='PIN Width', readonly=True, copy=False,
                               help='Maximum width of user PIN/password')

    # Network Information
    network_ip = fields.Char(string='Network IP', readonly=True, copy=False)
    network_mask = fields.Char(string='Network Mask', readonly=True, copy=False)
    network_gateway = fields.Char(string='Network Gateway', readonly=True, copy=False)

    # ==================== DEVICE CAPACITY (NEW - from pyzk) ====================
    user_capacity = fields.Integer(string='User Capacity', readonly=True, copy=False, default=0,
                                   help='Maximum number of users device can store')
    user_count = fields.Integer(string='Users Enrolled', readonly=True, copy=False, default=0,
                                help='Current number of users enrolled')
    finger_capacity = fields.Integer(string='Fingerprint Capacity', readonly=True, copy=False, default=0,
                                     help='Maximum number of fingerprints device can store')
    finger_count = fields.Integer(string='Fingerprints Enrolled', readonly=True, copy=False, default=0,
                                  help='Current number of fingerprints stored')
    record_capacity = fields.Integer(string='Record Capacity', readonly=True, copy=False, default=0,
                                     help='Maximum number of attendance records device can store')
    record_count = fields.Integer(string='Records Stored', readonly=True, copy=False, default=0,
                                  help='Current number of attendance records')
    face_capacity = fields.Integer(string='Face Capacity', readonly=True, copy=False, default=0,
                                   help='Maximum number of face templates device can store')
    face_count = fields.Integer(string='Faces Enrolled', readonly=True, copy=False, default=0,
                                help='Current number of face templates stored')

    # Computed Storage Fields
    user_usage_percent = fields.Float(string='User Storage %', compute='_compute_usage_percent',
                                      store=True, help='Percentage of user capacity used')
    record_usage_percent = fields.Float(string='Record Storage %', compute='_compute_usage_percent',
                                        store=True, help='Percentage of record capacity used')
    storage_warning = fields.Boolean(string='Storage Warning', compute='_compute_storage_warning',
                                     store=True, help='True if device storage is >80% full')

    # ==================== CONNECTION MODE ====================
    connection_mode = fields.Selection([
        ('direct', 'Direct Connection (PyZK)'),
        ('adms', 'Cloud Connection (ADMS Push)'),
        ('hybrid', 'Hybrid (ADMS Attendance + PyZK Control)'),
    ], string='Connection Mode', default='direct', required=True,
       help='Direct: Odoo connects to device via TCP/IP (same LAN / VPN required).\n'
            'Cloud (ADMS): Device pushes data to Odoo via HTTP (works behind firewalls, cloud-compatible).\n'
            'Hybrid: ADMS for automatic attendance push + PyZK for hardware control (LCD, voice, door).')

    device_serial = fields.Char(
        string='Device Serial Number',
        help='Serial number used for ADMS device matching. '
             'Auto-filled on first ADMS heartbeat, or set manually.')
    adms_auto_fill_serial = fields.Boolean(
        string='Auto-fill Serial on First Heartbeat',
        default=True,
        help='When enabled, the device serial number is automatically captured '
             'from the first ADMS handshake and saved to this record. '
             'Disable if you want to set the serial manually and prevent '
             'any automatic changes.')

    adms_receive_only = fields.Boolean(
        string='Receive Only (Block Time Sync)',
        default=True,
        help='When enabled, Odoo acts as a passive receiver:\n'
             '• Never sends ServerLocalTime or TimeZone to the device\n'
             '• Never queues set_time or other commands via getrequest\n'
             '• Never modifies device_firmware_tz (no auto-detection)\n'
             '• All ATTLOG timestamps are taken at face value and '
             'converted using the configured Custom Timezone\n\n'
             'Use this when you manage the device clock manually and '
             'do not want Odoo to interfere with the device time at all. '
             'Example: device is set to Asia/Dhaka (GMT+6) manually — '
             'a 3pm punch is stored as 3pm BDT regardless of firmware timezone.')

    # NOTE: device_serial uniqueness is enforced via a PARTIAL unique index
    # created in init() below — NOT a plain UNIQUE(device_serial) constraint.
    # A plain UNIQUE would also block multiple empty-string ('') serials, while
    # we need devices that have not captured a serial yet to coexist freely.
    # The partial index applies only to non-null, non-empty serials.

    def init(self):
        """Create a partial unique index on device_serial (non-null, non-empty).

        Replaces the old plain UNIQUE(device_serial) SQL constraint, which
        rejected multiple '' serials and could cause silent insert failures
        for unset-serial devices. Matches the Odoo 19 UniqueIndex behavior.
        """
        # Drop the legacy plain unique constraint if it still exists
        self.env.cr.execute("""
            ALTER TABLE biometric_device_details
            DROP CONSTRAINT IF EXISTS biometric_device_details_device_serial_unique
        """)
        # Create the partial unique index (idempotent)
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                biometric_device_details_serial_partial_uniq
            ON biometric_device_details (device_serial)
            WHERE device_serial IS NOT NULL AND device_serial != ''
        """)

    adms_server_url = fields.Char(
        string='ADMS Server Address',
        compute='_compute_adms_server_url',
        help='Paste into the ZKTeco firmware "Server Address" field '
             '(Menu → Comm → Cloud Server Setting). '
             'No protocol prefix (no https://). Port is shown separately below.')

    adms_server_port = fields.Char(
        string='ADMS Server Port',
        compute='_compute_adms_server_url',
        help='Set this as the "Server Port" on the ZKTeco device firmware. '
             '443 = HTTPS via nginx, 80 = HTTP via nginx, 8069 = direct Odoo (no proxy).')

    # Raw host WITHOUT the /db/<name> path. Use this on devices that cannot
    # accept a URL path after the address (most ZKTeco firmware only accepts a
    # bare host or IP). Devices configured this way reach whatever database
    # Odoo's dbfilter resolves — on Odoo.sh each domain already maps to one DB.
    adms_server_url_raw = fields.Char(
        string='Raw Domain (no /db/ path)',
        compute='_compute_adms_server_url',
        help='Bare host with NO database path. Use this when the device firmware '
             'will not accept a path after the address (e.g. you can only enter an '
             'IP or a plain domain). The database is then resolved by Odoo dbfilter '
             '/ Odoo.sh domain mapping. Devices that connect this way auto-register '
             'as INACTIVE for safety — activate them manually.')

    # Best-effort resolution of the server host to a public IP, for users whose
    # device firmware only accepts a numeric IP address.
    adms_server_host_ip = fields.Char(
        string='Server IP',
        compute='_compute_adms_server_url',
        help='Public IP that the domain above resolves to (best-effort DNS lookup). '
             'Use only if your device firmware cannot accept a domain name. '
             'IP-based devices cannot send a database path, so they auto-register '
             'as INACTIVE for safety — activate them manually.')

    @api.depends('company_id')
    def _compute_adms_server_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        db_name = self.env.cr.dbname

        # Detect protocol and strip it — firmware takes host+path only.
        is_https = base_url.startswith('https://')
        host_part = base_url
        for prefix in ('https://', 'http://'):
            if host_part.startswith(prefix):
                host_part = host_part[len(prefix):]
                break

        # Separate host:port from path
        host_segment = host_part.split('/')[0]
        if ':' in host_segment:
            host_only, port = host_segment.rsplit(':', 1)
        else:
            host_only = host_segment
            port = '443' if is_https else '80'

        server_address = f'{host_only}/db/{db_name}'

        # Best-effort DNS resolution of the bare host → IP. Never raises; on
        # failure we leave the IP blank (the domain is always usable anyway).
        # localhost resolves to 127.0.0.1 — shown as-is so the field is never
        # mysteriously empty during local testing. On a real domain this shows
        # the server's public IP.
        host_ip = ''
        if host_only:
            try:
                import socket as _socket
                host_ip = _socket.gethostbyname(host_only)
            except Exception:
                host_ip = ''

        for rec in self:
            rec.adms_server_url = server_address
            rec.adms_server_port = port
            rec.adms_server_url_raw = host_only
            rec.adms_server_host_ip = host_ip

    # ==================== AUTO-REGISTRATION SAFETY ====================
    # Devices that contact the server via ADMS push and are not yet known are
    # auto-created by the controller. Because such a device may have connected
    # using a bare IP / raw domain (no /db/ path, i.e. bypassing any intended
    # database filter), we create it INACTIVE. It still shows a heartbeat
    # (Online) so the admin can see it, but its attendance data is rejected
    # until the admin reviews and activates it.
    adms_auto_registered = fields.Boolean(
        string='Auto-Registered via ADMS', readonly=True, default=False, copy=False,
        help='Set automatically when this device first contacted the server via '
             'ADMS push and was created without manual setup. Such devices start '
             'INACTIVE for safety — review and activate to start receiving data.')

    adms_pending_activation = fields.Boolean(
        string='Pending Activation',
        compute='_compute_adms_pending_activation',
        help='True for auto-registered devices that are still inactive. Their '
             'attendance pushes are rejected until you activate them.')

    @api.depends('adms_auto_registered', 'active')
    def _compute_adms_pending_activation(self):
        for rec in self:
            rec.adms_pending_activation = bool(rec.adms_auto_registered and not rec.active)

    def action_activate_device(self):
        """One-click approve: activate an auto-registered device so it starts
        accepting attendance pushes. Clears the auto-registered safety flag."""
        for rec in self:
            rec.write({'active': True, 'adms_auto_registered': False})
            rec.message_post(
                body=_("Device activated by %s — ADMS attendance pushes are now "
                       "accepted.") % self.env.user.name,
                message_type='notification')
        return True

    # ==================== SERVER PORT REACHABILITY CHECK ====================
    adms_port_status_html = fields.Html(
        string='Server Port Status', readonly=True, sanitize=False, copy=False,
        help='Result of the last "Check Server Ports" run — which of the common '
             'ADMS ports (80, 443, 8069, 8081) are reachable on this server host.')

    def action_check_server_ports(self):
        """Best-effort TCP reachability probe of the common ADMS ports on the
        server's own public host. Helps the user pick a working Server Port for
        the device firmware. Runs from the Odoo server, so it reflects what the
        server itself can reach — a firewall in front may still block the device.
        """
        self.ensure_one()
        import socket as _socket

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        host = base_url
        for prefix in ('https://', 'http://'):
            if host.startswith(prefix):
                host = host[len(prefix):]
                break
        host = host.split('/')[0].split(':')[0]

        if not host:
            raise UserError(_('Could not determine the server host from '
                              'web.base.url. Set it in Settings → Technical → '
                              'System Parameters first.'))

        ports = [
            (80,   'HTTP (nginx/Apache proxy)'),
            (443,  'HTTPS (nginx/Apache proxy)'),
            (8069, 'Odoo HTTP (direct)'),
            (8081, 'Alternate HTTP (some proxies)'),
        ]
        rows = []
        for port, label in ports:
            state, color, icon = 'Closed / filtered', '#dc3545', 'fa-times-circle'
            try:
                sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((host, port))
                sock.close()
                if result == 0:
                    state, color, icon = 'Open', '#28a745', 'fa-check-circle'
            except Exception:
                state, color, icon = 'Error / unresolved', '#fd7e14', 'fa-exclamation-circle'
            rows.append(
                '<tr>'
                '<td style="padding:4px 10px;"><b>%s</b></td>'
                '<td style="padding:4px 10px;">%s</td>'
                '<td style="padding:4px 10px;color:%s;">'
                '<i class="fa %s"/> %s</td>'
                '</tr>' % (port, label, color, icon, state)
            )

        now_str = fields.Datetime.to_string(fields.Datetime.now())
        html = (
            '<div style="font-size:0.9em;">'
            '<div class="text-muted mb-1">Host probed: <code>%s</code> '
            '&nbsp;·&nbsp; checked %s UTC</div>'
            '<table class="table table-sm" style="width:auto;border-collapse:collapse;">'
            '<thead><tr>'
            '<th style="padding:4px 10px;">Port</th>'
            '<th style="padding:4px 10px;">Typical use</th>'
            '<th style="padding:4px 10px;">Status</th>'
            '</tr></thead><tbody>%s</tbody></table>'
            '<div class="text-muted mt-1" style="font-size:0.85em;">'
            'Probed from the Odoo server itself. "Open" means the server can reach '
            'that port locally — a device on another network may still be blocked '
            'by an external firewall. Use the lowest open proxy port (443 or 80) '
            'when available; <code>8069</code> only if Odoo is exposed directly.'
            '</div></div>'
        ) % (host, now_str, ''.join(rows))

        self.adms_port_status_html = Markup(html)
        return True

    adms_last_heartbeat = fields.Datetime(
        string='Last ADMS Heartbeat', readonly=True,
        help='Last time this device contacted the server via ADMS push protocol.')
    adms_status = fields.Selection([
        ('offline', 'Offline'),
        ('online', 'Online'),
    ], string='ADMS Status', compute='_compute_adms_status', store=True,
       help='Online if heartbeat received within the configured offline threshold.')
    adms_offline_threshold = fields.Integer(
        string='ADMS Offline Threshold (min)',
        default=10,
        help='Minutes without a heartbeat before this device is marked ADMS Offline. '
             'Set to at least 2× your device heartbeat interval (default: 10 min).')
    adms_push_count = fields.Integer(
        string='ADMS Records Pushed', readonly=True, default=0,
        help='Total attendance records received via ADMS push.')
    adms_command_count = fields.Integer(
        string='Pending Commands', compute='_compute_adms_command_count')

    # Stamps — sent in handshake so device only resends records we haven't seen.
    # The device echoes its own stamp in POST ?Stamp=N; we echo it back as OK: N
    # and store it here. Next handshake we send ATTLOGStamp=N → device skips old records.
    adms_attlog_stamp = fields.Integer(
        string='ATTLOG Stamp', readonly=True, default=0, copy=False,
        help='Last acknowledged ATTLOG stamp sent back to the device.')
    adms_operlog_stamp = fields.Integer(
        string='OPERLOG Stamp', readonly=True, default=0, copy=False,
        help='Last acknowledged OPERLOG stamp sent back to the device.')

    @api.depends('adms_last_heartbeat', 'adms_offline_threshold')
    def _compute_adms_status(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.adms_last_heartbeat:
                threshold_sec = max(1, rec.adms_offline_threshold or 10) * 60
                diff = (now - rec.adms_last_heartbeat).total_seconds()
                rec.adms_status = 'online' if diff < threshold_sec else 'offline'
            else:
                rec.adms_status = 'offline'

    def _compute_adms_command_count(self):
        command_model = self.env['adms.device.command']
        for rec in self:
            rec.adms_command_count = command_model.search_count([
                ('device_id', '=', rec.id),
                ('status', '=', 'pending'),
            ])

    # ==================== ATTENDANCE MODE SETTINGS (Existing) ====================
    attendance_mode = fields.Selection([
        ('traditional', 'Traditional Mode (Use Device Punch Type)'),
        ('auto', 'Auto Mode (Auto Check-in/Check-out)'),
        ('auto_per_day', 'Auto Per Day (First Punch = In, Last Punch = Out)'),
        ('traditional_per_day', 'Traditional Per Day (One Check-in & One Check-out Per Day)'),
    ], string='Attendance Mode', default='traditional', required=True,
       help='Traditional: Uses punch type from device (0=Check-in, 1=Check-out)\n'
            'Auto: Automatically determines Check-in/Check-out based on last attendance, '
            'ignores device punch type. Prevents HR mistakes.\n'
            'Auto Per Day: First punch of the day is check-in, every subsequent punch updates '
            'check-out (last punch = final check-out). One record per employee per day.\n'
            'Traditional Per Day: Uses device punch type but only allows one check-in and '
            'one check-out per employee per day. Subsequent punches are ignored.')

    duplicate_threshold = fields.Integer(
        string='Duplicate Prevention (Seconds)',
        default=5,
        help='Time window in seconds to ignore duplicate punches. '
             'If employee punches multiple times within this period, only first punch is counted. '
             'Default: 5 seconds')

    # ==================== TIME SYNCHRONIZATION SETTINGS (NEW) ====================
    time_sync_method = fields.Selection([
        ('company', 'Auto (Company Timezone)'),
        ('odoo', 'Odoo User Timezone'),
        ('server', 'Server Timezone (UTC)'),
        ('custom', 'Custom Timezone'),
        ('manual', 'Manual Time')
    ], string='Time Sync Method', default='company', required=True,
       help='Method to determine the correct time for this device.\n'
            'Auto (Company Timezone): Recommended. Uses your Odoo company timezone automatically — '
            'no manual configuration needed. Works for most setups where the device is in the same '
            'country as your company.\n'
            '⚠️ After changing, click "Sync Time" to push the correct timezone to the device.')

    company_timezone = fields.Char(
        string='Company Timezone',
        compute='_compute_company_timezone', store=False,
        help='The timezone configured on your Odoo company. When Time Sync Method is set to '
             '"Auto (Company Timezone)", this is the timezone used to interpret device timestamps.')

    custom_timezone = fields.Selection('_tz_get', string='Custom Timezone', default=lambda self: self.env.company.partner_id.tz or 'UTC',
                                       help='Select the timezone that matches your device\'s actual physical location. '
                                            '⚠️ After changing this, click "Sync Time" button and verify "Current Device TZ" '
                                            'shows the correct timezone (not UTC).')

    adms_custom_timezone = fields.Selection(
        '_tz_get',
        string='ADMS Timezone (Override)',
        help='[Hybrid Mode Only] Set a separate timezone for ADMS-pushed data. '
             'When set, Odoo uses this timezone to interpret ADMS ATTLOG timestamps, '
             'while PyZK downloads continue using the Custom Timezone above. '
             'Leave empty to use the same Custom Timezone for both modes. '
             'Example: Device is in Asia/Beirut but PyZK pulls UTC → set ADMS TZ to Asia/Beirut '
             'and Custom TZ to UTC.')

    adms_time_offset_hours = fields.Integer(
        string='ADMS Time Offset (hours)',
        default=0,
        help='Apply a fixed hour correction to all ADMS-pushed attendance times AFTER timezone conversion. '
             'Use this when the device clock cannot be changed but attendance times are consistently '
             'wrong by a fixed number of hours. '
             'Positive values ADD hours (e.g. +2 shifts 08:00 → 10:00). '
             'Negative values SUBTRACT hours (e.g. -3 shifts 12:00 → 09:00). '
             'Range: -12 to +12. Default: 0 (no correction). '
             'Example: Device always shows 3 hours ahead → set -3.')

    manual_datetime = fields.Datetime(string='Manual Date & Time',
                                      help='Set an exact date and time to push to the device.')

    effective_timezone = fields.Char(
        string='Effective Device Timezone',
        readonly=True, copy=False,
        help='⚠️ READ-ONLY: Shows the timezone the physical device clock is actually running in. '
             'Auto-updated on every time sync and attendance download. '
             'This MUST match your configured timezone (e.g., Asia/Beirut). '
             'If it shows UTC when you configured Asia/Beirut, click "Sync Time" button to fix!')

    device_firmware_tz = fields.Char(
        string='Auto-Detected Firmware Timezone',
        readonly=True, copy=False,
        help='Auto-detected from live ATTLOG punches. When set, Odoo uses this timezone '
             'to interpret device timestamps — overriding the configured Custom Timezone. '
             'Also, Odoo will NOT send ServerLocalTime in the handshake (preserving the '
             'time you manually set on the device). Clear to re-detect or revert.')

    adms_device_seen_time = fields.Datetime(
        string='ADMS Device Last Seen Time',
        readonly=True, copy=False,
        help='Last detected local time on the device, inferred from a fresh ATTLOG punch. '
             'Shows what time the device clock was showing when it last sent a real-time punch.')

    adms_device_seen_tz = fields.Char(
        string='ADMS Device Detected TZ',
        readonly=True, copy=False,
        help='Timezone detected from the last fresh ATTLOG punch (offset of device clock vs server UTC).')

    adms_device_echo_time = fields.Datetime(
        string='ADMS Device Current Time (Echo)',
        readonly=True, copy=False,
        help='The raw time the device clock is currently showing, parsed from its last OPERLOG or ATTLOG push. '
             'When ServerLocalTime must be sent, Odoo echoes this back — so the device clock never changes.')

    # ==================== SCHEDULED CRON SETTINGS ====================
    cron_download_mode = fields.Selection([
        ('all', 'All Records (Full Download)'),
        ('current_month', 'Current Month Only'),
        ('weekly', 'Current Week Only'),
        ('today', 'Today Only'),
    ], string='Scheduled Download Mode',
        default='all',
        required=True,
        help='Controls how much data the automatic scheduled cron job downloads '
             'from this device each run.\n\n'
             '• All Records: Downloads everything every time (high DB load).\n'
             '• Current Month: Only this month\'s records (recommended after first use).\n'
             '• Current Week: Only this week\'s records (good balance).\n'
             '• Today: Only today\'s records (lowest load, daily use).')

    # ==================== LIVE CAPTURE SETTINGS (NEW - from pyzk) ====================
    live_capture_enabled = fields.Boolean(
        string='Enable Live Capture',
        default=False,
        help='Enable real-time attendance monitoring. When enabled, attendance events '
             'are captured instantly as they happen instead of periodic polling.')
    live_capture_active = fields.Boolean(
        string='Live Capture Running',
        readonly=True,
        default=False,
        copy=False,
        help='Indicates if live capture is currently active')
    live_capture_timeout = fields.Integer(
        string='Live Capture Timeout (seconds)',
        default=60,
        help='Timeout in seconds for live capture. Recommended: 60 seconds.')
    last_live_event_time = fields.Datetime(
        string='Last Live Event',
        readonly=True,
        copy=False,
        help='Timestamp of last captured live event')
    live_events_today = fields.Integer(
        string='Live Events Today',
        readonly=True,
        compute='_compute_live_events_today',
        help='Number of events captured today via live capture')

    # ==================== LCD & AUDIO SETTINGS (NEW - from pyzk) ====================
    lcd_enabled = fields.Boolean(
        string='Enable LCD Messages',
        default=False,
        help='Enable custom LCD messages on device screen')
    lcd_welcome_message = fields.Char(
        string='Welcome Message',
        default='Welcome!',
        help='Message to display on check-in (max 20 chars)')
    lcd_goodbye_message = fields.Char(
        string='Goodbye Message',
        default='Goodbye!',
        help='Message to display on check-out (max 20 chars)')

    audio_enabled = fields.Boolean(
        string='Enable Audio Feedback',
        default=False,
        help='Enable custom audio alerts on device')
    checkin_voice_index = fields.Integer(
        string='Check-in Voice',
        default=0,
        help='Voice index for check-in (0-55). 0=default beep')
    checkout_voice_index = fields.Integer(
        string='Check-out Voice',
        default=0,
        help='Voice index for check-out (0-55). 0=default beep')
    error_voice_index = fields.Integer(
        string='Error Voice',
        default=1,
        help='Voice index for errors (0-55). 1=error beep')

    # ==================== DOOR CONTROL SETTINGS (NEW - from pyzk) ====================
    door_control_enabled = fields.Boolean(
        string='Enable Door Control',
        default=False,
        help='Enable door unlock control via device')
    default_unlock_duration = fields.Integer(
        string='Default Unlock Duration (seconds)',
        default=3,
        help='Default duration in seconds to keep door unlocked')
    current_lock_state = fields.Selection([
        ('locked', 'Locked'),
        ('unlocked', 'Unlocked'),
        ('unknown', 'Unknown')
    ], string='Door Lock State', default='unknown', readonly=True,
       help='Current door lock status')

    # ==================== LOG & ATTENDANCE TRACKING ====================
    device_log_ids = fields.One2many(
        'biometric.device.log', 'device_id', string='Device Logs')
    device_log_count = fields.Integer(
        string='Log Count', compute='_compute_device_log_count')
    live_capture_log_count = fields.Integer(
        string='Live Capture Log Count', compute='_compute_live_capture_log_count')
    device_attendance_ids = fields.One2many(
        'zk.machine.attendance', 'device_id', string='Device Attendance Records')
    device_attendance_count = fields.Integer(
        string='Attendance Count', compute='_compute_device_attendance_count')
    
    # ═══════════════════════════════════════════════════════
    # NEW: Log Summary Smart Button Fields
    # Shows success/failed/warning counts at a glance
    # ═══════════════════════════════════════════════════════
    log_success_count = fields.Integer(
        string='Success Logs', compute='_compute_log_summary',
        help='Number of successful operations')
    log_failed_count = fields.Integer(
        string='Failed Logs', compute='_compute_log_summary',
        help='Number of failed operations')
    log_warning_count = fields.Integer(
        string='Warning Logs', compute='_compute_log_summary',
        help='Number of operations with warnings')
    log_raw_count = fields.Integer(
        string='Raw Records', compute='_compute_log_summary',
        help='Total raw attendance records downloaded (zk.machine.attendance)')

    # ==================== DEVICE GEOLOCATION (Map Integration) ====================
    latitude = fields.Float(
        string='Latitude', digits=(10, 7),
        help='Physical latitude of the device. Used for map visualization and geofence validation.')
    longitude = fields.Float(
        string='Longitude', digits=(10, 7),
        help='Physical longitude of the device. Used for map visualization and geofence validation.')
    location_name = fields.Char(
        string='Location Name',
        help='Human-readable location name (e.g., "Main Office Lobby", "Factory Gate B")')
    geofence_radius = fields.Integer(
        string='Geofence Radius (meters)', default=100,
        help='Radius in meters around the device location for geofence validation. '
             'Mobile check-ins outside this radius will be flagged.')
    has_location = fields.Boolean(
        string='Has Location', compute='_compute_has_location', store=True,
        help='Technical field to check if device has coordinates set')

    @api.depends('latitude', 'longitude')
    def _compute_has_location(self):
        for rec in self:
            rec.has_location = bool(rec.latitude and rec.longitude)

    # ==================== DEVICE STATUS ====================
    device_status = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('unknown', 'Unknown')
    ], string='Device Status', default='unknown', readonly=True, compute='_compute_device_status',
       store=True, help='Current device connection status')
    last_online_time = fields.Datetime(string='Last Online', readonly=True, copy=False)
    pyzk_status = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('unknown', 'Unknown'),
    ], string='PyZK Status', default='unknown', readonly=True, copy=False,
       help='Last known result of a PyZK direct connection attempt.')
    pyzk_last_attempt = fields.Datetime(
        string='Last PyZK Attempt', readonly=True, copy=False,
        help='When the last PyZK connection attempt was made (success or failure).')
    pyzk_last_success = fields.Datetime(
        string='Last PyZK Success', readonly=True, copy=False,
        help='When PyZK last connected to this device successfully.')
    connectivity_warning = fields.Char(
        string='Connectivity Warning', compute='_compute_connectivity_warning',
        help='In Hybrid mode: which connection method is currently down.')

    # ==================== COMPUTED FIELDS ====================

    def _compute_device_log_count(self):
        """Count logs for each device"""
        log_data = self.env['biometric.device.log'].sudo().read_group(
            [('device_id', 'in', self.ids)],
            ['device_id'], ['device_id']
        )
        mapped = {d['device_id'][0]: d['device_id_count'] for d in log_data}
        for device in self:
            device.device_log_count = mapped.get(device.id, 0)

    def _compute_live_capture_log_count(self):
        """Count live capture logs for each device"""
        log_data = self.env['biometric.device.log'].sudo().read_group(
            [('device_id', 'in', self.ids), ('log_type', '=', 'live_capture')],
            ['device_id'], ['device_id']
        )
        mapped = {d['device_id'][0]: d['device_id_count'] for d in log_data}
        for device in self:
            device.live_capture_log_count = mapped.get(device.id, 0)

    def _compute_device_attendance_count(self):
        """Count attendance records for each device"""
        att_data = self.env['zk.machine.attendance'].sudo().read_group(
            [('device_id', 'in', self.ids)],
            ['device_id'], ['device_id']
        )
        mapped = {d['device_id'][0]: d['device_id_count'] for d in att_data}
        for device in self:
            device.device_attendance_count = mapped.get(device.id, 0)

    def _compute_log_summary(self):
        """Compute log summary counts: success, failed, warning, raw records.
        This provides a quick overview of device operation health.

        PERFORMANCE: uses _read_group (2 grouped queries total) instead of
        4 search_count per device. ADMS devices update on every heartbeat,
        so this method fires often — batching avoids N×4 query amplification.
        """
        LogModel = self.env['biometric.device.log'].sudo()
        RawModel = self.env['zk.machine.attendance'].sudo()

        # One grouped query: counts per (device, status)
        log_data = LogModel._read_group(
            [('device_id', 'in', self.ids),
             ('status', 'in', ['success', 'failed', 'warning'])],
            groupby=['device_id', 'status'],
            aggregates=['__count'],
        )
        status_map = {}  # {device_id: {status: count}}
        for device, status, count in log_data:
            status_map.setdefault(device.id, {})[status] = count

        # One grouped query: raw attendance counts per device
        raw_data = RawModel._read_group(
            [('device_id', 'in', self.ids)],
            groupby=['device_id'], aggregates=['__count'],
        )
        raw_map = {device.id: count for device, count in raw_data}

        for device in self:
            counts = status_map.get(device.id, {})
            device.log_success_count = counts.get('success', 0)
            device.log_failed_count = counts.get('failed', 0)
            device.log_warning_count = counts.get('warning', 0)
            device.log_raw_count = raw_map.get(device.id, 0)

    @api.depends('user_capacity', 'user_count', 'record_capacity', 'record_count')
    def _compute_usage_percent(self):
        """Calculate storage usage percentage"""
        for device in self:
            # User storage %
            if device.user_capacity > 0:
                device.user_usage_percent = round((device.user_count / device.user_capacity) * 100, 2)
            else:
                device.user_usage_percent = 0.0

            # Record storage %
            if device.record_capacity > 0:
                device.record_usage_percent = round((device.record_count / device.record_capacity) * 100, 2)
            else:
                device.record_usage_percent = 0.0

    @api.depends('record_usage_percent', 'user_usage_percent')
    def _compute_storage_warning(self):
        """Check if device storage is critical (>80%)"""
        for device in self:
            device.storage_warning = (
                device.record_usage_percent > 80 or
                device.user_usage_percent > 80
            )

    @api.depends('connection_mode', 'adms_status', 'pyzk_status')
    def _compute_device_status(self):
        for device in self:
            mode = device.connection_mode
            if mode == 'adms':
                device.device_status = device.adms_status or 'unknown'
            elif mode == 'direct':
                device.device_status = device.pyzk_status or 'unknown'
            elif mode == 'hybrid':
                adms = device.adms_status
                pyzk = device.pyzk_status
                if adms == 'online' or pyzk == 'online':
                    device.device_status = 'online'
                elif adms == 'offline' and pyzk == 'offline':
                    device.device_status = 'offline'
                else:
                    device.device_status = 'unknown'
            else:
                device.device_status = 'unknown'

    @api.depends('connection_mode', 'adms_status', 'pyzk_status')
    def _compute_connectivity_warning(self):
        for device in self:
            if device.connection_mode != 'hybrid':
                device.connectivity_warning = False
                continue
            adms = device.adms_status
            pyzk = device.pyzk_status
            if adms == 'online' and pyzk in ('offline', 'unknown'):
                device.connectivity_warning = 'PyZK direct connection is down — ADMS push is active'
            elif pyzk == 'online' and adms in ('offline', 'unknown'):
                device.connectivity_warning = 'ADMS push is offline — PyZK direct connection is active'
            else:
                device.connectivity_warning = False

    def _compute_live_events_today(self):
        """Count live events captured today"""
        for device in self:
            if device.live_capture_enabled:
                today_start = fields.Datetime.now().replace(hour=0, minute=0, second=0)
                count = self.env['zk.machine.attendance'].search_count([
                    ('address_id', '=', device.address_id.id if device.address_id else False),
                    ('punching_time', '>=', today_start)
                ])
                device.live_events_today = count
            else:
                device.live_events_today = 0

    # ==================== HELPER METHODS ====================

    @api.model
    def _tz_get(self):
        return [(x, x) for x in pytz.all_timezones]

    @api.depends('company_id')
    def _compute_company_timezone(self):
        for device in self:
            device.company_timezone = device.company_id.partner_id.tz or self.env.company.partner_id.tz or 'UTC'

    def _get_device_password(self):
        """Get device password or return default value (0)"""
        self.ensure_one()
        if self.device_password:
            try:
                return int(self.device_password)
            except ValueError:
                return self.device_password
        return 0

    def _get_device_timezone(self):
        """Return the timezone string this device's clock should be running in,
        and the timezone used to interpret incoming punches.

        The user-configured time_sync_method is the AUTHORITATIVE source.
        effective_timezone is a read-only display field that shows what was
        last computed — it must NOT override the configuration, otherwise
        a stale value (e.g. 'UTC' from an old sync) locks in forever
        because this same function sets effective_timezone, creating a
        circular dependency.

        time_sync_method mapping:
          server  → UTC
          odoo    → Odoo user / company timezone
          custom  → custom_timezone field
          manual  → custom_timezone (for punch interpretation; actual clock
                    value is set via manual_datetime in _auto_sync_time)

        NOTE: device_firmware_tz (auto-detected from ADMS live punches) always
        wins over any configured method — it reflects the actual timezone the
        device hardware is operating in, which is the only correct basis for
        interpreting ATTLOG timestamps and computing day boundaries.
        """
        self.ensure_one()
        # Auto-detected firmware TZ always wins (set by ADMS mismatch detection)
        if self.device_firmware_tz:
            return self.device_firmware_tz

        method = self.time_sync_method or 'company'

        if method == 'company':
            return self.company_id.partner_id.tz or self.env.company.partner_id.tz or 'UTC'
        elif method == 'server':
            return 'UTC'
        elif method == 'odoo':
            return (self.env.context.get('tz')
                    or self.env.user.tz
                    or self.company_id.partner_id.tz
                    or 'UTC')
        else:
            # 'custom' and 'manual' both use custom_timezone for interpretation
            return self.custom_timezone or 'UTC'

    # ─── Timezone offset → common timezone name mapping ───────────────────────
    _TZ_OFFSET_MAP = {
        -12.0: 'Etc/GMT+12',
        -11.0: 'Pacific/Midway',
        -10.0: 'Pacific/Honolulu',
        -9.0:  'America/Anchorage',
        -8.0:  'America/Los_Angeles',
        -7.0:  'America/Denver',
        -6.0:  'America/Chicago',
        -5.0:  'America/New_York',
        -4.0:  'America/Halifax',
        -3.5:  'America/St_Johns',
        -3.0:  'America/Sao_Paulo',
        -2.0:  'Etc/GMT+2',
        -1.0:  'Atlantic/Azores',
         0.0:  'UTC',
         1.0:  'Europe/Paris',
         2.0:  'Europe/Helsinki',
         3.0:  'Asia/Riyadh',
         3.5:  'Asia/Tehran',
         4.0:  'Asia/Dubai',
         4.5:  'Asia/Kabul',
         5.0:  'Asia/Karachi',
         5.5:  'Asia/Kolkata',
         5.75: 'Asia/Kathmandu',
         6.0:  'Asia/Dhaka',
         6.5:  'Asia/Rangoon',
         7.0:  'Asia/Bangkok',
         8.0:  'Asia/Shanghai',
         9.0:  'Asia/Tokyo',
         9.5:  'Australia/Adelaide',
        10.0:  'Australia/Sydney',
        11.0:  'Pacific/Guadalcanal',
        12.0:  'Pacific/Auckland',
    }

    def _suggest_timezone_if_mismatch(self, fresh_punches_utc):
        """Called after ADMS processing with a list of (device_naive_dt, server_utc_naive_dt)
        tuples for punches that arrived within 10 minutes of now.

        Computes the device's apparent firmware timezone offset, compares with the
        configured timezone, and posts a chatter message if they differ.
        """
        self.ensure_one()
        if not fresh_punches_utc:
            return

        # Cooldown: don't spam chatter — post at most once per 6 hours
        last_posted = self.env['mail.message'].search([
            ('res_id', '=', self.id),
            ('model', '=', self._name),
            ('body', 'ilike', 'Device Firmware Timezone Mismatch'),
        ], order='date desc', limit=1)
        if last_posted:
            age_hours = (fields.Datetime.now() - last_posted.date).total_seconds() / 3600
            if age_hours < 6:
                return

        # Compute apparent offset for each fresh punch
        offsets = []
        for device_dt, server_utc_dt in fresh_punches_utc:
            diff_seconds = (device_dt - server_utc_dt).total_seconds()
            # Round to nearest 15 minutes — ZKTeco offsets are always :00 or :30 or :45
            offset_hours = round(diff_seconds / 900) * 0.25
            if -14 <= offset_hours <= 14:
                offsets.append(offset_hours)

        if not offsets:
            return

        # Use median offset to avoid outliers
        offsets.sort()
        detected_offset = offsets[len(offsets) // 2]

        # Find timezone name for detected offset
        detected_tz = self._TZ_OFFSET_MAP.get(detected_offset)
        if not detected_tz:
            # Closest match
            closest = min(self._TZ_OFFSET_MAP.keys(), key=lambda k: abs(k - detected_offset))
            if abs(closest - detected_offset) <= 0.5:
                detected_tz = self._TZ_OFFSET_MAP[closest]
            else:
                detected_tz = f'UTC{detected_offset:+.1f}'

        # Get configured timezone offset (ignoring device_firmware_tz — raw config only)
        method = self.time_sync_method or 'company'
        if method == 'company':
            configured_tz_str = self.company_id.partner_id.tz or self.env.company.partner_id.tz or 'UTC'
        elif method == 'server':
            configured_tz_str = 'UTC'
        elif method == 'odoo':
            configured_tz_str = self.env.user.tz or self.company_id.partner_id.tz or 'UTC'
        else:
            configured_tz_str = self.custom_timezone or 'UTC'
        try:
            configured_offset = pytz.timezone(configured_tz_str).utcoffset(
                fields.Datetime.now()).total_seconds() / 3600
        except Exception:
            configured_offset = None

        # Always update the "last seen" fields regardless of mismatch
        device_naive_dt, server_utc_dt = fresh_punches_utc[-1]
        try:
            with self.env.cr.savepoint():
                self.write({
                    'adms_device_seen_time': fields.Datetime.to_string(device_naive_dt),
                    'adms_device_seen_tz': detected_tz,
                })
        except Exception as e:
            _logger.warning("Device %s: could not update seen time: %s", self.name, e)

        # No mismatch — device clock is in the configured timezone
        if configured_offset is None or abs(detected_offset - configured_offset) < 1.0:
            # If a firmware TZ override was stored from before, clear it
            # so Odoo knows the device is now in the correct timezone.
            # Note: ServerLocalTime is NEVER sent for ADMS+custom mode, so there's
            # no oscillation risk — the device clock is user-managed.
            if self.device_firmware_tz:
                try:
                    with self.env.cr.savepoint():
                        self.write({'device_firmware_tz': False})
                    self.message_post(
                        body=Markup(
                            f"✅ <b>Device Firmware TZ override cleared</b><br/>"
                            f"Device timestamps now match configured timezone "
                            f"<b>{configured_tz_str}</b> (UTC{configured_offset:+g}). "
                            f"Odoo will use <b>{configured_tz_str}</b> for ATTLOG conversion."
                        ),
                        message_type='notification', subtype_xmlid='mail.mt_note')
                except Exception:
                    pass
            return

        # ── Mismatch detected ──────────────────────────────────────────────────
        sign = '+' if detected_offset >= 0 else ''
        is_newly_detected = not self.device_firmware_tz or self.device_firmware_tz != detected_tz

        # Save firmware TZ — controller uses this for ATTLOG conversion
        # and will NOT send ServerLocalTime (preserves manually set device time)
        try:
            with self.env.cr.savepoint():
                self.write({'device_firmware_tz': detected_tz})
        except Exception as e:
            _logger.warning("Device %s: could not save device_firmware_tz: %s", self.name, e)

        if not is_newly_detected:
            return  # already posted chatter for this TZ, cooldown in caller

        msg = (
            f"⚠️ <b>Device Firmware Timezone Mismatch Auto-Detected &amp; Fixed</b><br/>"
            f"Device firmware timezone: <b>UTC{sign}{detected_offset:g}</b> ({detected_tz})<br/>"
            f"Odoo configured timezone: <b>{configured_tz_str}</b> (UTC{configured_offset:+g})<br/>"
            f"Difference: <b>{detected_offset - configured_offset:+g} hour(s)</b><br/><br/>"
            f"<b>✅ Auto-correction applied:</b><ul>"
            f"<li>Odoo will convert ATTLOG timestamps using <b>{detected_tz}</b> → UTC</li>"
            f"<li>Odoo will <b>not</b> send ServerLocalTime in handshake — your manually set "
            f"device time is preserved</li>"
            f"<li>Attendance records stored in Odoo will be correct in <b>{configured_tz_str}</b></li>"
            f"</ul>"
            f"<b>To permanently fix device timezone (optional):</b><ol>"
            f"<li>Via <b>ZKTime / ZKBioTime PC software</b>: Device Management → right-click "
            f"device → Set Date/Time → change timezone to <b>GMT{configured_offset:+g}</b></li>"
            f"<li>Via <b>device menu</b> (if available): Menu → System → Date/Time → "
            f"Time Zone → <b>GMT{configured_offset:+g}</b></li>"
            f"</ol>"
            f"After fixing, clear the <i>Auto-Detected Firmware TZ</i> field on this device "
            f"record so Odoo re-detects and resumes normal time sync."
        )
        try:
            self.message_post(body=Markup(msg), message_type='notification',
                              subtype_xmlid='mail.mt_note')
            _logger.info(
                "Device %s: firmware TZ mismatch — detected UTC%s%g (%s), "
                "configured %s (UTC%+g). device_firmware_tz saved.",
                self.name, sign, detected_offset, detected_tz,
                configured_tz_str, configured_offset)
        except Exception as e:
            _logger.warning("Device %s: could not post timezone chatter: %s", self.name, e)

    def log_adms_handshake(self):
        """Post a simple one-line chatter note on every ADMS handshake (GET /iclock/cdata).
        Throttled to once per hour to avoid spam.
        """
        self.ensure_one()

        # Cooldown: once per hour
        last = self.env['mail.message'].search([
            ('res_id', '=', self.id),
            ('model', '=', self._name),
            ('body', 'ilike', 'ADMS Handshake'),
        ], order='date desc', limit=1)
        if last:
            age_seconds = (fields.Datetime.now() - last.date).total_seconds()
            if age_seconds < 3600:
                return

        now_utc = fields.Datetime.now()
        device_tz_str = self._get_device_timezone()
        try:
            pytz.timezone(device_tz_str)  # validate TZ string
        except Exception:
            device_tz_str = 'UTC'

        # Determine what actually happens with ServerLocalTime in the controller:
        # - 'server' mode: always sent (UTC)
        # - custom/other: sent only if adms_device_echo_time is known (echo back device's own time)
        #                 otherwise NOT sent at all
        method = self.time_sync_method or 'company'
        if method == 'server':
            time_sync_note = 'ServerLocalTime sent (UTC — Odoo controls device clock)'
        elif self.device_firmware_tz:
            if self.adms_device_echo_time:
                time_sync_note = (f'ServerLocalTime echoed back '
                                  f'({fields.Datetime.to_string(self.adms_device_echo_time)}) '
                                  f'— device clock unchanged')
            else:
                time_sync_note = 'ServerLocalTime NOT sent — device clock unchanged (no echo time yet)'
        else:
            if self.adms_device_echo_time:
                time_sync_note = (f'ServerLocalTime echoed back '
                                  f'({fields.Datetime.to_string(self.adms_device_echo_time)}) '
                                  f'— device clock unchanged')
            else:
                time_sync_note = 'ServerLocalTime NOT sent — device clock unchanged'

        echo_display = (fields.Datetime.to_string(self.adms_device_echo_time)
                        if self.adms_device_echo_time else 'not yet received')
        msg = (
            f"📡 <b>ADMS Handshake</b> — {fields.Datetime.to_string(now_utc)} UTC<br/>"
            f"Device: <b>{self.name}</b> (S/N: {self.device_serial or 'N/A'})<br/>"
            f"Device current time (from OPERLOG): <b>{echo_display}</b><br/>"
            f"Detected TZ: <b>{self.adms_device_seen_tz or 'not yet detected'}</b> &nbsp;|&nbsp; "
            f"Last punch time: <b>{fields.Datetime.to_string(self.adms_device_seen_time) if self.adms_device_seen_time else 'N/A'}</b><br/>"
            f"Firmware TZ override: <b>{self.device_firmware_tz or 'none (using custom timezone)'}</b><br/>"
            f"⏰ {time_sync_note}"
        )
        try:
            self.message_post(body=Markup(msg), message_type='notification',
                              subtype_xmlid='mail.mt_note')
        except Exception as e:
            _logger.warning("Device %s: handshake chatter failed: %s", self.name, e)


    def _compute_expected_device_time(self):
        """Compute the naive datetime the device clock should show right now,
        based on the configured time_sync_method."""
        self.ensure_one()
        if self.time_sync_method == 'manual' and self.manual_datetime:
            return fields.Datetime.context_timestamp(
                self, self.manual_datetime).replace(tzinfo=None)
        device_tz = self._get_device_timezone()
        utc_now = pytz.utc.localize(fields.Datetime.now())
        local_now = utc_now.astimezone(pytz.timezone(device_tz))
        return local_now.replace(tzinfo=None)

    def _auto_sync_time(self, conn):
        """Check device time and auto-sync if drifted beyond 30 seconds.
        Also persists the effective_timezone on the device record.
        Returns the timezone string the device clock is running in.
        """
        self.ensure_one()
        device_tz_str = self._get_device_timezone()
        expected_time = self._compute_expected_device_time()

        try:
            device_time = conn.get_time()
            if device_time:
                drift = abs((expected_time - device_time).total_seconds())
                if drift > 30:  # More than 30 seconds drift
                    _logger.info(
                        "Device %s time drift: %.1fs (device=%s, expected=%s). Auto-syncing...",
                        self.name, drift, device_time, expected_time)
                    conn.set_time(expected_time)
                    _logger.info("Device %s time auto-synced to %s (%s)",
                                 self.name, expected_time, device_tz_str)
                else:
                    _logger.debug(
                        "Device %s time OK (drift: %.1fs)", self.name, drift)
            else:
                # Can't read time, force sync
                conn.set_time(expected_time)
                _logger.info(
                    "Device %s time could not be read, forced sync to %s",
                    self.name, expected_time)
        except Exception as e:
            _logger.warning(
                "Device %s auto-sync time failed: %s. Proceeding with download.",
                self.name, e)

        # Persist the effective timezone
        try:
            with self.env.cr.savepoint():
                self.write({'effective_timezone': device_tz_str})
        except Exception as _tz_err:
            _logger.warning("Device %s: could not persist effective_timezone: %s", self.name, _tz_err)
        return device_tz_str

    def device_connect(self, zk):
        """Connect to device"""
        try:
            conn = zk.connect()
            now = fields.Datetime.now()
            if conn:
                try:
                    with self.env.cr.savepoint():
                        self.write({
                            'last_online_time': now,
                            'pyzk_status': 'online',
                            'pyzk_last_success': now,
                            'pyzk_last_attempt': now,
                        })
                except Exception as _lo_err:
                    _logger.debug("Device %s: could not update pyzk status (concurrent write): %s", self.name, _lo_err)
            else:
                try:
                    with self.env.cr.savepoint():
                        self.write({'pyzk_status': 'offline', 'pyzk_last_attempt': now})
                except Exception:
                    pass
            return conn
        except Exception as e:
            _logger.error(f"Connection failed for device {self.name}: {str(e)}")
            try:
                with self.env.cr.savepoint():
                    self.write({'pyzk_status': 'offline', 'pyzk_last_attempt': fields.Datetime.now()})
            except Exception:
                pass
            return False

    # ==================== EXISTING METHODS (Enhanced) ====================

    def action_test_connection(self):
        """Test connection and retrieve device info"""
        self.ensure_one()
        device_password = self._get_device_password()
        zk = ZK(self.device_ip, port=self.port_number, timeout=30,
                password=device_password, ommit_ping=True)
        try:
            conn = self.device_connect(zk)
            if conn:
                # Also fetch basic device info on successful connection
                try:
                    self.firmware_version = conn.get_firmware_version()
                    self.serial_number = conn.get_serialnumber()
                except Exception as e:
                    _logger.debug("Could not fetch device info for %s: %s", self.name, e)
                finally:
                    conn.disconnect()

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': f'Successfully Connected to {self.name}',
                        'type': 'success',
                        'sticky': False
                    }
                }
        except Exception as error:
            raise ValidationError(f'Connection failed: {error}')

    def action_set_timezone(self):
        """Sync server timezone to device using configured time_sync_method."""
        for info in self:
            machine_ip = info.device_ip
            zk_port = info.port_number
            device_password = info._get_device_password()
            try:
                zk = ZK(machine_ip, port=zk_port, timeout=15,
                        password=device_password,
                        force_udp=False, ommit_ping=True)
            except NameError:
                raise UserError(
                    _("Pyzk module not Found. Please install it with 'pip3 install pyzk'."))

            conn = self.device_connect(zk)
            if conn:
                try:
                    device_tz_str = info._get_device_timezone()
                    expected_time = info._compute_expected_device_time()
                    conn.set_time(expected_time)
                    try:
                        with self.env.cr.savepoint():
                            info.effective_timezone = device_tz_str
                    except Exception as _tz_err:
                        _logger.warning("Device %s: could not persist effective_timezone: %s", info.name, _tz_err)
                    _logger.info(
                        "Device %s time synced to %s (tz=%s)",
                        info.name, expected_time, device_tz_str)
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'message': f'Time synchronized successfully on {self.name} ({device_tz_str})',
                            'type': 'success',
                            'sticky': False
                        }
                    }
                finally:
                    conn.disconnect()
            else:
                raise UserError(_("Unable to connect to device. Please check connection."))

    def action_restart_device(self):
        """Restart the device"""
        self.ensure_one()
        device_password = self._get_device_password()
        zk = ZK(self.device_ip, port=self.port_number, timeout=15,
                password=device_password, force_udp=False, ommit_ping=True)
        conn = self.device_connect(zk)
        if conn:
            try:
                conn.restart()
                self.message_post(body=f"Device {self.name} restarted successfully")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': f'Device {self.name} is restarting...',
                        'type': 'warning',
                        'sticky': False
                    }
                }
            finally:
                try:
                    conn.disconnect()
                except Exception:
                    pass  # Device already rebooting — socket is gone, ignore

    # ==================== NEW PYZK METHODS - DEVICE INFORMATION ====================

    def action_refresh_device_info(self):
        """
        Refresh all device information from the device
        Uses pyzk methods: get_firmware_version, get_serialnumber, get_platform,
        get_mac, get_device_name, get_face_version, get_fp_version, get_pin_width,
        get_network_params, read_sizes
        """
        self.ensure_one()
        device_password = self._get_device_password()
        zk = ZK(self.device_ip, port=self.port_number, timeout=30,
                password=device_password, ommit_ping=True)

        conn = self.device_connect(zk)
        if not conn:
            raise UserError(_('Unable to connect to device. Please check IP address and port.'))

        try:
            # Get device information
            firmware = conn.get_firmware_version()
            serial = conn.get_serialnumber()
            platform = conn.get_platform()
            mac = conn.get_mac()
            device_name = conn.get_device_name()
            pin_width = conn.get_pin_width()

            # Get face and fingerprint versions
            try:
                face_ver = conn.get_face_version()
            except Exception:
                face_ver = 'N/A'

            try:
                fp_ver = conn.get_fp_version()
            except Exception:
                fp_ver = 'N/A'

            # Get network parameters
            try:
                network_params = conn.get_network_params()
                if network_params and isinstance(network_params, dict):
                    network_ip = network_params.get('ip', '')
                    network_mask = network_params.get('mask', '')
                    network_gateway = network_params.get('gateway', '')
                else:
                    network_ip = self.device_ip
                    network_mask = 'N/A'
                    network_gateway = 'N/A'
            except Exception:
                network_ip = self.device_ip
                network_mask = 'N/A'
                network_gateway = 'N/A'

            # Get capacity information
            sizes = {}
            try:
                raw_sizes = conn.read_sizes()
                _logger.info(f"Device {self.name} read_sizes() returned: {raw_sizes}")

                if raw_sizes and isinstance(raw_sizes, dict):
                    sizes = raw_sizes
                else:
                    _logger.warning(f"Device {self.name} read_sizes() returned invalid data: {raw_sizes}")
            except Exception as e:
                _logger.error(f"Device {self.name} read_sizes() failed: {str(e)}")

            # Try to get user count from get_users if read_sizes failed
            users_list = []
            if not sizes:
                try:
                    users_list = conn.get_users()
                    if users_list:
                        _logger.info(f"Device {self.name} has {len(users_list)} users via get_users()")
                except Exception as e:
                    _logger.error(f"Device {self.name} get_users() failed: {str(e)}")

            # Update device record
            update_vals = {
                'firmware_version': firmware,
                'serial_number': serial,
                'platform': platform,
                'mac_address': mac,
                'device_name_from_device': device_name,
                'face_version': face_ver,
                'fp_version': fp_ver,
                'pin_width': pin_width,
                'network_ip': network_ip,
                'network_mask': network_mask,
                'network_gateway': network_gateway,
            }

            # Add capacity info if available
            if sizes:
                update_vals.update({
                    'user_count': sizes.get('users', 0) or len(users_list),
                    'user_capacity': sizes.get('users_cap', 0),
                    'finger_count': sizes.get('fingers', 0),
                    'finger_capacity': sizes.get('fingers_cap', 0),
                    'record_count': sizes.get('records', 0),
                    'record_capacity': sizes.get('records_cap', 0),
                    'face_count': sizes.get('faces', 0),
                    'face_capacity': sizes.get('faces_cap', 0),
                })
            elif users_list:
                # If read_sizes() failed but we got users, at least update user count
                update_vals['user_count'] = len(users_list)

            self.write(update_vals)

            # Send alert if storage is critical
            if self.storage_warning:
                self._send_storage_alert()

            # Log activity
            message_body = f"Device information refreshed successfully.\n" \
                          f"Firmware: {firmware}\n" \
                          f"Serial: {serial}\n"

            if sizes:
                message_body += f"Users: {sizes.get('users_cap', 0)}/{sizes.get('users', 0)}\n" \
                               f"Records: {sizes.get('records_cap', 0)}/{sizes.get('records', 0)}"
            elif users_list:
                message_body += f"Users: {len(users_list)} (capacity info not available)"
            else:
                message_body += "Capacity information not supported by this device"

            self.message_post(body=message_body)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Device information refreshed successfully!',
                    'type': 'success',
                    'sticky': False
                }
            }

        except Exception as e:
            raise UserError(_(f'Failed to retrieve device information: {str(e)}'))
        finally:
            conn.disconnect()

    def _send_storage_alert(self):
        """Send storage warning notification"""
        self.ensure_one()
        self.message_post(
            subject='Device Storage Warning',
            body=f'Device {self.name} storage is critical!\n\n'
                 f'User Storage: {self.user_usage_percent:.1f}% '
                 f'({self.user_count}/{self.user_capacity})\n'
                 f'Record Storage: {self.record_usage_percent:.1f}% '
                 f'({self.record_count}/{self.record_capacity})\n\n'
                 f'Please clear old records to prevent data loss.',
            message_type='notification',
            subtype_xmlid='mail.mt_comment'
        )

    # ==================== CONTINUED IN NEXT PART ====================
    # ==================== NEW PYZK METHODS - LIVE CAPTURE ====================

    def action_start_live_capture(self):
        """
        Start real-time attendance monitoring
        Uses pyzk method: live_capture()
        This captures attendance events in REAL-TIME as they happen.
        The device pushes events instantly — no polling needed.
        """
        self.ensure_one()

        if self.live_capture_active:
            raise UserError(_('Live capture is already running for this device!'))

        # Set both flags BEFORE starting the thread:
        # - live_capture_enabled=True: tells the worker to keep running
        # - live_capture_active=True: shows the status banner in UI
        self.write({
            'live_capture_enabled': True,
            'live_capture_active': True,
        })

        # Start live capture in background thread
        thread = threading.Thread(target=self._live_capture_worker)
        thread.daemon = True
        thread.start()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Live capture started on {self.name}',
                'type': 'success',
                'sticky': False
            }
        }

    def action_stop_live_capture(self):
        """Stop live capture — sets live_capture_enabled=False so the worker thread exits gracefully"""
        self.ensure_one()
        self.write({'live_capture_enabled': False, 'live_capture_active': False})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Live capture stopped on {self.name}',
                'type': 'warning',
                'sticky': False
            }
        }

    def action_reset_live_capture(self):
        """Reset stale live_capture_active flag (e.g. after Odoo restart killed the thread)"""
        self.ensure_one()
        self.write({'live_capture_active': False, 'live_capture_enabled': False})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Live capture flag reset for {self.name}',
                'type': 'info',
                'sticky': False
            }
        }

    def _live_capture_worker(self):
        """
        Background worker for live capture
        Runs in separate thread to capture real-time events
        IMPORTANT: This creates its own database cursor for thread safety
        """
        device_id = self.id
        device_name = self.name
        device_ip = self.device_ip
        port_number = self.port_number
        device_password = self._get_device_password()
        live_capture_timeout = self.live_capture_timeout

        # Guard: ADMS auto-registered devices have no IP — abort before ZK() crashes
        if not device_ip or device_ip in ('0.0.0.0', 'False', ''):
            _logger.error("Live capture aborted for %s: no device IP configured.", device_name)
            with self.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                env['biometric.device.details'].browse(device_id).write({'live_capture_active': False})
                cr.commit()
            return

        # Counters for session summary log
        start_time = _time.time()
        events_processed = 0
        events_duplicate = 0
        events_unknown = 0
        events_failed = 0
        session_error = None

        # Create ZK connection
        zk = ZK(device_ip, port=port_number, timeout=30,
                password=device_password, ommit_ping=True)

        # Connect to device
        try:
            conn = zk.connect()
            if not conn:
                _logger.error(f"Live capture failed: Unable to connect to {device_name}")
                # Log connection failure
                with self.pool.cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    device = env['biometric.device.details'].browse(device_id)
                    device.write({'live_capture_active': False})
                    env['biometric.device.log'].sudo().create({
                        'device_id': device_id,
                        'log_type': 'live_capture',
                        'status': 'failed',
                        'duration': _time.time() - start_time,
                        'error_message': f'Unable to connect to device {device_name} ({device_ip}:{port_number})',
                        'details': 'Connection refused. Check: IP address, port, network, device power.',
                    })
                    cr.commit()
                return
        except Exception as e:
            _logger.error(f"Live capture connection failed for {device_name}: {str(e)}")
            # Log connection exception
            with self.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                env['biometric.device.log'].sudo().create({
                    'device_id': device_id,
                    'log_type': 'live_capture',
                    'status': 'failed',
                    'duration': _time.time() - start_time,
                    'error_message': str(e),
                    'details': f'Connection exception for device {device_name}',
                })
                cr.commit()
            return

        try:
            # NOTE: Do NOT call conn.disable_device() here!
            # pyzk's live_capture() internally calls enable_device() and reg_event().
            # Calling disable_device() would put the device in "Communication..." mode
            # and block users from punching until live_capture() re-enables it.

            _logger.info(f"Live capture starting for device: {device_name}")

            # Check if live_capture method exists
            if not hasattr(conn, 'live_capture'):
                session_error = (f"Device {device_name} does not support live_capture() method. "
                                 "Ensure your PyZK version supports live_capture().")
                _logger.error(session_error)
                return

            # Start live capture — device pushes events in real-time via reg_event(EF_ATTLOG)
            # Timeout is per-receive, not total: if no event in {timeout}s, yields None and loops
            _logger.info(f"Live capture active for device: {device_name} (timeout={live_capture_timeout}s)")
            for attendance in conn.live_capture(new_timeout=live_capture_timeout):
                # Create new cursor for each event (thread-safe)
                with self.pool.cursor() as cr:
                    try:
                        env = api.Environment(cr, SUPERUSER_ID, {})
                        device = env['biometric.device.details'].browse(device_id)

                        # Check if we should stop
                        if not device.live_capture_enabled:
                            conn.end_live_capture = True
                            _logger.info(f"Live capture stop requested for {device_name}")
                            break

                        if attendance is None:
                            # No new events, continue listening
                            continue

                        _logger.info(f"Live event captured: User={attendance.user_id}, "
                                   f"Time={attendance.timestamp}, Punch={attendance.punch}")

                        # Process attendance event immediately
                        result = device._process_live_attendance_with_env(env, attendance)

                        # Track result
                        if result == 'success':
                            events_processed += 1
                        elif result == 'duplicate':
                            events_duplicate += 1
                        elif result == 'unknown_user':
                            events_unknown += 1

                        # Update last event time
                        device.write({'last_live_event_time': fields.Datetime.now()})

                        # Send real-time notification via bus
                        if result == 'success':
                            device._send_live_event_notification_with_env(env, attendance)

                        # Commit the transaction
                        cr.commit()

                    except Exception as e:
                        events_failed += 1
                        _logger.error(f"Error processing live event: {str(e)}")
                        cr.rollback()

        except AttributeError as e:
            session_error = f"Live capture not supported on {device_name}: {str(e)}"
            _logger.error(session_error)
        except Exception as e:
            session_error = f"Live capture error on {device_name}: {str(e)}"
            _logger.error(session_error)
        finally:
            try:
                # live_capture() already calls reg_event(0) and restores device state on exit.
                # We just need to disconnect.
                conn.disconnect()
            except Exception as e:
                _logger.debug("Error during live capture cleanup for %s: %s", device_name, e)

            # Create session summary log and update device status
            elapsed = _time.time() - start_time
            total_events = events_processed + events_duplicate + events_unknown + events_failed
            with self.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                device = env['biometric.device.details'].browse(device_id)
                device.write({'live_capture_active': False})

                # Determine log status
                if session_error:
                    log_status = 'failed'
                elif events_failed > 0 and events_processed == 0:
                    log_status = 'failed'
                elif events_failed > 0:
                    log_status = 'warning'
                else:
                    log_status = 'success'

                details_text = (
                    f"Device: {device_name} ({device_ip}:{port_number})\n"
                    f"Session duration: {elapsed:.1f}s\n"
                    f"Total events received: {total_events}\n"
                    f"Processed: {events_processed}\n"
                    f"Duplicates skipped: {events_duplicate}\n"
                    f"Unknown users: {events_unknown}\n"
                    f"Failed: {events_failed}"
                )

                env['biometric.device.log'].sudo().create({
                    'device_id': device_id,
                    'log_type': 'live_capture',
                    'status': log_status,
                    'records_found': total_events,
                    'records_new': events_processed,
                    'records_duplicate': events_duplicate,
                    'records_failed': events_failed,
                    'employees_not_found': events_unknown,
                    'duration': elapsed,
                    'error_message': session_error if session_error else False,
                    'details': details_text,
                })
                cr.commit()

            _logger.info(
                f"Live capture stopped for {device_name}: "
                f"processed={events_processed}, dup={events_duplicate}, "
                f"unknown={events_unknown}, failed={events_failed}, time={elapsed:.1f}s"
            )

    def _process_live_attendance_with_env(self, env, attendance):
        """
        Process a single live attendance event
        This version accepts explicit environment for thread-safe operation
        Returns: 'success', 'unknown_user', or 'duplicate'
        """
        # Find employee by device ID
        employee = env['hr.employee'].search([
            ('device_id_num', '=', attendance.user_id)
        ], limit=1)

        if not employee:
            _logger.warning(f"Live capture: Unknown user ID {attendance.user_id}")
            return 'unknown_user'

        # ═══════════════════════════════════════════════════════
        # CRITICAL TIMEZONE CONVERSION FIX (Live Capture)
        # ═══════════════════════════════════════════════════════
        # Same logic as PyZK download: device sends local time,
        # convert to UTC for Odoo storage. Handle DST transitions.
        # ═══════════════════════════════════════════════════════
        atten_time = attendance.timestamp
        local_tz = pytz.timezone(self._get_device_timezone())
        
        try:
            local_dt = local_tz.localize(atten_time, is_dst=None)
            utc_dt = local_dt.astimezone(pytz.utc)
        except pytz.exceptions.NonExistentTimeError:
            _logger.warning(
                "Device %s: Non-existent time %s during DST spring-forward in live capture",
                self.name, atten_time)
            local_dt = local_tz.localize(atten_time, is_dst=False)
            utc_dt = local_dt.astimezone(pytz.utc)
        except pytz.exceptions.AmbiguousTimeError:
            _logger.warning(
                "Device %s: Ambiguous time %s during DST fall-back in live capture",
                self.name, atten_time)
            local_dt = local_tz.localize(atten_time, is_dst=True)
            utc_dt = local_dt.astimezone(pytz.utc)
        
        atten_time_str = fields.Datetime.to_string(utc_dt)

        # Duplicate prevention: check time-window duplicate
        duplicate_threshold = self.duplicate_threshold or 5
        if self._is_duplicate_punch(employee.id, utc_dt, duplicate_threshold):
            _logger.debug(f"Live capture: Skipping duplicate punch for {employee.name} "
                         f"within {duplicate_threshold} sec window")
            return 'duplicate'

        # Serialize concurrent writes for the same employee across devices
        env.cr.execute("SELECT pg_advisory_xact_lock(%s)", (employee.id & 0x7FFFFFFF,))
        # Create ZK attendance record (sanitize device values to prevent ValueError)
        zk_attendance = env['zk.machine.attendance'].sudo().create({
            'employee_id': employee.id,
            'device_id': self.id,
            'device_id_num': attendance.user_id,
            'attendance_type': ZkMachineAttendance._sanitize_attendance_type(attendance.status),
            'punch_type': ZkMachineAttendance._sanitize_punch_type(attendance.punch),
            'punching_time': atten_time_str,
            'address_id': self.address_id.id if self.address_id else False
        })

        # Create/update hr.attendance based on mode
        hr_attendance = env['hr.attendance'].sudo()
        if self.attendance_mode == 'auto':
            self._process_auto_attendance(employee, atten_time_str, hr_attendance)
        elif self.attendance_mode == 'auto_per_day':
            self._process_auto_per_day_attendance(employee, atten_time_str, hr_attendance)
        elif self.attendance_mode == 'traditional_per_day':
            self._process_traditional_per_day_attendance(
                employee, atten_time_str, attendance.punch, hr_attendance)
        else:
            self._process_traditional_attendance(employee, atten_time_str, attendance.punch, hr_attendance)

        _logger.info(f"Live attendance processed for employee: {employee.name}")

        # Display LCD message if enabled
        if self.lcd_enabled:
            self._display_attendance_lcd_message(employee, attendance.punch)

        # Play audio if enabled
        if self.audio_enabled:
            self._play_attendance_audio(attendance.punch)

        _logger.info(f"Live capture: Processed attendance for {employee.name} at {atten_time_str}")
        return 'success'

    def _send_live_event_notification(self, attendance):
        """Send real-time notification via Odoo bus"""
        try:
            employee = self.env['hr.employee'].search([('device_id_num', '=', attendance.user_id)], limit=1)
            if employee:
                self.env['bus.bus']._sendone(
                    self.env.user.partner_id,
                    'attendance_live_event',
                    {
                        'device': self.name,
                        'employee': employee.name,
                        'time': str(attendance.timestamp),
                        'type': 'Check-in' if attendance.punch == 0 else 'Check-out'
                    }
                )
        except Exception as e:
            _logger.error(f"Failed to send live event notification: {str(e)}")

    def _send_live_event_notification_with_env(self, env, attendance):
        """
        Send real-time notification via Odoo bus
        This version accepts explicit environment for thread-safe operation
        """
        try:
            employee = env['hr.employee'].search([('device_id_num', '=', attendance.user_id)], limit=1)
            if employee:
                # Send bus notification to all users
                env['bus.bus']._sendmany([
                    (env.user.partner_id, 'attendance_live_event', {
                        'device': self.name,
                        'employee': employee.name,
                        'time': str(attendance.timestamp),
                        'type': 'Check-in' if attendance.punch == 0 else 'Check-out'
                    })
                ])
                _logger.info(f"Live event notification sent for {employee.name}")
        except Exception as e:
            _logger.error(f"Failed to send live event notification: {str(e)}")

    # ==================== NEW PYZK METHODS - LCD MESSAGES ====================

    def action_test_lcd(self):
        """
        Test LCD display with custom message
        Uses pyzk methods: write_lcd(), clear_lcd()
        """
        self.ensure_one()
        device_password = self._get_device_password()
        zk = ZK(self.device_ip, port=self.port_number, timeout=15,
                password=device_password, ommit_ping=True)

        conn = self.device_connect(zk)
        if not conn:
            raise UserError(_('Unable to connect to device'))

        try:
            # Check if LCD methods are available
            if not hasattr(conn, 'clear_lcd') or not hasattr(conn, 'write_lcd'):
                raise UserError(_('LCD display methods are not supported by this device or PyZK version'))

            # Clear LCD first
            conn.clear_lcd()

            # Write test message
            conn.write_lcd(line_number=1, text="Test Message")
            conn.write_lcd(line_number=2, text=f"From: {self.env.user.name[:15]}")

            self.message_post(body="LCD test message sent successfully")

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Test message displayed on device LCD',
                    'type': 'success',
                    'sticky': False
                }
            }
        except AttributeError as e:
            raise UserError(_('LCD display is not supported by this device or PyZK version'))
        finally:
            conn.disconnect()

    def action_clear_lcd(self):
        """Clear LCD display"""
        self.ensure_one()
        device_password = self._get_device_password()
        zk = ZK(self.device_ip, port=self.port_number, timeout=15,
                password=device_password, ommit_ping=True)

        conn = self.device_connect(zk)
        if not conn:
            raise UserError(_('Unable to connect to device'))

        try:
            if not hasattr(conn, 'clear_lcd'):
                raise UserError(_('LCD display is not supported by this device or PyZK version'))

            conn.clear_lcd()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'LCD cleared successfully',
                    'type': 'success',
                    'sticky': False
                }
            }
        except AttributeError as e:
            raise UserError(_('LCD display is not supported by this device or PyZK version'))
        finally:
            conn.disconnect()

    def _display_attendance_lcd_message(self, employee, punch_type):
        """Display personalized LCD message on attendance"""
        if not self.lcd_enabled:
            return

        device_password = self._get_device_password()
        zk = ZK(self.device_ip, port=self.port_number, timeout=5,
                password=device_password, ommit_ping=True)

        conn = self.device_connect(zk)
        if conn:
            try:
                # Check if LCD methods are available
                if hasattr(conn, 'write_lcd'):
                    # Display employee name and message
                    message = self.lcd_welcome_message if punch_type == 0 else self.lcd_goodbye_message
                    conn.write_lcd(1, employee.name[:20])
                    conn.write_lcd(2, message[:20])
            except Exception as e:
                _logger.debug("LCD write failed for device %s: %s", self.name, e)
            finally:
                conn.disconnect()

    # ==================== NEW PYZK METHODS - AUDIO FEEDBACK ====================

    def action_test_voice(self):
        """
        Test device voice/audio feedback
        Uses pyzk method: test_voice(index)
        Available indices: 0-55 (different sounds/voices)
        """
        self.ensure_one()
        device_password = self._get_device_password()
        zk = ZK(self.device_ip, port=self.port_number, timeout=15,
                password=device_password, ommit_ping=True)

        conn = self.device_connect(zk)
        if not conn:
            raise UserError(_('Unable to connect to device'))

        try:
            if not hasattr(conn, 'test_voice'):
                raise UserError(_('Audio/voice feedback is not supported by this device or PyZK version'))

            # Test with check-in voice
            conn.test_voice(index=self.checkin_voice_index)

            self.message_post(body=f"Voice test played (index: {self.checkin_voice_index})")

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Playing voice index {self.checkin_voice_index}',
                    'type': 'success',
                    'sticky': False
                }
            }
        except AttributeError as e:
            raise UserError(_('Audio/voice feedback is not supported by this device or PyZK version'))
        finally:
            conn.disconnect()

    def _play_attendance_audio(self, punch_type):
        """Play audio feedback on attendance"""
        if not self.audio_enabled:
            return

        device_password = self._get_device_password()
        zk = ZK(self.device_ip, port=self.port_number, timeout=5,
                password=device_password, ommit_ping=True)

        conn = self.device_connect(zk)
        if conn:
            try:
                if hasattr(conn, 'test_voice'):
                    voice_index = self.checkin_voice_index if punch_type == 0 else self.checkout_voice_index
                    conn.test_voice(index=voice_index)
            except Exception as e:
                _logger.debug("Voice feedback failed for device %s: %s", self.name, e)
            finally:
                conn.disconnect()

    # ==================== NEW PYZK METHODS - DOOR CONTROL ====================

    def action_unlock_door(self):
        """
        Unlock door for configured duration
        Uses pyzk method: unlock(time)
        """
        self.ensure_one()

        if not self.door_control_enabled:
            raise UserError(_('Door control is not enabled for this device'))

        device_password = self._get_device_password()
        zk = ZK(self.device_ip, port=self.port_number, timeout=15,
                password=device_password, ommit_ping=True)

        conn = self.device_connect(zk)
        if not conn:
            raise UserError(_('Unable to connect to device'))

        try:
            # Unlock door
            conn.unlock(time=self.default_unlock_duration)

            # Update lock state
            self.write({'current_lock_state': 'unlocked'})

            # Log activity
            self.message_post(
                body=f"Door unlocked by {self.env.user.name} for {self.default_unlock_duration} seconds"
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Door unlocked for {self.default_unlock_duration} seconds',
                    'type': 'success',
                    'sticky': False
                }
            }
        finally:
            conn.disconnect()

    def action_get_lock_state(self):
        """
        Get current door lock state
        Uses pyzk method: get_lock_state()
        """
        self.ensure_one()
        device_password = self._get_device_password()
        zk = ZK(self.device_ip, port=self.port_number, timeout=15,
                password=device_password, ommit_ping=True)

        conn = self.device_connect(zk)
        if not conn:
            raise UserError(_('Unable to connect to device'))

        try:
            if not hasattr(conn, 'get_lock_state'):
                raise UserError(_('Door lock status check is not supported by this device or PyZK version'))

            lock_state = conn.get_lock_state()
            state = 'locked' if lock_state else 'unlocked'
            self.write({'current_lock_state': state})

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Door is currently: {state.upper()}',
                    'type': 'info',
                    'sticky': False
                }
            }
        except AttributeError as e:
            raise UserError(_('Door lock status check is not supported by this device or PyZK version'))
        finally:
            conn.disconnect()

    # ==================== NEW PYZK METHODS - USER MANAGEMENT ====================

    def action_sync_users_to_device(self):
        """
        Sync all Odoo employees to device
        Uses pyzk method: set_user()
        """
        self.ensure_one()
        device_password = self._get_device_password()
        zk = ZK(self.device_ip, port=self.port_number, timeout=30,
                password=device_password, ommit_ping=True)

        conn = self.device_connect(zk)
        if not conn:
            raise UserError(_('Unable to connect to device'))

        try:
            conn.disable_device()

            # Get all employees with device ID
            employees = self.env['hr.employee'].search([
                ('device_id_num', '!=', False),
                ('company_id', '=', self.company_id.id)
            ])

            # Get all current users from device to map user_id -> uid
            try:
                device_users = conn.get_users()
                user_map = {str(u.user_id): u.uid for u in device_users} if device_users else {}
                
                # Log any users found on the device that aren't mapped in Odoo
                odoo_employee_ids = [str(e.device_id_num) for e in employees]
                for unknown_user in (device_users or []):
                    if str(unknown_user.user_id) not in odoo_employee_ids:
                        self.env['biometric.device.log'].sudo().create({
                            'device_id': self.id,
                            'log_type': 'sync',
                            'status': 'warning',
                            'error_message': f'Unmapped User on Device: {unknown_user.name} (ID: {unknown_user.user_id})',
                            'details': 'This user exists on the biometric device but has no linked hr.employee in Odoo.',
                        })
            except Exception as e:
                _logger.warning(f"Failed to fetch existing users prior to sync: {e}")
                user_map = {}

            enrolled_count = 0
            for employee in employees:
                try:
                    # Get existing internal uid if user already exists on device
                    internal_uid = user_map.get(str(employee.device_id_num))
                    
                    # Create/update user on device safely without destroying fingerprint links
                    conn.set_user(
                        uid=internal_uid,  # Use existing UID if present, otherwise let device auto-assign
                        name=employee.name[:24],  # Max 24 chars
                        privilege=0,  # 0=User, 14=Admin
                        password='',
                        group_id='',
                        user_id=str(employee.device_id_num),
                        card=0
                    )
                    enrolled_count += 1
                    _logger.info(f"Synced {employee.name} to device {self.name}")
                except Exception as e:
                    _logger.error(f"Failed to sync {employee.name}: {str(e)}")

            # Refresh device info to get updated user count
            sizes = conn.read_sizes()
            if sizes and isinstance(sizes, dict):
                self.write({
                    'user_count': sizes.get('users_cap', 0),
                })

            self.message_post(
                body=f"Successfully synced {enrolled_count} employees to device"
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Synced {enrolled_count} employees to device',
                    'type': 'success',
                    'sticky': False
                }
            }

        finally:
            conn.enable_device()
            conn.disconnect()

    def action_view_attendance_records(self):
        """View all attendance records downloaded from this device"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Attendance Records - {self.name}',
            'res_model': 'zk.machine.attendance',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.id)],
            'context': {'default_device_id': self.id},
        }

    def action_view_device_logs(self):
        """View download/operation logs for this device"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Device Logs - {self.name}',
            'res_model': 'biometric.device.log',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.id)],
            'context': {'default_device_id': self.id},
        }

    def action_view_live_capture_logs(self):
        """View live capture logs for this device"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Live Capture Logs - {self.name}',
            'res_model': 'biometric.device.log',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.id), ('log_type', '=', 'live_capture')],
            'context': {'default_device_id': self.id, 'default_log_type': 'live_capture'},
        }

    def action_view_operation_logs(self):
        """
        ═══════════════════════════════════════════════════════
        NEW: View all device operation logs with status filters
        Shows success/failed/warning logs for ALL connection modes:
        - PyZK (Direct Connection)
        - ADMS (Cloud Push)
        - Hybrid (ADMS + PyZK)
        ═══════════════════════════════════════════════════════
        This works regardless of Odoo log level (debug/info/warning)
        because logs are stored in database, not just in server log files.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Operation Logs - {self.name}',
            'res_model': 'biometric.device.log',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.id)],
            'context': {
                'default_device_id': self.id,
                'search_default_all_logs': 1,
                'group_by': ['status', 'log_type'],
            },
            'help': f'''
                <div class="o_empty_custom">
                    <h3>Device Operation Logs</h3>
                    <p>
                        View all attendance download, connection, and sync operations for this device.
                        Logs are stored in the database and persist regardless of Odoo log level.
                    </p>
                    <p class="mt-2">
                        <b>Connection Mode:</b> {dict(self._fields['connection_mode'].selection).get(self.connection_mode, self.connection_mode)}<br/>
                        <b>Attendance Mode:</b> {dict(self._fields['attendance_mode'].selection).get(self.attendance_mode, self.attendance_mode)}
                    </p>
                </div>
            ''',
        }

    def action_view_enrolled_users(self):
        """Show employees mapped to users enrolled on this device.

        Reads the actual user list from the device (Direct mode) so the count
        matches what the device reports.  Falls back to Odoo punch history when
        a live connection is not available (ADMS/Cloud devices).
        """
        self.ensure_one()
        employee_ids = []

        if self.connection_mode == 'direct':
            try:
                try:
                    from zk import ZK
                except ImportError:
                    from pyzk2 import ZK
                zk = ZK(self.device_ip, port=self.port_number, timeout=10,
                        password=self._get_device_password(),
                        force_udp=False, ommit_ping=True)
                conn = zk.connect()
                try:
                    users = conn.get_users()
                    device_pins = {str(u.user_id) for u in users}
                    employees = self.env['hr.employee'].sudo().search([
                        ('device_id_num', 'in', list(device_pins)),
                    ])
                    employee_ids = employees.ids
                finally:
                    try:
                        conn.disconnect()
                    except Exception:
                        pass
            except Exception:
                pass

        if not employee_ids:
            # Fallback: employees who have ever punched on this device
            employee_ids = self.env['zk.machine.attendance'].search([
                ('device_id', '=', self.id),
            ]).mapped('employee_id').ids

        return {
            'type': 'ir.actions.act_window',
            'name': f'Enrolled Users - {self.name}',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', employee_ids)],
            'context': {'default_company_id': self.company_id.id},
        }

    def action_import_employees_from_device(self):
        """Connect to device, fetch user list, open import preview wizard."""
        self.ensure_one()
        if self.connection_mode != 'direct':
            raise UserError(_(
                'Import Employees from Device only works in Direct connection mode.\n\n'
                'This feature connects directly to the device over your local network to '
                'fetch the enrolled user list. It cannot reach devices that are on a remote '
                'site or connected via Cloud mode.\n\n'
                'To add employees for a Cloud/Hybrid device, please create them manually in '
                'Odoo (HR → Employees) and set each employee\'s Device ID Number to match '
                'the ID shown on the biometric device.'))
        zk = ZK(self.device_ip, port=self.port_number, timeout=15,
                password=self._get_device_password(), force_udp=False, ommit_ping=True)
        conn = None
        try:
            conn = zk.connect()
            users = conn.get_users()
        except Exception as e:
            raise UserError(_('Could not connect to device: %s') % str(e))
        finally:
            if conn:
                try:
                    conn.disconnect()
                except Exception:
                    pass

        if not users:
            raise UserError(_('No users found on device.'))

        hr_employee = self.env['hr.employee'].sudo()
        line_vals = []
        for user in users:
            pin = str(user.user_id)
            existing = hr_employee.search([('device_id_num', '=', pin)], limit=1)
            privilege_val = str(user.privilege) if str(user.privilege) in ('0', '14') else '0'
            line_vals.append((0, 0, {
                'pin': pin,
                'name': user.name or f'Device User {pin}',
                'privilege': privilege_val,
                'status': 'exists' if existing else 'new',
                'employee_id': existing.id if existing else False,
                'is_selected': False,
            }))

        wizard = self.env['zk.import.users.wizard'].create({
            'device_id': self.id,
            'line_ids': line_vals,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Employees from Device'),
            'res_model': 'zk.import.users.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ==================== BIOMETRIC TEMPLATE MANAGEMENT ====================

    def _make_download_attachment(self, filename, json_bytes):
        """Create (or overwrite) an ir.attachment and return its download URL."""
        self.env['ir.attachment'].search([
            ('res_model', '=', 'biometric.device.details'),
            ('res_id', '=', self.id),
            ('name', '=', filename),
        ]).unlink()
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(json_bytes),
            'type': 'binary',
            'res_model': 'biometric.device.details',
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    # ── PyZK: per-device download (instant, no wizard) ──────────────────────

    def action_download_templates(self):
        """Download all fingerprint templates from device directly to PC as JSON.
        No wizard — file downloads instantly in the browser.
        """
        self.ensure_one()
        if self.connection_mode == 'adms':
            raise UserError(_(
                'PyZK download requires Direct or Hybrid connection mode. '
                'ADMS devices push templates automatically via the BIODATA endpoint.'))

        device_password = self._get_device_password()
        zk = ZK(self.device_ip, port=self.port_number, timeout=60,
                password=device_password, ommit_ping=True)

        conn = self.device_connect(zk)
        if not conn:
            raise UserError(_('Unable to connect to device'))

        try:
            # Step 1: Get users to map UID
            users = conn.get_users() or []
            uid_to_user = {}
            for u in users:
                uid_to_user[u.uid] = {
                    'user_id': str(u.user_id),
                    'name': u.name,
                }

            # Step 2: Get all templates
            templates = conn.get_templates() or []

            # Step 3: Package into JSON structure
            user_data_map = {}
            
            # Pre-populate all users so users with 0 templates are included
            for uid, info in uid_to_user.items():
                device_user_id = info['user_id']
                user_data_map[device_user_id] = {
                    "user_id": device_user_id,
                    "name": info['name'],
                    "templates": []
                }

            for t in templates:
                uid = getattr(t, 'uid', None)
                fid = getattr(t, 'fid', 0)
                template_data = getattr(t, 'template', None) or getattr(t, 'data', None)
                template_size = getattr(t, 'size', 0)

                if uid is None or not template_data:
                    continue

                if isinstance(template_data, bytes):
                    template_b64 = base64.b64encode(template_data).decode('ascii')
                elif isinstance(template_data, str):
                    template_b64 = template_data
                else:
                    template_b64 = str(template_data)

                user_info = uid_to_user.get(uid, {})
                device_user_id = user_info.get('user_id', str(uid))
                name = user_info.get('name', f"User {uid}")
                
                if device_user_id not in user_data_map:
                    user_data_map[device_user_id] = {
                        "user_id": device_user_id,
                        "name": name,
                        "templates": []
                    }
                
                user_data_map[device_user_id]["templates"].append({
                    "fid": fid,
                    "size": template_size,
                    "template_data": template_b64
                })

            export_data = list(user_data_map.values())
            
            # Log the downloaded users and their template counts
            download_log_details = []
            for user_data in export_data:
                u_id = user_data["user_id"]
                u_name = user_data["name"]
                t_count = len(user_data["templates"])
                download_log_details.append(f"• ID {u_id} ({u_name}): {t_count} template(s)")
                _logger.info(f"[{self.name}] Downloaded User ID {u_id} ({u_name}): {t_count} template(s)")
                
            summary_msg = f"Fingerprint download complete: {len(templates)} templates downloaded across {len(export_data)} users.\n\nDetails:\n" + "\n".join(download_log_details)
            self.message_post(body=summary_msg, message_type='notification')

            json_bytes = json.dumps(export_data, indent=2).encode('utf-8')
            filename = f'fingerprints_{self.name.replace(" ", "_")}.json'
            return self._make_download_attachment(filename, json_bytes)

        except AttributeError as e:
            raise UserError(_(
                'Template download not supported by this device or PyZK version: %s', str(e)))
        except Exception as e:
            _logger.exception("Template download failed for device %s", self.name)
            raise UserError(_('Failed to download templates: %s', str(e)))
        finally:
            conn.disconnect()

    action_backup_templates = action_download_templates

    # ── PyZK: per-device upload (minimal wizard, this device only) ───────────

    def action_upload_templates_to_device(self):
        """Open minimal file-picker popup — uploads fingerprints to THIS device only."""
        self.ensure_one()
        if self.connection_mode == 'adms':
            raise UserError(_('PyZK upload requires Direct or Hybrid connection mode.'))

        wizard = self.env['biometric.template.wizard'].create({
            'device_id': self.id,
        })
        return {
            'name': _('Upload Fingerprints from PC'),
            'type': 'ir.actions.act_window',
            'res_model': 'biometric.template.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    # ── ADMS: per-device download (instant, filters by this device) ──────────

    def action_download_adms_for_device(self):
        """Download ADMS biometric templates stored for THIS device as JSON (instant)."""
        self.ensure_one()
        templates = self.env['biometric.fp.template'].search([('device_id', '=', self.id)])
        if not templates:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('No ADMS biometric templates stored for this device yet. '
                                 'Templates are saved automatically when the device sends BIODATA.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        export_data = []
        for tmpl in templates:
            pin = tmpl.employee_id.device_id_num if tmpl.employee_id else None
            if not pin:
                continue
            export_data.append({
                'employee_name': tmpl.employee_id.name,
                'pin': pin,
                'template_type': tmpl.template_type,
                'finger_index': tmpl.finger_index,
                'template_size': tmpl.template_size,
                'template_data': tmpl.template_data,
            })
        if not export_data:
            raise UserError(_('No exportable templates — employees are missing PIN numbers.'))
        json_bytes = json.dumps(export_data, indent=2).encode('utf-8')
        filename = f'adms_templates_{self.name.replace(" ", "_")}.json'
        return self._make_download_attachment(filename, json_bytes)

    # ── ADMS: per-device upload (minimal wizard, syncs to this device only) ──

    def action_upload_adms_for_device(self):
        """Open minimal file-picker popup — imports ADMS templates and syncs to THIS device."""
        self.ensure_one()
        wizard = self.env['adms.template.wizard'].create({
            'state': 'upload',
            'device_ids': [(4, self.id)],
            'single_device_mode': True,
        })
        return {
            'name': _('Upload ADMS Templates from PC'),
            'type': 'ir.actions.act_window',
            'res_model': 'adms.template.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    # ── Bulk: download from ALL selected devices (ZKTeco Devices list view) ──

    def action_bulk_download_templates(self):
        """Download fingerprints from all selected devices as a combined JSON file."""
        if not self:
            raise UserError(_('Please select at least one device.'))

        all_user_data = {}
        errors = []

        for device in self:
            if device.connection_mode == 'adms':
                errors.append(f'{device.name}: skipped (ADMS mode — use ADMS Download instead)')
                continue
            device_password = device._get_device_password()
            zk = ZK(device.device_ip, port=device.port_number, timeout=60,
                    password=device_password, ommit_ping=True)
            conn = device.device_connect(zk)
            if not conn:
                errors.append(f'{device.name}: could not connect')
                continue
            try:
                users = conn.get_users() or []
                uid_to_user = {u.uid: {'user_id': str(u.user_id), 'name': u.name} for u in users}
                templates = conn.get_templates() or []
                for t in templates:
                    uid = getattr(t, 'uid', None)
                    fid = getattr(t, 'fid', 0)
                    raw = getattr(t, 'template', None) or getattr(t, 'data', None)
                    if uid is None or not raw:
                        continue
                    b64 = base64.b64encode(raw).decode('ascii') if isinstance(raw, bytes) else str(raw)
                    info = uid_to_user.get(uid, {})
                    key = info.get('user_id', str(uid))
                    if key not in all_user_data:
                        all_user_data[key] = {'user_id': key, 'name': info.get('name', f'User {uid}'), 'templates': []}
                    all_user_data[key]['templates'].append({'fid': fid, 'template_data': b64})
            except Exception as e:
                errors.append(f'{device.name}: error — {e}')
            finally:
                conn.disconnect()

        if not all_user_data:
            msg = 'No templates found.' + (' Errors: ' + '; '.join(errors) if errors else '')
            raise UserError(_(msg))

        export_data = list(all_user_data.values())
        json_bytes = json.dumps(export_data, indent=2).encode('utf-8')

        # Use first selected device as attachment host
        host = self[0]
        host.env['ir.attachment'].search([
            ('res_model', '=', 'biometric.device.details'),
            ('res_id', '=', host.id),
            ('name', 'like', 'bulk_fingerprints_'),
        ]).unlink()
        attachment = host.env['ir.attachment'].create({
            'name': f'bulk_fingerprints_{len(self)}_devices.json',
            'datas': base64.b64encode(json_bytes),
            'type': 'binary',
            'res_model': 'biometric.device.details',
            'res_id': host.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    # ── Bulk: upload to selected devices (ZKTeco Devices list view) ──────────

    def action_bulk_upload_templates(self):
        """Open multi-device upload wizard pre-loaded with selected devices."""
        if not self:
            raise UserError(_('Please select at least one device.'))
        direct_devices = self.filtered(lambda d: d.connection_mode in ('direct', 'hybrid'))
        if not direct_devices:
            raise UserError(_('None of the selected devices support PyZK (requires Direct or Hybrid mode).'))
        wizard = self.env['bulk.template.wizard'].create({
            'device_ids': [(6, 0, direct_devices.ids)],
        })
        return {
            'name': _('Upload Fingerprints to Selected Devices'),
            'type': 'ir.actions.act_window',
            'res_model': 'bulk.template.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def action_verify_employee_biometric(self):
        """
        Verify employee biometric against device
        Uses pyzk method: verify_user()
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Verify Employee Biometric',
            'res_model': 'hr.employee',
            'view_mode': 'list',
            'domain': [('device_id_num', '!=', False), ('company_id', '=', self.company_id.id)],
            'context': {
                'default_company_id': self.company_id.id,
                'biometric_device_id': self.id,
            },
            'target': 'new',
        }

    # ==================== DELETE OPERATIONS (COMMENTED FOR SAFETY) ====================

    # UNCOMMENT BELOW METHODS ONLY WHEN EXPLICITLY REQUESTED BY USER
    # These operations are DESTRUCTIVE and cannot be undone!

    # def action_clear_attendance(self):
    #     """
    #     ⚠️ DANGER: Clear ALL attendance records from device
    #     Uses pyzk method: clear_attendance()
    #     """
    #     self.ensure_one()
    #     device_password = self._get_device_password()
    #     zk = ZK(self.device_ip, port=self.port_number, timeout=30,
    #             password=device_password, ommit_ping=True)
    #
    #     conn = self.device_connect(zk)
    #     if not conn:
    #         raise UserError(_('Unable to connect to device'))
    #
    #     try:
    #         conn.disable_device()
    #         attendance = conn.get_attendance()
    #
    #         if attendance:
    #             # Clear attendance from device
    #             conn.clear_attendance()
    #
    #             # Also clear from zk.machine.attendance table
    #             self.env['zk.machine.attendance'].search([
    #                 ('address_id', '=', self.address_id.id if self.address_id else False)
    #             ]).unlink()
    #
    #             # Update record count
    #             sizes = conn.read_sizes()
    #             self.write({'record_count': sizes.get('records_cap', 0)})
    #
    #             self.message_post(
    #                 subject='⚠️ Attendance Records Cleared',
    #                 body=f"ALL attendance records cleared from device by {self.env.user.name}",
    #                 message_type='notification'
    #             )
    #
    #             return {
    #                 'type': 'ir.actions.client',
    #                 'tag': 'display_notification',
    #                 'params': {
    #                     'message': 'All attendance records cleared from device',
    #                     'type': 'warning',
    #                     'sticky': True
    #                 }
    #             }
    #         else:
    #             raise UserError(_('No attendance records found to clear'))
    #
    #     finally:
    #         conn.enable_device()
    #         conn.disconnect()

    # def action_delete_user_from_device(self, user_id):
    #     """
    #     ⚠️ DANGER: Delete user from device
    #     Uses pyzk method: delete_user()
    #     """
    #     self.ensure_one()
    #     device_password = self._get_device_password()
    #     zk = ZK(self.device_ip, port=self.port_number, timeout=15,
    #             password=device_password, ommit_ping=True)
    #
    #     conn = self.device_connect(zk)
    #     if not conn:
    #         raise UserError(_('Unable to connect to device'))
    #
    #     try:
    #         conn.disable_device()
    #         conn.delete_user(uid=None, user_id=user_id)
    #
    #         # Update user count
    #         sizes = conn.read_sizes()
    #         self.write({'user_count': sizes.get('users_cap', 0)})
    #
    #         self.message_post(
    #             body=f"User {user_id} deleted from device by {self.env.user.name}"
    #         )
    #
    #         return True
    #     finally:
    #         conn.enable_device()
    #         conn.disconnect()

    # def action_clear_all_data(self):
    #     """
    #     ⚠️⚠️⚠️ EXTREME DANGER: Clear ALL data from device (Factory Reset)
    #     Uses pyzk method: clear_data()
    #     This will delete EVERYTHING: users, fingerprints, attendance, face templates
    #     """
    #     self.ensure_one()
    #     device_password = self._get_device_password()
    #     zk = ZK(self.device_ip, port=self.port_number, timeout=30,
    #             password=device_password, ommit_ping=True)
    #
    #     conn = self.device_connect(zk)
    #     if not conn:
    #         raise UserError(_('Unable to connect to device'))
    #
    #     try:
    #         conn.disable_device()
    #         conn.clear_data()
    #
    #         # Reset all capacity counters
    #         self.write({
    #             'user_count': 0,
    #             'finger_count': 0,
    #             'record_count': 0,
    #             'face_count': 0,
    #         })
    #
    #         self.message_post(
    #             subject='⚠️⚠️⚠️ DEVICE FACTORY RESET',
    #             body=f"ALL DATA CLEARED from device {self.name} by {self.env.user.name}<br/>"
    #                  f"Users, fingerprints, attendance records, and face templates deleted.",
    #             message_type='notification'
    #         )
    #
    #         return {
    #             'type': 'ir.actions.client',
    #             'tag': 'display_notification',
    #             'params': {
    #                 'message': '⚠️ ALL DATA CLEARED FROM DEVICE',
    #                 'type': 'danger',
    #                 'sticky': True
    #             }
    #         }
    #
    #     finally:
    #         conn.enable_device()
    #         conn.disconnect()

    # def action_delete_user_template(self, uid, temp_id):
    #     """
    #     ⚠️ DANGER: Delete specific fingerprint template
    #     Uses pyzk method: delete_user_template()
    #     """
    #     self.ensure_one()
    #     device_password = self._get_device_password()
    #     zk = ZK(self.device_ip, port=self.port_number, timeout=15,
    #             password=device_password, ommit_ping=True)
    #
    #     conn = self.device_connect(zk)
    #     if not conn:
    #         raise UserError(_('Unable to connect to device'))
    #
    #     try:
    #         conn.disable_device()
    #         conn.delete_user_template(uid=uid, temp_id=temp_id, user_id=None)
    #
    #         # Update finger count
    #         sizes = conn.read_sizes()
    #         self.write({'finger_count': sizes.get('fingers_cap', 0)})
    #
    #         return True
    #     finally:
    #         conn.enable_device()
    #         conn.disconnect()

    # def action_poweroff_device(self):
    #     """
    #     ⚠️ DANGER: Shutdown device
    #     Uses pyzk method: poweroff()
    #     """
    #     self.ensure_one()
    #     device_password = self._get_device_password()
    #     zk = ZK(self.device_ip, port=self.port_number, timeout=15,
    #             password=device_password, ommit_ping=True)
    #
    #     conn = self.device_connect(zk)
    #     if not conn:
    #         raise UserError(_('Unable to connect to device'))
    #
    #     try:
    #         conn.poweroff()
    #
    #         self.message_post(
    #             subject='Device Powered Off',
    #             body=f"Device {self.name} powered off by {self.env.user.name}"
    #         )
    #
    #         return {
    #             'type': 'ir.actions.client',
    #             'tag': 'display_notification',
    #             'params': {
    #                 'message': 'Device is powering off...',
    #                 'type': 'warning',
    #                 'sticky': True
    #             }
    #         }
    #
    #     finally:
    #         conn.disconnect()

    # ==================== EXISTING DOWNLOAD METHOD (Keep as is) ====================

    def _is_duplicate_punch(self, employee_id, punch_time, threshold_seconds):
        """Check if this punch is a duplicate within threshold time window"""
        if threshold_seconds <= 0:
            return False

        zk_attendance = self.env['zk.machine.attendance']
        # Odoo 19 requires naive (no tzinfo) datetimes in search domains
        naive_punch = punch_time.replace(tzinfo=None) if punch_time.tzinfo else punch_time
        time_from = naive_punch - datetime.timedelta(seconds=threshold_seconds)
        time_to = naive_punch + datetime.timedelta(seconds=threshold_seconds)

        duplicate = zk_attendance.search([
            ('employee_id', '=', employee_id),
            ('punching_time', '>=', time_from),
            ('punching_time', '<=', time_to),
        ], limit=1)

        return bool(duplicate)

    def _process_traditional_attendance(self, employee, atten_time, punch_type, hr_attendance):
        """Process attendance in traditional mode (uses device punch type).

        Shift-aware: respects the employee's work schedule (fixed or flexible)
        when deciding whether an old open record belongs to the same shift or
        is a stale leftover to auto-close.
        """
        # Always use sudo() to bypass record rules (multi-company, etc.)
        hr_att_sudo = hr_attendance.sudo()

        # Parse atten_time to datetime for comparisons
        if isinstance(atten_time, str):
            atten_dt = fields.Datetime.from_string(atten_time)
        else:
            atten_dt = atten_time

        # Auto-close any open attendance whose shift window has already ended.
        # Uses the employee's resource.calendar when available (night-shift safe).
        self._auto_close_stale_shift(employee, atten_dt, hr_att_sudo)

        if punch_type == 0:  # check-in from device
            # Only create a new check-in if there is no open record already
            open_record = hr_att_sudo.search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False),
            ], limit=1, order='check_in desc')
            if not open_record:
                new_rec = hr_att_sudo.create({
                    'employee_id': employee.id,
                    'check_in': atten_time
                })
                _logger.info(f"Traditional mode: Check-in created for {employee.name}")
                return new_rec
        elif punch_type == 1:  # check-out from device
            # Always pick the most recent open record — avoids being stuck when
            # multiple open records exist due to missed previous check-outs.
            open_record = hr_att_sudo.search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False),
            ], limit=1, order='check_in desc')
            if open_record:
                # Guard: check_out must be after check_in (Odoo constraint)
                check_in_dt = fields.Datetime.from_string(open_record.check_in) \
                    if isinstance(open_record.check_in, str) else open_record.check_in
                if atten_dt <= check_in_dt:
                    _logger.warning(
                        f"Traditional mode: check-out {atten_dt} is not after "
                        f"check-in {check_in_dt} for {employee.name} — skipping")
                else:
                    open_record.write({'check_out': atten_time})
                    _logger.info(f"Traditional mode: Check-out added for {employee.name}")
                    return open_record

    def _process_auto_attendance(self, employee, atten_time, hr_attendance):
        """Process attendance in auto mode (ignores device punch type,
        auto-determines check-in/check-out).

        Shift-aware: if the last open record belongs to a shift that has
        already ended (based on employee's schedule or fallback window),
        close it at shift end and treat this punch as a new check-in —
        instead of blindly recording it as a cross-day check-out.
        """
        # Always use sudo() to bypass record rules — otherwise the search
        # may return empty and EVERY punch becomes a check-in.
        hr_att_sudo = hr_attendance.sudo()

        # Parse atten_time for comparisons
        if isinstance(atten_time, str):
            atten_dt = fields.Datetime.from_string(atten_time)
        else:
            atten_dt = atten_time

        # Auto-close any open records whose shift has already ended, so we
        # don't accidentally pair a fresh check-in to yesterday's forgotten
        # open record.
        self._auto_close_stale_shift(employee, atten_dt, hr_att_sudo)

        last_attendance = hr_att_sudo.search([
            ('employee_id', '=', employee.id)
        ], order='check_in desc', limit=1)

        if not last_attendance or last_attendance.check_out:
            new_rec = hr_att_sudo.create({
                'employee_id': employee.id,
                'check_in': atten_time
            })
            _logger.info(f"Auto mode: Check-in created for {employee.name} at {atten_time}")
            return new_rec

        # Open record still exists — it belongs to the same shift (otherwise
        # _auto_close_stale_shift would have closed it above).
        check_in_dt = fields.Datetime.from_string(last_attendance.check_in) \
            if isinstance(last_attendance.check_in, str) else last_attendance.check_in
        if atten_dt <= check_in_dt:
            _logger.warning(
                f"Auto mode: punch {atten_dt} is not after check-in "
                f"{check_in_dt} for {employee.name} — skipping")
            return False

        last_attendance.write({'check_out': atten_time})
        _logger.info(f"Auto mode: Check-out added for {employee.name} at {atten_time}")
        return last_attendance

    # ==================== PER-DAY MODE HELPERS ====================

    def _get_day_boundaries_utc(self, atten_time):
        """Convert punch time to local date and return (day_start_utc, day_end_utc, local_tz).
        day_start_utc and day_end_utc are naive datetimes for Odoo search domains.
        
        CRITICAL: atten_time is expected to be a naive UTC datetime (as stored by Odoo).
        This method converts it to the device's local timezone to determine the calendar date,
        then returns the start/end of that local day in UTC.
        """
        # Parse the attendance time
        if isinstance(atten_time, str):
            atten_dt = fields.Datetime.from_string(atten_time)
        else:
            atten_dt = atten_time

        # Determine device timezone
        tz_str = self._get_device_timezone()
        try:
            local_tz = pytz.timezone(tz_str)
        except pytz.UnknownTimeZoneError:
            local_tz = pytz.UTC

        # CRITICAL FIX: atten_dt is a naive UTC datetime (as stored by Odoo).
        # We must first interpret it as UTC, then convert to local timezone.
        # DO NOT localize naive datetimes as UTC if they're already UTC!
        if atten_dt.tzinfo is None:
            # Naive datetime from Odoo = UTC
            atten_dt_utc = atten_dt
        else:
            # Already timezone-aware, convert to UTC
            atten_dt_utc = atten_dt.astimezone(pytz.UTC).replace(tzinfo=None)
        
        # Convert UTC to local timezone to find the calendar date
        atten_dt_aware = pytz.UTC.localize(atten_dt_utc)
        local_dt = atten_dt_aware.astimezone(local_tz)
        punch_date = local_dt.date()

        # Build start/end of local day in UTC (naive for Odoo)
        day_start_local = local_tz.localize(
            datetime.datetime.combine(punch_date, datetime.time.min))
        day_end_local = local_tz.localize(
            datetime.datetime.combine(punch_date, datetime.time(23, 59, 59)))
        day_start_utc = day_start_local.astimezone(pytz.UTC).replace(tzinfo=None)
        day_end_utc = day_end_local.astimezone(pytz.UTC).replace(tzinfo=None)

        return day_start_utc, day_end_utc, local_tz

    # ==================== SHIFT-AWARE HELPERS (night-shift safe) ====================

    def _get_employee_resource_calendar(self, employee):
        """Return the employee's resource.calendar (v18: resource_calendar_id on employee)."""
        if hasattr(employee, 'resource_calendar_id') and employee.resource_calendar_id:
            return employee.resource_calendar_id
        return employee.company_id.resource_calendar_id if employee.company_id else False

    def _get_employee_shift_window(self, employee, check_in_utc):
        """Return (shift_start_utc, shift_end_utc) bounding the shift that began
        with ``check_in_utc`` for this employee.

        Logic:
        1. If employee has a fixed resource.calendar — use its attendance_ids
           for the check-in's local weekday; build shift end from hour_to of
           the latest-ending line (handles night shifts crossing midnight by
           also checking the next day's early-morning attendance lines).
        2. Otherwise (flexible calendar / no calendar) — fall back to a
           configurable max_shift_hours window.

        Returned datetimes are naive UTC (Odoo convention).
        """
        ICP = self.env['ir.config_parameter'].sudo()
        max_shift_hours = int(ICP.get_param(
            'dotbd_hr_zk_attendance_suite.max_shift_hours', default=16))
        default_shift_hours = int(ICP.get_param(
            'dotbd_hr_zk_attendance_suite.default_shift_hours', default=8))

        # Normalize check_in to naive UTC
        if isinstance(check_in_utc, str):
            check_in_utc = fields.Datetime.from_string(check_in_utc)
        if check_in_utc.tzinfo is not None:
            check_in_utc = check_in_utc.astimezone(pytz.UTC).replace(tzinfo=None)

        calendar = self._get_employee_resource_calendar(employee)

        # ── Tier 2/3 fallback: flexible or missing calendar ──────────────────
        is_flexible = False
        if calendar:
            is_flexible = bool(
                getattr(calendar, 'flexible_hours', False)
                or getattr(calendar, 'flexible', False)
                or not calendar.attendance_ids
            )

        if not calendar or is_flexible:
            shift_start = check_in_utc
            shift_end = check_in_utc + datetime.timedelta(hours=max_shift_hours)
            return shift_start, shift_end

        # ── Tier 1: fixed schedule — derive shift end from calendar lines ───
        cal_tz_name = calendar.tz or (employee.tz if employee else False) or 'UTC'
        try:
            local_tz = pytz.timezone(cal_tz_name)
        except pytz.UnknownTimeZoneError:
            local_tz = pytz.UTC

        check_in_local = pytz.UTC.localize(check_in_utc).astimezone(local_tz)
        check_in_weekday = str(check_in_local.weekday())  # '0'=Mon..'6'=Sun
        check_in_hour_float = check_in_local.hour + check_in_local.minute / 60.0

        # Current-day schedule lines that could contain this check-in
        today_lines = [
            s for s in calendar.attendance_ids
            if s.dayofweek == check_in_weekday
            and s.hour_from <= check_in_hour_float + 0.01
            and s.hour_to >= check_in_hour_float - 0.01
        ]

        shift_end_local = None

        if today_lines:
            line = max(today_lines, key=lambda s: s.hour_to)
            end_h = int(line.hour_to)
            end_m = int(round((line.hour_to - end_h) * 60))
            if end_h >= 24:
                end_h -= 24
                shift_end_date = check_in_local.date() + datetime.timedelta(days=1)
            else:
                shift_end_date = check_in_local.date()
            shift_end_local = local_tz.localize(datetime.datetime.combine(
                shift_end_date, datetime.time(end_h, end_m)))
        else:
            # Check-in is after all of today's shifts — likely night shift
            # rolling into next day. Look for next-day early-morning lines.
            next_weekday = str((check_in_local.weekday() + 1) % 7)
            next_day_lines = [
                s for s in calendar.attendance_ids
                if s.dayofweek == next_weekday and s.hour_from < 12
            ]
            if next_day_lines:
                line = max(next_day_lines, key=lambda s: s.hour_to)
                end_h = int(line.hour_to)
                end_m = int(round((line.hour_to - end_h) * 60))
                shift_end_local = local_tz.localize(datetime.datetime.combine(
                    check_in_local.date() + datetime.timedelta(days=1),
                    datetime.time(end_h, end_m)))

        if not shift_end_local:
            shift_end_utc = check_in_utc + datetime.timedelta(hours=default_shift_hours)
            return check_in_utc, shift_end_utc

        shift_end_utc = shift_end_local.astimezone(pytz.UTC).replace(tzinfo=None)
        if shift_end_utc <= check_in_utc:
            shift_end_utc = check_in_utc + datetime.timedelta(hours=default_shift_hours)

        return check_in_utc, shift_end_utc

    def _get_auto_close_offset(self):
        """Configurable offset (hours) added to shift end when auto-closing."""
        val = self.env['ir.config_parameter'].sudo().get_param(
            'dotbd_hr_zk_attendance_suite.auto_close_checkout_offset_hours', default='0')
        try:
            return int(val)
        except (TypeError, ValueError):
            return 0

    def _is_auto_close_enabled(self):
        """Master switch for the shift-aware auto-close feature."""
        val = self.env['ir.config_parameter'].sudo().get_param(
            'dotbd_hr_zk_attendance_suite.enable_auto_close', default='False')
        return str(val) in ('True', 'true', '1', 'yes')

    def _is_within_same_shift(self, employee, check_in_utc, candidate_punch_utc):
        """Return True if ``candidate_punch_utc`` belongs to the shift that
        started at ``check_in_utc``. The configurable auto-close offset is
        added past the shift end to accommodate punch-out variance and
        moderate overtime."""
        shift_start, shift_end = self._get_employee_shift_window(employee, check_in_utc)
        grace = datetime.timedelta(hours=self._get_auto_close_offset())
        if isinstance(candidate_punch_utc, str):
            candidate_punch_utc = fields.Datetime.from_string(candidate_punch_utc)
        if candidate_punch_utc.tzinfo is not None:
            candidate_punch_utc = candidate_punch_utc.astimezone(pytz.UTC).replace(tzinfo=None)
        return shift_start <= candidate_punch_utc <= (shift_end + grace)

    def _close_open_record_at_shift_end(self, open_record, employee):
        """Close an open hr.attendance at its shift end (from schedule) or
        check-in + default_shift_hours if schedule cannot be used.

        The configurable ``auto_close_checkout_offset_hours`` is added to the
        shift end — 0 means strict shift-end checkout, positive values give
        the employee credit for brief overtime before the auto-close runs.

        Idempotent & safe:
        - Re-fetches the record from DB before writing to catch concurrent
          updates (Odoo native cron, another worker, manual edit).
        - No-op if the record is already closed, the employee is missing, or
          the check-in is corrupted.
        - Clamps check_out to strictly after check_in so Odoo's SQL constraint
          does not raise.
        """
        if not open_record or not employee:
            return False

        # Re-fetch fresh state to avoid clobbering a concurrent write by the
        # Odoo native cron or a parallel worker.
        open_record = open_record.exists()
        if not open_record:
            return False
        fresh = open_record.sudo().read(['check_in', 'check_out'])
        if not fresh:
            return False
        current_check_in = fresh[0]['check_in']
        current_check_out = fresh[0]['check_out']

        if current_check_out:
            # Already closed (by native cron, another worker, manual edit).
            return False
        if not current_check_in:
            _logger.warning(
                "Shift-aware auto-close: attendance %s has no check_in — skipping.",
                open_record.id)
            return False

        check_in_utc = current_check_in
        if isinstance(check_in_utc, str):
            check_in_utc = fields.Datetime.from_string(check_in_utc)
        if check_in_utc.tzinfo is not None:
            check_in_utc = check_in_utc.astimezone(pytz.UTC).replace(tzinfo=None)

        _shift_start, shift_end_utc = self._get_employee_shift_window(
            employee, check_in_utc)
        offset = datetime.timedelta(hours=self._get_auto_close_offset())
        check_out_utc = shift_end_utc + offset

        # Guard: must be strictly after check_in (Odoo SQL constraint).
        min_check_out = check_in_utc + datetime.timedelta(seconds=1)
        if check_out_utc < min_check_out:
            check_out_utc = min_check_out

        open_record.sudo().write({'check_out': check_out_utc})
        _logger.warning(
            "Shift-aware auto-close: %s check-in %s -> auto check-out %s "
            "(shift_end=%s, offset=%sh)",
            employee.name, check_in_utc, check_out_utc, shift_end_utc, offset)
        return True

    def _auto_close_stale_shift(self, employee, now_utc, hr_att_sudo):
        """Close any open attendance whose shift end is already in the past.

        Used by ``auto`` and ``traditional`` modes as a drop-in replacement for
        the calendar-day-based ``_auto_close_stale_per_day`` — it respects
        night shifts and flexible schedules.

        No-op when the master switch ``enable_auto_close`` is False.
        """
        if not self._is_auto_close_enabled():
            return
        if isinstance(now_utc, str):
            now_utc = fields.Datetime.from_string(now_utc)
        if now_utc.tzinfo is not None:
            now_utc = now_utc.astimezone(pytz.UTC).replace(tzinfo=None)

        # Coexistence: if Odoo native auto_check_out would handle this employee,
        # skip to avoid two different formulas writing different check_out times.
        company = employee.company_id
        calendar = self._get_employee_resource_calendar(employee)
        is_flexible = bool(
            calendar and (
                getattr(calendar, 'flexible_hours', False)
                or getattr(calendar, 'flexible', False)
            )
        )
        if (company and getattr(company, 'auto_check_out', False)
                and calendar and not is_flexible):
            return

        open_records = hr_att_sudo.search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False),
        ], order='check_in asc')

        for rec in open_records:
            check_in_utc = rec.check_in
            if isinstance(check_in_utc, str):
                check_in_utc = fields.Datetime.from_string(check_in_utc)
            if not self._is_within_same_shift(employee, check_in_utc, now_utc):
                self._close_open_record_at_shift_end(rec, employee)

    def _auto_close_stale_per_day(self, employee, day_start_utc, hr_att_sudo):
        """Close any open attendance records from previous days at 23:59:59."""
        stale = hr_att_sudo.search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False),
            ('check_in', '<', day_start_utc),
        ])
        tz_str = self._get_device_timezone()
        try:
            local_tz = pytz.timezone(tz_str)
        except pytz.UnknownTimeZoneError:
            local_tz = pytz.UTC

        for rec in stale:
            # Close at 23:59:59 of the check-in's local date
            # rec.check_in is a naive UTC datetime (Odoo convention)
            checkin_naive = rec.check_in
            
            # CRITICAL FIX: checkin_naive is already UTC (naive), don't localize it again!
            # Just treat it as UTC directly for conversion to local timezone
            checkin_aware_utc = pytz.UTC.localize(checkin_naive)
            checkin_local = checkin_aware_utc.astimezone(local_tz)
            
            eod_local = local_tz.localize(
                datetime.datetime.combine(checkin_local.date(), datetime.time(23, 59, 59)))
            eod_utc = eod_local.astimezone(pytz.UTC).replace(tzinfo=None)
            rec.write({'check_out': eod_utc})
            _logger.warning(
                f"Per-Day mode: Auto-closed stale attendance for {employee.name} "
                f"(check-in: {rec.check_in}, auto check-out: {eod_utc})")

    def _process_auto_per_day_attendance(self, employee, atten_time, hr_attendance):
        """Auto Per Day: first punch of the day = check-in,
        every subsequent punch updates check-out.
        Result: one hr.attendance per employee per day."""
        hr_att_sudo = hr_attendance.sudo()

        day_start_utc, day_end_utc, local_tz = self._get_day_boundaries_utc(atten_time)

        # Auto-close any open attendance from previous days
        self._auto_close_stale_per_day(employee, day_start_utc, hr_att_sudo)

        # Find today's attendance for this employee
        today_att = hr_att_sudo.search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', day_start_utc),
            ('check_in', '<=', day_end_utc),
        ], order='check_in asc', limit=1)

        if not today_att:
            # First punch of the day -> create check-in
            new_rec = hr_att_sudo.create({
                'employee_id': employee.id,
                'check_in': atten_time,
            })
            _logger.info(f"Auto Per Day: Check-in created for {employee.name} at {atten_time}")
            return new_rec
        else:
            # Subsequent punch -> update check-out (last punch wins)
            # Guard: check_out must be after check_in (Odoo constraint)
            if isinstance(atten_time, str):
                atten_dt = fields.Datetime.from_string(atten_time)
            else:
                atten_dt = atten_time
            check_in_dt = fields.Datetime.from_string(today_att.check_in) \
                if isinstance(today_att.check_in, str) else today_att.check_in
            if atten_dt <= check_in_dt:
                _logger.warning(
                    f"Auto Per Day: punch {atten_dt} is not after check-in "
                    f"{check_in_dt} for {employee.name} — skipping")
            else:
                today_att.write({'check_out': atten_time})
                _logger.info(f"Auto Per Day: Check-out updated for {employee.name} at {atten_time}")
                return today_att

    def _process_traditional_per_day_attendance(self, employee, atten_time, punch_type, hr_attendance):
        """Traditional Per Day: uses device punch type but only one check-in
        and one check-out per employee per day."""
        hr_att_sudo = hr_attendance.sudo()

        day_start_utc, day_end_utc, local_tz = self._get_day_boundaries_utc(atten_time)

        # Auto-close any open attendance from previous days
        self._auto_close_stale_per_day(employee, day_start_utc, hr_att_sudo)

        # Find today's attendance
        today_att = hr_att_sudo.search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', day_start_utc),
            ('check_in', '<=', day_end_utc),
        ], order='check_in asc', limit=1)

        if punch_type == 0:  # check-in from device
            if not today_att:
                new_rec = hr_att_sudo.create({
                    'employee_id': employee.id,
                    'check_in': atten_time,
                })
                _logger.info(f"Traditional Per Day: Check-in created for {employee.name}")
                return new_rec
            else:
                _logger.info(
                    f"Traditional Per Day: Check-in already exists for {employee.name} today - skipping")
                return today_att
        elif punch_type == 1:  # check-out from device
            if today_att and not today_att.check_out:
                # Guard: check_out must be after check_in (Odoo constraint)
                if isinstance(atten_time, str):
                    atten_dt = fields.Datetime.from_string(atten_time)
                else:
                    atten_dt = atten_time
                check_in_dt = fields.Datetime.from_string(today_att.check_in) \
                    if isinstance(today_att.check_in, str) else today_att.check_in
                if atten_dt <= check_in_dt:
                    _logger.warning(
                        f"Traditional Per Day: check-out {atten_dt} is not after "
                        f"check-in {check_in_dt} for {employee.name} — skipping")
                else:
                    today_att.write({'check_out': atten_time})
                    _logger.info(f"Traditional Per Day: Check-out added for {employee.name}")
                    return today_att
            elif today_att and today_att.check_out:
                _logger.info(
                    f"Traditional Per Day: Check-out already recorded for {employee.name} today - skipping")
                return today_att
            else:
                _logger.warning(
                    f"Traditional Per Day: No check-in today for {employee.name} - cannot add check-out")

    _DOWNLOAD_FLAG_KEY = 'attendance.device.download.running'

    def _set_download_flag(self, running):
        """Set or clear the cron-download in-progress flag.

        Uses a separate cursor committed immediately so the flag is visible
        to any concurrent HTTP request (e.g. button click status check).
        """
        db = self.env.cr.dbname
        uid = self.env.uid
        value = datetime.datetime.now().isoformat() if running else ''
        with odoo_registry(db).cursor() as cr:
            env2 = api.Environment(cr, uid, self.env.context)
            env2['ir.config_parameter'].set_param(self._DOWNLOAD_FLAG_KEY, value)
            cr.commit()

    @api.model
    def _is_download_running(self):
        """Return True if a cron download is currently in progress (and not stale)."""
        val = self.env['ir.config_parameter'].sudo().get_param(
            self._DOWNLOAD_FLAG_KEY, '')
        if not val:
            return False
        try:
            ts = datetime.datetime.fromisoformat(val)
            if (datetime.datetime.now() - ts).total_seconds() > 1800:
                # Stale flag — server likely restarted mid-download; clear it
                self.env['ir.config_parameter'].sudo().set_param(
                    self._DOWNLOAD_FLAG_KEY, '')
                return False
        except Exception:
            return False
        return True

    def _process_attendance_from_list(self, attendance, users, download_mode='smart'):
        """Process attendance from pre-fetched list (used by download wizard).
        Returns dict with statistics for display in wizard."""
        self.ensure_one()
        info = self
        
        # Reuse existing download logic but return stats
        start_time = __import__('time').time()
        device_log = self.env['biometric.device.log']
        zk_attendance = self.env['zk.machine.attendance']
        hr_attendance = self.env['hr.attendance']
        device_password = info._get_device_password()
        machine_ip = info.device_ip or ''
        zk_port = info.port_number or 4370
        attendance_mode = info.attendance_mode or 'traditional'
        duplicate_threshold = info.duplicate_threshold or 5

        # Get timezone for conversion
        device_tz_str = info._get_device_timezone()
        try:
            local_tz = pytz.timezone(device_tz_str)
        except pytz.UnknownTimeZoneError:
            local_tz = pytz.UTC

        # Filter by download mode
        since_dt = None
        _now_utc = datetime.datetime.utcnow()
        if download_mode == 'today':
            since_dt = _now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        elif download_mode == 'weekly':
            _days_since_monday = _now_utc.weekday()
            since_dt = (_now_utc - datetime.timedelta(days=_days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0)
        elif download_mode == 'current_month':
            since_dt = _now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif download_mode == 'smart':
            _has_records = self.env['zk.machine.attendance'].sudo().search_count(
                [('device_id', '=', info.id)], limit=1)
            if _has_records:
                since_dt = _now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        if since_dt and attendance:
            _since_local = pytz.utc.localize(since_dt).astimezone(local_tz).replace(tzinfo=None)
            attendance = [a for a in attendance if a.timestamp >= _since_local]

        if not attendance:
            return {'records_found': 0, 'records_new': 0, 'records_duplicate': 0, 'records_failed': 0}

        # Build lookup maps
        user_map = {u.user_id: u for u in users} if users else {}
        _emp_recs = self.env['hr.employee'].sudo().search([
            ('device_id_num', '!=', False),
            ('company_id', '=', info.company_id.id)
        ])
        emp_map = {emp.device_id_num: emp for emp in _emp_recs}

        # Track statistics
        records_new = 0
        records_duplicate = 0
        records_failed = 0

        # Process each attendance record
        for each in attendance:
            try:
                with self.env.cr.savepoint():
                    atten_time = each.timestamp
                    
                    # Timezone conversion
                    try:
                        local_dt = local_tz.localize(atten_time, is_dst=None)
                        utc_dt = local_dt.astimezone(pytz.utc)
                    except pytz.exceptions.NonExistentTimeError:
                        local_dt = local_tz.localize(atten_time, is_dst=False)
                        utc_dt = local_dt.astimezone(pytz.utc)
                    except pytz.exceptions.AmbiguousTimeError:
                        local_dt = local_tz.localize(atten_time, is_dst=True)
                        utc_dt = local_dt.astimezone(pytz.utc)
                    
                    atten_time_str = fields.Datetime.to_string(utc_dt)

                    uid_match = user_map.get(each.user_id)
                    if not uid_match:
                        records_failed += 1
                        continue

                    get_user_id = emp_map.get(each.user_id)
                    if not get_user_id:
                        records_failed += 1
                        continue

                    # Check duplicates
                    existing = zk_attendance.search([
                        ('device_id_num', '=', each.user_id),
                        ('punching_time', '=', atten_time_str),
                    ], limit=1)
                    if existing:
                        records_duplicate += 1
                        continue

                    # Create raw attendance
                    zk_attendance.create({
                        'employee_id': get_user_id.id,
                        'device_id': info.id,
                        'device_id_num': each.user_id,
                        'attendance_type': self.env['zk.machine.attendance']._sanitize_attendance_type(each.status),
                        'punch_type': self.env['zk.machine.attendance']._sanitize_punch_type(each.punch),
                        'punching_time': atten_time_str,
                        'address_id': info.address_id.id if info.address_id else False,
                    })

                    # Process hr.attendance based on mode
                    try:
                        with self.env.cr.savepoint():
                            if attendance_mode == 'auto':
                                info._process_auto_attendance(get_user_id, atten_time_str, hr_attendance)
                            elif attendance_mode == 'auto_per_day':
                                info._process_auto_per_day_attendance(get_user_id, atten_time_str, hr_attendance)
                            elif attendance_mode == 'traditional_per_day':
                                info._process_traditional_per_day_attendance(get_user_id, atten_time_str, each.punch, hr_attendance)
                            else:
                                info._process_traditional_attendance(get_user_id, atten_time_str, each.punch, hr_attendance)
                    except Exception as hr_err:
                        _logger.warning("Wizard: HR Processing failed, but Raw Punch stored: %s", hr_err)

                    records_new += 1

            except Exception as rec_error:
                records_failed += 1
                _logger.error(f"Error processing record: {str(rec_error)}")

        # Create log entry
        elapsed = __import__('time').time() - start_time
        device_log.create({
            'device_id': info.id,
            'log_type': 'download',
            'status': 'success' if records_failed == 0 else 'warning',
            'records_found': len(attendance),
            'records_new': records_new,
            'records_duplicate': records_duplicate,
            'records_failed': records_failed,
            'duration': elapsed,
            'details': f"Wizard download. Mode: {download_mode}",
        })
        info.last_download_time = fields.Datetime.now()

        return {
            'records_found': len(attendance),
            'records_new': records_new,
            'records_duplicate': records_duplicate,
            'records_failed': records_failed,
        }

    @api.model
    def cron_download(self):
        """Cron method for downloading attendance from all devices.

        Each device uses its own ``cron_download_mode`` setting so admins can
        tune the load per device independently.

        Multi-database safety: when the same physical device IP is configured in
        more than one database, multiple cron instances could attempt a simultaneous
        TCP connection to port 4370, causing conflicts and duplicate records.
        A PostgreSQL session-level advisory lock keyed on the device IP prevents
        this — only one database wins the lock and downloads; others skip silently.
        The lock is released automatically when this database's session ends.
        """
        import zlib as _zlib
        machines = self.env['biometric.device.details'].search([
            ('connection_mode', 'in', ['direct', 'hybrid']),
        ])
        if not machines:
            return
        self._set_download_flag(True)
        try:
            for machine in machines:
                if not machine.device_ip:
                    continue
                # Compute a stable cross-process lock key from the device IP.
                # zlib.crc32 is stable across processes (unlike Python's hash()).
                lock_key = _zlib.crc32(
                    f'pyzk_device_{machine.device_ip}_{machine.port_number}'.encode()
                ) & 0x7FFFFFFF
                self.env.cr.execute(
                    "SELECT pg_try_advisory_lock(%s)", (lock_key,))
                got_lock = self.env.cr.fetchone()[0]
                if not got_lock:
                    _logger.info(
                        "Cron download: skipping device '%s' (%s) — another database "
                        "is already downloading from this device.",
                        machine.name, machine.device_ip)
                    continue
                try:
                    mode = machine.cron_download_mode or 'all'
                    machine.action_download_attendance(download_mode=mode)
                except Exception as e:
                    _logger.error(
                        "Cron download failed for device %s: %s", machine.name, e)
                finally:
                    self.env.cr.execute(
                        "SELECT pg_advisory_unlock(%s)", (lock_key,))
        finally:
            self._set_download_flag(False)

    @api.model
    def cron_auto_close_stale_attendance(self):
        """Sweep open hr.attendance records whose shift window has ended but
        check_out is still missing, and close them at the shift end.

        Only records older than ``max_open_attendance_hours`` (default 18h) are
        considered — leaves ongoing shifts alone. Shift end is derived from the
        employee's resource.calendar when available (night-shift safe), else
        falls back to check_in + default_shift_hours.

        Safe to run hourly; idempotent — records already closed are skipped.
        """
        helper = self.env['biometric.device.details']
        if not helper._is_auto_close_enabled():
            _logger.info("Auto-Close Stale Attendance: master switch is OFF — skipping.")
            return

        ICP = self.env['ir.config_parameter'].sudo()
        max_open_hours = int(ICP.get_param(
            'dotbd_hr_zk_attendance_suite.max_open_attendance_hours', default=18))
        # Safety-net threshold: if Odoo native was supposed to handle a record
        # but didn't, we step in after this many hours. 0 = disabled (always defer).
        native_fallback_hours = int(ICP.get_param(
            'dotbd_hr_zk_attendance_suite.native_fallback_hours', default=36))

        now = fields.Datetime.now()
        cutoff = now - datetime.timedelta(hours=max_open_hours)
        stale = self.env['hr.attendance'].sudo().search([
            ('check_out', '=', False),
            ('check_in', '<', cutoff),
        ])
        if not stale:
            return

        closed = 0
        closed_as_safety_net = 0
        skipped_native = 0

        for rec in stale:
            # ── Coexistence with Odoo native `_cron_auto_check_out` ──────────
            # Odoo's built-in auto-checkout (res.company.auto_check_out) runs
            # on its own cron and explicitly handles employees with a
            # non-flexible resource.calendar. Two-tier handling:
            #
            #   1. Normal: skip these records, let Odoo handle them.
            #   2. Safety net: if the record is STILL open after
            #      ``native_fallback_hours`` past check-in, we assume native
            #      missed it (cron failure / manual edit / schedule flipped
            #      flexible→fixed mid-shift) and close it ourselves using the
            #      current work schedule.
            employee = rec.employee_id
            company = employee.company_id
            calendar = helper._get_employee_resource_calendar(employee)
            is_flexible = bool(
                calendar and (
                    getattr(calendar, 'flexible_hours', False)
                    or getattr(calendar, 'flexible', False)
                )
            )
            native_would_handle = bool(
                company and getattr(company, 'auto_check_out', False)
                and calendar and not is_flexible
            )

            if native_would_handle:
                check_in_dt = rec.check_in
                if isinstance(check_in_dt, str):
                    check_in_dt = fields.Datetime.from_string(check_in_dt)
                open_age_hours = (now - check_in_dt).total_seconds() / 3600.0
                if native_fallback_hours <= 0 or open_age_hours < native_fallback_hours:
                    # Still within native's reasonable window — let Odoo handle.
                    skipped_native += 1
                    continue
                # Fall-through: safety-net kicks in.
                try:
                    helper._close_open_record_at_shift_end(rec, employee)
                    closed_as_safety_net += 1
                    _logger.warning(
                        "Auto-Close SAFETY NET: attendance %s for %s was "
                        "open %.1fh (> %sh) and Odoo native didn't close it. "
                        "Closed via shift-aware fallback.",
                        rec.id, employee.name, open_age_hours, native_fallback_hours)
                except Exception as e:
                    _logger.warning(
                        "Auto-close SAFETY NET failed for attendance %s: %s",
                        rec.id, e)
                continue

            try:
                helper._close_open_record_at_shift_end(rec, employee)
                closed += 1
            except Exception as e:
                _logger.warning(
                    "Auto-close stale attendance failed for attendance %s: %s",
                    rec.id, e)

        if closed or skipped_native or closed_as_safety_net:
            _logger.info(
                "Auto-Close Stale Attendance: closed %s record(s) older than %sh; "
                "closed %s record(s) as safety-net (native missed); "
                "skipped %s record(s) currently handled by Odoo native.",
                closed, max_open_hours, closed_as_safety_net, skipped_native)

    @api.model
    def cron_refresh_device_info(self):
        """Cron method for refreshing device information"""
        devices = self.search([('connection_mode', 'in', ['direct', 'hybrid'])])
        for device in devices:
            try:
                device.action_refresh_device_info()
            except Exception as e:
                _logger.error(f"Failed to refresh device info for {device.name}: {str(e)}")

    def _safe_get_attendance(self, conn):
        """Download attendance from device, skipping corrupted records.

        pyzk's get_attendance() calls __decode_time() which can throw
        ValueError if the device has corrupted binary records
        (e.g., day=31 in a 30-day month, month=0, etc.).

        This method patches the decode function to return None for invalid
        records, then filters them out.
        """
        import struct
        from collections import namedtuple

        _logger.info("Device %s: Using safe attendance download (skipping corrupted records)", self.name)

        skipped = 0

        def safe_decode_time(t):
            """Safely decode pyzk's packed timestamp."""
            try:
                d = (
                    ((t[0] >> 1) & 0x3F) + 2000,  # year
                    ((t[0] << 3 | t[1] >> 5) & 0x0F),  # month
                    t[1] & 0x1F,  # day
                    t[2] & 0x1F,  # hour
                    t[3] & 0x3F,  # minute
                    t[4] & 0x3F,  # second
                )
                import datetime as dt_mod
                return dt_mod.datetime(*d)
            except (ValueError, OverflowError) as e:
                _logger.warning("Device %s: Skipping corrupted timestamp bytes=%s: %s",
                                self.name, t.hex() if hasattr(t, 'hex') else t, e)
                return None

        # Monkey-patch pyzk's __decode_time to skip corrupted records
        # instead of raising ValueError and aborting the entire download.
        import datetime as dt_mod
        try:
            import zk.base as zk_base          # pyzk
        except ImportError:
            import pyzk2.base as zk_base        # pyzk2 fork

        _original_decode_time = zk_base.ZK._ZK__decode_time

        def _patched_decode_time(self_zk, t):
            try:
                return _original_decode_time(self_zk, t)
            except (ValueError, OverflowError):
                # Return a sentinel date — filtered out after download
                return dt_mod.datetime(2000, 1, 1, 0, 0, 0)

        zk_base.ZK._ZK__decode_time = _patched_decode_time
        try:
            attendance = conn.get_attendance()
        except Exception as e:
            _logger.warning("Device %s: get_attendance() failed even with patch: %s. Returning empty list.", self.name, e)
            return []
        finally:
            # Always restore the original method
            zk_base.ZK._ZK__decode_time = _original_decode_time

        # Filter out the sentinel year-2000 records produced by corrupted timestamps
        before = len(attendance)
        attendance = [a for a in attendance if a.timestamp.year >= 2010]
        if before != len(attendance):
            _logger.info("Device %s: Safe download filtered %d corrupted records, %d valid remain",
                         self.name, before - len(attendance), len(attendance))

        _logger.info("Device %s: Safe download complete — %d valid records, %d skipped",
                     self.name, len(attendance), skipped)
        return attendance

    def action_download_attendance(self, download_mode='smart'):
        """Download attendance records from the device with per-device logging.

        download_mode:
            'smart'         — First install (no records) → all; subsequent → current month
            'all'           — Full historical download, no date filter
            'current_month' — Records from 1st of current month only
            'today'         — Records from today only
        """
        _logger.info("++++++++++++Download Attendance Executed [mode=%s]++++++++++++++++++++++", download_mode)
        zk_attendance = self.env['zk.machine.attendance']
        hr_attendance = self.env['hr.attendance']
        device_log = self.env['biometric.device.log'].sudo()

        for info in self:
            start_time = _time.time()
            records_found = 0
            records_new = 0
            records_duplicate = 0
            records_failed = 0
            employees_not_found = 0
            log_details = []

            machine_ip = info.device_ip
            zk_port = info.port_number
            device_password = info._get_device_password()
            attendance_mode = info.attendance_mode or 'traditional'
            duplicate_threshold = info.duplicate_threshold or 5
            
            try:
                zk = ZK(machine_ip, port=zk_port, timeout=15,
                        password=device_password,
                        force_udp=False, ommit_ping=True)
            except NameError:
                device_log.create({
                    'device_id': info.id,
                    'log_type': 'download',
                    'status': 'failed',
                    'error_message': 'pyzk module not found. Install with: pip3 install pyzk',
                })
                raise UserError(
                    _("Pyzk module not Found. Please install it with 'pip3 install pyzk'."))

            conn = info.device_connect(zk)
            if not conn:
                device_log.create({
                    'device_id': info.id,
                    'log_type': 'download',
                    'status': 'failed',
                    'duration': _time.time() - start_time,
                    'error_message': f'Unable to connect to device {info.name} ({machine_ip}:{zk_port})',
                    'details': 'Connection refused. Check: IP address, port, network, device power.',
                })
                if len(self) == 1:
                    raise UserError(_('Unable to connect, please check parameters'))
                else:
                    continue


            try:
                conn.disable_device()

                # Resolve device timezone for timestamp conversion (do NOT change device clock during download)
                device_tz_str = info._get_device_timezone()
                try:
                    with self.env.cr.savepoint():
                        info.write({'effective_timezone': device_tz_str})
                except Exception as _tz_err:
                    _logger.warning("Device %s: could not persist effective_timezone: %s", info.name, _tz_err)
                
                # ⚠️ TIMEZONE MISMATCH WARNING
                # Check if configured timezone matches effective device timezone
                if info.time_sync_method == 'custom' and info.custom_timezone:
                    if info.custom_timezone != device_tz_str:
                        _logger.warning(
                            "Device %s: TIMEZONE MISMATCH! Configured=%s, Effective=%s. "
                            "This will cause incorrect attendance times! Click 'Sync Time' button to fix.",
                            info.name, info.custom_timezone, device_tz_str)
                        device_log.create({
                            'device_id': info.id,
                            'log_type': 'download',
                            'status': 'warning',
                            'error_message': f'Timezone mismatch: Configured={info.custom_timezone}, Device={device_tz_str}',
                            'details': f'The device clock is running in {device_tz_str} but configured for {info.custom_timezone}. '
                                       f'This will cause attendance times to be wrong! Please click "Sync Time" button to fix.',
                        })
                try:
                    local_tz = pytz.timezone(device_tz_str)
                except pytz.UnknownTimeZoneError:
                    local_tz = pytz.UTC

                # ── Determine download cutoff (UTC naive) ────────────────────
                since_dt = None  # None = no filter (download all)
                _now_utc = datetime.datetime.utcnow()
                if download_mode == 'today':
                    since_dt = _now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
                elif download_mode == 'weekly':
                    _days_since_monday = _now_utc.weekday()  # Monday=0, Sunday=6
                    since_dt = (_now_utc - datetime.timedelta(days=_days_since_monday)).replace(
                        hour=0, minute=0, second=0, microsecond=0)
                elif download_mode == 'current_month':
                    since_dt = _now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                elif download_mode == 'smart':
                    _has_records = self.env['zk.machine.attendance'].sudo().search_count(
                        [('device_id', '=', info.id)], limit=1)
                    if _has_records:
                        since_dt = _now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    else:
                        _logger.info("Device %s: first install detected — downloading all records", info.name)
                # 'all' → since_dt stays None

                user = conn.get_users()
                try:
                    attendance = conn.get_attendance()
                except ValueError as ve:
                    _logger.warning(
                        "Device %s: get_attendance() ValueError: %s — using safe fallback",
                        info.name, ve)
                    attendance = info._safe_get_attendance(conn)

                # ── Filter attendance list by since_dt ───────────────────────
                if since_dt and attendance:
                    _since_local = pytz.utc.localize(since_dt).astimezone(local_tz).replace(tzinfo=None)
                    _before = len(attendance)
                    attendance = [a for a in attendance if a.timestamp >= _since_local]
                    _logger.info(
                        "Device %s: date filter [%s] reduced %d → %d records (since %s UTC / %s local)",
                        info.name, download_mode, _before, len(attendance), since_dt, _since_local
                    )

                # Sort by user_id so all transactions acquire per-employee advisory locks
                # in the same order, eliminating deadlock cycles across concurrent device downloads.
                if attendance:
                    attendance = sorted(attendance, key=lambda a: a.user_id)

                if not attendance:
                    device_log.create({
                        'device_id': info.id,
                        'log_type': 'download',
                        'status': 'warning',
                        'records_found': 0,
                        'records_new': 0,
                        'duration': _time.time() - start_time,
                        'details': 'Connected successfully but no attendance records found on device.',
                    })
                    conn.disconnect()
                    info.last_download_time = fields.Datetime.now()
                    return True

                records_found = len(attendance)
                # Build user lookup dict for faster matching
                user_map = {u.user_id: u for u in user} if user else {}

                # Pre-load employee map (one query)
                _emp_recs = self.env['hr.employee'].sudo().search([
                    ('device_id_num', '!=', False),
                    ('company_id', '=', info.company_id.id)
                ])
                emp_map = {emp.device_id_num: emp for emp in _emp_recs}

                # Pre-load existing punches for this device (one query)
                # Scope to since_dt window so the in-memory set stays small
                _existing_domain = [('device_id', '=', info.id)]
                if since_dt:
                    _existing_domain.append(
                        ('punching_time', '>=', fields.Datetime.to_string(since_dt)))
                _existing_raw = self.env['zk.machine.attendance'].sudo().search_read(
                    _existing_domain,
                    ['device_id_num', 'punching_time']
                )
                _punch_exact = {(r['device_id_num'], r['punching_time'].replace(tzinfo=None) if hasattr(r['punching_time'], 'tzinfo') and r['punching_time'].tzinfo else r['punching_time']) for r in _existing_raw}
                _punch_windows = defaultdict(list)
                for r in _existing_raw:
                    pt = r['punching_time'].replace(tzinfo=None) if hasattr(r['punching_time'], 'tzinfo') and r['punching_time'].tzinfo else r['punching_time']
                    _punch_windows[r['device_id_num']].append(pt)
                for uid in _punch_windows:
                    _punch_windows[uid].sort()
                _td = timedelta(seconds=10)

                _invalid_year_ids = set()   # track IDs with bad timestamps (batched log)
                _unrecognized_ids = set()   # track unrecognized user IDs (batched log)

                for each in attendance:
                    try:
                        with self.env.cr.savepoint():
                            atten_time = each.timestamp

                            # ── Sanity check: reject timestamps from before 2010 ──
                            # ZKTeco devices with a dead RTC battery reset to Jan 1,
                            # 2000.  Importing those records pollutes the DB and
                            # confuses attendance sheets.  Skip and batch-log them.
                            if atten_time.year < 2010:
                                _invalid_year_ids.add(each.user_id)
                                employees_not_found += 1
                                continue

                            # ═══════════════════════════════════════════════════════
                            # CRITICAL TIMEZONE CONVERSION FIX
                            # ═══════════════════════════════════════════════════════
                            # The pyzk library returns naive datetimes from the device.
                            # The device clock shows LOCAL time (e.g., Beirut UTC+3).
                            # We must convert local time → UTC for storage in Odoo.
                            #
                            # IMPORTANT: Handle DST transitions (e.g., Beirut, Europe)
                            # where clocks spring forward or fall back.
                            # ═══════════════════════════════════════════════════════

                            try:
                                # Treat naive timestamp as device local time
                                local_dt = local_tz.localize(atten_time, is_dst=None)
                                utc_dt = local_dt.astimezone(pytz.utc)
                            except pytz.exceptions.NonExistentTimeError:
                                # DST gap (e.g., spring forward: 2:00 AM → 3:00 AM)
                                # The local time doesn't exist. Use pre-transition offset.
                                _logger.warning(
                                    "Device %s: Non-existent time %s during DST spring-forward, "
                                    "adjusting to standard time (pre-transition offset)",
                                    info.name, atten_time)
                                local_dt = local_tz.localize(atten_time, is_dst=False)
                                utc_dt = local_dt.astimezone(pytz.utc)
                            except pytz.exceptions.AmbiguousTimeError:
                                # DST overlap (e.g., fall back: 2:00 AM occurs twice)
                                # Use the first occurrence (pre-transition, DST=True)
                                _logger.warning(
                                    "Device %s: Ambiguous time %s during DST fall-back, "
                                    "using first occurrence (DST=True)",
                                    info.name, atten_time)
                                local_dt = local_tz.localize(atten_time, is_dst=True)
                                utc_dt = local_dt.astimezone(pytz.utc)

                            # Store as naive UTC (Odoo convention)
                            atten_time_dt = utc_dt
                            atten_time_str = fields.Datetime.to_string(utc_dt)

                            uid_match = user_map.get(each.user_id)
                            if not uid_match:
                                employees_not_found += 1
                                _unrecognized_ids.add(each.user_id)
                                continue

                            # Use pre-loaded employee map instead of per-record search
                            get_user_id = emp_map.get(each.user_id)

                            if get_user_id:
                                # In-memory exact duplicate check
                                naive_utc = utc_dt.replace(tzinfo=None) if utc_dt.tzinfo else utc_dt
                                if (each.user_id, naive_utc) in _punch_exact:
                                    records_duplicate += 1
                                    continue
    
                                # In-memory time-window duplicate check
                                _uid_punches = _punch_windows.get(each.user_id, [])
                                if _uid_punches:
                                    _idx = bisect.bisect_left(_uid_punches, naive_utc)
                                    _dup_found = False
                                    for _ci in (_idx - 1, _idx):
                                        if 0 <= _ci < len(_uid_punches):
                                            if abs((_uid_punches[_ci] - naive_utc).total_seconds()) <= duplicate_threshold:
                                                _dup_found = True
                                                break
                                    if _dup_found:
                                        records_duplicate += 1
                                        continue

                                # Serialize concurrent writes for the same employee across
                                # all devices — prevents "deadlock detected" and
                                # "could not serialize access due to concurrent update".
                                self.env.cr.execute(
                                    "SELECT pg_advisory_xact_lock(%s)",
                                    (get_user_id.id & 0x7FFFFFFF,))
                                zk_record = zk_attendance.create({
                                    'employee_id': get_user_id.id,
                                    'device_id': info.id,
                                    'device_id_num': each.user_id,
                                    'attendance_type': ZkMachineAttendance._sanitize_attendance_type(each.status),
                                    'punch_type': ZkMachineAttendance._sanitize_punch_type(each.punch),
                                    'punching_time': atten_time_str,
                                    'address_id': info.address_id.id
                                })
    
                                # Handle stale attendance (open > 24 hours)
                                att_var = hr_attendance.sudo().search([
                                    ('employee_id', '=', get_user_id.id),
                                    ('check_out', '=', False)
                                ])
    
                                if att_var:
                                    for old_att in att_var:
                                        # old_att.check_in is naive UTC (Odoo convention)
                                        checkin_naive = old_att.check_in
                                        checkin_utc_aware = pytz.UTC.localize(checkin_naive)
                                        # atten_time_dt may be aware or naive; normalise to aware UTC
                                        if atten_time_dt.tzinfo is None:
                                            cur_utc_aware = pytz.UTC.localize(atten_time_dt)
                                        else:
                                            cur_utc_aware = atten_time_dt.astimezone(pytz.UTC)
                                        hours_open = (cur_utc_aware - checkin_utc_aware).total_seconds() / 3600.0

                                        if hours_open > 24:
                                            # Convert check-in UTC → local to get the correct LOCAL date
                                            checkin_local = checkin_utc_aware.astimezone(local_tz)
                                            eod_local = local_tz.localize(
                                                datetime.datetime.combine(
                                                    checkin_local.date(),
                                                    datetime.time(23, 59, 59)))
                                            auto_checkout_naive = eod_local.astimezone(pytz.UTC).replace(tzinfo=None)
                                            old_att.sudo().write({'check_out': auto_checkout_naive})
                                            _logger.warning(
                                                f"Auto-closed stale attendance for {get_user_id.name} "
                                                f"(check-in: {checkin_naive}, auto check-out: {auto_checkout_naive})"
                                            )
    
                                # Wrap HR processing in a nested savepoint so if Odoo's rigid HR Attendance validation
                                # fails (e.g. Check Out earlier than Check In), we DON'T lose the raw zk_record!
                                try:
                                    with self.env.cr.savepoint():
                                        if attendance_mode == 'auto':
                                            hr_att = info._process_auto_attendance(get_user_id, atten_time_str, hr_attendance)
                                        elif attendance_mode == 'auto_per_day':
                                            hr_att = info._process_auto_per_day_attendance(get_user_id, atten_time_str, hr_attendance)
                                        elif attendance_mode == 'traditional_per_day':
                                            hr_att = info._process_traditional_per_day_attendance(get_user_id, atten_time_str, each.punch, hr_attendance)
                                        else:
                                            hr_att = info._process_traditional_attendance(get_user_id, atten_time_str, each.punch, hr_attendance)
                                        # Link the raw punch to the hr.attendance record so
                                        # Management view (zk.machine.attendance) and Overview
                                        # (hr.attendance) show the same data.
                                        if hr_att:
                                            zk_record.write({'hr_attendance_id': hr_att.id, 'processed': True})
                                except Exception as hr_err:
                                    _logger.warning("Cron Pull: HR Processing failed, but Raw Punch stored: %s", hr_err)

                                records_new += 1
                                # Update in-memory duplicate sets
                                _punch_exact.add((each.user_id, naive_utc))
                                bisect.insort(_punch_windows.setdefault(each.user_id, []), naive_utc)
                            else:
                                device_log.create({
                                    'device_id': info.id,
                                    'log_type': 'download',
                                    'status': 'warning',
                                    'error_message': f'Unknown Device User: {uid_match.name} (ID: {each.user_id})',
                                    'details': f'An attendance record was found for an unmapped device user. A new hr.employee record was auto-created to store this attendance.',
                                })
                                # Create new employee from device user under the device's company
                                employee = self.env['hr.employee'].sudo().with_company(info.company_id).create({
                                    'device_id_num': each.user_id,
                                    'name': uid_match.name,
                                    'company_id': info.company_id.id,
                                })
                                self.env.cr.execute(
                                    "SELECT pg_advisory_xact_lock(%s)",
                                    (employee.id & 0x7FFFFFFF,))
                                zk_record = zk_attendance.create({
                                    'employee_id': employee.id,
                                    'device_id': info.id,
                                    'device_id_num': each.user_id,
                                    'attendance_type': ZkMachineAttendance._sanitize_attendance_type(each.status),
                                    'punch_type': ZkMachineAttendance._sanitize_punch_type(each.punch),
                                    'punching_time': atten_time_str,
                                    'address_id': info.address_id.id
                                })
                                new_attendance = hr_attendance.create({
                                    'employee_id': employee.id,
                                    'check_in': atten_time_str
                                })
                                zk_record.write({
                                    'hr_attendance_id': new_attendance.id,
                                    'processed': True
                                })
                                records_new += 1
                                # Update in-memory duplicate sets and employee map
                                _punch_exact.add((each.user_id, naive_utc))
                                bisect.insort(_punch_windows.setdefault(each.user_id, []), naive_utc)
                                emp_map[each.user_id] = employee
                                log_details.append(f"New employee created: {uid_match.name} (Device ID: {each.user_id})")
    
                    except Exception as rec_error:
                        records_failed += 1
                        log_details.append(f"Failed record: User={each.user_id}, Time={each.timestamp}, Error={str(rec_error)}")
                        _logger.error(f"Error processing record from {info.name}: {str(rec_error)}")

                # ── Batched warning logs (one entry per issue type, not per record) ──
                if _invalid_year_ids:
                    device_log.create({
                        'device_id': info.id,
                        'log_type': 'download',
                        'status': 'warning',
                        'error_message': f'Skipped {len(_invalid_year_ids)} records with invalid timestamps (year < 2010)',
                        'details': (
                            'These records likely came from a device with a dead RTC battery '
                            '(clock reset to Jan 1, 2000). Please replace the device battery and '
                            'reset the device clock.\n'
                            f'Affected User IDs: {sorted(_invalid_year_ids)}'
                        ),
                    })
                if _unrecognized_ids:
                    device_log.create({
                        'device_id': info.id,
                        'log_type': 'download',
                        'status': 'warning',
                        'error_message': f'Skipped records for {len(_unrecognized_ids)} unrecognized User ID(s)',
                        'details': (
                            'These User IDs exist in attendance log but are not enrolled on the device '
                            '(not returned by get_users()). Records were skipped.\n'
                            f'Unrecognized IDs: {sorted(_unrecognized_ids)}'
                        ),
                    })

                elapsed = _time.time() - start_time
                info.last_download_time = fields.Datetime.now()

                # Determine log status
                if records_failed > 0 and records_new == 0:
                    log_status = 'failed'
                elif records_failed > 0:
                    log_status = 'warning'
                else:
                    log_status = 'success'

                details_text = (
                    f"Device: {info.name} ({machine_ip}:{zk_port})\n"
                    f"Mode: {attendance_mode}\n"
                    f"Download filter: {download_mode}"
                    + (f" (since {since_dt.strftime('%Y-%m-%d')} UTC)" if since_dt else " (all records)")
                    + f"\nUsers on device: {len(user) if user else 0}\n"
                    f"Duplicate threshold: {duplicate_threshold} sec"
                )
                if log_details:
                    details_text += "\n\nNotes:\n" + "\n".join(log_details)

                device_log.create({
                    'device_id': info.id,
                    'log_type': 'download',
                    'status': log_status,
                    'records_found': records_found,
                    'records_new': records_new,
                    'records_duplicate': records_duplicate,
                    'records_failed': records_failed,
                    'employees_not_found': employees_not_found,
                    'duration': elapsed,
                    'details': details_text,
                    'error_message': "\n".join(log_details) if records_failed > 0 else False,
                })

                _logger.info(
                    f"Download complete for {info.name}: "
                    f"found={records_found}, new={records_new}, "
                    f"dup={records_duplicate}, failed={records_failed}, "
                    f"unknown_emp={employees_not_found}, time={elapsed:.1f}s"
                )

            except Exception as e:
                elapsed = _time.time() - start_time
                device_log.create({
                    'device_id': info.id,
                    'log_type': 'download',
                    'status': 'failed',
                    'records_found': records_found,
                    'records_new': records_new,
                    'records_duplicate': records_duplicate,
                    'records_failed': records_failed,
                    'employees_not_found': employees_not_found,
                    'duration': elapsed,
                    'error_message': str(e),
                    'details': f"Exception during download from {info.name}",
                })
                _logger.error(f"Download failed for device {info.name}: {str(e)}")
                if len(self) == 1:
                    raise
            finally:
                try:
                    conn.disconnect()
                except Exception:
                    pass

        return True

    def action_download_today(self):
        """Download today's attendance from all devices via background cron."""
        return self.action_download_attendance_background(download_mode='today')

    def action_download_current_week(self):
        """Download this week's attendance from all devices via background cron."""
        return self.action_download_attendance_background(download_mode='weekly')

    def action_download_current_month(self):
        """Download this month's attendance from all devices via background cron."""
        return self.action_download_attendance_background(download_mode='current_month')

    def action_download_all(self):
        """Download all historical attendance from all devices via background cron."""
        return self.action_download_attendance_background(download_mode='all')

    def action_download_attendance_background(self, download_mode='smart'):
        """Trigger attendance download via the scheduled cron (non-blocking UI).

        All download buttons (smart, today, current_month, all) funnel through
        here so they all run in the background across every active device.

        If a download is already running, shows a warning instead of queuing
        another job, so users are not confused when the UI returns quickly but
        the background process is still processing large datasets.
        """
        if self._is_download_running():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Download In Progress'),
                    'message': _(
                        'Your attendance data is currently being downloaded and processed '
                        'in the background. Please wait for it to complete before '
                        'starting a new download.'
                    ),
                    'type': 'warning',
                    'sticky': True,
                },
            }

        cron_code = (
            'model.search([]).action_download_attendance(download_mode="%s")'
            % download_mode
        )
        existing_cron = self.env.ref(
            'dotbd_hr_zk_attendance_suite.ir_cron_biometric_download',
            raise_if_not_found=False)
        if existing_cron:
            existing_cron.sudo().write({
                'nextcall': fields.Datetime.now(),
                'code': cron_code,
                'active': True,
            })
        else:
            self.env['ir.cron'].sudo().create({
                'name': _('ZK Attendance – One-shot Download'),
                'model_id': self.env['ir.model'].search(
                    [('model', '=', self._name)], limit=1).id,
                'state': 'code',
                'code': cron_code,
                'interval_number': 1,
                'interval_type': 'minutes',
                'nextcall': fields.Datetime.now(),
                'active': True,
            })

        mode_label = {
            'smart': 'smart (auto)',
            'today': "today's",
            'weekly': "this week's",
            'current_month': "this month's",
            'all': 'all historical',
        }.get(download_mode, download_mode)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Downloading in Background'),
                'message': _(
                    'Downloading %s attendance records from all devices. '
                    'It will run via the scheduled job. '
                    'Depending on device data volume and server/database speed, '
                    'this may take a few minutes.'
                ) % mode_label,
                'sticky': True,
                'type': 'info',
            },
        }

    def action_download_with_progress(self):
        """
        ═══════════════════════════════════════════════════════
        NEW: Open download wizard with real-time progress
        Shows live progress during attendance download
        Works for PyZK mode only (ADMS is push-based)
        ═══════════════════════════════════════════════════════
        """
        self.ensure_one()
        if self.connection_mode == 'adms':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('ADMS Mode'),
                    'message': _(
                        'ADMS mode devices push data automatically. '
                        'No manual download needed. Check "Operation Logs" to see recent syncs.'
                    ),
                    'type': 'info',
                    'sticky': False,
                },
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Download Attendance - %s') % self.name,
            'res_model': 'attendance.download.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_device_id': self.id},
        }

    # ==================== ADMS COMMAND METHODS ====================

    def action_adms_enroll_fingerprint(self):
        """Trigger fingerprint enrollment on ADMS-connected device.
        Queues an ENROLL_FP command for the device to pick up."""
        self.ensure_one()
        if self.connection_mode not in ('adms', 'hybrid'):
            raise UserError(_('Fingerprint enrollment via ADMS is only available '
                             'in Cloud (ADMS) or Hybrid connection mode.'))
        # Open wizard to select employee and finger
        return {
            'type': 'ir.actions.act_window',
            'name': _('Enroll Fingerprint'),
            'res_model': 'adms.device.command',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_device_id': self.id,
                'default_command_type': 'enroll_fp',
            },
        }

    def action_adms_reboot(self):
        """Queue a REBOOT command for ADMS device."""
        self.ensure_one()
        if self.connection_mode not in ('adms', 'hybrid'):
            raise UserError(_('ADMS commands are only available in Cloud (ADMS) or Hybrid mode.'))
        self.env['adms.device.command'].create({
            'device_id': self.id,
            'command_type': 'reboot',
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Reboot command queued. Device will reboot on next heartbeat.'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_adms_sync_users(self):
        """Queue user sync commands for all mapped employees."""
        self.ensure_one()
        if self.connection_mode not in ('adms', 'hybrid'):
            raise UserError(_('ADMS commands are only available in Cloud (ADMS) or Hybrid mode.'))
        employees = self.env['hr.employee'].search([
            ('device_id_num', '!=', False),
            ('device_id_num', '!=', ''),
        ])
        count = 0
        for emp in employees:
            self.env['adms.device.command'].create({
                'device_id': self.id,
                'command_type': 'sync_user',
                'employee_id': emp.id,
            })
            count += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _(f'{count} user sync commands queued for {self.name}.'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_view_adms_commands(self):
        """View ADMS command queue for this device."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('ADMS Commands'),
            'res_model': 'adms.device.command',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.id)],
            'context': {'default_device_id': self.id},
        }

    def action_view_fp_templates(self):
        """View fingerprint templates for this device."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fingerprint Templates'),
            'res_model': 'biometric.fp.template',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.id)],
        }
