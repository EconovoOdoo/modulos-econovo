# -*- coding: utf-8 -*-

import json
import logging
import re
import traceback
from datetime import datetime, timedelta

import pytz
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

from markupsafe import Markup

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
    module_enabled = fields.Boolean(
        string='Module Enabled',
        compute='_compute_module_enabled',
        help='Indicates if the Custom Rate Providers module is enabled in settings'
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Lower values have higher priority'
    )
    source_currency_id = fields.Many2one(
        'res.currency',
        string='Source Currency',
        required=True,
        tracking=True,
        help='The currency being quoted (e.g., USD). The extracted value represents how much of the target currency equals 1 unit of this currency.'
    )
    target_currency_id = fields.Many2one(
        'res.currency',
        string='Target Currency',
        required=True,
        tracking=True,
        default=lambda self: self.env.company.currency_id,
        help='The reference currency (e.g., ARS). The extracted value represents the price of 1 source currency in this currency. Only companies with this currency as their base will be updated.'
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
            ('custom', 'Custom (specify separators)'),
        ],
        string='Number Format',
        default='es_AR',
        required=True,
        help='Format used by the source for decimal numbers. Select "Custom" to specify separators manually.'
    )
    custom_thousand_sep = fields.Char(
        string='Thousands Separator',
        size=3,
        help='Character(s) used as thousands separator (e.g., ".", ",", " ", "\'"). Leave empty if none.'
    )
    custom_decimal_sep = fields.Char(
        string='Decimal Separator',
        size=3,
        default=',',
        help='Character used as decimal separator (e.g., "," or ".")'
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

    # === VALIDATION & ERROR HANDLING ===
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
            ('fallback', 'Trigger Fallback Source'),
        ],
        string='On Validation Failure',
        default='log_error',
        help='Action to take when extracted rate fails validation'
    )
    fallback_source_id = fields.Many2one(
        'currency.rate.source',
        string='Fallback Source',
        domain="[('id', '!=', id), ('auto_update', '=', False)]",
        help='Alternative source to execute if this one fails. '
             'Only sources with "Automatic Update" disabled are shown to prevent circular triggers.'
    )

    # === NOTIFICATION SETTINGS ===
    notify_on_error = fields.Boolean(
        string='Enable Error Notifications',
        default=False,
        help='Send notifications when errors occur during rate updates',
    )
    notify_user_ids = fields.One2many(
        'currency.rate.source.notify.user',
        'source_id',
        string='Users to Notify',
        help='Users who will receive error notifications',
    )
    notify_partner_ids = fields.Many2many(
        'res.partner',
        'currency_rate_source_notify_partner_rel',
        'source_id',
        'partner_id',
        string='Contacts to Notify',
        help='External contacts (partners) who will receive email notifications. '
             'These contacts do not need to have an Odoo user account.',
    )
    notify_channel_id = fields.Many2one(
        'discuss.channel',
        string='Notification Channel',
        help='Odoo Discuss channel where errors will be posted',
    )
    notify_channel_mention_all = fields.Boolean(
        string='Mention All Members',
        default=False,
        help='Add @mention for all channel members in the message',
    )
    notify_channel_send_email = fields.Boolean(
        string='Send Email to Members',
        default=False,
        help='Send email notification to all channel members',
    )
    notify_template_id = fields.Many2one(
        'mail.template',
        string='Notification Template',
        domain="[('model', '=', 'currency.rate.source')]",
        help='Email template for notifications. Uses default if empty.',
    )

    # === DATE EXTRACTION ===
    extract_date = fields.Boolean(
        string='Extract Date from Source',
        default=False,
        help='Extract rate date from source instead of using current date'
    )
    date_extraction_method = fields.Selection(
        [
            ('regex', 'Regular Expression'),
            ('xpath', 'XPath (HTML/XML)'),
            ('jsonpath', 'JSONPath (JSON)'),
            ('css', 'CSS Selector'),
        ],
        string='Date Extraction Method',
        default='regex',
        help='Method to extract the date from the response'
    )
    date_regex = fields.Char(
        string='Date Regex Pattern',
        help='Regular expression with capturing group to extract date. Example: (\\d{2}/\\d{2}/\\d{4})'
    )
    date_xpath = fields.Char(
        string='Date XPath',
        help='XPath expression to extract date from HTML/XML'
    )
    date_jsonpath = fields.Char(
        string='Date JSONPath',
        help='JSONPath expression to extract date from JSON. Example: $.data.date'
    )
    date_css_selector = fields.Char(
        string='Date CSS Selector',
        help='CSS selector to extract date from HTML'
    )
    date_format = fields.Char(
        string='Date Format',
        default='%d/%m/%Y',
        help='Python strptime format for parsing date. Example: %d/%m/%Y'
    )

    # === SCHEDULING ===
    @api.model
    def _tz_get(self):
        """Return list of timezones (same pattern as calendar module)."""
        return [(tz, tz) for tz in sorted(pytz.all_timezones, key=lambda tz: tz if not tz.startswith('Etc/') else '_')]

    source_tz = fields.Selection(
        '_tz_get',
        string='Source Timezone',
        default=lambda self: self.env.user.tz or 'UTC',
        required=True,
        help='Timezone for schedule configuration. All scheduled times are interpreted in this timezone. '
             'This should typically match the timezone where the rate source publishes updates.'
    )
    auto_update = fields.Boolean(
        string='Automatic Update',
        default=True,
        tracking=True,
        help='Enable scheduled automatic updates'
    )
    update_frequency = fields.Selection(
        [
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('specific', 'Specific Days/Hours'),
        ],
        string='Update Frequency',
        default='daily',
        help='How often to update the currency rate'
    )
    preferred_hour = fields.Selection(
        selection='_get_hour_selection',
        string='Preferred Hour',
        default='9:00',
        help='Preferred hour for daily/weekly/monthly updates'
    )
    preferred_weekday = fields.Selection(
        [
            ('0', 'Monday'),
            ('1', 'Tuesday'),
            ('2', 'Wednesday'),
            ('3', 'Thursday'),
            ('4', 'Friday'),
            ('5', 'Saturday'),
            ('6', 'Sunday'),
        ],
        string='Preferred Day',
        default='0',
        help='Preferred day of week for weekly updates'
    )
    preferred_monthdays = fields.Char(
        string='Days of Month',
        default='1',
        help='Days of month for monthly updates. Comma-separated, e.g.: 1, 15, 30'
    )
    schedule_ids = fields.One2many(
        'currency.rate.schedule',
        'source_id',
        string='Specific Schedule',
        help='Define specific day/hour combinations (only used when frequency is "Specific Days/Hours")'
    )
    next_execution = fields.Datetime(
        string='Next Scheduled Execution',
        compute='_compute_next_execution',
        store=True
    )

    @api.model
    def _get_hour_selection(self):
        """Generate hour selection options with 30-minute intervals."""
        options = []
        for h in range(24):
            options.append((f'{h}:00', f'{h:02d}:00'))
            options.append((f'{h}:30', f'{h:02d}:30'))
        return options

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
    cron_id = fields.Many2one(
        'ir.cron',
        string='Scheduled Action',
        readonly=True,
        ondelete='set null',
        copy=False,
        help='Dedicated scheduled action for this source. Created automatically when auto_update is enabled.'
    )

    # === CONSTRAINTS ===
    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Source name must be unique!'),
        ('url_required', 'CHECK(url IS NOT NULL)', 'URL is required!'),
    ]

    # ==========================================
    # HELPER METHODS
    # ==========================================

    def _is_module_enabled(self):
        """Check if the module feature is enabled.
        
        The module is considered enabled when the group_custom_rate_sources
        is assigned to users (controlled via implied_group in settings).
        
        Returns:
            bool: True if the feature is enabled, False otherwise.
        """
        group = self.env.ref(
            'econovo_currency_rate_custom_providers.group_custom_rate_sources',
            raise_if_not_found=False
        )
        return bool(group and group.users)

    # ==========================================
    # COMPUTE METHODS
    # ==========================================

    def _compute_module_enabled(self):
        """Check if the module is enabled in settings.
        
        The module is considered enabled when the group_custom_rate_sources
        is assigned to users (controlled via implied_group in settings).
        """
        enabled = self._is_module_enabled()
        for record in self:
            record.module_enabled = enabled

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

    @api.depends('auto_update', 'update_frequency', 'preferred_hour', 'preferred_weekday', 'preferred_monthdays', 'schedule_ids', 'schedule_ids.dayofweek', 'schedule_ids.hour', 'source_tz')
    def _compute_next_execution(self):
        """Compute next scheduled execution time.
        
        Uses the source's configured timezone (source_tz) to calculate 
        scheduled times, following the pattern used by calendar.event.
        All datetimes are stored as naive UTC in the database.
        """
        for record in self:
            if not record.auto_update:
                record.next_execution = False
                continue
            
            # Use source timezone (not user timezone) for schedule calculations
            # This ensures consistent scheduling regardless of who views/edits
            tz_name = record.source_tz or 'UTC'
            try:
                source_tz = pytz.timezone(tz_name)
            except pytz.UnknownTimeZoneError:
                source_tz = pytz.UTC
            
            # Convert current UTC time to source timezone for calculations
            utc_now = fields.Datetime.now()
            local_now = pytz.utc.localize(utc_now).astimezone(source_tz)
            
            # Parse preferred hour (represents time in source_tz)
            pref_hour = 9
            pref_minute = 0
            if record.preferred_hour:
                parts = record.preferred_hour.split(':')
                pref_hour = int(parts[0])
                pref_minute = int(parts[1]) if len(parts) > 1 else 0
            
            if record.update_frequency == 'hourly':
                # Next hour (runs every hour when cron executes)
                next_exec_local = local_now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                record.next_execution = next_exec_local.astimezone(pytz.utc).replace(tzinfo=None)
                
            elif record.update_frequency == 'daily':
                # Today or tomorrow at preferred hour (source timezone)
                next_exec_local = local_now.replace(hour=pref_hour, minute=pref_minute, second=0, microsecond=0)
                if next_exec_local <= local_now:
                    next_exec_local += timedelta(days=1)
                record.next_execution = next_exec_local.astimezone(pytz.utc).replace(tzinfo=None)
                
            elif record.update_frequency == 'weekly':
                # Next preferred weekday at preferred hour (source timezone)
                pref_weekday = int(record.preferred_weekday or '0')
                days_until = (pref_weekday - local_now.weekday()) % 7
                next_exec_local = (local_now + timedelta(days=days_until)).replace(
                    hour=pref_hour, minute=pref_minute, second=0, microsecond=0
                )
                if next_exec_local <= local_now:
                    next_exec_local += timedelta(days=7)
                record.next_execution = next_exec_local.astimezone(pytz.utc).replace(tzinfo=None)
                
            elif record.update_frequency == 'monthly':
                # Find next valid day from preferred_monthdays (source timezone)
                pref_days = record._parse_monthdays()
                if not pref_days:
                    pref_days = [1]
                
                # Find next execution using source timezone
                next_exec = record._find_next_monthday_execution(local_now, pref_days, pref_hour, pref_minute, source_tz)
                record.next_execution = next_exec
                
            elif record.update_frequency == 'specific' and record.schedule_ids:
                # Find next scheduled time from schedule_ids (source timezone)
                record.next_execution = record._compute_next_specific_execution(local_now, source_tz)
            else:
                record.next_execution = False

    def _parse_monthdays(self):
        """Parse preferred_monthdays string into list of integers."""
        if not self.preferred_monthdays:
            return [1]
        try:
            days = []
            for part in self.preferred_monthdays.split(','):
                day = int(part.strip())
                if 1 <= day <= 31:
                    days.append(day)
            return sorted(set(days)) if days else [1]
        except (ValueError, AttributeError):
            return [1]

    def _find_next_monthday_execution(self, local_now, pref_days, pref_hour, pref_minute, user_tz):
        """Find next execution datetime for monthly schedule (returns UTC)."""
        import calendar
        
        # Check current month first
        for day in pref_days:
            # Get last day of current month
            _, last_day = calendar.monthrange(local_now.year, local_now.month)
            actual_day = min(day, last_day)
            try:
                candidate = local_now.replace(day=actual_day, hour=pref_hour, minute=pref_minute, second=0, microsecond=0)
                if candidate > local_now:
                    return candidate.astimezone(pytz.utc).replace(tzinfo=None)
            except ValueError:
                continue
        
        # Check next month
        if local_now.month == 12:
            next_year, next_month = local_now.year + 1, 1
        else:
            next_year, next_month = local_now.year, local_now.month + 1
        
        _, last_day = calendar.monthrange(next_year, next_month)
        for day in pref_days:
            actual_day = min(day, last_day)
            try:
                from datetime import datetime
                candidate = user_tz.localize(datetime(next_year, next_month, actual_day, pref_hour, pref_minute, 0))
                return candidate.astimezone(pytz.utc).replace(tzinfo=None)
            except ValueError:
                continue
        
        # Fallback
        return (local_now + timedelta(days=30)).astimezone(pytz.utc).replace(tzinfo=None)

    def _compute_next_specific_execution(self, local_now, user_tz):
        """Calculate next execution time based on schedule_ids (returns UTC)."""
        if not self.schedule_ids:
            return False
        
        # Get all active schedules sorted
        schedules = self.schedule_ids.filtered(lambda s: s.active).sorted(
            key=lambda s: (int(s.dayofweek), s.hour)
        )
        if not schedules:
            return False
        
        current_weekday = local_now.weekday()
        
        # Find next schedule
        for days_ahead in range(8):  # Check up to a week ahead
            check_day = (current_weekday + days_ahead) % 7
            for schedule in schedules:
                if int(schedule.dayofweek) == check_day:
                    # Parse schedule hour
                    parts = schedule.hour.split(':')
                    sched_hour = int(parts[0])
                    sched_minute = int(parts[1]) if len(parts) > 1 else 0
                    
                    next_exec_local = (local_now + timedelta(days=days_ahead)).replace(
                        hour=sched_hour, minute=sched_minute, second=0, microsecond=0
                    )
                    if next_exec_local > local_now:
                        return next_exec_local.astimezone(pytz.utc).replace(tzinfo=None)
        
        # Fallback: first schedule next week
        first_sched = schedules[0]
        parts = first_sched.hour.split(':')
        sched_hour = int(parts[0])
        sched_minute = int(parts[1]) if len(parts) > 1 else 0
        days_until = (int(first_sched.dayofweek) - current_weekday) % 7 or 7
        next_exec_local = (local_now + timedelta(days=days_until)).replace(
            hour=sched_hour, minute=sched_minute, second=0, microsecond=0
        )
        return next_exec_local.astimezone(pytz.utc).replace(tzinfo=None)

    def action_create_default_schedule(self):
        """Create default schedule: weekdays at 09:00 and 15:00."""
        self.ensure_one()
        Schedule = self.env['currency.rate.schedule']
        # Clear existing
        self.schedule_ids.unlink()
        # Set frequency to specific
        self.update_frequency = 'specific'
        # Create weekday schedule at 09:00 and 15:00
        for day in ['0', '1', '2', '3', '4']:  # Mon-Fri
            for hour in ['9:00', '15:00']:
                Schedule.create({
                    'source_id': self.id,
                    'dayofweek': day,
                    'hour': hour,
                })
        return True
        return True

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

    @api.constrains('decimal_format', 'custom_decimal_sep')
    def _check_custom_decimal_format(self):
        for record in self:
            if record.decimal_format == 'custom' and not record.custom_decimal_sep:
                raise ValidationError(_(
                    'Decimal Separator is required when using Custom number format.'
                ))

    @api.constrains('update_frequency', 'schedule_ids')
    def _check_specific_schedule(self):
        for record in self:
            if record.update_frequency == 'specific' and not record.schedule_ids:
                raise ValidationError(_(
                    'At least one schedule line is required when using "Specific Days/Hours" frequency.'
                ))

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
            'name': f'Rates for {self.source_currency_id.name}',
            'res_model': 'res.currency.rate',
            'view_mode': 'tree,form',
            'domain': [('currency_id', '=', self.source_currency_id.id)],
            'context': {'default_currency_id': self.source_currency_id.id},
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
        return self._execute_update(trigger_fallback=True)

    # ==========================================
    # MAIN EXECUTION METHODS
    # ==========================================

    def _execute_update(self, trigger_fallback=True, triggered_by='manual', triggered_by_source_id=False):
        """Execute rate update and create/update currency rates.
        
        Args:
            trigger_fallback: If True and on_validation_fail='fallback', 
                            execute fallback source on error. Set to False
                            during test extraction to prevent cascading calls.
            triggered_by: Origin of the execution ('manual', 'cron', 'test', 'fallback')
            triggered_by_source_id: ID of the source that triggered this execution via fallback
        """
        self.ensure_one()
        
        log_vals = {
            'source_id': self.id,
            'execution_date': fields.Datetime.now(),
            'triggered_by': triggered_by,
            'triggered_by_source_id': triggered_by_source_id,
        }
        
        start_time = datetime.now()
        
        try:
            # Fetch content
            content, http_status, response_time = self._fetch_content()
            log_vals['http_status_code'] = http_status
            log_vals['content_length'] = len(content) if content else 0
            log_vals['http_response_time'] = response_time
            
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
            if self.extract_date:
                rate_date, raw_date_value = self._extract_date(content)
                log_vals['date_extraction_used'] = True
                log_vals['extracted_date'] = rate_date
                log_vals['raw_date_value'] = raw_date_value
            else:
                rate_date = fields.Date.today()
                log_vals['date_extraction_used'] = False
                log_vals['extracted_date'] = rate_date
            
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
            fallback_triggered = False
            
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
            
            # Send error notifications
            try:
                self._send_error_notification(error_msg, error_type='update')
            except Exception as notify_error:
                _logger.warning('Failed to send error notification: %s', str(notify_error))
            
            # Check if we should trigger fallback source
            fallback_triggered = False
            if (trigger_fallback and 
                self.on_validation_fail == 'fallback' and 
                self.fallback_source_id):
                fallback_triggered = True
                _logger.info(
                    'Triggering fallback source %s due to failure in %s',
                    self.fallback_source_id.name, self.name
                )
        
        finally:
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            log_vals['duration'] = duration
            
            # Create log entry
            self.env['currency.rate.log'].create(log_vals)
            
            # Update cron nextcall for next execution (only for cron-triggered updates)
            if triggered_by == 'cron' and self.cron_id:
                self._update_cron_nextcall()
            
            # Execute fallback after logging (outside try block to avoid nested exceptions)
            if fallback_triggered:
                try:
                    # Execute fallback with trigger_fallback=False to prevent infinite loops
                    self.fallback_source_id._execute_update(
                        trigger_fallback=False,
                        triggered_by='fallback',
                        triggered_by_source_id=self.id
                    )
                except Exception as fallback_error:
                    _logger.error(
                        'Fallback source %s also failed: %s',
                        self.fallback_source_id.name, str(fallback_error)
                    )
        
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
        keyword = self.auto_keyword or self.source_currency_id.name
        currency_code = self.source_currency_id.name if self.source_currency_id else ''
        
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
        if self.decimal_format == 'custom':
            fmt = {
                'thousand': self.custom_thousand_sep or '',
                'decimal': self.custom_decimal_sep or '.'
            }
        else:
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
            elif self.on_validation_fail == 'fallback':
                # Raise error to trigger fallback in _execute_update
                raise UserError(_('Validation failed, triggering fallback: %s') % error_msg)
        
        return result

    def _extract_date(self, content):
        """Extract rate date from content using configured method.
        
        Returns:
            tuple: (parsed_date, raw_date_string) where raw_date_string is the 
                   extracted string before parsing, or None if not found.
        """
        method = self.date_extraction_method or 'regex'
        date_str = None
        
        if method == 'regex':
            if not self.date_regex:
                return fields.Date.today(), None
            match = re.search(self.date_regex, content)
            if match:
                date_str = match.group(1) if match.groups() else match.group(0)
                
        elif method == 'xpath':
            if not self.date_xpath:
                return fields.Date.today(), None
            try:
                tree = etree.HTML(content)
                results = tree.xpath(self.date_xpath)
                if results:
                    date_str = str(results[0]).strip() if results else None
            except Exception as e:
                _logger.warning('XPath date extraction failed: %s', e)
                
        elif method == 'jsonpath':
            if not self.date_jsonpath or not HAS_JSONPATH:
                return fields.Date.today(), None
            try:
                data = json.loads(content)
                jsonpath_expr = parse(self.date_jsonpath)
                matches = [m.value for m in jsonpath_expr.find(data)]
                if matches:
                    date_str = str(matches[0]).strip()
            except Exception as e:
                _logger.warning('JSONPath date extraction failed: %s', e)
                
        elif method == 'css':
            if not self.date_css_selector or not HAS_CSSSELECT:
                return fields.Date.today(), None
            try:
                tree = etree.HTML(content)
                selector = CSSSelector(self.date_css_selector)
                results = selector(tree)
                if results:
                    date_str = results[0].text_content().strip() if results else None
            except Exception as e:
                _logger.warning('CSS date extraction failed: %s', e)
        
        if not date_str:
            _logger.warning('Date not found using %s method, using today', method)
            return fields.Date.today(), None
        
        try:
            parsed_date = datetime.strptime(date_str, self.date_format or '%d/%m/%Y')
            return parsed_date.date(), date_str
        except ValueError:
            _logger.warning('Could not parse date %s with format %s, using today', date_str, self.date_format)
            return fields.Date.today(), date_str

    def _update_currency_rates(self, rate, rate_date):
        """Create or update currency rates for configured companies.
        
        Uses sudo() to bypass multi-company access rules since currency
        rates are system-level data that should be updated regardless
        of the current user's company access.
        
        Note: Odoo only allows creating currency rates for main companies
        (companies without a parent). Branches inherit rates from their parent.
        """
        CurrencyRate = self.env['res.currency.rate'].sudo()
        
        # Get companies to update
        if self.update_all_companies:
            # Only main companies (without parent) - Odoo constraint
            companies = self.env['res.company'].sudo().search([
                ('parent_id', '=', False),
            ])
        else:
            # Filter to only include main companies from the selected ones
            companies = self.company_ids.filtered(lambda c: not c.parent_id)
        
        # Filter companies: only those whose base currency matches target_currency_id
        # Example: If source=USD, target=ARS, only update companies with ARS as base
        companies = companies.filtered(
            lambda c: c.currency_id.id == self.target_currency_id.id
        )
        
        if not companies:
            _logger.warning(
                'No companies found with base currency %s for source %s',
                self.target_currency_id.name, self.name
            )
            return 0, 0
        
        created = 0
        updated = 0
        
        for company in companies:
            # Search for existing rate
            existing = CurrencyRate.search([
                ('currency_id', '=', self.source_currency_id.id),
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
                    'currency_id': self.source_currency_id.id,
                    'company_id': company.id,
                    'name': rate_date,
                    'inverse_company_rate': rate,
                })
                created += 1
        
        _logger.info(
            'Updated currency rates for %s: %d created, %d updated',
            self.source_currency_id.name, created, updated
        )
        
        return created, updated

    # ==========================================
    # CRON METHODS - Individual Cron per Source
    # ==========================================

    @api.model
    def _cron_update_single_source(self, source_id):
        """Cron job method called by individual source crons.
        
        Each source has its own ir.cron that calls this method with its ID.
        This ensures precise execution at the scheduled time.
        
        Args:
            source_id: ID of the currency.rate.source to update
        """
        source = self.browse(source_id)
        if not source.exists():
            _logger.warning('Cron called for non-existent source ID: %s', source_id)
            return
        
        if not source.active or not source.auto_update:
            _logger.info('Skipping disabled source: %s', source.name)
            return
        
        # Check if module feature is enabled
        if not self._is_module_enabled():
            _logger.info('Currency Rate Custom Providers is disabled, skipping update for: %s', source.name)
            return
        
        try:
            _logger.info('Running scheduled update for source: %s', source.name)
            source._execute_update(triggered_by='cron')
        except Exception as e:
            _logger.error('Scheduled update failed for %s: %s', source.name, str(e))

    def _get_cron_nextcall(self):
        """Calculate the next execution datetime for cron based on source schedule.
        
        Returns UTC datetime for the next scheduled execution.
        """
        self.ensure_one()
        next_exec = self.next_execution
        if next_exec:
            return next_exec
        # Fallback: 1 hour from now
        return fields.Datetime.now() + timedelta(hours=1)

    def _get_cron_interval(self):
        """Get cron interval configuration based on update_frequency.
        
        Returns tuple (interval_number, interval_type) for ir.cron.
        The cron will be re-scheduled after each execution via _update_cron_nextcall().
        """
        self.ensure_one()
        if self.update_frequency == 'hourly':
            return (1, 'hours')
        elif self.update_frequency == 'daily':
            return (1, 'days')
        elif self.update_frequency == 'weekly':
            return (7, 'days')
        elif self.update_frequency == 'monthly':
            return (30, 'days')
        elif self.update_frequency == 'specific':
            # For specific schedules, recalculate after each run
            return (1, 'days')
        return (1, 'days')

    def _create_source_cron(self):
        """Create a dedicated ir.cron for this source."""
        self.ensure_one()
        if self.cron_id:
            return self.cron_id
        
        interval_number, interval_type = self._get_cron_interval()
        nextcall = self._get_cron_nextcall()
        
        # Check if module feature is globally enabled
        module_enabled = self._is_module_enabled()
        
        # Get model reference
        model = self.env['ir.model'].sudo().search([
            ('model', '=', 'currency.rate.source')
        ], limit=1)
        
        cron_vals = {
            'name': f'Currency Rate: {self.name}',
            'model_id': model.id,
            'state': 'code',
            'code': f'model._cron_update_single_source({self.id})',
            'interval_number': interval_number,
            'interval_type': interval_type,
            'nextcall': nextcall,
            'numbercall': -1,
            'active': self.active and self.auto_update and module_enabled,
            'doall': False,
            'priority': 15,
        }
        
        cron = self.env['ir.cron'].sudo().create(cron_vals)
        self.sudo().write({'cron_id': cron.id})
        
        _logger.info(
            'Created cron for source %s (ID: %s), next execution: %s',
            self.name, cron.id, nextcall
        )
        return cron

    def _update_source_cron(self):
        """Update the dedicated cron based on current source configuration."""
        self.ensure_one()
        if not self.cron_id:
            if self.auto_update and self.active:
                return self._create_source_cron()
            return False
        
        interval_number, interval_type = self._get_cron_interval()
        nextcall = self._get_cron_nextcall()
        
        # Check if module feature is globally enabled
        module_enabled = self._is_module_enabled()
        
        cron_vals = {
            'name': f'Currency Rate: {self.name}',
            'code': f'model._cron_update_single_source({self.id})',
            'interval_number': interval_number,
            'interval_type': interval_type,
            'nextcall': nextcall,
            'active': self.active and self.auto_update and module_enabled,
        }
        
        self.cron_id.sudo().write(cron_vals)
        
        _logger.info(
            'Updated cron for source %s, active: %s, next execution: %s',
            self.name, cron_vals['active'], nextcall
        )
        return self.cron_id

    def _update_cron_nextcall(self):
        """Update only the nextcall of the cron after execution.
        
        Call this after a successful execution to schedule next run.
        """
        self.ensure_one()
        if not self.cron_id:
            return
        
        nextcall = self._get_cron_nextcall()
        self.cron_id.sudo().write({'nextcall': nextcall})
        
        _logger.debug(
            'Updated nextcall for source %s cron to: %s',
            self.name, nextcall
        )

    def _delete_source_cron(self):
        """Delete the dedicated cron for this source."""
        self.ensure_one()
        if self.cron_id:
            cron_name = self.cron_id.name
            self.cron_id.sudo().unlink()
            _logger.info('Deleted cron: %s', cron_name)

    @api.model
    def _update_all_source_crons(self, enabled=None):
        """Update all source crons based on global module enabled state.
        
        Called from res.config.settings when the module enable/disable toggle changes.
        
        Args:
            enabled: If provided, use this value. Otherwise check via group membership.
        """
        if enabled is None:
            enabled = self._is_module_enabled()
        
        sources = self.search([])
        for source in sources:
            if source.cron_id:
                source.cron_id.sudo().write({
                    'active': enabled and source.active and source.auto_update
                })
            elif enabled and source.active and source.auto_update:
                source._create_source_cron()

    # ==========================================
    # CRUD OVERRIDES - Auto-manage crons
    # ==========================================

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-create cron for new sources with auto_update."""
        records = super().create(vals_list)
        
        # Check if module feature is enabled
        enabled = self._is_module_enabled()
        
        for record in records:
            if enabled and record.auto_update and record.active:
                record._create_source_cron()
        
        return records

    def write(self, vals):
        """Override write to update cron when relevant fields change."""
        result = super().write(vals)
        
        # Fields that affect cron configuration
        cron_affecting_fields = {
            'name', 'active', 'auto_update', 'update_frequency',
            'preferred_hour', 'preferred_weekday', 'preferred_monthdays',
            'source_tz', 'schedule_ids'
        }
        
        if cron_affecting_fields & set(vals.keys()):
            for record in self:
                if record.auto_update and record.active:
                    record._update_source_cron()
                elif record.cron_id:
                    # Deactivate cron if auto_update or active is disabled
                    record.cron_id.sudo().write({'active': False})
        
        return result

    def unlink(self):
        """Override unlink to delete associated crons."""
        for record in self:
            if record.cron_id:
                record._delete_source_cron()
        return super().unlink()

    # Keep legacy method for backward compatibility (deprecated)
    @api.model
    def _cron_update_rates(self):
        """DEPRECATED: Legacy cron method kept for backward compatibility.
        
        This method is no longer used. Each source now has its own dedicated cron.
        This method will be removed in a future version.
        """
        _logger.warning(
            'DEPRECATED: _cron_update_rates() called. '
            'Each source now has its own cron. Please update your configuration.'
        )
        # Fallback: update all due sources
        sources = self.search([
            ('active', '=', True),
            ('auto_update', '=', True),
        ])
        for source in sources:
            try:
                source._execute_update(triggered_by='cron')
            except Exception as e:
                _logger.error('Update failed for %s: %s', source.name, str(e))

    # === NOTIFICATION METHODS ===
    
    def _get_default_notification_body(self, error_message, error_type='validation'):
        """Generate default notification body for error alerts (HTML for emails).
        
        Args:
            error_message: The error description
            error_type: Type of error (validation, extraction, connection)
            
        Returns:
            str: HTML formatted notification body
        """
        self.ensure_one()
        return _("""
