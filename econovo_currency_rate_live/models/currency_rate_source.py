# -*- coding: utf-8 -*-

import json
import logging
import re
import traceback
from datetime import datetime, timedelta

import requests
from lxml import etree

# CSS Selector support (optional)
try:
    from lxml.cssselect import CSSSelector
    HAS_CSSSELECT = True
except ImportError:
    HAS_CSSSELECT = False
    CSSSelector = None

# JSONPath support (optional)
try:
    from jsonpath_ng import parse as jsonpath_parse
    HAS_JSONPATH = True
except ImportError:
    HAS_JSONPATH = False
    jsonpath_parse = None

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Decimal format configurations
DECIMAL_FORMATS = {
    'es_AR': {'thousand': '.', 'decimal': ','},  # 1.234,56
    'en_US': {'thousand': ',', 'decimal': '.'},  # 1,234.56
    'de_DE': {'thousand': '.', 'decimal': ','},  # 1.234,56
    'fr_FR': {'thousand': ' ', 'decimal': ','},  # 1 234,56
    'ch_CH': {"thousand": "'", 'decimal': '.'},  # 1'234.56
    'in_IN': {'thousand': ',', 'decimal': '.'},  # 1,23,456.78
}


class CurrencyRateSource(models.Model):
    _name = 'currency.rate.source'
    _description = 'Currency Rate Source'
    _order = 'sequence, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # === GENERAL FIELDS ===
    name = fields.Char(
        string='Name',
        required=True,
        tracking=True,
        help='Descriptive name for this rate source'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Lower values have higher priority'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        tracking=True,
        help='Target currency to update rates for'
    )
    notes = fields.Text(
        string='Notes',
        help='Internal notes about this source'
    )

    # === COMPANY CONFIGURATION ===
    update_all_companies = fields.Boolean(
        string='Update All Companies',
        default=True,
        help='If checked, updates rates for all companies without a parent company'
    )
    company_ids = fields.Many2many(
        'res.company',
        string='Companies',
        help='Specific companies to update (only if "Update All Companies" is unchecked)'
    )

    # === HTTP CONFIGURATION ===
    url = fields.Char(
        string='URL',
        required=True,
        tracking=True,
        help='Full URL of the source (must include http:// or https://)'
    )
    http_method = fields.Selection(
        [('GET', 'GET'), ('POST', 'POST')],
        string='HTTP Method',
        default='GET'
    )
    http_timeout = fields.Integer(
        string='Timeout (seconds)',
        default=30,
        help='Maximum time to wait for response'
    )
    http_retries = fields.Integer(
        string='Retries',
        default=3,
        help='Number of retry attempts on failure'
    )
    http_user_agent = fields.Char(
        string='User-Agent',
        default='Mozilla/5.0 (compatible; OdooCurrencyBot/1.0)',
        help='User-Agent header for HTTP requests'
    )
    http_headers = fields.Text(
        string='Additional Headers (JSON)',
        help='Additional HTTP headers in JSON format, e.g.: {"Accept": "text/html"}'
    )
    http_body = fields.Text(
        string='Request Body',
        help='Request body for POST requests'
    )

    # === RESPONSE TYPE ===
    response_type = fields.Selection(
        [
            ('html', 'HTML'),
            ('json', 'JSON'),
            ('xml', 'XML'),
            ('text', 'Plain Text'),
        ],
        string='Response Type',
        default='html',
        required=True,
        help='Expected format of the response'
    )

    # === EXTRACTION METHOD ===
    extraction_method = fields.Selection(
        [
            ('auto', 'Automatic Detection'),
            ('regex', 'Regular Expression'),
            ('xpath', 'XPath'),
            ('jsonpath', 'JSONPath'),
            ('css', 'CSS Selector'),
        ],
        string='Extraction Method',
        default='regex',
        required=True,
        tracking=True,
        help='Method to extract the rate value from the response'
    )

    # === REGEX CONFIGURATION ===
    regex_pattern = fields.Char(
        string='Regex Pattern',
        help='Regular expression pattern with capture groups. Example: USD.*?([0-9.,]+)'
    )
    regex_group = fields.Integer(
        string='Capture Group',
        default=1,
        help='Which capture group contains the rate value (1-indexed)'
    )
    regex_flag_ignorecase = fields.Boolean(
        string='Ignore Case',
        default=True,
        help='Make pattern case-insensitive'
    )
    regex_flag_multiline = fields.Boolean(
        string='Multiline',
        default=False,
        help='Make ^ and $ match line boundaries'
    )
    regex_flag_dotall = fields.Boolean(
        string='Dotall',
        default=False,
        help='Make . match newline characters'
    )

    # === XPATH CONFIGURATION ===
    xpath_expression = fields.Char(
        string='XPath Expression',
        help='XPath expression to select element. Example: //table[@id="rates"]//tr[2]/td[3]'
    )
    xpath_attribute = fields.Char(
        string='XPath Attribute',
        help='Attribute to extract (leave empty for text content)'
    )
    xpath_result_index = fields.Integer(
        string='Result Index',
        default=1,
        help='Which result to use if XPath returns multiple elements (1-indexed)'
    )

    # === JSONPATH CONFIGURATION ===
    jsonpath_expression = fields.Char(
        string='JSONPath Expression',
        help='JSONPath expression. Example: $.data.rates.USD.sell'
    )
    jsonpath_result_index = fields.Integer(
        string='Result Index',
        default=1,
        help='Which result to use if JSONPath returns multiple values (1-indexed)'
    )

    # === CSS SELECTOR CONFIGURATION ===
    css_selector = fields.Char(
        string='CSS Selector',
        help='CSS selector. Example: #rate-usd, .price-value, table.rates td:nth-child(3)'
    )
    css_attribute = fields.Char(
        string='CSS Attribute',
        help='Attribute to extract (leave empty for text content)'
    )
    css_result_index = fields.Integer(
        string='Result Index',
        default=1,
        help='Which result to use if selector returns multiple elements (1-indexed)'
    )

    # === AUTO DETECTION CONFIGURATION ===
    auto_keyword = fields.Char(
        string='Search Keyword',
        help='Keyword to search for when using automatic detection (e.g., "USD", "Bitcoin")'
    )

    # === VALUE PROCESSING ===
    decimal_format = fields.Selection(
        [
            ('es_AR', 'Argentine/Spanish (1.234,56)'),
            ('en_US', 'US/International (1,234.56)'),
            ('de_DE', 'German (1.234,56)'),
            ('fr_FR', 'French (1 234,56)'),
            ('ch_CH', "Swiss (1'234.56)"),
            ('in_IN', 'Indian (1,23,456.78)'),
        ],
        string='Number Format',
        default='es_AR',
        required=True,
        help='Format used by the source for decimal numbers'
    )
    value_multiplier = fields.Float(
        string='Multiplier',
        default=1.0,
        help='Multiply extracted value by this factor (e.g., 0.01 if value is in cents)'
    )
    invert_rate = fields.Boolean(
        string='Invert Rate',
        default=False,
        help='If the source provides inverse rate (e.g., foreign per local instead of local per foreign)'
    )

    # === VALIDATION ===
    min_valid_rate = fields.Float(
        string='Minimum Valid Rate',
        default=0.0,
        help='Reject rates below this value (0 = no minimum)'
    )
    max_valid_rate = fields.Float(
        string='Maximum Valid Rate',
        default=0.0,
        help='Reject rates above this value (0 = no maximum)'
    )
    max_variation_percent = fields.Float(
        string='Max Variation (%)',
        default=0.0,
        help='Maximum percentage change from last rate (0 = no limit)'
    )
    on_validation_fail = fields.Selection(
        [
            ('skip', 'Skip Update'),
            ('log_error', 'Log Error and Skip'),
            ('use_last', 'Use Last Valid Rate'),
        ],
        string='On Validation Failure',
        default='log_error',
        help='Action to take when extracted rate fails validation'
    )

    # === DATE EXTRACTION ===
    extract_date = fields.Boolean(
        string='Extract Date from Source',
        default=False,
        help='Extract rate date from source instead of using current date'
    )
    date_regex_pattern = fields.Char(
        string='Date Regex Pattern',
        help='Regex pattern to extract date. Example: (\\d{2}/\\d{2}/\\d{4})'
    )
    date_format = fields.Char(
        string='Date Format',
        default='%d/%m/%Y',
        help='Python strptime format for parsing date. Example: %d/%m/%Y'
    )

    # === SCHEDULING ===
    auto_update = fields.Boolean(
        string='Automatic Update',
        default=True,
        tracking=True,
        help='Enable scheduled automatic updates'
    )
    update_interval = fields.Selection(
        [
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
        ],
        string='Update Interval',
        default='daily'
    )
    update_hours = fields.Char(
        string='Update Hours',
        default='11,15',
        help='Comma-separated hours (24h format) when to run updates. Example: 9,12,18'
    )
    update_weekdays = fields.Char(
        string='Update Weekdays',
        default='0,1,2,3,4',
        help='Comma-separated weekdays (0=Monday, 6=Sunday). Example: 0,1,2,3,4 for weekdays'
    )
    next_execution = fields.Datetime(
        string='Next Scheduled Execution',
        compute='_compute_next_execution',
        store=True
    )

    # === STATUS (computed) ===
    state = fields.Selection(
        [
            ('draft', 'Not Tested'),
            ('active', 'Active'),
            ('error', 'Error'),
        ],
        string='Status',
        default='draft',
        compute='_compute_state',
        store=True,
        tracking=True
    )
    last_sync_date = fields.Datetime(
        string='Last Sync',
        readonly=True
    )
    last_rate = fields.Float(
        string='Last Rate',
        readonly=True,
        digits=(16, 6)
    )
    last_raw_value = fields.Char(
        string='Last Raw Value',
        readonly=True
    )
    last_error = fields.Text(
        string='Last Error',
        readonly=True
    )
    last_status = fields.Selection(
        [
            ('success', 'Success'),
            ('warning', 'Warning'),
            ('error', 'Error'),
        ],
        string='Last Status',
        readonly=True,
        help='Status of the last synchronization attempt'
    )
    last_http_response = fields.Text(
        string='Last HTTP Response',
        readonly=True,
        help='Stored for debugging purposes'
    )

    # === STATISTICS ===
    execution_count = fields.Integer(
        string='Total Executions',
        readonly=True,
        default=0
    )
    success_count = fields.Integer(
        string='Successful Executions',
        readonly=True,
        default=0
    )
    error_count = fields.Integer(
        string='Failed Executions',
        readonly=True,
        default=0
    )
    success_rate = fields.Float(
        string='Success Rate (%)',
        compute='_compute_success_rate',
        digits=(5, 2)
    )
    color = fields.Integer(
        string='Color Index',
        default=0,
        help='Kanban color index'
    )

    # === RELATIONS ===
    log_ids = fields.One2many(
        'currency.rate.log',
        'source_id',
        string='Execution Logs'
    )
    log_count = fields.Integer(
        string='Log Count',
        compute='_compute_log_count'
    )

    # === CONSTRAINTS ===
    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Source name must be unique!'),
        ('url_required', 'CHECK(url IS NOT NULL)', 'URL is required!'),
    ]

    # ==========================================
    # COMPUTE METHODS
    # ==========================================

    @api.depends('execution_count', 'success_count')
    def _compute_success_rate(self):
        for record in self:
            if record.execution_count > 0:
                record.success_rate = (record.success_count / record.execution_count) * 100
            else:
                record.success_rate = 0.0

    @api.depends('log_ids')
    def _compute_log_count(self):
        for record in self:
            record.log_count = len(record.log_ids)

    @api.depends('last_error', 'last_sync_date', 'active')
    def _compute_state(self):
        for record in self:
            if not record.active:
                record.state = 'draft'
            elif record.last_error:
                record.state = 'error'
            elif record.last_sync_date:
                record.state = 'active'
            else:
                record.state = 'draft'

    @api.depends('auto_update', 'update_interval', 'update_hours', 'update_weekdays')
    def _compute_next_execution(self):
        for record in self:
            if not record.auto_update:
                record.next_execution = False
                continue
            # Simple calculation - will be refined by cron
            record.next_execution = fields.Datetime.now() + timedelta(hours=1)

    # ==========================================
    # VALIDATION METHODS
    # ==========================================

    @api.constrains('url')
    def _check_url(self):
        for record in self:
            if record.url and not record.url.startswith(('http://', 'https://')):
                raise ValidationError(_('URL must start with http:// or https://'))

    @api.constrains('regex_pattern', 'extraction_method')
    def _check_regex_pattern(self):
        for record in self:
            if record.extraction_method == 'regex' and record.regex_pattern:
                try:
                    re.compile(record.regex_pattern)
                except re.error as e:
                    raise ValidationError(_('Invalid regex pattern: %s') % str(e))

    @api.constrains('http_headers')
    def _check_http_headers(self):
        for record in self:
            if record.http_headers:
                try:
                    json.loads(record.http_headers)
                except json.JSONDecodeError as e:
                    raise ValidationError(_('Invalid JSON in HTTP headers: %s') % str(e))

    # ==========================================
    # ACTION METHODS
    # ==========================================

    def action_test_extraction(self):
        """Test the extraction without saving rates."""
        self.ensure_one()
        return {
            'name': _('Test Extraction'),
            'type': 'ir.actions.act_window',
            'res_model': 'currency.rate.source.test.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_source_id': self.id,
            },
        }

    def action_update_rates(self):
        """Manually trigger rate update."""
        self.ensure_one()
        return self._execute_update()

    def action_view_logs(self):
        """Open log view for this source."""
        self.ensure_one()
        return {
            'name': _('Execution Logs'),
            'type': 'ir.actions.act_window',
            'res_model': 'currency.rate.log',
            'view_mode': 'tree,form',
            'domain': [('source_id', '=', self.id)],
            'context': {'default_source_id': self.id},
        }

    def action_view_rates(self):
        """Open currency rates for this source's currency."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Rates for {self.currency_id.name}',
            'res_model': 'res.currency.rate',
            'view_mode': 'tree,form',
            'domain': [('currency_id', '=', self.currency_id.id)],
            'context': {'default_currency_id': self.currency_id.id},
        }

    def action_clear_error(self):
        """Clear last error status."""
        self.ensure_one()
        self.write({
            'last_error': False,
        })
        return True

    def action_activate(self):
        """Activate the source."""
        self.ensure_one()
        self.state = 'active'
        return True

    def action_pause(self):
        """Pause the source."""
        self.ensure_one()
        self.state = 'paused'
        return True

    def action_update_rate(self):
        """Manual trigger for rate update."""
        self.ensure_one()
        return self._execute_update()

    # ==========================================
    # MAIN EXECUTION METHODS
    # ==========================================

    def _execute_update(self):
        """Execute rate update and create/update currency rates."""
        self.ensure_one()
        
        log_vals = {
            'source_id': self.id,
            'execution_date': fields.Datetime.now(),
        }
        
        start_time = datetime.now()
        
        try:
            # Fetch content
            content, http_status, response_time = self._fetch_content()
            log_vals['http_status_code'] = http_status
            log_vals['http_response_size'] = len(content) if content else 0
            
            # Store response for debugging (truncated)
            self.last_http_response = content[:10000] if content else ''
            
            # Extract value
            raw_value = self._extract_value(content)
            log_vals['raw_value'] = raw_value
            
            # Process value
            rate = self._process_value(raw_value)
            log_vals['processed_rate'] = rate
            
            # Validate rate
            validation_result = self._validate_rate(rate)
            if validation_result.get('rate') != rate:
                rate = validation_result['rate']
                log_vals['processed_rate'] = rate
            
            # Extract date if configured
            rate_date = self._extract_date(content) if self.extract_date else fields.Date.today()
            
            # Update currency rates
            created, updated = self._update_currency_rates(rate, rate_date)
            log_vals['rates_created'] = created
            log_vals['rates_updated'] = updated
            
            # Update source status
            self.write({
                'last_sync_date': fields.Datetime.now(),
                'last_rate': rate,
                'last_raw_value': raw_value,
                'last_error': False,
                'last_status': 'success',
                'execution_count': self.execution_count + 1,
                'success_count': self.success_count + 1,
            })
            
            log_vals['state'] = 'success'
            
        except Exception as e:
            error_msg = str(e)
            error_tb = traceback.format_exc()
            
            self.write({
                'last_error': error_msg,
                'last_status': 'error',
                'execution_count': self.execution_count + 1,
                'error_count': self.error_count + 1,
            })
            
            log_vals['state'] = 'error'
            log_vals['error_message'] = error_msg
            log_vals['error_traceback'] = error_tb
            
            _logger.error('Currency rate update failed for %s: %s', self.name, error_msg)
        
        finally:
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            log_vals['duration'] = duration
            
            # Create log entry
            self.env['currency.rate.log'].create(log_vals)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rate Update'),
                'message': _('Rate updated successfully: %s') % self.last_rate if not self.last_error else _('Update failed: %s') % self.last_error,
                'type': 'success' if not self.last_error else 'danger',
                'sticky': False,
            }
        }

    def _fetch_content(self):
        """Fetch content from URL.
        
        Returns:
            tuple: (content, status_code, response_time_seconds)
        """
        self.ensure_one()
        import time
        
        headers = {
            'User-Agent': self.http_user_agent or 'Mozilla/5.0 (compatible; OdooCurrencyBot/1.0)',
        }
        
        # Add custom headers
        if self.http_headers:
            try:
                custom_headers = json.loads(self.http_headers)
                headers.update(custom_headers)
            except json.JSONDecodeError:
                pass
        
        # Execute request with retries
        last_error = None
        for attempt in range(self.http_retries or 1):
            try:
                start_time = time.time()
                if self.http_method == 'POST':
                    response = requests.post(
                        self.url,
                        headers=headers,
                        data=self.http_body,
                        timeout=self.http_timeout or 30
                    )
                else:
                    response = requests.get(
                        self.url,
                        headers=headers,
                        timeout=self.http_timeout or 30
                    )
                response_time = time.time() - start_time
                
                response.raise_for_status()
                return response.text, response.status_code, response_time
                
            except requests.RequestException as e:
                last_error = e
                _logger.warning(
                    'Request attempt %d/%d failed for %s: %s',
                    attempt + 1, self.http_retries, self.url, str(e)
                )
        
        raise UserError(_('Failed to fetch URL after %d attempts: %s') % (
            self.http_retries, str(last_error)
        ))

    def _extract_value(self, content):
        """Extract rate value from content using configured method."""
        self.ensure_one()
        
        if self.extraction_method == 'auto':
            return self._extract_auto(content)
        elif self.extraction_method == 'regex':
            return self._extract_regex(content)
        elif self.extraction_method == 'xpath':
            return self._extract_xpath(content)
        elif self.extraction_method == 'jsonpath':
            return self._extract_jsonpath(content)
        elif self.extraction_method == 'css':
            return self._extract_css(content)
        else:
            raise UserError(_('Unknown extraction method: %s') % self.extraction_method)

    def _extract_auto(self, content):
        """Automatically detect and extract rate value."""
        keyword = self.auto_keyword or self.currency_id.name
        currency_code = self.currency_id.name if self.currency_id else ''
        
        # Currency-specific keywords mapping
        currency_keywords = {
            'USD': ['dolar', 'dollar', 'usd', 'u.s.a', 'u.s.d', 'us$', '$'],
            'EUR': ['euro', 'eur', '€'],
            'GBP': ['libra', 'pound', 'gbp', 'sterling', '£'],
            'BRL': ['real', 'brl', 'r$'],
            'ARS': ['peso', 'ars', '$'],
            'CLP': ['peso chileno', 'clp'],
            'UYU': ['peso uruguayo', 'uyu'],
            'MXN': ['peso mexicano', 'mxn'],
            'JPY': ['yen', 'jpy', '¥'],
            'CNY': ['yuan', 'cny', 'rmb', '¥'],
            'CHF': ['franco suizo', 'chf', 'swiss franc'],
            'CAD': ['dolar canadiense', 'cad', 'canadian dollar'],
            'AUD': ['dolar australiano', 'aud', 'australian dollar'],
        }
        
        # Build list of keywords to try
        keywords_to_try = [keyword]
        if currency_code in currency_keywords:
            keywords_to_try.extend(currency_keywords[currency_code])
        
        # Common exchange rate patterns (for sell/buy rates)
        # Pattern looks for: keyword ... number ... number (compra/venta pattern)
        for kw in keywords_to_try:
            # Pattern for table-like data: keyword followed by two numbers (buy/sell)
            # Example: "Dolar U.S.A | 1410,00 | 1460,00"
            pattern = rf'{re.escape(kw)}[^\d]{{0,50}}?([\d]+[.,][\d]+)[^\d]{{0,30}}?([\d]+[.,][\d]+)'
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                # Return the second value (typically "sell" rate for foreign currency)
                return match.group(2).strip()
        
        # Simpler pattern: keyword followed by any number
        for kw in keywords_to_try:
            pattern = rf'{re.escape(kw)}[^\d]{{0,100}}?([\d]+[.,][\d]+)'
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        # Fallback: numbers followed by keyword
        for kw in keywords_to_try:
            pattern = rf'([\d]+[.,][\d]+)[^\d]{{0,30}}?{re.escape(kw)}'
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        raise UserError(_('Could not auto-detect value for currency: %s (tried keywords: %s)') % (
            currency_code, ', '.join(keywords_to_try[:5])
        ))

    def _extract_regex(self, content):
        """Extract value using regular expression."""
        if not self.regex_pattern:
            raise UserError(_('Regex pattern is required'))
        
        # Build flags
        flags = 0
        if self.regex_flag_ignorecase:
            flags |= re.IGNORECASE
        if self.regex_flag_multiline:
            flags |= re.MULTILINE
        if self.regex_flag_dotall:
            flags |= re.DOTALL
        
        # Execute regex
        match = re.search(self.regex_pattern, content, flags)
        
        if not match:
            raise UserError(_('Regex pattern did not match: %s') % self.regex_pattern)
        
        # Extract specified group
        group_num = self.regex_group or 1
        
        if group_num > len(match.groups()):
            raise UserError(_('Capture group %d not found. Pattern has %d groups.') % (
                group_num, len(match.groups())
            ))
        
        return match.group(group_num)

    def _extract_xpath(self, content):
        """Extract value using XPath selector."""
        if not self.xpath_expression:
            raise UserError(_('XPath expression is required'))
        
        # Parse HTML
        try:
            tree = etree.HTML(content)
        except Exception as e:
            raise UserError(_('Failed to parse HTML: %s') % str(e))
        
        # Execute XPath
        results = tree.xpath(self.xpath_expression)
        
        if not results:
            raise UserError(_('XPath returned no results: %s') % self.xpath_expression)
        
        # Select by index
        index = (self.xpath_result_index or 1) - 1
        if index >= len(results):
            raise UserError(_('Index %d out of range. XPath returned %d results.') % (
                index + 1, len(results)
            ))
        
        element = results[index]
        
        # Extract value
        if self.xpath_attribute:
            value = element.get(self.xpath_attribute)
            if value is None:
                raise UserError(_("Attribute '%s' not found on element") % self.xpath_attribute)
        elif isinstance(element, str):
            value = element
        else:
            value = element.text or ''
            if not value.strip():
                value = etree.tostring(element, method='text', encoding='unicode').strip()
        
        return value

    def _extract_jsonpath(self, content):
        """Extract value using JSONPath expression."""
        if not self.jsonpath_expression:
            raise UserError(_('JSONPath expression is required'))
        
        # Parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise UserError(_('Invalid JSON response: %s') % str(e))
        
        # Try using jsonpath-ng if available
        if HAS_JSONPATH:
            try:
                jsonpath_expr = jsonpath_parse(self.jsonpath_expression)
                matches = jsonpath_expr.find(data)
                
                if not matches:
                    raise UserError(_('JSONPath returned no results: %s') % self.jsonpath_expression)
                
                index = (self.jsonpath_result_index or 1) - 1
                if index >= len(matches):
                    raise UserError(_('Index %d out of range. JSONPath returned %d results.') % (
                        index + 1, len(matches)
                    ))
                
                return str(matches[index].value)
            except Exception as e:
                raise UserError(_('JSONPath error: %s') % str(e))
        else:
            # Fallback: basic implementation for simple expressions
            return self._extract_jsonpath_basic(data)

    def _extract_jsonpath_basic(self, data):
        """Basic JSONPath implementation for simple expressions like $.a.b.c"""
        expr = self.jsonpath_expression
        
        # Remove $ prefix
        if expr.startswith('$.'):
            expr = expr[2:]
        elif expr.startswith('$'):
            expr = expr[1:]
        
        # Navigate structure
        current = data
        for part in expr.split('.'):
            if not part:
                continue
                
            # Handle array index: property[0]
            if '[' in part:
                prop, rest = part.split('[', 1)
                idx = int(rest.rstrip(']'))
                if prop:
                    current = current[prop]
                current = current[idx]
            else:
                current = current[part]
        
        return str(current)

    def _extract_css(self, content):
        """Extract value using CSS selector."""
        if not HAS_CSSSELECT:
            raise UserError(_('CSS selector extraction requires the cssselect package. '
                            'Install it with: pip install cssselect'))
        
        if not self.css_selector:
            raise UserError(_('CSS selector is required'))
        
        # Parse HTML
        try:
            tree = etree.HTML(content)
        except Exception as e:
            raise UserError(_('Failed to parse HTML: %s') % str(e))
        
        # Convert CSS to XPath and execute
        try:
            selector = CSSSelector(self.css_selector)
            results = selector(tree)
        except Exception as e:
            raise UserError(_('Invalid CSS selector: %s') % str(e))
        
        if not results:
            raise UserError(_('CSS selector returned no results: %s') % self.css_selector)
        
        # Select by index
        index = (self.css_result_index or 1) - 1
        if index >= len(results):
            raise UserError(_('Index %d out of range. Selector returned %d results.') % (
                index + 1, len(results)
            ))
        
        element = results[index]
        
        # Extract value
        if self.css_attribute:
            value = element.get(self.css_attribute)
            if value is None:
                raise UserError(_("Attribute '%s' not found on element") % self.css_attribute)
        else:
            value = element.text or ''
            if not value.strip():
                value = etree.tostring(element, method='text', encoding='unicode').strip()
        
        return value

    def _process_value(self, raw_value):
        """Process raw extracted value into float rate."""
        if not raw_value:
            raise UserError(_('Extracted value is empty'))
        
        # Clean the value
        value = raw_value.strip()
        
        # Remove common non-numeric prefixes/suffixes
        value = re.sub(r'^[^\d\s.,\'-]+', '', value)
        value = re.sub(r'[^\d\s.,\'-]+$', '', value)
        value = value.strip()
        
        # Get decimal format configuration
        fmt = DECIMAL_FORMATS.get(self.decimal_format, DECIMAL_FORMATS['en_US'])
        
        # Remove thousand separators and normalize decimal
        if fmt['thousand']:
            value = value.replace(fmt['thousand'], '')
        if fmt['decimal'] != '.':
            value = value.replace(fmt['decimal'], '.')
        
        # Remove any remaining whitespace
        value = value.replace(' ', '')
        
        try:
            rate = float(value)
        except ValueError:
            raise UserError(_('Could not convert value to number: %s') % raw_value)
        
        # Apply multiplier
        if self.value_multiplier and self.value_multiplier != 1.0:
            rate *= self.value_multiplier
        
        # Invert if needed
        if self.invert_rate and rate != 0:
            rate = 1.0 / rate
        
        return rate

    def _validate_rate(self, rate):
        """Validate extracted rate against configured limits.
        
        Returns:
            dict: {'valid': bool, 'warnings': list, 'errors': list, 'rate': float}
        """
        result = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'rate': rate,
        }
        
        # Check minimum
        if self.min_valid_rate and rate < self.min_valid_rate:
            result['errors'].append(_('Rate %s is below minimum %s') % (rate, self.min_valid_rate))
        
        # Check maximum
        if self.max_valid_rate and rate > self.max_valid_rate:
            result['errors'].append(_('Rate %s is above maximum %s') % (rate, self.max_valid_rate))
        
        # Check variation from last rate
        if self.max_variation_percent and self.last_rate:
            variation = abs((rate - self.last_rate) / self.last_rate) * 100
            if variation > self.max_variation_percent:
                result['errors'].append(_('Rate variation %.2f%% exceeds maximum %.2f%%') % (
                    variation, self.max_variation_percent
                ))
        
        if result['errors']:
            result['valid'] = False
            error_msg = '\n'.join(result['errors'])
            if self.on_validation_fail == 'skip':
                raise UserError(error_msg)
            elif self.on_validation_fail == 'log_error':
                result['warnings'].append(_('Validation failed but continuing: %s') % error_msg)
            elif self.on_validation_fail == 'use_last':
                if self.last_rate:
                    result['rate'] = self.last_rate
                    result['warnings'].append(_('Using last rate due to validation failure'))
                else:
                    raise UserError(error_msg)
        
        return result

    def _extract_date(self, content):
        """Extract rate date from content."""
        if not self.date_regex_pattern:
            return fields.Date.today()
        
        match = re.search(self.date_regex_pattern, content)
        if not match:
            _logger.warning('Date pattern not found, using today')
            return fields.Date.today()
        
        date_str = match.group(1) if match.groups() else match.group(0)
        
        try:
            parsed_date = datetime.strptime(date_str, self.date_format or '%d/%m/%Y')
            return parsed_date.date()
        except ValueError:
            _logger.warning('Could not parse date %s, using today', date_str)
            return fields.Date.today()

    def _update_currency_rates(self, rate, rate_date):
        """Create or update currency rates for configured companies."""
        CurrencyRate = self.env['res.currency.rate']
        
        # Get companies to update
        if self.update_all_companies:
            companies = self.env['res.company'].search([
                '|',
                ('parent_id', '=', False),
                ('parent_id.parent_id', '=', False),
            ])
        else:
            companies = self.company_ids
        
        if not companies:
            raise UserError(_('No companies configured for rate update'))
        
        created = 0
        updated = 0
        
        for company in companies:
            # Search for existing rate
            existing = CurrencyRate.search([
                ('currency_id', '=', self.currency_id.id),
                ('company_id', '=', company.id),
                ('name', '=', rate_date),
            ], limit=1)
            
            # Calculate the technical rate (inverse for Odoo)
            # Odoo stores rates as: 1 company_currency = X foreign_currency
            # So if we have 1 USD = 1045 ARS, and company currency is ARS
            # The rate should be 1/1045 = 0.000957
            # But inverse_company_rate stores the direct value (1045)
            
            if existing:
                existing.write({
                    'inverse_company_rate': rate,
                })
                updated += 1
            else:
                CurrencyRate.create({
                    'currency_id': self.currency_id.id,
                    'company_id': company.id,
                    'name': rate_date,
                    'inverse_company_rate': rate,
                })
                created += 1
        
        _logger.info(
            'Updated currency rates for %s: %d created, %d updated',
            self.currency_id.name, created, updated
        )
        
        return created, updated

    # ==========================================
    # CRON METHODS
    # ==========================================

    @api.model
    def _cron_update_rates(self):
        """Cron job to update rates for all active sources."""
        sources = self.search([
            ('active', '=', True),
            ('auto_update', '=', True),
        ])
        
        now = fields.Datetime.now()
        current_hour = now.hour
        current_weekday = now.weekday()
        
        for source in sources:
            try:
                # Check if should run based on schedule
                if not source._should_run_now(current_hour, current_weekday):
                    continue
                
                _logger.info('Running scheduled update for source: %s', source.name)
                source._execute_update()
                
            except Exception as e:
                _logger.error('Scheduled update failed for %s: %s', source.name, str(e))

    def _should_run_now(self, current_hour, current_weekday):
        """Check if source should run at current time."""
        # Check weekday
        if self.update_weekdays:
            allowed_days = [int(d.strip()) for d in self.update_weekdays.split(',') if d.strip()]
            if current_weekday not in allowed_days:
                return False
        
        # Check hour
        if self.update_hours:
            allowed_hours = [int(h.strip()) for h in self.update_hours.split(',') if h.strip()]
            if current_hour not in allowed_hours:
                return False
        
        # Check if already ran today at this hour
        if self.last_sync_date:
            last_sync_hour = self.last_sync_date.hour
            last_sync_date = self.last_sync_date.date()
            today = fields.Date.today()
            
            if last_sync_date == today and last_sync_hour == current_hour:
                return False
        
        return True
