# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from zk import ZK
except ImportError:
    try:
        from pyzk2 import ZK
    except ImportError:
        _logger.error("Please install the 'pyzk' or 'pyzk2' library.")


class ZkImportUsersWizard(models.TransientModel):
    """Wizard to preview and import employees from ZKTeco device."""
    _name = 'zk.import.users.wizard'
    _description = 'Import Employees from ZKTeco Device'

    device_id = fields.Many2one('biometric.device.details', string='Device', readonly=True)
    line_ids = fields.One2many('zk.import.users.wizard.line', 'wizard_id', string='Device Users')
    total_count = fields.Integer(string='Total on Device', compute='_compute_counts')
    new_count = fields.Integer(string='New', compute='_compute_counts')
    existing_count = fields.Integer(string='Already in Odoo', compute='_compute_counts')
    selected_count = fields.Integer(string='Selected', compute='_compute_counts')

    @api.depends('line_ids', 'line_ids.is_selected', 'line_ids.status')
    def _compute_counts(self):
        for rec in self:
            rec.total_count = len(rec.line_ids)
            rec.new_count = len(rec.line_ids.filtered(lambda l: l.status == 'new'))
            rec.existing_count = len(rec.line_ids.filtered(lambda l: l.status == 'exists'))
            rec.selected_count = len(rec.line_ids.filtered(lambda l: l.is_selected))

    def action_select_all_new(self):
        self.line_ids.filtered(lambda l: l.status == 'new').write({'is_selected': True})

    def action_deselect_all(self):
        self.line_ids.write({'is_selected': False})

    def action_import_selected(self):
        """Create hr.employee records for selected new users."""
        self.ensure_one()
        selected = self.line_ids.filtered(lambda l: l.is_selected and l.status == 'new')
        if not selected:
            raise UserError(_("No new users selected for import."))

        created = 0
        for line in selected:
            self.env['hr.employee'].create({
                'name': line.name or f'Device User {line.pin}',
                'device_id_num': line.pin,
                'company_id': self.device_id.company_id.id,
            })
            created += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import Complete'),
                'message': _(f'{created} employee(s) imported successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }


class ZkImportUsersWizardLine(models.TransientModel):
    _name = 'zk.import.users.wizard.line'
    _description = 'ZKTeco Device User Line'
    _order = 'pin asc'

    wizard_id = fields.Many2one('zk.import.users.wizard', ondelete='cascade')
    pin = fields.Char(string='Device ID (PIN)', readonly=True)
    name = fields.Char(string='Name on Device', readonly=True)
    privilege = fields.Selection([
        ('0', 'User'),
        ('14', 'Administrator'),
    ], string='Role', readonly=True)
    status = fields.Selection([
        ('new', 'New'),
        ('exists', 'Already in Odoo'),
    ], string='Status', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Linked Employee', readonly=True)
    is_selected = fields.Boolean(string='Import', default=False)