<div style="font-family: Arial, sans-serif;">
    <h3 style="color: #dc3545;">⚠️ Currency Rate Update Failed</h3>
    <table style="width: 100%%; border-collapse: collapse; margin: 10px 0;">
        <tr>
            <td style="padding: 5px; border-bottom: 1px solid #ddd;"><strong>Source:</strong></td>
            <td style="padding: 5px; border-bottom: 1px solid #ddd;">%(source_name)s</td>
        </tr>
        <tr>
            <td style="padding: 5px; border-bottom: 1px solid #ddd;"><strong>Currency:</strong></td>
            <td style="padding: 5px; border-bottom: 1px solid #ddd;">%(source_currency)s → %(target_currency)s</td>
        </tr>
        <tr>
            <td style="padding: 5px; border-bottom: 1px solid #ddd;"><strong>Error Type:</strong></td>
            <td style="padding: 5px; border-bottom: 1px solid #ddd;">%(error_type)s</td>
        </tr>
        <tr>
            <td style="padding: 5px; border-bottom: 1px solid #ddd;"><strong>Error:</strong></td>
            <td style="padding: 5px; border-bottom: 1px solid #ddd; color: #dc3545;">%(error_message)s</td>
        </tr>
        <tr>
            <td style="padding: 5px; border-bottom: 1px solid #ddd;"><strong>Time:</strong></td>
            <td style="padding: 5px; border-bottom: 1px solid #ddd;">%(error_time)s</td>
        </tr>
    </table>
