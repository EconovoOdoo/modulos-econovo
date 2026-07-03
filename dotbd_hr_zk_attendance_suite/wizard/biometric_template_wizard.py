# -*- coding: utf-8 -*-
import json
import base64
import logging
import threading
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from zk import ZK
    from zk.finger import Finger
    from zk.user import User
except ImportError:
    try:
        # pyzk2 fork — same submodules (finger, user), imports as 'pyzk2'.
        from pyzk2 import ZK
        from pyzk2.finger import Finger
        from pyzk2.user import User
    except ImportError:
        _logger.error("Neither 'pyzk' nor 'pyzk2' is installed — "
                      "PyZK fingerprint features unavailable.")

_BACKGROUND_THRESHOLD = 30  # users above this run in background thread


class BiometricTemplateWizard(models.TransientModel):
    """Minimal single-device fingerprint upload wizard.
    Used from the device form page — always uploads to device_id only.
    For multi-device bulk upload use bulk.template.wizard.
    """
    _name = 'biometric.template.wizard'
    _description = 'Fingerprint Upload Wizard'

    device_id = fields.Many2one('biometric.device.details', string="Device", required=True)
    file_data = fields.Binary('Fingerprint File (.json)', attachment=False)
    file_name = fields.Char('File Name')

    def action_process_upload(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_("Please select a fingerprint template file (.json)."))

        try:
            templates_data = json.loads(base64.b64decode(self.file_data).decode('utf-8'))
        except Exception as e:
            raise UserError(_("Could not read the file. Must be a valid JSON template file.\nError: %s") % e)

        if not isinstance(templates_data, list):
            raise UserError(_("Invalid file format — expected a list of users."))

        dev = self.device_id
        devices_info = [{
            'id': dev.id,
            'name': dev.name,
            'ip': dev.device_ip,
            'port': dev.port_number,
            'password': dev._get_device_password() if hasattr(dev, '_get_device_password') else (dev.device_password or 0),
        }]

        if len(templates_data) <= _BACKGROUND_THRESHOLD:
            results = self._run_upload(templates_data, devices_info, env=self.env)
            total = sum(r['uploaded'] for r in results)
            failed = sum(r['failed'] for r in results)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Upload Complete'),
                    'message': _('%(up)s templates uploaded to %(dev)s.', up=total, dev=dev.name),
                    'type': 'success' if not failed else 'warning',
                    'sticky': False,
                }
            }

        # Large dataset — background thread
        db = self.env.cr.dbname
        uid = self.env.uid
        est = round(len(templates_data) * 1.5 / 60, 1)
        threading.Thread(
            target=self._background_thread,
            args=(templates_data, devices_info, db, uid),
            daemon=True,
        ).start()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Upload Running in Background'),
                'message': _(
                    'Uploading %(u)s users to %(dev)s. ~%(t)s min. '
                    'Watch the device Chatter for live progress.',
                    u=len(templates_data), dev=dev.name, t=est,
                ),
                'type': 'info',
                'sticky': True,
            }
        }

    @staticmethod
    def _background_thread(templates_data, devices_info, db_name, uid):
        try:
            import odoo
            from odoo import api as odoo_api
            with odoo.registry(db_name).cursor() as cr:
                env = odoo_api.Environment(cr, uid, {})
                BiometricTemplateWizard._run_upload(
                    templates_data, devices_info, env=env, post_progress=True
                )
        except Exception:
            _logger.exception("Background PyZK upload failed.")

    @staticmethod
    def _run_upload(templates_data, devices_info, env, post_progress=False):
        results = []
        for dev in devices_info:
            device_rec = env['biometric.device.details'].browse(dev['id'])
            zk = ZK(dev['ip'], port=dev['port'], timeout=300,
                    password=dev['password'], ommit_ping=True)
            conn = device_rec.device_connect(zk)
            if not conn:
                device_rec.message_post(body=f"Fingerprint upload: could not connect.", message_type='notification')
                results.append({'name': dev['name'], 'uploaded': 0, 'failed': 0})
                continue

            uploaded = failed = skipped = 0
            total = len(templates_data)
            try:
                conn.disable_device()
                _logger.info("PyZK fingerprint upload START on '%s' — %d user(s) to process",
                             dev['name'], total)
                for idx, user_data in enumerate(templates_data, 1):
                    user_id = user_data.get('user_id')
                    name = user_data.get('name', '')
                    fingers = user_data.get('templates', [])
                    if not user_id:
                        skipped += 1
                        _logger.info("[%d/%d] SKIP — empty user_id (name=%s)", idx, total, name)
                        continue
                    try:
                        uid_int = int(user_id) if str(user_id).isdigit() else 0
                        if uid_int <= 0:
                            skipped += 1
                            _logger.info("[%d/%d] SKIP — non-numeric user_id %r (name=%s)",
                                         idx, total, user_id, name)
                            continue
                        _logger.info("[%d/%d] Uploading uid=%s name='%s' (%d template(s))...",
                                     idx, total, uid_int, name, len(fingers))
                        conn.set_user(uid=uid_int, name=name[:24], user_id=str(user_id))
                        finger_objs = []
                        for t in fingers:
                            try:
                                finger_objs.append(Finger(
                                    uid=uid_int, fid=t.get('fid', 0), valid=1,
                                    template=base64.b64decode(t['template_data'])
                                ))
                            except Exception as _fe:
                                _logger.warning("[%d/%d] uid=%s: bad template fid=%s skipped: %s",
                                                idx, total, uid_int, t.get('fid'), _fe)
                        if finger_objs:
                            conn.save_user_template(User(uid=uid_int, name=name[:24], privilege=0, user_id=str(user_id)), finger_objs)
                            uploaded += len(finger_objs)
                            _logger.info("[%d/%d] OK — uid=%s '%s': %d template(s) uploaded",
                                         idx, total, uid_int, name, len(finger_objs))
                        else:
                            _logger.info("[%d/%d] uid=%s '%s': user set but no valid templates to upload",
                                         idx, total, uid_int, name)
                    except Exception as e:
                        failed += len(fingers)
                        _logger.warning("[%d/%d] FAILED — uid=%s '%s' on %s: %s",
                                        idx, total, user_id, name, dev['name'], e)

                    if post_progress and idx % 10 == 0:
                        device_rec.message_post(
                            body=f"Uploading fingerprints: {idx}/{total} users done, {uploaded} templates...",
                            message_type='notification',
                        )
                        env.cr.commit()
            finally:
                try:
                    conn.enable_device()
                except Exception:
                    pass
                conn.disconnect()

            _logger.info("PyZK fingerprint upload DONE on '%s' — uploaded=%d failed=%d skipped=%d (of %d users)",
                         dev['name'], uploaded, failed, skipped, total)
            device_rec.message_post(
                body=f"Fingerprint upload done: {uploaded} templates uploaded" +
                     (f", {failed} failed" if failed else "") +
                     (f", {skipped} skipped" if skipped else "") + ".",
                message_type='notification',
            )
            if post_progress:
                env.cr.commit()
            results.append({'name': dev['name'], 'uploaded': uploaded, 'failed': failed})
        return results
