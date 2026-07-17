# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class IrActionsActWindow(models.Model):
    _inherit = 'ir.actions.act_window'

    # Fields whose change may affect which models need a real-time
    # Automated Action (see `_kiosk_sync_automations`). Kept as a private
    # attribute so `create`/`write` only pay the sync cost when relevant.
    _KIOSK_SYNC_FIELDS = {'kiosk_enabled', 'kiosk_refresh_mode', 'res_model'}

    kiosk_enabled = fields.Boolean(
        string="Kiosk Mode",
        help="When enabled, this action can be opened full-screen (no menu, "
             "no breadcrumbs) at the Kiosk URL below, and will auto-refresh "
             "according to the selected Refresh Mode.",
    )
    kiosk_refresh_mode = fields.Selection(
        selection=[
            ('realtime', "Real Time (bus)"),
            ('interval', "Interval"),
            ('manual', "Manual"),
        ],
        string="Refresh Mode",
        default='realtime',
        help="Real Time: refreshes instantly through Odoo's bus whenever a "
             "record of this action's model is created, modified or "
             "deleted (an Automated Action is managed automatically).\n"
             "Interval: refreshes every 'Refresh Interval' seconds.\n"
             "Manual: never refreshes automatically.",
    )
    kiosk_refresh_interval = fields.Integer(
        string="Refresh Interval (seconds)",
        default=30,
        help="Used when Refresh Mode is 'Interval'. Also used as a "
             "safety-net refresh in 'Real Time' mode, in case a bus "
             "notification is ever missed.",
    )
    kiosk_hide_chat_window = fields.Boolean(
        string="Hide Chat Window",
        default=True,
        help="Suppress the floating Discuss chat window popups while this "
             "kiosk screen is active, so an incoming message to the "
             "logged-in kiosk user is never displayed on the wall screen.",
    )
    kiosk_url = fields.Char(
        string="Kiosk URL",
        compute='_compute_kiosk_url',
        help="Stable URL to open in the kiosk browser/launcher. Requires a "
             "logged-in Odoo session in that browser.",
    )

    @api.depends()
    def _compute_kiosk_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        for action in self:
            action.kiosk_url = f"{base_url}/web#action={action.id}" if action.id else False

    def _get_readable_fields(self):
        # /web/action/load filters the action dict through this allow-list
        # (see web/controllers/utils.py `clean_action`). Any real stored
        # field not listed here would silently never reach the browser.
        #
        # NOTE: the web client caches the action dict in memory per browser
        # tab (action_service.js `actionCache`, keyed by action id) until a
        # full page reload. So these values, once read from
        # `currentController.action`, can go stale if the action record is
        # edited afterwards in that same tab. JS code must NOT rely on them
        # for live kiosk-state decisions - use the `get_kiosk_state` method
        # below (called fresh on every action update) instead. These are
        # only kept readable here for convenience/debugging.
        return super()._get_readable_fields() | {
            'kiosk_enabled', 'kiosk_refresh_mode', 'kiosk_refresh_interval',
            'kiosk_hide_chat_window', 'kiosk_url',
        }

    @api.model
    def get_kiosk_state(self, action_id):
        """Always-fresh read of the kiosk fields for a given action id,
        bypassing both ir.model.access (via sudo, mirroring what the core
        `/web/action/load` controller already does for action definitions)
        and the web client's own action cache. Called by the kiosk JS
        client on every action update instead of trusting the (cacheable)
        `currentController.action` fields.
        """
        action = self.sudo().browse(int(action_id)).exists()
        if not action:
            return False
        return {
            'kiosk_enabled': action.kiosk_enabled,
            'kiosk_refresh_mode': action.kiosk_refresh_mode,
            'kiosk_refresh_interval': action.kiosk_refresh_interval,
            'kiosk_hide_chat_window': action.kiosk_hide_chat_window,
        }

    @api.constrains('kiosk_enabled', 'kiosk_refresh_mode', 'kiosk_refresh_interval')
    def _check_kiosk_refresh_interval(self):
        for action in self:
            if (
                action.kiosk_enabled
                and action.kiosk_refresh_mode == 'interval'
                and action.kiosk_refresh_interval <= 0
            ):
                raise ValidationError(_(
                    "The Kiosk refresh interval must be a positive number of seconds."
                ))

    @api.onchange('kiosk_enabled')
    def _onchange_kiosk_enabled(self):
        if self.kiosk_enabled and self.target != 'fullscreen':
            self.target = 'fullscreen'

    @api.model_create_multi
    def create(self, vals_list):
        actions = super().create(vals_list)
        if any(self._KIOSK_SYNC_FIELDS & vals.keys() for vals in vals_list):
            self._kiosk_sync_automations()
        return actions

    def write(self, vals):
        result = super().write(vals)
        if self._KIOSK_SYNC_FIELDS & vals.keys():
            self._kiosk_sync_automations()
        return result

    def unlink(self):
        had_kiosk = bool(self.filtered('kiosk_enabled'))
        result = super().unlink()
        if had_kiosk:
            self.env['ir.actions.act_window']._kiosk_sync_automations()
        return result

    @api.model
    def _kiosk_sync_automations(self):
        """Ensure exactly one pair of Automated Actions (save + delete)
        exists for every res_model currently used by a real-time kiosk
        action, and remove any pair that is no longer needed.

        Automations created by this method are tagged through
        `base.automation.kiosk_managed_model` so they can always be told
        apart from rules created manually by users.
        """
        Automation = self.env['base.automation'].sudo()
        needed_models = set(self.sudo().search([
            ('kiosk_enabled', '=', True),
            ('kiosk_refresh_mode', '=', 'realtime'),
        ]).mapped('res_model'))

        code = "env['ir.actions.act_window']._kiosk_notify(model._name)"
        for model_name in needed_models:
            self._kiosk_ensure_automation(
                model_name, 'on_create_or_write',
                _("[Kiosk] %(model)s \u2014 save", model=model_name), code,
            )
            self._kiosk_ensure_automation(
                model_name, 'on_unlink',
                _("[Kiosk] %(model)s \u2014 delete", model=model_name), code,
            )

        managed = Automation.search([('kiosk_managed_model', '!=', False)])
        obsolete = managed.filtered(lambda a: a.kiosk_managed_model not in needed_models)
        obsolete.unlink()

    @api.model
    def _kiosk_ensure_automation(self, model_name, trigger, name, code):
        Automation = self.env['base.automation'].sudo()
        existing = Automation.search([
            ('kiosk_managed_model', '=', model_name),
            ('trigger', '=', trigger),
        ], limit=1)
        if existing:
            return existing
        model = self.env['ir.model']._get(model_name)
        return Automation.create({
            'name': name,
            'model_id': model.id,
            'trigger': trigger,
            'kiosk_managed_model': model_name,
            'action_server_ids': [(0, 0, {
                'name': _("Kiosk bus notification"),
                'model_id': model.id,
                'state': 'code',
                'code': code,
            })],
        })

    @api.model
    def _kiosk_notify(self, res_model):
        """Called from the auto-managed Automated Actions to notify every
        kiosk screen currently watching `res_model` that it should
        refresh its data. The bus payload is intentionally signal-only
        (no record data): each kiosk client re-fetches with its own
        action's domain/context.
        """
        self.env['bus.bus']._sendone(
            f'kiosk_refresh-{res_model}', 'kiosk_refresh', {'model': res_model},
        )
