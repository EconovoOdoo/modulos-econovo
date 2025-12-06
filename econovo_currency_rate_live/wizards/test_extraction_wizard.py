# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
import logging
import time
import traceback

_logger = logging.getLogger(__name__)


class TestExtractionWizard(models.TransientModel):
    """
    Wizard to test extraction configuration without saving to currency rates.
    Useful for debugging and validating configuration before activation.
    """
    _name = 'currency.rate.source.test.wizard'
    _description = 'Test Currency Rate Extraction'

    source_id = fields.Many2one(
        'currency.rate.source',
        string='Source',
        required=True,
        readonly=True,
    )

    # Test Results
    test_executed = fields.Boolean(
        string='Test Executed',
        default=False,
    )
    test_success = fields.Boolean(
        string='Test Success',
        default=False,
    )
    test_duration = fields.Float(
        string='Duration (seconds)',
        digits=(10, 3),
    )

    # HTTP Results
    http_status_code = fields.Integer(
        string='HTTP Status Code',
    )
    http_response_time = fields.Float(
        string='HTTP Response Time (s)',
        digits=(10, 3),
    )
    content_length = fields.Integer(
        string='Content Length',
    )
    content_preview = fields.Text(
        string='Content Preview',
        help='First 5000 characters of the fetched content',
    )

    # Extraction Results
    raw_extracted_value = fields.Char(
        string='Raw Extracted Value',
        help='Value as extracted before processing',
    )
    processed_rate = fields.Float(
        string='Processed Rate',
        digits=(16, 6),
    )
    current_rate = fields.Float(
        string='Current Rate',
        digits=(16, 6),
        help='Current rate for comparison',
    )
    rate_difference = fields.Float(
        string='Rate Difference',
        digits=(16, 6),
        compute='_compute_rate_difference',
    )
    rate_variation_percent = fields.Float(
        string='Variation (%)',
        digits=(10, 4),
        compute='_compute_rate_difference',
    )

    # Validation Results
    validation_passed = fields.Boolean(
        string='Validation Passed',
        default=True,
    )
    validation_messages = fields.Text(
        string='Validation Details',
    )

    # Error Information
    error_message = fields.Text(
        string='Error Message',
    )
    error_traceback = fields.Text(
        string='Error Traceback',
    )

    # Display fields
    source_url = fields.Char(
        related='source_id.url',
        readonly=True,
    )
    extraction_method = fields.Selection(
        related='source_id.extraction_method',
        readonly=True,
    )
    currency_id = fields.Many2one(
        related='source_id.currency_id',
        readonly=True,
    )

    @api.depends('processed_rate', 'current_rate')
    def _compute_rate_difference(self):
        for record in self:
            if record.processed_rate and record.current_rate:
                record.rate_difference = record.processed_rate - record.current_rate
                record.rate_variation_percent = (
                    record.rate_difference / record.current_rate * 100
                )
            else:
                record.rate_difference = 0.0
                record.rate_variation_percent = 0.0

    def action_test(self):
        """Execute the extraction test."""
        self.ensure_one()
        source = self.source_id
        
        start_time = time.time()
        
        try:
            # Get current rate for comparison
            current_rate_record = self.env['res.currency.rate'].search([
                ('currency_id', '=', source.currency_id.id),
                ('company_id', '=', self.env.company.id),
            ], order='name desc', limit=1)
            
            current_rate = current_rate_record.inverse_company_rate if current_rate_record else 0.0
            
            # Fetch content
            content, http_status, response_time = source._fetch_content()
            
            self.http_status_code = http_status
            self.http_response_time = response_time
            self.content_length = len(content) if content else 0
            self.content_preview = content[:5000] if content else ''
            
            if not content:
                raise ValueError('No content received from URL')
            
            # Extract value
            raw_value = source._extract_value(content)
            
            if not raw_value:
                raise ValueError(f'Could not extract value using {source.extraction_method} method')
            
            self.raw_extracted_value = raw_value
            
            # Process value
            processed_value = source._process_value(raw_value)
            
            if not processed_value:
                raise ValueError(f'Could not process extracted value: {raw_value}')
            
            self.processed_rate = processed_value
            self.current_rate = current_rate
            
            # Validate
            validation_result = source._validate_rate(processed_value)
            self.validation_passed = validation_result.get('valid', True)
            
            validation_messages = []
            if validation_result.get('warnings'):
                validation_messages.extend(validation_result['warnings'])
            if validation_result.get('errors'):
                validation_messages.extend(validation_result['errors'])
            self.validation_messages = '\n'.join(validation_messages) if validation_messages else 'All validations passed'
            
            self.test_success = True
            self.error_message = ''
            self.error_traceback = ''
            
        except Exception as e:
            self.test_success = False
            self.error_message = str(e)
            self.error_traceback = traceback.format_exc()
            _logger.exception('Test extraction failed for source %s', source.name)
        
        finally:
            self.test_duration = time.time() - start_time
            self.test_executed = True
        
        # Return the wizard to show results
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_close(self):
        """Close the wizard."""
        return {'type': 'ir.actions.act_window_close'}

    def action_apply_to_source(self):
        """
        Execute actual update using source's action_update_rate.
        Only available after successful test.
        """
        self.ensure_one()
        if self.test_success:
            return self.source_id.action_update_rate()
        return {'type': 'ir.actions.act_window_close'}

    def action_view_source(self):
        """Open the source in form view."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'currency.rate.source',
            'res_id': self.source_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
