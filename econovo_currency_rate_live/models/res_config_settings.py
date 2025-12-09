# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Currency Rate Live Settings - Main toggle
    currency_rate_live_enabled = fields.Boolean(
        string='Enable Econovo Currency Rate Live',
        config_parameter='econovo_currency_rate_live.enabled',
        help='Enable automatic currency rate updates from external sources (websites, APIs)',
    )

    currency_rate_live_cron_interval = fields.Selection(
        selection=[
            ('5', 'Every 5 minutes'),
            ('10', 'Every 10 minutes'),
            ('15', 'Every 15 minutes'),
            ('30', 'Every 30 minutes'),
            ('60', 'Every hour'),
        ],
        string='Check Interval',
        default='15',
        config_parameter='econovo_currency_rate_live.cron_interval',
        help='How often the system checks if any source needs to run.\n\n'
             'This is NOT the update frequency - it is how often the scheduler '
             'looks for sources that are due.\n\n'
             'Example: If a source is configured to run at 09:30 and Check Interval '
             'is 15 minutes, the scheduler will detect it between 09:30 and 09:45.\n\n'
             'Tip: Use 15 minutes for a good balance between precision and performance.',
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

    def set_values(self):
        """Override to update cron settings when config changes."""
        res = super().set_values()
        self._update_cron_settings()
        return res

    def _update_cron_settings(self):
        """Update cron job based on configuration."""
        cron = self.env.ref(
            'econovo_currency_rate_live.ir_cron_update_currency_rates',
            raise_if_not_found=False
        )
        if not cron:
            return
        
        # Get config values
        enabled = self.env['ir.config_parameter'].sudo().get_param(
            'econovo_currency_rate_live.enabled', 'False'
        ) == 'True'
        interval = int(self.env['ir.config_parameter'].sudo().get_param(
            'econovo_currency_rate_live.cron_interval', '15'
        ))
        
        # Update cron
        cron.sudo().write({
            'active': enabled,
            'interval_number': interval,
            'interval_type': 'minutes',
        })

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
