# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.onchange('type')
    def _onchange_type(self):
        # sale_project resets service_tracking to 'no' as soon as the type is
        # not 'service'. Since tracking is allowed on any product type here,
        # keep whatever the user already configured.
        service_tracking = self.service_tracking
        res = super()._onchange_type()
        self.service_tracking = service_tracking
        return res

    def write(self, vals):
        # sale_project.write() also force-resets service_tracking/project_id to
        # 'no'/False whenever 'type' is saved as anything but 'service' (the
        # server-side counterpart of the onchange reset handled above). Capture
        # the current configuration beforehand so it can be restored afterwards.
        to_restore = self._get_service_tracking_to_restore(vals)
        res = super().write(vals)
        self._restore_service_tracking(to_restore)
        return res

    def _get_service_tracking_to_restore(self, vals):
        if 'type' not in vals or vals['type'] == 'service':
            return {}
        if 'service_tracking' in vals or 'project_id' in vals or 'project_template_id' in vals:
            # The caller is explicitly managing tracking in this same write, let it win.
            return {}
        return {
            record.id: (record.service_tracking, record.project_id.id, record.project_template_id.id)
            for record in self if record.service_tracking != 'no'
        }

    def _restore_service_tracking(self, to_restore):
        for record in self:
            restore = to_restore.get(record.id)
            if not restore:
                continue
            service_tracking, project_id, project_template_id = restore
            record.write({
                'service_tracking': service_tracking,
                'project_id': project_id if service_tracking == 'task_global_project' else False,
                'project_template_id': project_template_id if service_tracking in ('task_in_project', 'project_only') else False,
            })
