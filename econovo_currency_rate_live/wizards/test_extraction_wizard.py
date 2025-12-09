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
    extracted_fragment = fields.Text(
        string='Extracted Fragment',
        help='The portion of content that matched the extraction pattern',
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

    # Date Extraction Results
    extract_date_enabled = fields.Boolean(
        related='source_id.extract_date',
        string='Date Extraction Enabled',
        readonly=True,
    )
    extracted_date = fields.Date(
        string='Extracted Date',
        help='Date extracted from the source content',
    )
    raw_extracted_date = fields.Char(
        string='Raw Date Value',
        help='Date string as extracted before parsing',
    )
    date_extraction_error = fields.Char(
        string='Date Extraction Error',
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
    source_currency_id = fields.Many2one(
        related='source_id.source_currency_id',
        readonly=True,
    )
    target_currency_id = fields.Many2one(
        related='source_id.target_currency_id',
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
                ('currency_id', '=', source.source_currency_id.id),
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
            
            # Extract value and get the matched fragment for debugging
            raw_value = source._extract_value(content)
            
            if not raw_value:
                raise ValueError(f'Could not extract value using {source.extraction_method} method')
            
            self.raw_extracted_value = raw_value
            
            # Extract fragment with context (100 chars before and after the value)
            self.extracted_fragment = self._get_extraction_fragment(
                content, raw_value, source.extraction_method
            )
            
            # Process value
            processed_value = source._process_value(raw_value)
            
            if not processed_value:
                raise ValueError(f'Could not process extracted value: {raw_value}')
            
            self.processed_rate = processed_value
            self.current_rate = current_rate
            
            # Extract date if enabled
            if source.extract_date:
                try:
                    # _extract_date now returns tuple (date, raw_value)
                    extracted_date, raw_date_value = source._extract_date(content)
                    self.extracted_date = extracted_date
                    self.raw_extracted_date = raw_date_value or ''
                except Exception as date_err:
                    self.date_extraction_error = str(date_err)
                    self.extracted_date = fields.Date.today()
            
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

    def _get_extraction_fragment(self, content, extracted_value, method):
        """
        Get a fragment of the content showing the extracted value in context.
        Shows approximately 150 characters before and after the extracted value.
        """
        import re
        
        if not content or not extracted_value:
            return ''
        
        # Escape special regex characters in the extracted value
        escaped_value = re.escape(str(extracted_value))
        
        # Try to find the value in the content
        match = re.search(escaped_value, content)
        
        if not match:
            # If exact match not found, return just the value
            return f"Extracted value: {extracted_value}"
        
        start_pos = match.start()
        end_pos = match.end()
        
        # Get context around the match (150 chars before and after)
        context_chars = 150
        fragment_start = max(0, start_pos - context_chars)
        fragment_end = min(len(content), end_pos + context_chars)
        
        # Extract the fragment
        fragment = content[fragment_start:fragment_end]
        
        # Add ellipsis if truncated
        prefix = '...' if fragment_start > 0 else ''
        suffix = '...' if fragment_end < len(content) else ''
        
        # Mark the extracted value in the fragment
        # Find position of value in fragment
        value_start_in_fragment = start_pos - fragment_start
        value_end_in_fragment = end_pos - fragment_start
        
        # Build result with markers
        result = (
            f"{prefix}{fragment[:value_start_in_fragment]}"
            f">>>{fragment[value_start_in_fragment:value_end_in_fragment]}<<<"
            f"{fragment[value_end_in_fragment:]}{suffix}"
        )
        
        return result

    def _get_raw_date_value(self, content, source):
        """Extract raw date string before parsing, for display purposes."""
        import re
        import json
        from lxml import etree
        
        method = source.date_extraction_method or 'regex'
        
        try:
            if method == 'regex' and source.date_regex:
                match = re.search(source.date_regex, content)
                if match:
                    return match.group(1) if match.groups() else match.group(0)
                    
            elif method == 'xpath' and source.date_xpath:
                tree = etree.HTML(content)
                results = tree.xpath(source.date_xpath)
                if results:
                    return str(results[0]).strip()
                    
            elif method == 'jsonpath' and source.date_jsonpath:
                try:
                    from jsonpath_ng import parse
                    data = json.loads(content)
                    jsonpath_expr = parse(source.date_jsonpath)
                    matches = [m.value for m in jsonpath_expr.find(data)]
                    if matches:
                        return str(matches[0]).strip()
                except ImportError:
                    pass
                    
            elif method == 'css' and source.date_css_selector:
                try:
                    from lxml.cssselect import CSSSelector
                    tree = etree.HTML(content)
                    selector = CSSSelector(source.date_css_selector)
                    results = selector(tree)
                    if results:
                        return results[0].text_content().strip()
                except ImportError:
                    pass
        except Exception:
            pass
        
        return ''
