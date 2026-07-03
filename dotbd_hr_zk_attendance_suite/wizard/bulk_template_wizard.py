# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, _
from odoo.exceptions import UserError
from .biometric_template_wizard import BiometricTemplateWizard

_logger = logging.getLogger(__name__)


class BulkTemplateWizard(models.TransientModel):
    """Multi-device fingerprint upload wizard.
    Used from the ZKTeco Devices list view — user picks a file and selects
    which devices to upload to. Reuses BiometricTemplateWizard._run_upload.
    """
    _name = 'bulk.template.wizard'
    _description = 'Bulk Fingerprint Upload Wizard'

    device_ids = fields.Many2many(
        'biometric.device.details',
        'bulk_template_wizard_device_rel',
        'wizard_id', 'device_id',
        string="Target Devices",
        required=True,
    )
    file_data = fields.Binary('Fingerprint File (.json)', attachment=False)
    file_name = fields.Char('File Name')

    def action_process_upload(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_("Please select a fingerprint template file (.json)."))
        if not self.device_ids:
            raise UserError(_("Please select at least one target device."))

        import json, base64, threading
        try:
            templates_data = json.loads(base64.b64decode(self.file_data).decode('utf-8'))
        except Exception as e:
            raise UserError(_("Could not read the file.\nError: %s") % e)

        if not isinstance(templates_data, list):
            raise UserError(_("Invalid file format — expected a list of users."))

        devices_info = [
            {
                'id': d.id,
                'name': d.name,
                'ip': d.device_ip,
                'port': d.port_number,
                'password': d._get_device_password() if hasattr(d, '_get_device_password') else (d.device_password or 0),
            }
            for d in self.device_ids
        ]

        user_count = len(templates_data)
        from .biometric_template_wizard import _BACKGROUND_THRESHOLD

        if user_count <= _BACKGROUND_THRESHOLD:
            results = BiometricTemplateWizard._run_upload(templates_data, devices_info, env=self.env)
            total = sum(r['uploaded'] for r in results)
            failed = sum(r['failed'] for r in results)
            lines = ', '.join(f"{r['name']}: {r['uploaded']} uploaded" for r in results)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Bulk Upload Complete'),
                    'message': _(f'{total} templates uploaded. {lines}'),
                    'type': 'success' if not failed else 'warning',
                    'sticky': False,
                }
            }

        # Large — background thread
        db = self.env.cr.dbname
        uid = self.env.uid
        est = round(user_count * len(devices_info) * 1.5 / 60, 1)
        threading.Thread(
            target=BiometricTemplateWizard._background_thread,
            args=(templates_data, devices_info, db, uid),
            daemon=True,
        ).start()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk Upload Running in Background'),
                'message': _(
                    f'Uploading {user_count} users to {len(devices_info)} device(s). '
                    f'~{est} min. Check each device Chatter for progress.'
                ),
                'type': 'info',
                'sticky': True,
            }
        }
