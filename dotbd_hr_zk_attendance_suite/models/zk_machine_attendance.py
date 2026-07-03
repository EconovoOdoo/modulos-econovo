# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit
#
################################################################################
from odoo import fields, models

# ==================== ZKTeco Status Code Mappings ====================
# These are ALL known verification method codes returned by ZKTeco devices
# via the pyzk library's attendance.status field.
# Different device models (especially iFace series with palm/face) return
# different codes. We must handle ALL of them to avoid ValueError crashes.
ATTENDANCE_TYPE_SELECTION = [
    ('0', 'Password'),
    ('1', 'Finger'),
    ('2', 'Type_2'),
    ('3', 'Password'),
    ('4', 'Card'),
    ('5', 'Other'),
    ('6', 'Multi-Modal'),
    ('7', 'Palm'),
    ('8', 'Palm Vein'),
    ('9', 'Iris'),
    ('10', 'Voice'),
    ('15', 'Face'),
    ('20', 'Face + Finger'),
    ('21', 'Face + Password'),
    ('22', 'Finger + Password'),
    ('23', 'Face + Finger + Card'),
    ('24', 'Palm + Face'),
    ('25', 'Palm + Finger'),
    ('26', 'Palm + Face + Finger'),
    ('27', 'Card + Finger'),
    ('28', 'Card + Face'),
    ('100', 'Other Biometric'),
    ('200', 'Mixed Verification'),
    ('255', 'Duplicate'),
    ('other', 'Unknown Method'),
]

PUNCH_TYPE_SELECTION = [
    ('0', 'Check In'),
    ('1', 'Check Out'),
    ('2', 'Break Out'),
    ('3', 'Break In'),
    ('4', 'Overtime In'),
    ('5', 'Overtime Out'),
    ('255', 'Duplicate'),
    ('other', 'Unknown'),
]

# Build lookup sets for fast validation
_VALID_ATTENDANCE_TYPES = {code for code, _ in ATTENDANCE_TYPE_SELECTION}
_VALID_PUNCH_TYPES = {code for code, _ in PUNCH_TYPE_SELECTION}


class ZkMachineAttendance(models.Model):
    """Model to hold raw punch data from the biometric device"""
    _name = 'zk.machine.attendance'
    _description = 'ZK Machine Attendance Raw Data'
    _order = 'punching_time desc'

    employee_id = fields.Many2one('hr.employee', string='Employee',
                                   required=True, ondelete='cascade', index=True,
                                   help='Employee who punched')
    device_id = fields.Many2one('biometric.device.details', string='Source Device',
                                 ondelete='set null', index=True,
                                 help='The biometric device this punch was downloaded from')
    device_id_num = fields.Char(string='ZK Device User ID',
                                 help="The ID of the Biometric Device")
    punch_type = fields.Selection(PUNCH_TYPE_SELECTION,
                                  string='Punching Type',
                                  help='Punching type of the attendance')
    attendance_type = fields.Selection(ATTENDANCE_TYPE_SELECTION,
                                       string='Category',
                                       help="Attendance detecting methods")
    punching_time = fields.Datetime(string='Punching Time', required=True, index=True,
                                    help="Punching time in the device")
    address_id = fields.Many2one('res.partner', string='Working Address',
                                 help="Working address of the employee")
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company,
                                 help='Company')
    source = fields.Selection([
        ('pyzk', 'PyZK Download'),
        ('adms', 'ADMS Push'),
        ('live', 'Live Capture'),
    ], string='Source', default='pyzk',
       help='How this record was captured: PyZK download, ADMS push, or Live capture')

    # Link to processed attendance record
    hr_attendance_id = fields.Many2one('hr.attendance', string='Linked Attendance',
                                       ondelete='set null', index=True,
                                       help='Reference to the hr.attendance record created from this punch')

    # Status tracking
    processed = fields.Boolean(string='Processed', default=False, index=True,
                               help='Whether this punch has been processed into hr.attendance')

    _sql_constraints = [
        ('unique_punch', 'unique(employee_id, punching_time, device_id_num)',
         'Duplicate punch detected! Same employee cannot punch at the exact same time.')
    ]

    @classmethod
    def _sanitize_attendance_type(cls, raw_value):
        """Safely convert device status code to a valid selection value.
        If the code is unknown, returns 'other' instead of crashing."""
        val = str(raw_value) if raw_value is not None else 'other'
        return val if val in _VALID_ATTENDANCE_TYPES else 'other'

    @classmethod
    def _sanitize_punch_type(cls, raw_value):
        """Safely convert device punch code to a valid selection value.
        If the code is unknown, returns 'other' instead of crashing."""
        val = str(raw_value) if raw_value is not None else 'other'
        return val if val in _VALID_PUNCH_TYPES else 'other'
