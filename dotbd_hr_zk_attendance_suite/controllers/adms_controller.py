# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit
#
#    ADMS Push Protocol Controller
#    Receives attendance data and commands from ZKTeco devices
#    using the ADMS (Automatic Data Master Server) push protocol.
#
################################################################################

import logging
import re
import threading
import zlib
from datetime import datetime

import pytz
from odoo import http, fields, SUPERUSER_ID, api
from odoo.modules.registry import Registry as OdooRegistry
from odoo.http import request
from ..models.zk_machine_attendance import ZkMachineAttendance

_logger = logging.getLogger(__name__)

# Thread-local storage for multi-database ADMS routing.
# When a db-path route (/db/<dbname>/iclock/...) is used, the target database
# cursor is stored here so _senv() returns the correct environment even though
# request.env.cr still points to Odoo's default/session database.
_adms_local = threading.local()


class ADMSController(http.Controller):
    """HTTP Controller for ZKTeco ADMS Push Protocol.

    The device connects to Odoo and pushes attendance data.
    Protocol endpoints:
        /iclock/cdata       GET  = handshake, POST = push data (attendance/users/biometrics)
        /iclock/getrequest  GET  = device polls for pending commands
        /iclock/devicecmd   POST = device reports command execution result
    """

    # ─────────────────────────── helpers ───────────────────────────

    def _senv(self):
        """Return a SUPERUSER environment safe for use in auth='none' routes.

        In auth='none', request.env.uid is None/False. Even with .sudo() on
        individual models, Odoo ORM can internally call self.env.user through
        compute triggers or mail.thread hooks and get an empty recordset →
        'Expected singleton: res.users()'. Using api.Environment with
        SUPERUSER_ID ensures uid=1 propagates everywhere, including through
        mail.thread hooks and compute triggers in auth='none' routes.

        When called from a db-path route (/db/<dbname>/iclock/...), the
        thread-local cursor for the target database is used instead of
        request.env.cr (which points to Odoo's default/session database).
        This is the core of multi-database ADMS routing support.
        """
        cr = getattr(_adms_local, 'db_cursor', None)
        if cr is not None:
            return api.Environment(cr, SUPERUSER_ID, {})
        return api.Environment(request.env.cr, SUPERUSER_ID, request.env.context)

    # ─────────────────── Multi-database routing ────────────────────────────

    def _route_with_db(self, db, handler, **kwargs):
        """Execute an ADMS route handler against a specific named database.

        Used by the /db/<db>/iclock/... routes to support Odoo installations
        with multiple databases. Sets a thread-local cursor so _senv() (and
        therefore all downstream ORM calls) use the correct database, then
        delegates to the existing single-database handler.

        The ZKTeco device should have its ADMS server address configured as:
            http://{odoo_host}:{port}/db/{database_name}
        The device firmware appends /iclock/cdata (etc.) automatically, giving:
            http://{odoo_host}:{port}/db/{database_name}/iclock/cdata
        """
        try:
            registry = OdooRegistry(db)
        except Exception as e:
            # Catch broadly: a missing database raises KeyError (not in the
            # registry cache) on first lookup, then psycopg2.OperationalError
            # ("database ... does not exist") when the registry tries to connect.
            # Either way we must NOT return a 500 — just acknowledge with OK so a
            # misconfigured device stops retrying instead of erroring.
            _logger.warning(
                "ADMS multi-db route: cannot open database '%s' (%s). "
                "Check the database name in the device ADMS server address.", db, e)
            return self._make_response('OK')

        with registry.cursor() as cr:
            _adms_local.db_cursor = cr
            try:
                result = handler(**kwargs)
                try:
                    api.Environment(cr, SUPERUSER_ID, {}).flush_all()
                except Exception:
                    pass
                return result
            finally:
                _adms_local.db_cursor = None

    @http.route('/db/<string:db>/iclock/cdata', type='http', auth='none',
                csrf=False, methods=['GET', 'POST'], save_session=False)
    def cdata_db(self, db, **kwargs):
        """Database-specific ADMS cdata endpoint for multi-database Odoo setups.

        Set the ZKTeco device ADMS server address to:
            http://{odoo_host}:{port}/db/{database_name}
        The device will then push attendance to this database only.
        """
        return self._route_with_db(db, self.cdata, **kwargs)

    @http.route('/db/<string:db>/iclock/getrequest', type='http', auth='none',
                csrf=False, methods=['GET'], save_session=False)
    def getrequest_db(self, db, **kwargs):
        """Database-specific ADMS getrequest endpoint for multi-database setups."""
        return self._route_with_db(db, self.getrequest, **kwargs)

    @http.route('/db/<string:db>/iclock/devicecmd', type='http', auth='none',
                csrf=False, methods=['POST'], save_session=False)
    def devicecmd_db(self, db, **kwargs):
        """Database-specific ADMS devicecmd endpoint for multi-database setups."""
        return self._route_with_db(db, self.devicecmd, **kwargs)

    def _find_device_by_serial(self, serial_number, remote_ip=None,
                               return_direct_rejection=False,
                               include_inactive=False):
        """Find device record by serial number, with IP fallback.

        Search priority:
        1. Match by device_serial (ADMS/hybrid modes)
        2. Match by serial_number (populated by PyZK refresh)
        3. Fallback: match by IP address (any connection mode)

        Args:
            return_direct_rejection: When True, returns (recordset, rejected_flag)
                where rejected_flag=True means a device with this serial exists
                but is set to 'direct' mode (so caller must NOT auto-register).
                When False (default), returns just the recordset.
            include_inactive: When True, INACTIVE (archived / pending-activation)
                devices are also matched. Used by the handshake so that an
                auto-registered-but-inactive device is recognised (no duplicate
                created, heartbeat still updates → shows Online). ATTLOG data
                processing keeps this False so inactive devices' punches are
                rejected until an admin activates the device.
        """
        env = self._senv()
        DeviceModel = env['biometric.device.details']
        if include_inactive:
            # active_test=False makes search() return archived records too.
            DeviceModel = DeviceModel.with_context(active_test=False)
        empty = DeviceModel
        # Build the active-state domain leaf once. When include_inactive, we add
        # no active filter at all (active_test is already off on the recordset).
        active_clause = [] if include_inactive else [('active', '=', True)]

        # Try matching by device_serial (primary ADMS identifier).
        if serial_number and serial_number != '0':
            device = DeviceModel.search([
                ('device_serial', '=', serial_number),
                ('connection_mode', 'in', ['adms', 'hybrid']),
            ] + active_clause, limit=1)
            if device:
                return (device, False) if return_direct_rejection else device

            # Also try the serial_number field (populated by PyZK refresh)
            # Must also check connection_mode — if device is set to PyZK ('direct'),
            # we must NOT process ADMS pushes for it.
            device = DeviceModel.search([
                ('serial_number', '=', serial_number),
                ('connection_mode', 'in', ['adms', 'hybrid']),
            ] + active_clause, limit=1)
            if device:
                if not device.device_serial and device.adms_auto_fill_serial:
                    device.device_serial = serial_number
                return (device, False) if return_direct_rejection else device

            # If device exists but is in 'direct' (PyZK) mode, reject ADMS push.
            # We signal this to the caller so it does NOT auto-register a
            # duplicate device record for the same serial.
            device_direct = DeviceModel.search([
                '|',
                ('device_serial', '=', serial_number),
                ('serial_number', '=', serial_number),
            ], limit=1)
            if device_direct and device_direct.connection_mode == 'direct':
                _logger.info(
                    "ADMS push from device S/N=%s ignored — device '%s' is set to "
                    "Direct Connection (PyZK) mode. Change to Hybrid or ADMS mode "
                    "to accept ADMS pushes, or remove the ADMS server URL from "
                    "the device firmware to stop these requests.",
                    serial_number, device_direct.name)
                return (empty, True) if return_direct_rejection else empty

        # Fallback: match by IP address
        if remote_ip and remote_ip not in ('0.0.0.0', '127.0.0.1'):
            device = DeviceModel.search([
                ('device_ip', '=', remote_ip),
                ('connection_mode', 'in', ['adms', 'hybrid']),
            ] + active_clause, limit=1)
            if device:
                if (serial_number and serial_number != '0'
                        and not device.device_serial
                        and device.adms_auto_fill_serial):
                    device.device_serial = serial_number
                return (device, False) if return_direct_rejection else device

        return (empty, False) if return_direct_rejection else empty

    # Minimum interval between heartbeat DB writes per device, in seconds.
    # ADMS devices can ping every 10 seconds; without throttling we would
    # emit ~8,640 writes/day/device, cascading compute fields and bloating
    # mail tracking. 60 seconds is plenty of granularity for "online" status.
    _HEARTBEAT_THROTTLE_SECONDS = 60

    # Max commands handed to a device in a single getrequest poll. The ZKTeco
    # PUSH protocol accepts multiple newline-separated "C:{id}:..." commands per
    # response, so batching drains large queues (bulk fingerprint/template sync)
    # in seconds instead of one command per ~10s poll.
    _CMD_BATCH_SIZE = 10

    def _register_heartbeat(self, device):
        """Update the device's last heartbeat timestamp, throttled.

        Writes at most once per ``_HEARTBEAT_THROTTLE_SECONDS`` per device to
        avoid runaway write amplification on chatty ADMS devices.
        """
        if not device:
            return
        now = fields.Datetime.now()
        last = device.adms_last_heartbeat
        if last:
            if (now - last).total_seconds() < self._HEARTBEAT_THROTTLE_SECONDS:
                return
        device.write({
            'adms_last_heartbeat': now,
            'last_online_time': now,
        })

    def _make_response(self, body, headers=None):
        """Wrap make_response.

        IMPORTANT: do NOT inject an empty ``Date`` header here. Odoo 17's WSGI
        server (odoo/service/server.py → send_header) feeds the Date header to
        email.utils.parsedate_to_datetime() for its de-duplication logic; an
        empty string raises ``ValueError: Invalid date value or format ""`` and
        the entire response is dropped — the device sees "Remote end closed
        connection without response" and every ADMS push fails. Suppressing the
        Date header (to stop ZKteco firmware syncing its clock from it) is done
        at the nginx layer instead — see the ADMS device setup guide.
        """
        base_headers = [('Content-Type', 'text/plain')]
        if headers:
            caller_keys = {h[0].lower() for h in headers}
            base_headers = [h for h in base_headers if h[0].lower() not in caller_keys]
            base_headers.extend(headers)

        _logger.debug(
            "ADMS response  body=%r  extra_headers=%s",
            body[:200] if isinstance(body, str) and len(body) > 200 else body,
            headers,
        )
        return request.make_response(body, headers=base_headers)

    def _get_device_timezone_for_adms(self, device):
        """Get the timezone for ADMS ATTLOG interpretation AND ServerLocalTime.

        Priority:
        1. device_firmware_tz — auto-detected from live punches. When the device
           firmware timezone cannot be changed (e.g. ZKTeco factory UTC+8), this
           field stores the detected TZ so both ATTLOG conversion AND ServerLocalTime
           use the same timezone the device actually operates in.
        2. adms_custom_timezone — explicit ADMS override (hybrid mode). Allows
           different timezones for ADMS push vs PyZK pull on the same device.
        3. User-configured time_sync_method / custom_timezone — used when no firmware
           TZ or ADMS override has been set.

        Both uses MUST stay in sync: whatever timezone we send in ServerLocalTime,
        the device records timestamps in that timezone, so we interpret with the same TZ.
        """
        # 1. Auto-detected firmware TZ wins — device timestamps are in this TZ
        #    regardless of what the user configured.
        if device.device_firmware_tz:
            return device.device_firmware_tz

        # 2. ADMS-specific timezone override (hybrid mode: separate TZ per protocol)
        if device.adms_custom_timezone:
            return device.adms_custom_timezone

        # 3. User-configured method (for ADMS only Custom and Server make sense)
        method = device.time_sync_method or 'custom'
        if method == 'server':
            # Device clock will be set to UTC, ATTLOG timestamps are UTC
            return 'UTC'
        else:
            # 'custom', 'manual', or 'odoo' (odoo TZ is irrelevant in ADMS because
            # ADMS runs as SUPERUSER — fall back to custom_timezone in all cases)
            return device.custom_timezone or 'UTC'

    # ─────────────────────────── /iclock/cdata ───────────────────────────

    @http.route('/iclock/cdata', type='http', auth='none',
                csrf=False, methods=['GET', 'POST'], save_session=False)
    def cdata(self, **kwargs):
        """Main ADMS endpoint.
        GET  = device handshake (sends SN, gets config)
        POST = device pushes data (ATTLOG, OPERLOG, BIODATA)
        """
        serial = kwargs.get('SN', '')
        method = request.httprequest.method
        remote_ip = request.httprequest.remote_addr or '0.0.0.0'

        # ── Dump every incoming HTTP header so we can see exactly what the device sent ──
        incoming_headers = dict(request.httprequest.headers)
        _logger.info(
            "ADMS /iclock/cdata %s  SN=%s  IP=%s\n"
            "  ┌─ Query params ─────────────────────────────────────────────\n"
            "  │  %s\n"
            "  ├─ HTTP headers ─────────────────────────────────────────────\n"
            "%s"
            "  └────────────────────────────────────────────────────────────",
            method, serial, remote_ip,
            "  │  ".join(f"{k}={v}" for k, v in kwargs.items()) or "(none)",
            "".join(f"  │  {k}: {v}\n" for k, v in incoming_headers.items()),
        )

        if method == 'GET':
            return self._handle_handshake(serial, kwargs)

        # POST — device is pushing data
        table = kwargs.get('table', '')
        body = request.httprequest.data
        if isinstance(body, bytes):
            body = body.decode('utf-8', errors='replace')

        _logger.info(
            "ADMS POST  SN=%s  table=%s  body_size=%d bytes\n"
            "  ┌─ Body preview (first 500 chars) ───────────────────────────\n"
            "  │  %s\n"
            "  └────────────────────────────────────────────────────────────",
            serial, table, len(body),
            body[:500].replace('\n', '\n  │  ') if body else "(empty)",
        )

        if table == 'ATTLOG':
            return self._process_attendance(serial, body)
        elif table == 'OPERLOG':
            return self._process_operation_log(serial, body)
        elif table in ('BIODATA', 'BIOTEMPLATE'):
            return self._process_biometric_template(serial, body)
        elif table == 'options':
            return self._process_device_options(serial, body)

        _logger.warning("ADMS POST  SN=%s  unrecognised table='%s' — returning OK", serial, table)
        return self._make_response('OK')

    def _handle_handshake(self, serial, kwargs):
        """Device sends GET /iclock/cdata?SN=xxx on first connect.
        We respond with server configuration options."""
        remote_ip = request.httprequest.remote_addr or '0.0.0.0'

        _logger.info(
            "ADMS HANDSHAKE ── begin ─────────────────────────────────────────\n"
            "  Device SN   : %s\n"
            "  Remote IP   : %s\n"
            "  Full URL    : %s\n"
            "  All params  : %s\n"
            "  Server UTC  : %s",
            serial, remote_ip,
            request.httprequest.url,
            dict(kwargs),
            datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
        )

        # include_inactive=True: an auto-registered device starts INACTIVE for
        # safety. We must still recognise it on subsequent handshakes (so we do
        # not create duplicates) and keep its heartbeat fresh (so it shows
        # Online and the admin can find and activate it).
        device, rejected_as_direct = self._find_device_by_serial(
            serial, remote_ip=remote_ip, return_direct_rejection=True,
            include_inactive=True)

        # If device exists but is in 'direct' mode, DO NOT auto-register a
        # duplicate. Return a minimal OK so the device stops retrying config.
        if rejected_as_direct:
            return request.make_response(
                'OK', headers=[('Content-Type', 'text/plain')])

        if not device:
            # Only auto-register if we have a valid (non-empty, non-zero) serial
            if not serial or serial == '0':
                _logger.warning(
                    "ADMS HANDSHAKE ── REJECTED ──────────────────────────────────\n"
                    "  Reason : Empty or zero serial number\n"
                    "  IP     : %s  SN='%s'\n"
                    "  Action : Sending minimal config (ErrorDelay=60). "
                    "Add device manually in Odoo or configure SN in device firmware.",
                    remote_ip, serial)
                config_lines = [
                    'GET OPTION FROM: {}'.format(serial),
                    'ErrorDelay=60',
                    'Delay=30',
                    'Realtime=1',
                    'ServerVer=2.4.1',
                ]
                return self._make_response('\r\n'.join(config_lines) + '\r\n')

            # Use PostgreSQL advisory lock to prevent concurrent auto-registration
            # IMPORTANT: Python's built-in hash() is salted per-process (PYTHONHASHSEED),
            # so two Odoo workers would compute DIFFERENT keys for the SAME serial and
            # the lock would not actually prevent duplicates. Use zlib.crc32 — stable
            # across processes.
            lock_key = zlib.crc32(
                f'adms_register_{serial}'.encode('utf-8')) & 0x7FFFFFFF
            env = self._senv()
            env.cr.execute("SELECT pg_try_advisory_xact_lock(%s)", (lock_key,))
            got_lock = env.cr.fetchone()[0]
            if not got_lock:
                _logger.info(
                    "ADMS HANDSHAKE ── concurrent registration SN=%s — skipping duplicate", serial)
                return self._make_response('OK')

            # Double-check after acquiring lock (include_inactive so a previously
            # auto-registered inactive device is not duplicated).
            device = self._find_device_by_serial(
                serial, remote_ip=remote_ip, include_inactive=True)
            if not device:
                _logger.info(
                    "ADMS HANDSHAKE ── AUTO-REGISTER ─────────────────────────────\n"
                    "  SN=%s  IP=%s\n"
                    "  Creating new biometric.device.details record automatically "
                    "(INACTIVE — pending admin activation for safety).",
                    serial, remote_ip)
                # SAFETY: auto-registered devices start INACTIVE. A device that
                # reaches us may have connected via a bare IP / raw domain with no
                # /db/ path — i.e. bypassing the intended database filter. We
                # create it archived (active=False) and flagged so the admin must
                # explicitly review and activate it before any attendance data is
                # accepted. The heartbeat below still marks it Online so it is
                # visible in the (archived) device list.
                device = env['biometric.device.details'].with_context(
                    active_test=False).create({
                        'name': f'ADMS Device ({serial})',
                        'device_serial': serial,
                        'connection_mode': 'adms',
                        'device_ip': remote_ip,
                        'port_number': 4370,
                        'active': False,
                        'adms_auto_registered': True,
                    })
                device.message_post(
                    body=f"Device auto-registered via ADMS push (SN: {serial}, "
                         f"IP: {remote_ip}). Created INACTIVE for safety — review "
                         f"and activate it to start accepting attendance data.",
                    message_type='notification',
                )
                _logger.info(
                    "ADMS HANDSHAKE ── auto-registered device id=%s name='%s' "
                    "(INACTIVE, pending activation)",
                    device.id, device.name)
            else:
                _logger.info(
                    "ADMS HANDSHAKE ── device found after lock  SN=%s  id=%s  name='%s'",
                    serial, device.id, device.name)
        else:
            _logger.info(
                "ADMS HANDSHAKE ── device found ──────────────────────────────\n"
                "  id=%s  name='%s'  mode=%s  firmware_tz=%s\n"
                "  custom_tz=%s  time_sync_method=%s\n"
                "  adms_attlog_stamp=%s  adms_operlog_stamp=%s\n"
                "  last_heartbeat=%s",
                device.id, device.name, device.connection_mode,
                device.device_firmware_tz or '(not detected)',
                device.custom_timezone or '(not set)',
                device.time_sync_method or 'custom',
                device.adms_attlog_stamp or 0,
                device.adms_operlog_stamp or 0,
                device.adms_last_heartbeat or '(never)',
            )

        self._register_heartbeat(device)

        # Log a simple handshake note to chatter (once per hour max to avoid spam)
        try:
            device.log_adms_handshake()
        except Exception as _he:
            _logger.warning("ADMS: handshake chatter log failed for SN=%s: %s", serial, _he)

        # ── HARDCODED Receive-Only mode ───────────────────────────────────────
        # Time sync to device is PERMANENTLY DISABLED.
        # Device manages its own clock — Odoo never sends ServerLocalTime or TimeZone.
        # ATTLOG timestamps are taken at face value and converted with custom_timezone.
        receive_only = True
        _logger.info(
            "ADMS HANDSHAKE SN=%s: receive-only — time sync DISABLED, "
            "ATTLOG will be treated as '%s' local time.",
            serial, device.custom_timezone or 'UTC',
        )

        # Stamps tell the device which records we've already acknowledged.
        # Device only sends records newer than the stamp → avoids full resync every connect.
        attlog_stamp = device.adms_attlog_stamp or 0
        operlog_stamp = device.adms_operlog_stamp or 0

        config_lines = [
            'GET OPTION FROM: {}'.format(serial),
            'ATTLOGStamp={}'.format(attlog_stamp),
            'OPERLOGStamp={}'.format(operlog_stamp),
            'BIODATAStamp=0',
            'ATTPHOTOStamp=0',
            'ErrorDelay=30',
            'Delay=10',
            'TransTimes=00:00;14:05',
            'TransInterval=1',
            'TransFlag=TransData AttLog\tOpLog\tBioData',
            'Realtime=1',
            'ServerVer=2.4.1',
            'PushProtVer=2.4.1',
        ]

        utc_now_dt = datetime.now(pytz.utc)
        utc_now = utc_now_dt.strftime('%Y-%m-%d %H:%M:%S')

        # TimeZone and ServerLocalTime are NOT added — device clock is untouched.
        _logger.info(
            "ADMS HANDSHAKE ── time sync BLOCKED ─────────────────────────────\n"
            "  ATTLOGStamp : %s  OPERLOGStamp : %s",
            attlog_stamp, operlog_stamp,
        )

        response_body = '\r\n'.join(config_lines) + '\r\n'

        _logger.info(
            "ADMS HANDSHAKE ── response ──────────────────────────────────────\n"
            "%s"
            "  └────────────────────────────────────────────────────────────",
            "".join(f"  │  {line}\n" for line in config_lines),
        )

        # Return handshake config WITHOUT Date header.
        # ZKteco devices use the HTTP Date header as a clock reference — omitting it
        # prevents the device from syncing its clock to the server time.
        return request.make_response(response_body, headers=[('Content-Type', 'text/plain')])

    # ─────────────────────────── Attendance Push ───────────────────────────

    # ADMS VERIFY code → our attendance_type selection value
    # ADMS protocol:  0=Fingerprint, 1=PIN/Password, 2=Card, 3=RF/RFID, 9=Face
    # PyZK protocol:  0=Password,    1=Finger (reversed!)
    # We map ADMS codes to our selection values which were built for PyZK.
    _ADMS_VERIFY_MAP = {
        0: '1',   # Fingerprint → Finger
        1: '0',   # PIN/Password → Password
        2: '4',   # Card/PW → Card
        3: '4',   # RF/RFID → Card
        4: '6',   # FP or PW → Multi-Modal
        5: '6',   # FP or RF → Multi-Modal
        6: '6',   # PW or RF → Multi-Modal
        7: '6',   # PIN and FP → Multi-Modal
        8: '6',   # FP and PW → Multi-Modal
        9: '15',  # Face
        10: '6',  # PW and RF → Multi-Modal
        11: '6',  # FP+PW+RF → Multi-Modal
        12: '6',  # All methods → Multi-Modal
        15: '15', # Face (some firmware)
    }

    def _process_attendance(self, serial, body):
        """Parse ATTLOG data pushed by device and create attendance records.

        ATTLOG format (tab-delimited, one record per line):
        USER_ID\\tTIMESTAMP\\tSTATUS\\tVERIFY\\t\\t\\t
        Example: 1\\t2026-02-26 09:00:00\\t0\\t1\\t\\t\\t

        STATUS: 0=Check-in, 1=Check-out, 2=Break-out, 3=Break-in, 4=OT-in, 5=OT-out
        VERIFY (ADMS): 0=Fingerprint, 1=PIN, 2=Card, 3=RF, 9=Face
        """
        # Capture the Stamp from the POST URL — echo it back in response so device
        # knows we acknowledged these records and won't resend them next cycle.
        stamp = request.httprequest.args.get('Stamp', '0')

        device = self._find_device_by_serial(serial, remote_ip=request.httprequest.remote_addr)
        if not device:
            # No ACTIVE device matched. Distinguish two cases:
            #  (a) an auto-registered device exists but is still INACTIVE
            #      (pending admin activation) → reject the data but keep its
            #      heartbeat fresh so it still shows Online and the admin notices.
            #      Respond "OK: 0" (zero records accepted) so the device HOLDS the
            #      punches and resends them on the next cycle — once the admin
            #      activates the device the buffered records are then accepted and
            #      nothing is lost.
            #  (b) genuinely unknown serial → acknowledge with the echoed stamp so
            #      the device stops retrying (we can never process it anyway).
            pending = self._find_device_by_serial(
                serial, remote_ip=request.httprequest.remote_addr,
                include_inactive=True)
            if pending and not pending.active:
                self._register_heartbeat(pending)
                _logger.warning(
                    "ADMS ATTLOG: device SN=%s (id=%s '%s') is INACTIVE — "
                    "attendance push HELD pending admin activation (responded "
                    "OK: 0 so the device resends after you activate it).",
                    serial, pending.id, pending.name)
                return self._make_response('OK: 0')
            _logger.warning("ADMS ATTLOG: Unknown device SN=%s", serial)
            return self._make_response('OK: {}'.format(stamp))

        self._register_heartbeat(device)

        # Determine device timezone for converting local time → UTC
        # Odoo stores ALL datetimes as UTC, and displays in user's timezone.
        # Device sends local time (e.g. 14:14 BDT) → must convert to UTC (08:14).
        tz_str = self._get_device_timezone_for_adms(device)
        
        # ⚠️ TIMEZONE MISMATCH WARNING for ADMS
        # Log warning if there's a mismatch between configured and effective timezone
        if device.time_sync_method == 'custom' and device.custom_timezone:
            if device.custom_timezone != tz_str:
                _logger.warning(
                    "ADMS Device SN=%s: TIMEZONE MISMATCH! Configured=%s, Using=%s. "
                    "This may cause incorrect attendance times! Click 'Sync Time' button to fix.",
                    serial, device.custom_timezone, tz_str)
        
        _logger.info(
            "ADMS ATTLOG SN=%s: Using timezone '%s' (custom_tz=%s, effective_tz=%s)",
            serial, tz_str, device.custom_timezone, device.effective_timezone)
        try:
            local_tz = pytz.timezone(tz_str)
        except pytz.UnknownTimeZoneError:
            local_tz = pytz.UTC

        lines = body.strip().split('\n')
        records_processed = 0
        records_duplicate = 0
        records_failed = 0
        new_employees_created = []
        log_msgs = []
        # Collect (device_naive_dt, server_utc_naive_dt) for punches close to now
        fresh_punches_for_tz_detect = []
        server_utc_now = datetime.utcnow()

        # Use SUPERUSER environment for all operations.
        # _senv() returns the db-path-specific cursor when called from a
        # multi-database route (/db/<dbname>/iclock/...), otherwise falls back
        # to request.env.cr (standard single-database behavior).
        env = self._senv()
        zk_attendance = env['zk.machine.attendance']
        hr_attendance = env['hr.attendance']
        hr_employee = env['hr.employee']

        attendance_mode = device.attendance_mode or 'traditional'
        duplicate_threshold = device.duplicate_threshold or 5

        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                # flush=False: prevent _FlushingSavepoint from calling cr.flush()
                # on exit using default_env. We flush manually with superuser env.
                with env.cr.savepoint(flush=False):
                    # Format: USER_ID\tTIMESTAMP\tSTATUS\tVERIFY
                    # Example: 1	2023-10-25 09:00:00	0	1
                    parts = line.split('\t')
                    if len(parts) < 3:
                        _logger.warning("ADMS ATTLOG: Invalid line format: %s", line)
                        records_failed += 1
                        continue

                    user_id = parts[0].strip()
                    timestamp_str = parts[1].strip()
                    zk_status = int(parts[2].strip())
                    verify = int(parts[3].strip()) if len(parts) > 3 and parts[3].strip() else 0

                    _logger.info(
                        "ADMS ATTLOG SN=%s: RAW punch → user_id=%s device_time=%s status=%s verify=%s",
                        serial, user_id, timestamp_str, zk_status, verify)

                    # Parse timestamp
                    try:
                        atten_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        _logger.warning("ADMS ATTLOG: Invalid timestamp: %s", timestamp_str)
                        records_failed += 1
                        continue

                    # ═══════════════════════════════════════════════════════
                    # CRITICAL TIMEZONE CONVERSION FIX (ADMS Mode)
                    # ═══════════════════════════════════════════════════════
                    # Device sends local time (e.g., 14:14 Beirut UTC+3)
                    # Convert to UTC (08:14) for Odoo storage.
                    # Handle DST transitions (Beirut, Europe, etc.)
                    # ═══════════════════════════════════════════════════════
                    try:
                        local_dt = local_tz.localize(atten_time, is_dst=None)
                        utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
                    except pytz.exceptions.NonExistentTimeError:
                        # DST gap (spring forward)
                        _logger.warning(
                            "ADMS Device SN=%s: Non-existent time %s during DST spring-forward",
                            serial, timestamp_str)
                        local_dt = local_tz.localize(atten_time, is_dst=False)
                        utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
                    except pytz.exceptions.AmbiguousTimeError:
                        # DST overlap (fall back)
                        _logger.warning(
                            "ADMS Device SN=%s: Ambiguous time %s during DST fall-back, "
                            "using first occurrence (DST=True)", serial, timestamp_str)
                        local_dt = local_tz.localize(atten_time, is_dst=True)
                        utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)

                    # ═══════════════════════════════════════════════════════
                    # ADMS TIME OFFSET CORRECTION
                    # ═══════════════════════════════════════════════════════
                    # Apply a fixed hour offset AFTER timezone conversion.
                    # Used when the device clock is permanently wrong by a known
                    # number of hours and cannot be physically corrected.
                    # Example: device always 3h ahead → adms_time_offset_hours = -3
                    # ═══════════════════════════════════════════════════════
                    offset_hours = device.adms_time_offset_hours or 0
                    if offset_hours:
                        from datetime import timedelta as _td
                        utc_dt_before = utc_dt
                        utc_dt = utc_dt + _td(hours=offset_hours)
                        _logger.info(
                            "ADMS ATTLOG SN=%s: TIME OFFSET %+dh applied → %s → %s",
                            serial, offset_hours,
                            utc_dt_before.strftime('%Y-%m-%d %H:%M:%S'),
                            utc_dt.strftime('%Y-%m-%d %H:%M:%S'))

                    atten_time_str = fields.Datetime.to_string(utc_dt)

                    _logger.info(
                        "ADMS ATTLOG SN=%s: TIMEZONE → device_local=%s tz=%s → utc=%s",
                        serial, timestamp_str, tz_str, atten_time_str)

                    # Collect punches for TZ auto-detection.
                    # We compare raw device local time vs server UTC to compute the apparent
                    # offset: device_local - server_utc = firmware timezone offset.
                    # Freshness window: if |device_local - server_utc| < 14h it's likely a
                    # real-time punch (not a replayed historical record from weeks ago).
                    # Using 14h covers all UTC offsets (-12 to +14) without filtering out
                    # wrong-timezone devices (e.g. UTC+8 device on UTC+6 server → diff=2h).
                    # Old approach: checked (utc_dt - server_utc) < 600s — this EXCLUDED
                    # wrong-tz punches because after conversion they appeared 2h in the future.
                    raw_diff_seconds = abs((atten_time - server_utc_now).total_seconds())
                    if raw_diff_seconds < 50400:  # 14 hours
                        fresh_punches_for_tz_detect.append((atten_time, server_utc_now))

                    # Find employee by device_id_num — try device company first, then any company
                    employee = hr_employee.search([
                        ('device_id_num', '=', user_id),
                        ('company_id', '=', device.company_id.id),
                    ], limit=1)
                    if not employee:
                        # Fallback: search across all companies (multi-company setups)
                        employee = hr_employee.search([
                            ('device_id_num', '=', user_id),
                        ], limit=1)

                    if employee:
                        _logger.info(
                            "ADMS ATTLOG SN=%s: EMPLOYEE FOUND → user_id=%s matched '%s' (id=%s)",
                            serial, user_id, employee.name, employee.id)
                    if not employee:
                        _logger.warning(
                            "ADMS ATTLOG SN=%s: NO EMPLOYEE for user_id=%s — "
                            "check 'ZK Device User ID' field on employee record",
                            serial, user_id)
                        # Auto-create a new employee for this unknown device user ID.
                        # Guard: a device without a company_id would otherwise
                        # produce an employee with no company, which breaks record
                        # rules. Fall back to the env's default company.
                        target_company = (
                            device.company_id or env.company or env['res.company'].search([], limit=1))
                        if not target_company:
                            _logger.error(
                                "ADMS ATTLOG: cannot auto-create employee '%s' — "
                                "device %s has no company and env has no default company.",
                                user_id, device.id)
                            records_failed += 1
                            continue
                        _logger.info(
                            "ADMS ATTLOG: No employee found for Device ID '%s'. "
                            "Auto-creating new employee in company '%s'.",
                            user_id, target_company.name)
                        employee = hr_employee.with_company(target_company).create({
                            'name': f'Device User {user_id}',
                            'device_id_num': user_id,
                            'company_id': target_company.id,
                            'active': True,
                        })
                        new_employees_created.append(user_id)
                        _logger.info(
                            "ADMS ATTLOG: Auto-created employee '%s' (ID=%s) for Device ID '%s'",
                            employee.name, employee.id, user_id)

                    # Serialize concurrent writes for the same employee across all
                    # devices — prevents "could not serialize access due to concurrent
                    # update" when 10+ devices push live data for the same employees.
                    env.cr.execute(
                        "SELECT pg_advisory_xact_lock(%s)",
                        (employee.id & 0x7FFFFFFF,))

                    # Check exact duplicate
                    existing = zk_attendance.search([
                        ('device_id_num', '=', user_id),
                        ('punching_time', '=', atten_time_str),
                    ], limit=1)
                    if existing:
                        _logger.info(
                            "ADMS ATTLOG SN=%s: DUPLICATE (exact) user_id=%s time=%s — skipped",
                            serial, user_id, atten_time_str)
                        records_duplicate += 1
                        continue

                    # Check time-window duplicate
                    if device._is_duplicate_punch(employee.id, utc_dt, duplicate_threshold):
                        _logger.info(
                            "ADMS ATTLOG SN=%s: DUPLICATE (window %ssec) user_id=%s time=%s — skipped",
                            serial, duplicate_threshold, user_id, atten_time_str)
                        records_duplicate += 1
                        continue

                    # Sanitize punch type: 0=Check-in, 1=Check-out
                    # ZKTeco STATUS map: 0/3/4=Check-in, 1/2/5=Check-out
                    punch_type = 0 if zk_status in (0, 3, 4) else 1
                    _logger.info(
                        "ADMS ATTLOG SN=%s: STORING → user_id=%s employee='%s' utc=%s punch=%s(%s) verify=%s",
                        serial, user_id, employee.name, atten_time_str,
                        'CHECK-IN' if punch_type == 0 else 'CHECK-OUT', zk_status, verify)

                    # Map ADMS verify code → our attendance_type selection value.
                    # ADMS and PyZK use different code schemes (0=FP in ADMS, 0=Password in PyZK).
                    mapped_attendance_type = self._ADMS_VERIFY_MAP.get(
                        verify, ZkMachineAttendance._sanitize_attendance_type(verify))

                    # Create raw attendance record
                    zk_rec = zk_attendance.create({
                        'employee_id': employee.id,
                        'device_id': device.id,
                        'device_id_num': user_id,
                        'attendance_type': mapped_attendance_type,
                        'punch_type': ZkMachineAttendance._sanitize_punch_type(punch_type),
                        'punching_time': atten_time_str,
                        'address_id': device.address_id.id if device.address_id else False,
                        'source': 'adms',
                    })

                    # Process attendance (check-in / check-out in hr.attendance).
                    # We wrap this in a nested savepoint so if Odoo's rigid HR
                    # Attendance validation fails (e.g. Check Out earlier than
                    # Check In), we DON'T lose the raw zk_rec.
                    # Capture the returned hr.attendance so we can link it to
                    # the zk.machine.attendance row (anomaly dashboard relies
                    # on hr_attendance.zk_punch_count > 0 to tell biometric
                    # from manual entries).
                    hr_att_record = False
                    try:
                        with env.cr.savepoint(flush=False):
                            if attendance_mode == 'auto':
                                hr_att_record = device._process_auto_attendance(
                                    employee, atten_time_str, hr_attendance)
                            elif attendance_mode == 'auto_per_day':
                                hr_att_record = device._process_auto_per_day_attendance(
                                    employee, atten_time_str, hr_attendance)
                            elif attendance_mode == 'traditional_per_day':
                                hr_att_record = device._process_traditional_per_day_attendance(
                                    employee, atten_time_str, punch_type, hr_attendance)
                            else:
                                hr_att_record = device._process_traditional_attendance(
                                    employee, atten_time_str, punch_type, hr_attendance)
                    except Exception as hr_err:
                        _logger.warning("ADMS ATTLOG: HR Processing failed, but Raw Punch stored: %s", hr_err)
                        # We do not raise here, so the outer savepoint COMMITS the zk_rec!

                    # Link raw punch to hr.attendance record so Biometric vs
                    # Manual distinction works in reports/dashboards.
                    if hr_att_record:
                        try:
                            zk_rec.write({
                                'hr_attendance_id': hr_att_record.id,
                                'processed': True,
                            })
                        except Exception as link_err:
                            _logger.warning(
                                "ADMS ATTLOG: Could not link zk punch to hr.attendance: %s",
                                link_err)

                    # Flush pending ORM ops (e.g. computed fields on hr.attendance)
                    # using our superuser env so env.user is always the admin user.
                    env.flush_all()
                    records_processed += 1

            except Exception as e:
                _logger.error("ADMS ATTLOG: Error processing line '%s': %s", line, e)
                records_failed += 1
                log_msgs.append(f"Failed record '{line[:30]}...': {e}")

        # Auto-detect device firmware timezone from fresh punches
        # (skipped in receive-only mode — device clock is trusted as-is)
        if fresh_punches_for_tz_detect and not device.adms_receive_only:
            try:
                device._suggest_timezone_if_mismatch(fresh_punches_for_tz_detect)
            except Exception as _tz_e:
                _logger.warning("ADMS: TZ detection failed for SN=%s: %s", serial, _tz_e)

        # Update push count and store the acknowledged stamp.
        # IMPORTANT: update stamp whenever we received ANY records (including duplicates).
        # If we only update when records_processed > 0, the stamp never advances for
        # duplicate-only batches — causing the device to resend those same records
        # on every reconnect (infinite resend loop).
        total_received = records_processed + records_failed + records_duplicate
        if total_received > 0:
            try:
                stamp_int = int(stamp)
            except (ValueError, TypeError):
                stamp_int = 0
            device.sudo().write({
                'adms_push_count': device.adms_push_count + records_processed,
                'last_download_time': fields.Datetime.now(),
                'adms_attlog_stamp': stamp_int,
            })

        # Generate a device log summary
        if records_processed > 0 or records_failed > 0 or records_duplicate > 0 or new_employees_created:
            log_status = 'success'
            if records_failed > 0:
                log_status = 'warning' if records_processed > 0 else 'failed'

            details_text = f"ADMS sync via Webhook.\nDuplicates: {records_duplicate}"
            if new_employees_created:
                details_text += (
                    f"\n\nAuto-created {len(new_employees_created)} new employee(s) "
                    f"for Device IDs: {', '.join(new_employees_created)}\n"
                    "Please update their names in HR → Employees."
                )
            if log_msgs:
                details_text += "\n\nError Notes:\n" + "\n".join(log_msgs)

            env['biometric.device.log'].create({
                'device_id': device.id,
                'log_type': 'live_capture',
                'status': log_status,
                'records_found': records_processed + records_failed + records_duplicate,
                'records_new': records_processed,
                'records_duplicate': records_duplicate,
                'records_failed': records_failed,
                'error_message': "\n".join(log_msgs) if log_msgs else False,
                'details': details_text,
            })

        _logger.info(
            "ADMS ATTLOG SN=%s: %d processed, %d duplicates, %d failed, %d new employees",
            serial, records_processed, records_duplicate, records_failed, len(new_employees_created))

        # Protocol requires "OK: {count}" where count = number of records successfully
        # processed. The device uses this count to advance its Stamp pointer so it
        # won't resend already-acknowledged records next cycle.
        # NOTE: returning the stamp value instead of count is a protocol violation —
        # devices interpret the response as a record count, not a stamp.
        total_accepted = records_processed + records_duplicate
        return self._make_response('OK: {}'.format(total_accepted))

    # ─────────────────────────── Operation Log ───────────────────────────

    def _process_operation_log(self, serial, body):
        """Process OPERLOG data — device operation events.

        OPERLOG format: USER_ID\tTIMESTAMP\tEVENT_TYPE\t...
        We parse the timestamp to keep track of what time the device clock
        is currently showing (used as "echo" for ServerLocalTime).
        """
        stamp = request.httprequest.args.get('Stamp', '0')

        device = self._find_device_by_serial(serial, remote_ip=request.httprequest.remote_addr)
        if device:
            self._register_heartbeat(device)

        # Log full OPERLOG body at INFO level so we can see the format
        _logger.info("ADMS OPERLOG SN=%s raw: %r", serial, body[:300] if body else '')

        # In receive-only mode skip ALL clock analysis and command queueing
        if device and device.adms_receive_only:
            _logger.debug("ADMS OPERLOG SN=%s: receive-only mode — skipping clock analysis", serial)
            operlog_count = len(body.strip().split('\n')) if body and body.strip() else 0
            return self._make_response('OK: {}'.format(operlog_count))

        # Parse device timestamp from OPERLOG.
        # ZKTeco OPERLOG formats vary by firmware:
        #   Format A (common): PIN\tTime\tSerialNo\tEventType\tInOut\tVerify\t...
        #   Format B (some):   Time\tEventType\t...
        #   Format C (door):   CardNo\tTime\t...
        # We scan all tab-separated fields for anything matching a datetime pattern.
        if device and body:
            import re
            dt_pattern = re.compile(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')
            found_dt = None
            for line in body.strip().split('\n'):
                for field in line.strip().split('\t'):
                    field = field.strip()
                    if dt_pattern.fullmatch(field):
                        try:
                            found_dt = datetime.strptime(field, '%Y-%m-%d %H:%M:%S')
                            break
                        except ValueError:
                            continue
                if found_dt:
                    break

            if found_dt:
                try:
                    env = self._senv()
                    try:
                        stamp_int = int(stamp)
                    except (ValueError, TypeError):
                        stamp_int = 0
                    # Device reports local time — convert to UTC before storing,
                    # otherwise ``adms_device_echo_time`` (Odoo Datetime = naive
                    # UTC) would display 3-6 hours off for non-UTC devices.
                    tz_str = self._get_device_timezone_for_adms(device)
                    try:
                        local_tz = pytz.timezone(tz_str)
                        utc_dt = local_tz.localize(found_dt).astimezone(
                            pytz.UTC).replace(tzinfo=None)
                    except Exception:
                        utc_dt = found_dt  # best-effort fallback
                    env['biometric.device.details'].browse(device.id).write({
                        'adms_device_echo_time': fields.Datetime.to_string(utc_dt),
                        'adms_operlog_stamp': stamp_int,
                    })
                    _logger.info(
                        "ADMS OPERLOG SN=%s: device clock shows %s (local), stored %s (UTC)",
                        serial, found_dt, utc_dt)

                    # Clock drift check: compare device clock vs server UTC clock.
                    # The OPERLOG timestamp is the device's raw local time (no TZ applied).
                    # We compute: apparent_offset = device_local - server_utc.
                    # Compare against the USER-CONFIGURED base timezone ONLY — never against
                    # device_firmware_tz itself, because that would cause a circular clear:
                    #   1. ATTLOG 17:xx → device_firmware_tz=Asia/Shanghai set
                    #   2. OPERLOG 17:xx → _get_device_timezone returns Asia/Shanghai
                    #      → apparent(+8) vs configured(+8) → drift=0 → clears firmware TZ ← WRONG
                    # By always diffing against the user's configured_tz (not the firmware override),
                    # we detect when the device returns to the correct timezone and only then clear.
                    server_utc = datetime.utcnow()
                    apparent_offset_seconds = (found_dt - server_utc).total_seconds()
                    apparent_offset_hours = round(apparent_offset_seconds / 900) * 0.25  # round to 15min

                    # Use raw user-configured TZ — NEVER device_firmware_tz — as the baseline
                    if device.time_sync_method == 'server':
                        base_tz_str = 'UTC'
                    else:
                        base_tz_str = device.custom_timezone or 'UTC'
                    try:
                        base_offset_seconds = pytz.timezone(base_tz_str).utcoffset(
                            datetime.now()).total_seconds()
                    except Exception:
                        base_offset_seconds = 0

                    drift_from_base = abs(apparent_offset_seconds - base_offset_seconds)

                    _logger.info(
                        "ADMS OPERLOG SN=%s: clock check → device_local=%s  server_utc=%s  "
                        "apparent_tz_offset=%+.2fh  base_tz=%s(%+.2fh)  firmware_tz=%s  "
                        "drift_from_base=%.0fs",
                        serial, found_dt.strftime('%Y-%m-%d %H:%M:%S'),
                        server_utc.strftime('%Y-%m-%d %H:%M:%S'),
                        apparent_offset_hours,
                        base_tz_str, base_offset_seconds / 3600,
                        device.device_firmware_tz or '(none)',
                        drift_from_base,
                    )

                    if drift_from_base > 300:  # 5 minutes — device not in configured TZ
                        # Determine what timezone the device actually appears to be in
                        tz_map = getattr(type(device), '_TZ_OFFSET_MAP', {})
                        detected_tz = tz_map.get(apparent_offset_hours)
                        if not detected_tz and tz_map:
                            closest = min(tz_map.keys(), key=lambda k: abs(k - apparent_offset_hours))
                            if abs(closest - apparent_offset_hours) <= 0.5:
                                detected_tz = tz_map[closest]
                            else:
                                detected_tz = f'Etc/GMT{int(-apparent_offset_hours):+d}'

                        _logger.warning(
                            "ADMS OPERLOG SN=%s: CLOCK DRIFT %.0f seconds from configured TZ! "
                            "Device appears to be in %s (UTC%+.2g) but configured as %s. "
                            "Auto-setting device_firmware_tz='%s' so ATTLOG converts correctly.",
                            serial, drift_from_base,
                            detected_tz or 'unknown', apparent_offset_hours, base_tz_str,
                            detected_tz or base_tz_str,
                        )

                        if detected_tz and detected_tz != device.device_firmware_tz:
                            try:
                                with self._senv().cr.savepoint():
                                    device.write({'device_firmware_tz': detected_tz})
                                _logger.info(
                                    "ADMS OPERLOG SN=%s: device_firmware_tz set to '%s'",
                                    serial, detected_tz)
                            except Exception as _fw_e:
                                _logger.warning(
                                    "ADMS OPERLOG SN=%s: could not write device_firmware_tz: %s",
                                    serial, _fw_e)

                        # Queue an immediate SET TIME correction via getrequest.
                        # The device polled getrequest every Delay=10 seconds so this
                        # corrects the device clock within ~10 seconds — faster than
                        # waiting for the next handshake. The command always uses
                        # custom_timezone (NOT firmware_tz) so the device displays
                        # the correct local time (e.g. 3pm BDT, not 5pm UTC+8).
                        try:
                            env = self._senv()
                            # Cancel any stale pending set_time commands first
                            env['adms.device.command'].search([
                                ('device_id', '=', device.id),
                                ('command_type', '=', 'set_time'),
                                ('status', '=', 'pending'),
                            ]).write({'status': 'failed', 'result': 'superseded by new drift correction'})
                            env['adms.device.command'].create({
                                'device_id': device.id,
                                'command_type': 'set_time',
                            })
                            _logger.info(
                                "ADMS OPERLOG SN=%s: queued set_time correction command "
                                "(device will be corrected via next getrequest within ~10s)",
                                serial)
                        except Exception as _cmd_e:
                            _logger.warning(
                                "ADMS OPERLOG SN=%s: could not queue set_time command: %s",
                                serial, _cmd_e)
                    else:
                        # Device clock matches configured TZ — drift is acceptable.
                        # Clear firmware TZ override so next handshake and ATTLOG
                        # conversion both use the plain custom_timezone again.
                        if device.device_firmware_tz:
                            try:
                                with self._senv().cr.savepoint():
                                    device.write({'device_firmware_tz': False})
                                _logger.info(
                                    "ADMS OPERLOG SN=%s: drift OK (%.0fs) — "
                                    "device_firmware_tz override cleared, "
                                    "device clock is back in '%s'",
                                    serial, drift_from_base, base_tz_str)
                            except Exception:
                                pass
                        _logger.info(
                            "ADMS OPERLOG SN=%s: drift OK (%.0fs) — device clock in sync with '%s'",
                            serial, drift_from_base, base_tz_str,
                        )
                except Exception as e:
                    _logger.warning("ADMS OPERLOG: could not save echo time: %s", e)
            else:
                _logger.info("ADMS OPERLOG SN=%s: no datetime found in body", serial)

        # Protocol requires "OK: {count}" where count = number of records processed.
        # Returning stamp value here is a protocol violation.
        operlog_count = len(body.strip().split('\n')) if body and body.strip() else 0
        return self._make_response('OK: {}'.format(operlog_count))

    # ─────────────────────────── Biometric Templates ───────────────────────────

    def _process_biometric_template(self, serial, body):
        """Process BIODATA — fingerprint/face templates pushed from device.

        Called when device completes fingerprint enrollment or syncs templates.
        Format: PIN=1\\tFID=0\\tTMP=<base64>\\tSZ=1024\\tValid=1
        """
        device = self._find_device_by_serial(serial, remote_ip=request.httprequest.remote_addr)
        if not device:
            _logger.warning("ADMS BIODATA: Unknown device SN=%s", serial)
            return self._make_response('OK')

        self._register_heartbeat(device)

        env = self._senv()
        lines = body.strip().split('\n')
        fp_template_model = env['biometric.fp.template']
        hr_employee = env['hr.employee']

        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                # Parse key=value pairs separated by tabs
                params = {}
                for part in line.split('\t'):
                    if '=' in part:
                        key, _, value = part.partition('=')
                        params[key.strip().upper()] = value.strip()

                pin = params.get('PIN', '')
                fid = int(params.get('FID', '0'))
                
                # Biometric type heuristics from ADMS:
                # 'TYPE' is usually sent for faces and palms. If missing, assume finger.
                bio_type_id = int(params.get('VALID', '1'))  # sometimes used
                bio_type_param = int(params.get('TYPE', '1'))
                
                if bio_type_param == 9 or bio_type_param == 2 or fid == 50:
                    template_type = 'face'
                elif bio_type_param == 8:
                    template_type = 'palm'
                else:
                    template_type = 'finger'
                    
                tmp_data = params.get('TMP', '')
                tmp_size = int(params.get('SZ', '0'))

                if not pin or not tmp_data:
                    continue

                # Find employee
                employee = hr_employee.search([
                    ('device_id_num', '=', pin)
                ], limit=1)

                if not employee:
                    _logger.info("ADMS BIODATA: No employee for PIN=%s", pin)
                    continue

                # Check if template already exists for this type and finger
                existing = fp_template_model.search([
                    ('employee_id', '=', employee.id),
                    ('template_type', '=', template_type),
                    ('finger_index', '=', fid),
                ], limit=1)

                template_vals = {
                    'employee_id': employee.id,
                    'device_id': device.id,
                    'template_type': template_type,
                    'finger_index': fid,
                    'template_data': tmp_data,
                    'template_size': tmp_size,
                    'capture_time': fields.Datetime.now(),
                }

                if existing:
                    existing.write(template_vals)
                    _logger.info("ADMS BIODATA: Updated %s template for %s (FID %d)",
                                 template_type, employee.name, fid)
                else:
                    fp_template_model.create(template_vals)
                    _logger.info("ADMS BIODATA: Saved new %s template for %s (FID %d)",
                                 template_type, employee.name, fid)

                # Mark enrollment command as done
                pending_cmd = env['adms.device.command'].search([
                    ('device_id', '=', device.id),
                    ('command_type', '=', 'enroll_fp'),
                    ('employee_id', '=', employee.id),
                    ('status', 'in', ['pending', 'sent']),
                ], limit=1)
                if pending_cmd:
                    pending_cmd.write({
                        'status': 'done',
                        'done_time': fields.Datetime.now(),
                        'result': f'{template_type.capitalize()} received: FID {fid}, size {tmp_size}',
                    })

            except Exception as e:
                _logger.error("ADMS BIODATA: Error: %s", e)

        return self._make_response('OK')

    # ─────────────────────────── Device Options ───────────────────────────

    def _process_device_options(self, serial, body):
        """Handle table=options POST — device reports its own capabilities.

        The device pushes a line like:
          FingerFunOn=1\tFaceFunOn=1\tMaxUserCount=3000\t...
        We log the capabilities and store key fields on the device record.
        Protocol section 8: server must respond OK.
        """
        device = self._find_device_by_serial(serial, remote_ip=request.httprequest.remote_addr)
        if device:
            self._register_heartbeat(device)

        _logger.info("ADMS OPTIONS SN=%s: %s", serial, body[:500] if body else '')

        if device and body:
            try:
                params = {}
                for part in body.strip().replace('\r\n', '\n').replace('\r', '\n').split('\n'):
                    for item in part.split('\t'):
                        if '=' in item:
                            k, _, v = item.partition('=')
                            params[k.strip()] = v.strip()

                _logger.info("ADMS OPTIONS SN=%s capabilities: %s", serial, params)
            except Exception as e:
                _logger.warning("ADMS OPTIONS parse error SN=%s: %s", serial, e)

        return self._make_response('OK')

    # ─────────────────────────── Heartbeat Ping ───────────────────────────

    @http.route('/iclock/ping', type='http', auth='none',
                csrf=False, methods=['GET', 'POST'], save_session=False)
    def ping(self, **kwargs):
        """Heartbeat endpoint called by device during large data uploads.

        Protocol section 10: device sends GET /iclock/ping?SN=xxx periodically
        while uploading large batches of records to keep the session alive.
        Responding with OK prevents session timeout and 404 errors that break uploads.
        """
        serial = kwargs.get('SN', '')
        device = self._find_device_by_serial(serial, remote_ip=request.httprequest.remote_addr)
        if device:
            self._register_heartbeat(device)
        _logger.debug("ADMS ping SN=%s", serial)
        return self._make_response('OK')

    # ─────────────────────────── Command Polling ───────────────────────────

    @http.route('/iclock/getrequest', type='http', auth='none',
                csrf=False, methods=['GET'], save_session=False)
    def getrequest(self, **kwargs):
        """Device polls here (~every Delay seconds) for pending commands.

        Returns the next queued command as ``C:{id}:{command_body}\\r\\n`` so the
        device executes it and reports back via /iclock/devicecmd. Returns plain
        'OK' when the queue is empty. The Date header is omitted (via
        _make_response) so the device cannot use it to sync its clock.

        Without this dispatch the ADMS/Hybrid control path (enroll fingerprint,
        sync/delete user, sync template, reboot, set-time) is queued but never
        delivered — the device only ever receives 'OK'.
        """
        serial = kwargs.get('SN', '')
        device = self._find_device_by_serial(
            serial, remote_ip=request.httprequest.remote_addr)

        if not device:
            return self._make_response('OK')

        self._register_heartbeat(device)

        # Next pending command for this device (oldest first).
        cmd_domain = [
            ('device_id', '=', device.id),
            ('status', '=', 'pending'),
        ]
        # Receive-only devices must never have their clock touched — never
        # dispatch a set_time command to them (defence in depth; OPERLOG also
        # refuses to queue set_time when adms_receive_only is set).
        if device.adms_receive_only:
            cmd_domain.append(('command_type', '!=', 'set_time'))

        commands = self._senv()['adms.device.command'].search(
            cmd_domain, order='create_date asc', limit=self._CMD_BATCH_SIZE)

        if commands:
            now = fields.Datetime.now()
            lines = []
            for cmd in commands:
                lines.append(cmd.format_for_device())
                cmd.write({
                    'status': 'sent',
                    'sent_time': now,
                    'dispatch_attempts': cmd.dispatch_attempts + 1,
                })
            _logger.info(
                "ADMS getrequest SN=%s: dispatching %d command(s) ids=%s",
                serial, len(commands), commands.mapped('command_id'))
            return self._make_response('\r\n'.join(lines) + '\r\n')

        # No pending commands
        return self._make_response('OK')

    # ─────────────────────────── Command Response ───────────────────────────

    @http.route('/iclock/devicecmd', type='http', auth='none',
                csrf=False, methods=['POST'], save_session=False)
    def devicecmd(self, **kwargs):
        """Device reports back the result of a command execution.
        Body format: ID=xxx&Return=0 (0=success)
        """
        serial = kwargs.get('SN', '')
        device = self._find_device_by_serial(serial, remote_ip=request.httprequest.remote_addr)

        if device:
            self._register_heartbeat(device)

        body = request.httprequest.data
        if isinstance(body, bytes):
            body = body.decode('utf-8', errors='replace')

        _logger.info("ADMS devicecmd SN=%s: %s", serial, body)

        # Parse command ID and result from response
        try:
            params = {}
            for part in body.strip().replace('&', '\n').split('\n'):
                if '=' in part:
                    key, _, value = part.partition('=')
                    params[key.strip()] = value.strip()

            cmd_id = int(params.get('ID', 0))
            return_code = int(params.get('Return', -1))

            if device and cmd_id:
                command = self._senv()['adms.device.command'].search([
                    ('device_id', '=', device.id),
                    ('command_id', '=', cmd_id),
                    ('status', '=', 'sent'),
                ], limit=1)
                if command:
                    command.write({
                        'status': 'done' if return_code == 0 else 'failed',
                        'done_time': fields.Datetime.now(),
                        'result': f'Return={return_code}',
                    })
        except Exception as e:
            _logger.error("ADMS devicecmd parse error: %s", e)

        return self._make_response('OK')
