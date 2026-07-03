# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit

################################################################################
from odoo import fields, models, tools


class AttendanceAnomalyAnalysis(models.Model):
    """Model to analyze attendance anomalies like missing check-out,
    duplicate check-in, etc."""
    _name = 'attendance.anomaly.analysis'
    _description = 'Attendance Anomaly Analysis'
    _auto = False
    _order = 'attendance_date desc'

    employee_id = fields.Many2one('hr.employee', string='Employee',
                                  readonly=True, help='Employee Name')
    attendance_date = fields.Date(string='Date', readonly=True,
                                  help='Date of attendance')
    anomaly_type = fields.Selection([
        ('missing_checkout', 'Missing Check-out'),
        ('duplicate_checkin', 'Duplicate Check-in'),
        ('missing_checkin', 'Missing Check-in'),
    ], string='Anomaly Type', readonly=True,
       help='Type of attendance anomaly detected')
    check_in_time = fields.Datetime(string='First Check-in',
                                    readonly=True,
                                    help='First check-in time of the day')
    last_punch_time = fields.Datetime(string='Last Punch Time',
                                      readonly=True,
                                      help='Last punch time of the day')
    total_punches = fields.Integer(string='Total Punches',
                                   readonly=True,
                                   help='Total number of punches in a day')
    checkin_count = fields.Integer(string='Check-in Count',
                                   readonly=True,
                                   help='Number of check-ins')
    checkout_count = fields.Integer(string='Check-out Count',
                                    readonly=True,
                                    help='Number of check-outs')
    address_id = fields.Many2one('res.partner', string='Working Address',
                                 readonly=True,
                                 help='Working address of the employee')

    def init(self):
        """Create SQL view to identify attendance anomalies.

        Reads from hr_attendance (processed records) instead of raw ZK punches,
        so detection is correct regardless of device punch_type encoding.

        Anomaly rules depend on the device's attendance mode:

        • traditional / auto:
            Multiple hr.attendance sessions per day are NORMAL (split-day,
            lunch break, etc.).  Only flag missing_checkout.

        • auto_per_day / traditional_per_day:
            Exactly ONE session per day is expected.  Flag:
              – missing_checkout  (open session)
              – duplicate_checkin (>1 session, all closed)

        Device mode is read from biometric_device_details.attendance_mode,
        joined via the shared address_id (working address).  If no device is
        found for an address, the view conservatively treats it as
        non-per-day (no false duplicate_checkin alarms).
        """
        tools.drop_view_if_exists(self.env.cr, self._table)

        query = """
            CREATE OR REPLACE VIEW %s AS (
                WITH daily_att AS (
                    SELECT
                        a.employee_id,
                        DATE(a.check_in)                       AS attendance_date,
                        e.address_id,
                        COUNT(*)                               AS total_punches,
                        COUNT(*)                               AS checkin_count,
                        COUNT(a.check_out)                     AS checkout_count,
                        MIN(a.check_in)                        AS check_in_time,
                        MAX(COALESCE(a.check_out, a.check_in)) AS last_punch_time
                    FROM hr_attendance a
                    JOIN hr_employee e ON e.id = a.employee_id
                    WHERE a.employee_id IS NOT NULL
                      AND a.check_in IS NOT NULL
                    GROUP BY a.employee_id, DATE(a.check_in), e.address_id
                ),
                -- For each working address determine whether ANY linked device
                -- operates in a per-day mode (one session expected per day).
                address_mode AS (
                    SELECT
                        address_id,
                        bool_or(attendance_mode IN ('auto_per_day', 'traditional_per_day'))
                            AS is_per_day
                    FROM biometric_device_details
                    WHERE address_id IS NOT NULL
                    GROUP BY address_id
                ),
                anomalies AS (
                    SELECT
                        da.employee_id,
                        da.attendance_date,
                        da.address_id,
                        da.total_punches,
                        da.checkin_count,
                        da.checkout_count,
                        da.check_in_time,
                        da.last_punch_time,
                        CASE
                            -- Open session: always an anomaly in every mode
                            WHEN da.checkout_count < da.checkin_count
                                THEN 'missing_checkout'
                            -- Extra sessions: anomaly only in per-day modes
                            WHEN da.checkin_count > 1
                                 AND COALESCE(am.is_per_day, FALSE)
                                THEN 'duplicate_checkin'
                        END AS anomaly_type
                    FROM daily_att da
                    LEFT JOIN address_mode am ON am.address_id = da.address_id
                )
                SELECT
                    ROW_NUMBER() OVER (ORDER BY employee_id, attendance_date) AS id,
                    employee_id,
                    attendance_date,
                    address_id,
                    total_punches,
                    checkin_count,
                    checkout_count,
                    check_in_time,
                    last_punch_time,
                    anomaly_type
                FROM anomalies
                WHERE anomaly_type IS NOT NULL
            )
        """ % self._table
        self.env.cr.execute(query)