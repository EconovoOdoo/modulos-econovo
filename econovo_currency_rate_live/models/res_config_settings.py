# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Currency Rate Live Settings
    module_econovo_currency_rate_live = fields.Boolean(
        string='Enable Currency Rate Live Updates',
        help='Enable automatic currency rate updates from external sources',
    )

    currency_rate_live_log_retention_days = fields.Integer(
        string='Log Retention (Days)',
        default=30,
        config_parameter='econovo_currency_rate_live.log_retention_days',
        help='Number of days to keep execution logs. Older logs are automatically deleted.',
    )

    currency_rate_live_default_timeout = fields.Integer(
        string='Default HTTP Timeout',
        default=30,
        config_parameter='econovo_currency_rate_live.default_timeout',
        help='Default timeout in seconds for HTTP requests',
    )

    currency_rate_live_max_retries = fields.Integer(
        string='Max Retries',
        default=3,
        config_parameter='econovo_currency_rate_live.max_retries',
        help='Maximum number of retry attempts for failed requests',
    )

    currency_rate_live_enable_notifications = fields.Boolean(
        string='Enable Notifications',
        default=True,
        config_parameter='econovo_currency_rate_live.enable_notifications',
        help='Send notifications on errors or important events',
    )

    currency_rate_live_notify_on_error = fields.Boolean(
        string='Notify on Errors',
        default=True,
        config_parameter='econovo_currency_rate_live.notify_on_error',
        help='Create activity when a rate update fails',
    )

    currency_rate_live_notify_on_high_variation = fields.Boolean(
        string='Notify on High Variation',
        default=True,
        config_parameter='econovo_currency_rate_live.notify_on_high_variation',
        help='Create activity when rate variation exceeds threshold',
    )

    currency_rate_live_variation_threshold = fields.Float(
        string='Variation Threshold (%)',
        default=10.0,
        config_parameter='econovo_currency_rate_live.variation_threshold',
        help='Percentage variation that triggers notification',
    )

    currency_rate_live_sources_count = fields.Integer(
        string='Active Sources',
        compute='_compute_sources_count',
    )

    @api.depends()
    def _compute_sources_count(self):
        Source = self.env['currency.rate.source']
        for record in self:
            record.currency_rate_live_sources_count = Source.search_count([
                ('active', '=', True)
            ])

    def action_open_currency_rate_sources(self):
        """Open the currency rate sources list."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Currency Rate Sources',
            'res_model': 'currency.rate.source',
            'view_mode': 'tree,kanban,form',
            'target': 'current',
        }

    def action_cleanup_old_logs(self):
        """Manually trigger log cleanup."""
        Log = self.env['currency.rate.log']
        days = self.currency_rate_live_log_retention_days or 30
        deleted_count = Log.cleanup_old_logs(days=days)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Log Cleanup Complete',
                'message': f'{deleted_count} old log entries deleted.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_update_all_rates_now(self):
        """Manually trigger update for all active sources."""
        Source = self.env['currency.rate.source']
        sources = Source.search([
            ('active', '=', True),
            ('state', '=', 'active'),
        ])
        success_count = 0
        error_count = 0
        for source in sources:
            try:
                source.action_update_rate()
                if source.last_status == 'success':
                    success_count += 1
                else:
                    error_count += 1
            except Exception:
                error_count += 1
        
        message_type = 'success' if error_count == 0 else 'warning'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Rate Update Complete',
                'message': f'Updated: {success_count}, Errors: {error_count}',
                'type': message_type,
                'sticky': False,
            }
        }
