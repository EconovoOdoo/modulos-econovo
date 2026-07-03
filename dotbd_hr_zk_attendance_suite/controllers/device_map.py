# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit
#
################################################################################

import json
import logging
from datetime import datetime, timedelta
from markupsafe import Markup
from odoo import http
from odoo.http import request, content_disposition
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)


class DeviceMapController(http.Controller):
    """Controller for the Device Location Map page.
    
    Renders a full-page Leaflet.js map showing all biometric devices
    with their configured GPS coordinates.
    """

    @http.route('/zkteco/device/map', type='http', auth='user', website=False)
    def device_map(self, **kwargs):
        """Render the device location map page."""
        devices = request.env['biometric.device.details'].sudo().search([
            ('has_location', '=', True),
        ])
        
        device_data = []
        for d in devices:
            device_data.append({
                'id': d.id,
                'name': d.name,
                'lat': d.latitude,
                'lng': d.longitude,
                'location_name': d.location_name or '',
                'status': d.device_status,
                'connection_mode': d.connection_mode,
                'ip': d.device_ip or '',
                'user_count': d.user_count,
                'record_count': d.record_count,
                'storage_pct': round(d.record_usage_percent, 1),
                'geofence_radius': d.geofence_radius,
                'attendance_count': d.device_attendance_count,
                'firmware': d.firmware_version or '',
                'last_online': d.last_online_time.isoformat() if d.last_online_time else '',
            })
        
        now = datetime.now()
        default_from = now.replace(day=1).strftime('%Y-%m-%d')
        default_to = now.strftime('%Y-%m-%d')
        is_manager = request.env.user.has_group(
            'dotbd_hr_zk_attendance_suite.group_attendance_officer')
        meta = {
            'is_manager': is_manager,
            'date_from': default_from,
            'date_to': default_to,
        }
        values = {
            'device_json': Markup(json.dumps(device_data)),
            'markers_json': Markup(json.dumps([])),
            'departments_json': Markup(json.dumps([])),
            'meta_json': Markup(json.dumps(meta)),
            'device_count': len(device_data),
            'total_devices': request.env['biometric.device.details'].sudo().search_count([]),
            'marker_count': 0,
            'is_manager': is_manager,
            'date_from': default_from,
            'date_to': default_to,
        }
        return request.render('dotbd_hr_zk_attendance_suite.device_map_template', values)

    @http.route('/zkteco/device/map/data', type='json', auth='user', website=False)
    def device_map_data(self, **kwargs):
        """JSON endpoint returning device locations for AJAX updates."""
        devices = request.env['biometric.device.details'].sudo().search([
            ('has_location', '=', True),
        ])
        
        result = []
        for d in devices:
            result.append({
                'id': d.id,
                'name': d.name,
                'lat': d.latitude,
                'lng': d.longitude,
                'location_name': d.location_name or '',
                'status': d.device_status,
                'connection_mode': d.connection_mode,
                'ip': d.device_ip or '',
                'user_count': d.user_count,
                'record_count': d.record_count,
                'storage_pct': round(d.record_usage_percent, 1),
                'geofence_radius': d.geofence_radius,
                'attendance_count': d.device_attendance_count,
            })
        return result

    # ─── Team Check-in Map ────────────────────────────────────────────────
    # Access control:
    #   • Employee → record rules auto-filter to their own attendance only
    #   • Officer / Manager / Admin → can see all employees
    # We intentionally do NOT use .sudo() so record rules are applied.

    @staticmethod
    def _haversine_m(lat1, lon1, lat2, lon2):
        """Haversine formula — distance in metres between two GPS points."""
        import math
        R = 6371000  # Earth radius in metres
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _get_device_geofences(self):
        """Return list of device (lat, lng, radius) for inside/outside check."""
        devices = request.env['biometric.device.details'].sudo().search([
            ('has_location', '=', True),
            ('geofence_radius', '>', 0),
        ])
        return [(d.latitude, d.longitude, d.geofence_radius) for d in devices]

    def _is_inside_office(self, lat, lng, geofences):
        """Check if a point is inside ANY device geofence."""
        for d_lat, d_lng, d_radius in geofences:
            if self._haversine_m(lat, lng, d_lat, d_lng) <= d_radius:
                return True
        return False

    def _get_attendance_map_data(self, date_from=None, date_to=None):
        """Return attendance markers for the map.

        Uses the current user's access rights (no .sudo()) so:
        - Regular employees only see their own check-in pins
        - HR Officers / Managers / Admins see everyone

        Supports date range (date_from .. date_to).
        """
        Attend = request.env['hr.attendance']

        if date_from:
            start = datetime.strptime(date_from, '%Y-%m-%d').replace(
                hour=0, minute=0, second=0)
        else:
            # Default to 1st of current month
            start = datetime.now().replace(day=1, hour=0, minute=0, second=0)

        if date_to:
            end = datetime.strptime(date_to, '%Y-%m-%d').replace(
                hour=23, minute=59, second=59)
        else:
            end = start.replace(hour=23, minute=59, second=59)

        # Search WITHOUT sudo → record rules apply automatically
        records = Attend.search([
            ('check_in', '>=', start.strftime(DEFAULT_SERVER_DATETIME_FORMAT)),
            ('check_in', '<=', end.strftime(DEFAULT_SERVER_DATETIME_FORMAT)),
            ('in_latitude', '!=', 0),
            ('in_longitude', '!=', 0),
        ])

        geofences = self._get_device_geofences()

        markers = []
        for rec in records:
            emp = rec.employee_id
            src = rec.attendance_source or 'manual'
            src_icon = {'biometric': '🔐', 'mobile_app': '📱', 'web': '🌐'}.get(src, '✏️')

            # Office in/out detection
            inside = self._is_inside_office(
                rec.in_latitude, rec.in_longitude, geofences)

            dept = emp.department_id
            markers.append({
                'id': rec.id,
                'emp_id': emp.id,
                'emp_name': emp.name or '',
                'emp_job': emp.job_title or '',
                'emp_mobile': emp.mobile_phone or emp.work_phone or '',
                'emp_badge': emp.device_id_num or emp.barcode or '',
                'emp_image_url': '/web/image/hr.employee/' + str(emp.id) + '/image_128' if emp.image_128 else '',
                'emp_initials': ''.join([n[0].upper() for n in (emp.name or '').split()[:2]]) if emp.name else '?',
                'department_id': dept.id if dept else 0,
                'department_name': dept.name if dept else 'No Department',
                'check_in': rec.check_in.isoformat() if rec.check_in else '',
                'check_out': rec.check_out.isoformat() if rec.check_out else '',
                'check_in_date': rec.check_in.strftime('%Y-%m-%d') if rec.check_in else '',
                'in_lat': rec.in_latitude,
                'in_lng': rec.in_longitude,
                'out_lat': rec.out_latitude or 0,
                'out_lng': rec.out_longitude or 0,
                'has_checkout_gps': bool(rec.out_latitude and rec.out_longitude),
                'source': src,
                'source_icon': src_icon,
                'distance': round(rec.checkin_distance, 0),
                'in_browser': rec.in_browser or '',
                'inside_office': inside,
            })
        return markers

    def _get_department_list(self):
        """Return departments that have employees with GPS attendance."""
        Attend = request.env['hr.attendance']
        today = datetime.now()
        start = today.replace(hour=0, minute=0, second=0)
        end = today.replace(hour=23, minute=59, second=59)

        records = Attend.search([
            ('check_in', '>=', start.strftime(DEFAULT_SERVER_DATETIME_FORMAT)),
            ('check_in', '<=', end.strftime(DEFAULT_SERVER_DATETIME_FORMAT)),
            ('in_latitude', '!=', 0),
            ('in_longitude', '!=', 0),
        ])

        dept_map = {}
        for rec in records:
            dept = rec.employee_id.department_id
            if dept and dept.id not in dept_map:
                dept_map[dept.id] = dept.name
        return [{'id': k, 'name': v} for k, v in sorted(
            dept_map.items(), key=lambda x: x[1])]

    @http.route('/zkteco/attendance/map', type='http', auth='user', website=False)
    def attendance_map_page(self, **kwargs):
        """Full-page Team Check-in Map.

        Employees see only their own pins. Managers see the whole team.
        Supports date range via ?date_from=...&date_to=...
        """
        date_from = kwargs.get('date_from') or kwargs.get('date')
        date_to = kwargs.get('date_to') or date_from
        markers = self._get_attendance_map_data(date_from, date_to)

        # Device locations with full details (same for all users)
        devices = request.env['biometric.device.details'].sudo().search([
            ('has_location', '=', True),
        ])
        device_data = [{
            'id': d.id,
            'name': d.name,
            'lat': d.latitude,
            'lng': d.longitude,
            'location_name': d.location_name or '',
            'status': d.device_status,
            'connection_mode': d.connection_mode,
            'ip': d.device_ip or '',
            'user_count': d.user_count,
            'record_count': d.record_count,
            'storage_pct': round(d.record_usage_percent, 1),
            'geofence_radius': d.geofence_radius,
            'attendance_count': d.device_attendance_count,
        } for d in devices]

        # Departments for filter dropdown
        departments = self._get_department_list()

        # Determine if user is manager/officer (for UI hints)
        is_manager = request.env.user.has_group(
            'dotbd_hr_zk_attendance_suite.group_attendance_officer')

        now = datetime.now()
        default_from = date_from or now.replace(day=1).strftime('%Y-%m-%d')
        default_to = date_to or now.strftime('%Y-%m-%d')
        meta = {
            'is_manager': is_manager,
            'date_from': default_from,
            'date_to': default_to,
        }
        values = {
            'device_json': Markup(json.dumps(device_data)),
            'markers_json': Markup(json.dumps(markers)),
            'departments_json': Markup(json.dumps(departments)),
            'meta_json': Markup(json.dumps(meta)),
            'device_count': len(device_data),
            'marker_count': len(markers),
            'is_manager': is_manager,
            'date_from': default_from,
            'date_to': default_to,
        }
        return request.render(
            'dotbd_hr_zk_attendance_suite.device_map_template', values)

    @http.route('/zkteco/attendance/map/data', type='json', auth='user', website=False)
    def attendance_map_data(self, **kwargs):
        """JSON endpoint for AJAX refresh of attendance markers."""
        date_from = kwargs.get('date_from') or kwargs.get('date')
        date_to = kwargs.get('date_to') or date_from
        return self._get_attendance_map_data(date_from, date_to)
