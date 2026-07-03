# -*- coding: utf-8 -*-
import json
import base64
import logging
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# How many records to insert per DB transaction batch
_BATCH_SIZE = 50


class AdmsTemplateWizard(models.TransientModel):
    _name = 'adms.template.wizard'
    _description = 'ADMS Biometric Template Manager'

    state = fields.Selection([
        ('download', 'Ready to Download'),
        ('upload', 'Upload File'),
    ], string="Mode", default='upload')

    file_data = fields.Binary('Template File', attachment=False)
    file_name = fields.Char('File Name')
    summary = fields.Text('Result', readonly=True)
    template_ids = fields.Many2many('biometric.fp.template', string='Templates to Export')

    # Devices to sync to right after upload
    device_ids = fields.Many2many(
        'biometric.device.details',
        'adms_template_wizard_device_rel',
        'wizard_id', 'device_id',
        string="Sync to Devices",
        help="After importing, immediately queue templates to these devices via ADMS command queue.",
    )
    # True when opened from a single device page — hides device selection in view
    single_device_mode = fields.Boolean(default=False)

    # ─────────────────────────────────────────────
    #  Download: DB → JSON file
    # ─────────────────────────────────────────────

    def action_download_json(self):
        """Export stored ADMS biometric templates to a JSON file for download."""
        self.ensure_one()
        if not self.template_ids:
            self.template_ids = self.env['biometric.fp.template'].search([])

        if not self.template_ids:
            raise UserError(_(
                "No biometric templates are stored in Odoo yet.\n\n"
                "Templates are saved automatically when a device sends BIODATA "
                "(face, fingerprint, palm) over ADMS. Make sure your device is "
                "connected and employees have enrolled their biometrics."
            ))

        export_data = []
        skipped = 0
        for tmpl in self.template_ids:
            pin = tmpl.employee_id.device_id_num if tmpl.employee_id else None
            if not pin:
                skipped += 1
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
            raise UserError(_("No templates could be exported — employees are missing PIN numbers."))

        json_bytes = json.dumps(export_data, indent=2).encode('utf-8')
        self.write({
            'state': 'download',
            'file_data': base64.b64encode(json_bytes),
            'file_name': 'adms_biometric_templates.json',
            'summary': (
                f"{len(export_data)} template(s) exported."
                + (f" {skipped} skipped (no employee PIN)." if skipped else "")
            ),
        })

        return {
            'name': _('Download ADMS Templates'),
            'type': 'ir.actions.act_window',
            'res_model': 'adms.template.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    # ─────────────────────────────────────────────
    #  Upload: JSON file → DB → (optional) device sync
    # ─────────────────────────────────────────────

    def action_process_upload(self):
        """
        Import ADMS JSON into biometric.fp.template, then optionally queue
        a DATA UPDATE BIODATA command to selected devices.

        For large files (500+ templates) we batch inserts in groups of
        _BATCH_SIZE and commit after each batch so no single transaction
        locks the table for too long.
        """
        self.ensure_one()
        if not self.file_data:
            raise UserError(_("Please select a biometric template file (.json) first."))

        try:
            file_content = base64.b64decode(self.file_data).decode('utf-8')
            templates_data = json.loads(file_content)
        except Exception as e:
            raise UserError(_("Could not read the file. Make sure it is a valid JSON template file.\nError: %s") % e)

        if not isinstance(templates_data, list):
            raise UserError(_("Invalid file format. Expected a list of templates."))

        Template = self.env['biometric.fp.template']
        Employee = self.env['hr.employee']

        imported = updated = skipped = 0
        batch_vals = []   # collect creates for bulk insert
        batch_updates = []  # (record, vals) for bulk write

        for t_data in templates_data:
            pin = t_data.get('pin')
            tmp_data = t_data.get('template_data')
            if not pin or not tmp_data:
                skipped += 1
                continue

            employee = Employee.search([('device_id_num', '=', str(pin))], limit=1)
            if not employee:
                skipped += 1
                continue

            tmpl_type = t_data.get('template_type', 'finger')
            fid = int(t_data.get('finger_index', 0))
            sz = int(t_data.get('template_size', len(tmp_data)))

            vals = {
                'employee_id': employee.id,
                'template_type': tmpl_type,
                'finger_index': fid,
                'template_data': tmp_data,
                'template_size': sz,
            }

            existing = Template.search([
                ('employee_id', '=', employee.id),
                ('template_type', '=', tmpl_type),
                ('finger_index', '=', fid),
            ], limit=1)

            if existing:
                batch_updates.append((existing, vals))
                updated += 1
            else:
                batch_vals.append(vals)
                imported += 1

            # Flush batch every _BATCH_SIZE records to keep transactions short
            if (imported + updated) % _BATCH_SIZE == 0:
                if batch_vals:
                    Template.create(batch_vals)
                    batch_vals = []
                for rec, v in batch_updates:
                    rec.write(v)
                batch_updates = []
                self.env.cr.commit()

        # Flush remaining
        if batch_vals:
            Template.create(batch_vals)
        for rec, v in batch_updates:
            rec.write(v)

        # ── Sync to selected devices (queues ADMS commands) ──
        synced_to = []
        sync_warning = ''
        if self.device_ids and (imported + updated) > 0:
            all_templates = Template.search([])
            for device in self.device_ids:
                try:
                    all_templates.with_context(target_device_id=device.id).action_sync_to_adms_devices()
                    synced_to.append(device.name)
                except Exception as e:
                    _logger.warning("Auto-sync to device %s failed: %s", device.name, e)
            if synced_to:
                sync_warning = (
                    "\n\nNote: ADMS sync uses a command queue. "
                    "Devices will receive templates on their next poll (~30 seconds)."
                )

        total = imported + updated
        summary_parts = [
            f"{imported} new template(s) added, {updated} updated.",
        ]
        if skipped:
            summary_parts.append(f"{skipped} entries skipped (employee PIN not found in Odoo).")
        if synced_to:
            summary_parts.append(f"Queued for sync to: {', '.join(synced_to)}.")

        self.write({
            'summary': ' '.join(summary_parts) + sync_warning,
            'state': 'download',
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import Complete'),
                'message': _(
                    '%(total)s templates imported/updated.'
                    '%(sync)s',
                    total=total,
                    sync=(' Syncing to ' + ', '.join(synced_to) + ' via ADMS queue.') if synced_to else
                         ' Go to ADMS Stored Biometrics to sync manually.',
                ),
                'type': 'success' if total > 0 else 'warning',
                'sticky': False,
            }
        }
