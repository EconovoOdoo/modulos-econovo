
################################################################################
import datetime
import logging
import pytz
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)
try:
    from zk import ZK, const
except ImportError:
    _logger.error("Please Install pyzk library.")


class BiometricDeviceDetails(models.Model):
    """Model for configuring and connect the biometric device with odoo"""
    _name = 'biometric.device.details'
    _description = 'Biometric Device Details'

    name = fields.Char(string='Name', required=True, help='Record Name')
    device_ip = fields.Char(string='Device IP', required=True,
                            help='The IP address of the Device')
    port_number = fields.Integer(string='Port Number', required=True,
                                 help="The Port Number of the Device")
    address_id = fields.Many2one('res.partner', string='Working Address',
                                 help='Working address of the partner')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda
                                     self: self.env.user.company_id.id,
                                 help='Current Company')
    last_download_time = fields.Datetime(string='Last Download Time',
                                         help='The last time the attendance data was downloaded')

    # Auto Check-in/Check-out Mode Settings
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

    def device_connect(self, zk):
        """Function for connecting the device with Odoo"""
        try:
            conn = zk.connect()
            return conn
        except Exception:
            return False

    def action_test_connection(self):
        """Checking the connection status"""
        zk = ZK(self.device_ip, port=self.port_number, timeout=30,
                password=False, ommit_ping=True)  # Changed to True
        try:
            if zk.connect():
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': 'Successfully Connected',
                        'type': 'success',
                        'sticky': False
                    }
                }
        except Exception as error:
            raise ValidationError(f'{error}')

    def action_set_timezone(self):
        """Function to set user's timezone to device"""
        for info in self:
            machine_ip = info.device_ip
            zk_port = info.port_number
            try:
                # Connecting with the device with the ip and port provided
                zk = ZK(machine_ip, port=zk_port, timeout=15,
                        password=0,
                        force_udp=False, ommit_ping=True)
            except NameError:
                raise UserError(
                    _("Pyzk module not Found. Please install it"
                      "with 'pip3 install pyzk'."))
            conn = self.device_connect(zk)
            if conn:
                user_tz = self.env.context.get(
                    'tz') or self.env.user.tz or 'UTC'
                user_timezone_time = pytz.utc.localize(fields.Datetime.now())
                user_timezone_time = user_timezone_time.astimezone(
                    pytz.timezone(user_tz))
                conn.set_time(user_timezone_time)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': 'Successfully Set the Time',
                        'type': 'success',
                        'sticky': False
                    }
                }
            else:
                raise UserError(_(
                    "Please Check the Connection"))

    # def action_clear_attendance(self):
    #     """Methode to clear record from the zk.machine.attendance model and
    #     from the device"""
    #     for info in self:
    #         try:
    #             machine_ip = info.device_ip
    #             zk_port = info.port_number
    #             try:
    #                 # Connecting with the device
    #                 zk = ZK(machine_ip, port=zk_port, timeout=30,
    #                         password=0, force_udp=False, ommit_ping=False)
    #             except NameError:
    #                 raise UserError(_(
    #                     "Please install it with 'pip3 install pyzk'."))
    #             conn = self.device_connect(zk)
    #             if conn:
    #                 conn.enable_device()
    #                 clear_data = zk.get_attendance()
    #                 if clear_data:
    #                     # Clearing data in the device
    #                     conn.clear_attendance()
    #                     # Clearing data from attendance log
    #                     self._cr.execute(
    #                         """delete from zk_machine_attendance""")
    #                     conn.disconnect()
    #                 else:
    #                     raise UserError(
    #                         _('Unable to clear Attendance log.Are you sure '
    #                           'attendance log is not empty.'))
    #             else:
    #                 raise UserError(
    #                     _('Unable to connect to Attendance Device. Please use '
    #                       'Test Connection button to verify.'))
    #         except Exception as error:
    #             raise ValidationError(f'{error}')

    @api.model
    def cron_download(self):
        machines = self.env['biometric.device.details'].search([])
        for machine in machines:
            machine.action_download_attendance()

    def _is_duplicate_punch(self, employee_id, punch_time, threshold_minutes):
        """Check if this punch is a duplicate within threshold time window"""
        if threshold_minutes <= 0:
            return False

        zk_attendance = self.env['zk.machine.attendance']

        # Calculate time range (threshold minutes before and after)
        time_from = punch_time - datetime.timedelta(minutes=threshold_minutes)
        time_to = punch_time + datetime.timedelta(minutes=threshold_minutes)

        # Search for any punch within threshold window
        duplicate = zk_attendance.search([
            ('employee_id', '=', employee_id),
            ('punching_time', '>=', time_from),
            ('punching_time', '<=', time_to),
        ], limit=1)

        return bool(duplicate)

    def action_download_attendance(self):
        """Function to download attendance records from the device
        Supports both Traditional and Auto modes"""
        _logger.info("++++++++++++Cron Executed++++++++++++++++++++++")
        zk_attendance = self.env['zk.machine.attendance']
        hr_attendance = self.env['hr.attendance']

        for info in self:
            machine_ip = info.device_ip
            zk_port = info.port_number
            attendance_mode = info.attendance_mode or 'traditional'
            duplicate_threshold = info.duplicate_threshold or 2

            try:
                # Connecting with the device with the ip and port provided
                zk = ZK(machine_ip, port=zk_port, timeout=15,
                        password=0,
                        force_udp=False, ommit_ping=True)
            except NameError:
                raise UserError(
                    _("Pyzk module not Found. Please install it"
                      "with 'pip3 install pyzk'."))

            conn = self.device_connect(zk)

            if conn:
                conn.disable_device()  # Device Cannot be used during this time.
                user = conn.get_users()
                attendance = conn.get_attendance()

                if attendance:
                    for each in attendance:
                        atten_time = each.timestamp
                        local_tz = pytz.timezone('Asia/Dhaka')  # Use Dhaka timezone
                        local_dt = local_tz.localize(atten_time, is_dst=None)
                        utc_dt = local_dt.astimezone(pytz.utc)  # Convert to UTC
                        atten_time = fields.Datetime.to_string(utc_dt)

                        for uid in user:
                            if uid.user_id == each.user_id:
                                get_user_id = self.env['hr.employee'].search(
                                    [('device_id_num', '=', each.user_id)])

                                if get_user_id:
                                    # Check for duplicate punch in exact time
                                    duplicate_exact = zk_attendance.search([
                                        ('device_id_num', '=', each.user_id),
                                        ('punching_time', '=', atten_time)
                                    ])

                                    if duplicate_exact:
                                        _logger.info(f"Skipping exact duplicate punch for employee {get_user_id.name} at {atten_time}")
                                        continue

                                    # Check for duplicate within threshold window
                                    if self._is_duplicate_punch(get_user_id.id, utc_dt, duplicate_threshold):
                                        _logger.info(f"Skipping duplicate punch within {duplicate_threshold} minutes for employee {get_user_id.name}")
                                        continue

                                    # Create ZK attendance record
                                    zk_attendance.create({
                                        'employee_id': get_user_id.id,
                                        'device_id_num': each.user_id,
                                        'attendance_type': str(each.status),
                                        'punch_type': str(each.punch),
                                        'punching_time': atten_time,
                                        'address_id': info.address_id.id
                                    })

                                    # Process attendance based on mode
                                    if attendance_mode == 'auto':
                                        # AUTO MODE: Ignore device punch type, auto-determine check-in/check-out
                                        self._process_auto_attendance(get_user_id, atten_time, hr_attendance)
                                    else:
                                        # TRADITIONAL MODE: Use device punch type
                                        self._process_traditional_attendance(get_user_id, atten_time, each.punch, hr_attendance)

                                else:
                                    # Create new employee if not found
                                    employee = self.env['hr.employee'].create({
                                        'device_id_num': each.user_id,
                                        'name': uid.name
                                    })

                                    zk_attendance.create({
                                        'employee_id': employee.id,
                                        'device_id_num': each.user_id,
                                        'attendance_type': str(each.status),
                                        'punch_type': str(each.punch),
                                        'punching_time': atten_time,
                                        'address_id': info.address_id.id
                                    })

                                    # For new employees, always create check-in first
                                    hr_attendance.create({
                                        'employee_id': employee.id,
                                        'check_in': atten_time
                                    })

                    conn.disconnect

                    # Update the last download time after the attendance data is downloaded
                    info.last_download_time = fields.Datetime.now()

                    return True
                else:
                    raise UserError(_('Unable to get the attendance log, please try again later.'))
            else:
                raise UserError(_('Unable to connect, please check the parameters and network connections.'))

    def _process_traditional_attendance(self, employee, atten_time, punch_type, hr_attendance):
        """Process attendance in traditional mode (uses device punch type)"""
        att_var = hr_attendance.search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ])

        if punch_type == 0:  # check-in from device
            if not att_var:
                hr_attendance.create({
                    'employee_id': employee.id,
                    'check_in': atten_time
                })
                _logger.info(f"Traditional mode: Check-in created for {employee.name}")
        elif punch_type == 1:  # check-out from device
            if len(att_var) == 1:
                att_var.write({'check_out': atten_time})
                _logger.info(f"Traditional mode: Check-out added for {employee.name}")
            else:
                # If multiple open records or no open record, find last attendance
                att_var1 = hr_attendance.search([
                    ('employee_id', '=', employee.id)
                ], order='check_in desc', limit=1)
                if att_var1:
                    att_var1.write({'check_out': atten_time})
                    _logger.info(f"Traditional mode: Check-out added to last attendance for {employee.name}")

    def _process_auto_attendance(self, employee, atten_time, hr_attendance):
        """Process attendance in auto mode (ignores device punch type, auto-determines check-in/check-out)"""
        # Find last attendance record
        last_attendance = hr_attendance.search([
            ('employee_id', '=', employee.id)
        ], order='check_in desc', limit=1)

        # Determine if this should be check-in or check-out
        if not last_attendance or last_attendance.check_out:
            # No previous attendance OR last one has check-out → This is CHECK-IN
            hr_attendance.create({
                'employee_id': employee.id,
                'check_in': atten_time
            })
            _logger.info(f"Auto mode: Check-in created for {employee.name} at {atten_time}")
        else:
            # Last attendance has check-in but no check-out → This is CHECK-OUT
            last_attendance.write({'check_out': atten_time})
            _logger.info(f"Auto mode: Check-out added for {employee.name} at {atten_time}")

    def action_restart_device(self):
        """For restarting the device"""
        zk = ZK(self.device_ip, port=self.port_number, timeout=15,
                password=0,
                force_udp=False, ommit_ping=True)
        self.device_connect(zk).restart()