</div>
        """) % {
            'source_name': self.name,
            'source_currency': self.source_currency_id.name,
            'target_currency': self.target_currency_id.name,
            'error_type': error_type.replace('_', ' ').title(),
            'error_message': error_message,
            'error_time': fields.Datetime.now(),
        }

    def _get_channel_notification_body(self, error_message, error_type='validation'):
        """Generate notification body for Discuss channels.
        
        Uses Markup to indicate HTML is safe and should be rendered.
        
        Args:
            error_message: The error description
            error_type: Type of error (validation, extraction, connection)
            
        Returns:
            Markup: Safe HTML notification body for channel
        """
        self.ensure_one()
        # Use Markup to indicate this HTML is safe and should be rendered
        return Markup(
            '<div class="o_mail_notification">'
            '<p><strong>⚠️ Currency Rate Update Failed</strong></p>'
            '<p>'
            '<strong>Source:</strong> %(source_name)s<br/>'
            '<strong>Currency:</strong> %(source_currency)s → %(target_currency)s<br/>'
            '<strong>Error Type:</strong> %(error_type)s<br/>'
            '<strong>Error:</strong> %(error_message)s<br/>'
            '<strong>Time:</strong> %(error_time)s'
            '</p>'
            '</div>'
        ) % {
            'source_name': self.name,
            'source_currency': self.source_currency_id.name,
            'target_currency': self.target_currency_id.name,
            'error_type': error_type.replace('_', ' ').title(),
            'error_message': error_message,
            'error_time': fields.Datetime.now(),
        }
    
    def _send_error_notification(self, error_message, error_type='validation'):
        """Send error notifications to configured users, partners, and/or channel.
        
        Args:
            error_message: The error description
            error_type: Type of error (validation, extraction, connection)
        """
        self.ensure_one()
        if not self.notify_on_error:
            return
        
        subject = _('⚠️ Currency Rate Error: %s') % self.name
        # Body for emails (HTML format)
        email_body = self._get_default_notification_body(error_message, error_type)
        # Body for channels (simple format that Discuss can render)
        channel_body = self._get_channel_notification_body(error_message, error_type)
        
        # 1. Notify specific users via internal notification + optional email
        if self.notify_user_ids:
            partner_ids = self.notify_user_ids.mapped('user_id.partner_id').ids
            
            try:
                # Send internal notification (appears in user's inbox)
                self.message_notify(
                    partner_ids=partner_ids,
                    body=channel_body,  # Use simple format for chatter/inbox
                    subject=subject,
                )
                
                # Handle forced email sending
                force_email_partners = self.notify_user_ids.filtered(
                    lambda u: u.force_email
                ).mapped('user_id.partner_id')
                
                if force_email_partners:
                    # If custom template exists, use it for email
                    if self.notify_template_id:
                        template = self.notify_template_id.with_context(
                            error_message=error_message,
                            error_type=error_type,
                            error_datetime=fields.Datetime.now(),
                        )
                        template.send_mail(
                            self.id,
                            force_send=True,
                            email_values={
                                'recipient_ids': [(6, 0, force_email_partners.ids)],
                                'email_to': False,  # Clear default to use recipient_ids
                            }
                        )
                    else:
                        # Use default HTML body for email
                        self.env['mail.mail'].sudo().create({
                            'subject': subject,
                            'body_html': email_body,
                            'recipient_ids': [(6, 0, force_email_partners.ids)],
                            'auto_delete': True,
                        }).send()
                        
            except Exception as e:
                _logger.warning('Failed to send user notification: %s', str(e))
        
        # 2. Notify external contacts (partners without Odoo users)
        if self.notify_partner_ids:
            try:
                # Filter partners with valid email
                partners_with_email = self.notify_partner_ids.filtered(lambda p: p.email)
                if partners_with_email:
                    if self.notify_template_id:
                        # Generate email from template
                        template = self.notify_template_id.with_context(
                            error_message=error_message,
                            error_type=error_type,
                            error_datetime=fields.Datetime.now(),
                        )
                        # Generate mail values from template
                        mail_values = template.generate_email(self.id, ['subject', 'body_html', 'email_from'])
                        # Create mail with explicit recipients
                        self.env['mail.mail'].sudo().create({
                            'subject': mail_values.get('subject', subject),
                            'body_html': mail_values.get('body_html', email_body),
                            'email_from': mail_values.get('email_from'),
                            'recipient_ids': [(6, 0, partners_with_email.ids)],
                            'auto_delete': True,
                        }).send()
                    else:
                        self.env['mail.mail'].sudo().create({
                            'subject': subject,
                            'body_html': email_body,
                            'recipient_ids': [(6, 0, partners_with_email.ids)],
                            'auto_delete': True,
                        }).send()
            except Exception as e:
                _logger.warning('Failed to send partner notification: %s', str(e))
        
        # 3. Post to Discuss channel
        if self.notify_channel_id:
            try:
                post_body = channel_body
                
                # Mention all members if configured
                if self.notify_channel_mention_all:
                    members = self.notify_channel_id.channel_member_ids.mapped('partner_id')
                    if members:
                        # Create proper mention format for Discuss using Markup
                        mentions = Markup(' ').join([
                            Markup('<a href="#" data-oe-model="res.partner" data-oe-id="%s">@%s</a>') % (p.id, p.name)
                            for p in members
                        ])
                        post_body = Markup('<p>%s</p>') % mentions + channel_body
                
                # Post message to channel
                self.notify_channel_id.message_post(
                    body=post_body,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
                
                # Force email to channel members if configured
                if self.notify_channel_send_email:
                    members = self.notify_channel_id.channel_member_ids.mapped('partner_id')
                    if members:
                        if self.notify_template_id:
                            template = self.notify_template_id.with_context(
                                error_message=error_message,
                                error_type=error_type,
                                error_datetime=fields.Datetime.now(),
                            )
                            template.send_mail(
                                self.id,
                                force_send=True,
                                email_values={
                                    'recipient_ids': [(6, 0, members.ids)],
                                    'email_to': False,
                                }
                            )
                        else:
                            self.env['mail.mail'].sudo().create({
                                'subject': subject,
                                'body_html': email_body,
                                'recipient_ids': [(6, 0, members.ids)],
                                'auto_delete': True,
                            }).send()
                        
            except Exception as e:
                _logger.warning('Failed to send channel notification: %s', str(e))


