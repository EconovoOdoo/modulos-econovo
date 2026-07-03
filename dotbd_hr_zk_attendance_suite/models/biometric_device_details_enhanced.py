# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit
#
################################################################################

import datetime
import logging
import pytz
import threading
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)
try:
    from zk import ZK, const
except ImportError:
    _logger.error("Please Install pyzk library.")


class BiometricDeviceDetails(models.Model):
    """Enhanced Model for biometric device with full pyzk capabilities"""
    _name = 'biometric.device.details'
    _description = 'Biometric Device Details - Enhanced'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ==================== BASIC DEVICE INFORMATION ====================
    name = fields.Char(string='Name', required=True, help='Device Name', tracking=True)
    device_ip = fields.Char(string='Device IP', required=True,
                            help='The IP address of the Device', tracking=True)
    port_number = fields.Integer(string='Port Number', required=True, default=4370,
                                 help="The Port Number of the Device (default: 4370)", tracking=True)
    device_password = fields.Char(string='Device Password',
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

    # ==================== ATTENDANCE MODE SETTINGS (Existing) ====================
    attendance_mode = fields.Selection([
        ('traditional', 'Traditional Mode (Use Device Punch Type)'),
        ('auto', 'Auto Mode (Auto Check-in/Check-out)')
    ], string='Attendance Mode', default='traditional', required=True,
       help='Traditional: Uses punch type from device (0=Check-in, 1=Check-out)\n'
            'Auto: Automatically determines Check-in/Check-out based on last attendance, '
            'ignores device punch type. Prevents HR mistakes.')

    duplicate_threshold = fields.Integer(
        string='Duplicate Prevention (Minutes)',
        default=2,
        help='Time window in minutes to ignore duplicate punches. '
             'If employee punches multiple times within this period, only first punch is counted. '
             'Default: 2 minutes')

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

    # ==================== DEVICE STATUS ====================
    device_status = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('unknown', 'Unknown')
    ], string='Device Status', default='unknown', readonly=True, compute='_compute_device_status',
       help='Current device connection status')
    last_online_time = fields.Datetime(string='Last Online', readonly=True, copy=False)

    # ==================== COMPUTED FIELDS ====================

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

    @api.depends('last_online_time')
    def _compute_device_status(self):
        """Determine device status based on last online time"""
        for device in self:
            if not device.last_online_time:
                device.device_status = 'unknown'
            else:
                time_diff = fields.Datetime.now() - device.last_online_time
                if time_diff.total_seconds() < 300:  # 5 minutes
                    device.device_status = 'online'
                else:
                    device.device_status = 'offline'

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

    def _get_device_password(self):
        """Get device password or return default value (0)"""
        self.ensure_one()
        if self.device_password:
            try:
                return int(self.device_password)
            except ValueError:
                return self.device_password
        return 0

    def device_connect(self, zk):
        """Connect to device"""
        try:
            conn = zk.connect()
            if conn:
                self.last_online_time = fields.Datetime.now()
            return conn
        except Exception as e:
            _logger.error(f"Connection failed for device {self.name}: {str(e)}")
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
                except:
                    pass
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
        """Sync server timezone to device"""
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
                    user_tz = self.env.context.get('tz') or self.env.user.tz or 'UTC'
                    user_timezone_time = pytz.utc.localize(fields.Datetime.now())
                    user_timezone_time = user_timezone_time.astimezone(pytz.timezone(user_tz))
                    conn.set_time(user_timezone_time)
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'message': f'Time synchronized successfully on {self.name}',
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
                conn.disconnect()

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
            except:
                face_ver = 'N/A'

            try:
                fp_ver = conn.get_fp_version()
            except:
                fp_ver = 'N/A'

            # Get network parameters
            try:
                network_params = conn.get_network_params()
                network_ip = network_params.get('ip', '')
                network_mask = network_params.get('mask', '')
                network_gateway = network_params.get('gateway', '')
            except:
                network_ip = self.device_ip
                network_mask = 'N/A'
                network_gateway = 'N/A'

            # Get capacity information
            sizes = conn.read_sizes()

            # Update device record
            self.write({
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
                'user_capacity': sizes.get('users', 0),
                'user_count': sizes.get('users_cap', 0),
                'finger_capacity': sizes.get('fingers', 0),
                'finger_count': sizes.get('fingers_cap', 0),
                'record_capacity': sizes.get('records', 0),
                'record_count': sizes.get('records_cap', 0),
                'face_capacity': sizes.get('faces', 0),
                'face_count': sizes.get('faces_cap', 0),
            })

            # Send alert if storage is critical
            if self.storage_warning:
                self._send_storage_alert()

            # Log activity
            self.message_post(
                body=f"Device information refreshed successfully.<br/>"
                     f"Firmware: {firmware}<br/>"
                     f"Serial: {serial}<br/>"
                     f"Users: {sizes.get('users_cap', 0)}/{sizes.get('users', 0)}<br/>"
                     f"Records: {sizes.get('records_cap', 0)}/{sizes.get('records', 0)}"
            )

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
            subject='⚠️ Device Storage Warning',
            body=f'Device <b>{self.name}</b> storage is critical!<br/><br/>'
                 f'📊 User Storage: <b>{self.user_usage_percent:.1f}%</b> '
                 f'({self.user_count}/{self.user_capacity})<br/>'
                 f'📝 Record Storage: <b>{self.record_usage_percent:.1f}%</b> '
                 f'({self.record_count}/{self.record_capacity})<br/><br/>'
                 f'Please clear old records to prevent data loss.',
            message_type='notification',
            subtype_xmlid='mail.mt_comment'
        )

    # ==================== CONTINUED IN NEXT PART ====================
