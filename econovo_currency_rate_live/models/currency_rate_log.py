# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class CurrencyRateLog(models.Model):
    """
    Stores execution history for currency rate source updates.
    Each record represents one execution attempt of a source.
    """
    _name = 'currency.rate.log'
    _description = 'Currency Rate Update Log'
    _order = 'execution_date desc, id desc'
    _rec_name = 'display_name'

    # Relationships
    source_id = fields.Many2one(
        'currency.rate.source',
        string='Source',
        required=True,
        ondelete='cascade',
        index=True,
    )
    source_currency_id = fields.Many2one(
        related='source_id.source_currency_id',
        store=True,
        index=True,
    )
    target_currency_id = fields.Many2one(
        related='source_id.target_currency_id',
        store=True,
        index=True,
    )

    # Execution info
    execution_date = fields.Datetime(
        string='Execution Date',
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    duration = fields.Float(
        string='Duration (seconds)',
        digits=(10, 3),
        help='Total execution time in seconds',
    )
    triggered_by = fields.Selection(
        selection=[
            ('manual', 'Manual'),
            ('cron', 'Scheduled'),
            ('test', 'Test'),
            ('fallback', 'Fallback'),
        ],
        string='Triggered By',
        default='manual',
    )
    triggered_by_source_id = fields.Many2one(
        'currency.rate.source',
        string='Triggered By Source',
        ondelete='set null',
        help='The source that triggered this execution via fallback',
    )

    # Extracted date information
    extracted_date = fields.Date(
        string='Extracted Date',
        help='Date extracted from the source (if date extraction is configured)',
    )
    date_extraction_used = fields.Boolean(
        string='Date Extraction Used',
        default=False,
        help='Whether date was extracted from source or used current date',
    )
    raw_date_value = fields.Char(
        string='Raw Date Value',
        help='Raw date string as extracted from the source before parsing',
    )

    # Result status
    state = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('warning', 'Warning'),
            ('error', 'Error'),
        ],
        string='Status',
        required=True,
        default='success',
        index=True,
    )

    # HTTP info
    http_status_code = fields.Integer(
        string='HTTP Status Code',
        help='HTTP response status code',
    )
    http_response_time = fields.Float(
        string='HTTP Response Time (s)',
        digits=(10, 3),
    )
    content_length = fields.Integer(
        string='Content Length',
        help='Size of the fetched content in bytes',
    )

    # Extraction results
    raw_value = fields.Char(
        string='Raw Extracted Value',
        help='Value as extracted before processing',
    )
    processed_rate = fields.Float(
        string='Processed Rate',
        digits=(16, 6),
        help='Final rate value after processing',
    )
    previous_rate = fields.Float(
        string='Previous Rate',
        digits=(16, 6),
        help='Rate before this update',
    )
    rate_variation = fields.Float(
        string='Rate Variation (%)',
        digits=(10, 4),
        compute='_compute_rate_variation',
        store=True,
        help='Percentage change from previous rate',
    )

    # Update statistics
    rates_created = fields.Integer(
        string='Rates Created',
        default=0,
    )
    rates_updated = fields.Integer(
        string='Rates Updated',
        default=0,
    )
    companies_affected = fields.Integer(
        string='Companies Affected',
        default=0,
    )

    # Error handling
    error_message = fields.Text(
        string='Error Message',
        help='Short error description',
    )
    error_traceback = fields.Text(
        string='Error Traceback',
        help='Full error traceback for debugging',
    )
    warning_message = fields.Text(
        string='Warning Message',
        help='Warning messages if any',
    )

    # Validation info
    validation_passed = fields.Boolean(
        string='Validation Passed',
        default=True,
    )
    validation_message = fields.Text(
        string='Validation Details',
        help='Details about validation checks',
    )

    # Content preview (for debugging)
    content_preview = fields.Text(
        string='Content Preview',
        help='First 2000 characters of fetched content',
    )

    display_name = fields.Char(
        compute='_compute_display_name',
        store=True,
    )

    @api.depends('source_id.name', 'execution_date', 'state')
    def _compute_display_name(self):
        for record in self:
            if record.source_id and record.execution_date:
                date_str = fields.Datetime.to_string(record.execution_date)[:16]
                record.display_name = f"{record.source_id.name} - {date_str}"
            else:
                record.display_name = f"Log #{record.id or 'New'}"

    @api.depends('processed_rate', 'previous_rate')
    def _compute_rate_variation(self):
        for record in self:
            if record.previous_rate and record.processed_rate:
                record.rate_variation = (
                    (record.processed_rate - record.previous_rate) / 
                    record.previous_rate * 100
                )
            else:
                record.rate_variation = 0.0

    def action_view_source(self):
        """Open the related source in form view."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'currency.rate.source',
            'res_id': self.source_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def cleanup_old_logs(self, days=30):
        """
        Remove logs older than specified days.
        Called by cron or manually.
        """
        cutoff_date = fields.Datetime.subtract(
            fields.Datetime.now(), 
            days=days
        )
        old_logs = self.search([
            ('execution_date', '<', cutoff_date)
        ])
        count = len(old_logs)
        old_logs.unlink()
        return count
