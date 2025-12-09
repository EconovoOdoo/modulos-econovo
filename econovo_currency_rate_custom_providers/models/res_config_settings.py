# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Custom Rate Providers Settings - Main toggle
    currency_rate_custom_providers_enabled = fields.Boolean(
        string='Enable Econovo Custom Rate Providers',
        config_parameter='econovo_currency_rate_custom_providers.enabled',
        help='Enable automatic currency rate updates from external sources (websites, APIs).\n\n'
             'When enabled, each source with "Automatic Update" will have its own dedicated '
             'scheduled action that runs exactly at the configured time.',
    )

    currency_rate_custom_providers_log_retention_days = fields.Integer(
        string='Log Retention (Days)',
        default=30,
        config_parameter='econovo_currency_rate_custom_providers.log_retention_days',
        help='Number of days to keep execution logs. Older logs are automatically deleted.',
    )

    currency_rate_custom_providers_default_timeout = fields.Integer(
        string='Default HTTP Timeout',
        default=30,
        config_parameter='econovo_currency_rate_custom_providers.default_timeout',
        help='Default timeout in seconds for HTTP requests',
    )

    currency_rate_custom_providers_max_retries = fields.Integer(
        string='Max Retries',
        default=3,
        config_parameter='econovo_currency_rate_custom_providers.max_retries',
        help='Maximum number of retry attempts for failed requests',
    )

    currency_rate_custom_providers_enable_notifications = fields.Boolean(
        string='Enable Notifications',
        default=True,
        config_parameter='econovo_currency_rate_custom_providers.enable_notifications',
        help='Send notifications on errors or important events',
    )

    currency_rate_custom_providers_notify_on_error = fields.Boolean(
        string='Notify on Errors',
        default=True,
        config_parameter='econovo_currency_rate_custom_providers.notify_on_error',
        help='Create activity when a rate update fails',
    )

    currency_rate_custom_providers_notify_on_high_variation = fields.Boolean(
        string='Notify on High Variation',
        default=True,
        config_parameter='econovo_currency_rate_custom_providers.notify_on_high_variation',
        help='Create activity when rate variation exceeds threshold',
    )

    currency_rate_custom_providers_variation_threshold = fields.Float(
        string='Variation Threshold (%)',
        default=10.0,
        config_parameter='econovo_currency_rate_custom_providers.variation_threshold',
        help='Percentage variation that triggers notification',
    )

    currency_rate_custom_providers_sources_count = fields.Integer(
        string='Active Sources',
        compute='_compute_sources_count',
    )

    currency_rate_custom_providers_crons_count = fields.Integer(
        string='Active Scheduled Actions',
        compute='_compute_crons_count',
    )

    @api.depends()
    def _compute_sources_count(self):
        Source = self.env['currency.rate.source']
        for record in self:
            record.currency_rate_custom_providers_sources_count = Source.search_count([
                ('active', '=', True)
            ])

    @api.depends()
    def _compute_crons_count(self):
        Source = self.env['currency.rate.source']
        for record in self:
            record.currency_rate_custom_providers_crons_count = Source.search_count([
                ('active', '=', True),
                ('auto_update', '=', True),
                ('cron_id', '!=', False),
            ])

    def set_values(self):
        """Override to update all source crons when module enabled state changes."""
        # Get previous enabled state
        was_enabled = self.env['ir.config_parameter'].sudo().get_param(
            'econovo_currency_rate_custom_providers.enabled', 'False'
        ) == 'True'
        
        res = super().set_values()
        
        # Get new enabled state
        is_enabled = self.env['ir.config_parameter'].sudo().get_param(
            'econovo_currency_rate_custom_providers.enabled', 'False'
        ) == 'True'
        
        # Update all source crons if enabled state changed
        if was_enabled != is_enabled:
            self.env['currency.rate.source']._update_all_source_crons(enabled=is_enabled)
        
        return res

    def action_open_currency_rate_sources(self):
        """Open the currency rate sources list."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Currency Rate Sources',
            'res_model': 'currency.rate.source',
            'view_mode': 'tree,kanban,form',
            'target': 'current',
        }

    def action_open_currency_rate_crons(self):
        """Open the list of currency rate scheduled actions."""
        Source = self.env['currency.rate.source']
        cron_ids = Source.search([
            ('cron_id', '!=', False)
        ]).mapped('cron_id').ids
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Currency Rate Scheduled Actions',
            'res_model': 'ir.cron',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', cron_ids)],
            'target': 'current',
        }

    def action_cleanup_old_logs(self):
        """Manually trigger log cleanup."""
        Log = self.env['currency.rate.log']
        days = self.currency_rate_custom_providers_log_retention_days or 30
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

    def action_recreate_all_crons(self):
        """Recreate all source crons. Useful for fixing broken cron configurations."""
        Source = self.env['currency.rate.source']
        sources = Source.search([
            ('active', '=', True),
            ('auto_update', '=', True),
        ])
        
        created_count = 0
        updated_count = 0
        
        for source in sources:
            if source.cron_id:
                source._update_source_cron()
                updated_count += 1
            else:
                source._create_source_cron()
                created_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Crons Synchronized',
                'message': f'Created: {created_count}, Updated: {updated_count}',
                'type': 'success',
                'sticky': False,
            }
        }