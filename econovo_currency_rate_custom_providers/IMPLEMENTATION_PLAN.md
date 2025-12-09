# Implementation Plan: econovo_currency_rate_custom_providers

## Module Overview

**Name:** `econovo_currency_rate_custom_providers`  
**Version:** 17.0.1.0.0  
**Author:** Jose D. Leonett  
**License:** AGPL-3  
**Purpose:** Universal currency/asset rate updater from any web source using multiple extraction methods.

## Key Features

- **Agnostic Design:** Works for any country, currency, or asset (USD, EUR, Bitcoin, Gold, etc.)
- **Multiple Extraction Methods:** Automatic, Regex, XPath, JSONPath, CSS Selector
- **Multi-company Support:** Updates rates for all or selected companies
- **Scheduling:** Configurable execution times and days
- **Logging:** Complete execution history with error tracking
- **Validation:** Rate range validation and change percentage limits
- **Odoo.sh Compatible:** No iframes, no CSP issues

---

## Implementation Status

### Phase 1: Module Structure
| Task | Status | Notes |
|------|--------|-------|
| Create folder structure | DONE | models, views, wizards, data, security |
| Create __manifest__.py | DONE | Dependencies: base, account |
| Create __init__.py files | DONE | All subfolders |
| Create IMPLEMENTATION_PLAN.md | DONE | This file |

### Phase 2: Models
| Task | Status | Notes |
|------|--------|-------|
| currency.rate.source model | DONE | Main configuration model (~1000 lines) |
| currency.rate.log model | DONE | Execution history |
| res.config.settings | DONE | Global configuration extension |
| Extraction methods | DONE | 5 methods: auto, regex, xpath, jsonpath, css |
| Rate update logic | DONE | Create/update res.currency.rate |

### Phase 3: Views
| Task | Status | Notes |
|------|--------|-------|
| Tree view (sources) | DONE | With status badges |
| Kanban view (sources) | DONE | Cards with last rate |
| Form view (sources) | DONE | Complete configuration with notebook |
| Search view (sources) | DONE | Filters and groupings |
| Log views | DONE | Tree and form |
| Menu items | DONE | Under Invoicing/Configuration |
| Settings view | DONE | Extension of account settings |

### Phase 4: Wizards
| Task | Status | Notes |
|------|--------|-------|
| Test extraction wizard | DONE | Preview before saving |
| Wizard views | DONE | Form with results tabs |

### Phase 5: Automation
| Task | Status | Notes |
|------|--------|-------|
| Cron job | DONE | Hourly rate updates |
| Log cleanup cron | DONE | Daily cleanup of old logs |

### Phase 6: Security & Data
| Task | Status | Notes |
|------|--------|-------|
| Security groups | DONE | User and Manager groups |
| Access rules | DONE | ir.model.access.csv |
| Demo data | DONE | BNA USD/EUR, ECB API, XPath example |

### Phase 7: Testing
| Task | Status | Notes |
|------|--------|-------|
| Module installation | PENDING | Odoo 17 CE |
| Functional testing | PENDING | All extraction methods |
| Odoo.sh compatibility | PENDING | Verify no restrictions |

---

## File Structure

```
econovo_currency_rate_custom_providers/
|-- __init__.py
|-- __manifest__.py
|-- IMPLEMENTATION_PLAN.md
|-- README.md
|-- models/
|   |-- __init__.py
|   |-- currency_rate_source.py
|   |-- currency_rate_log.py
|   |-- res_config_settings.py
|-- views/
|   |-- currency_rate_source_views.xml
|   |-- currency_rate_log_views.xml
|   |-- res_config_settings_views.xml
|   |-- menu_views.xml
|-- wizards/
|   |-- __init__.py
|   |-- test_extraction_wizard.py
|   |-- test_extraction_wizard_views.xml
|-- data/
|   |-- ir_cron_data.xml
|   |-- demo_data.xml
|-- security/
|   |-- ir.model.access.csv
|   |-- security_groups.xml
|-- i18n/
|   |-- (translation files)
```

---

## Model Fields Reference

### currency.rate.source

#### General
- `name` - Source name
- `active` - Active flag
- `sequence` - Priority order
- `currency_id` - Target currency (Many2one res.currency)
- `company_ids` - Companies to update (Many2many res.company)
- `update_all_companies` - Boolean to update all companies

#### HTTP Configuration
- `url` - Source URL
- `http_method` - GET/POST
- `http_timeout` - Timeout in seconds
- `http_retries` - Number of retries
- `http_user_agent` - Custom User-Agent
- `http_headers` - Additional headers (JSON)

#### Extraction Method
- `extraction_method` - Selection (auto/regex/xpath/jsonpath/css)
- `response_type` - Selection (html/json/xml/text)

#### Regex Configuration
- `regex_pattern` - Regular expression pattern
- `regex_group` - Group number to extract
- `regex_flag_ignorecase` - Boolean
- `regex_flag_multiline` - Boolean
- `regex_flag_dotall` - Boolean

#### XPath Configuration
- `xpath_expression` - XPath expression
- `xpath_attribute` - Attribute to extract
- `xpath_result_index` - Index of result

#### JSONPath Configuration
- `jsonpath_expression` - JSONPath expression
- `jsonpath_result_index` - Index of result

#### CSS Selector Configuration
- `css_selector` - CSS selector
- `css_attribute` - Attribute to extract
- `css_result_index` - Index of result

#### Auto Detection Configuration
- `auto_keyword` - Keyword to search near

#### Value Processing
- `decimal_format` - Selection (es_AR/en_US/de_DE/fr_FR)
- `value_multiplier` - Float multiplier
- `invert_rate` - Boolean to invert value

#### Validation
- `min_valid_rate` - Minimum acceptable rate
- `max_valid_rate` - Maximum acceptable rate
- `max_variation_percent` - Maximum change from last rate
- `on_validation_fail` - Selection (skip/log_error/use_last)

#### Date Extraction
- `extract_date` - Boolean
- `date_regex_pattern` - Regex for date
- `date_format` - Python strptime format

#### Scheduling
- `auto_update` - Boolean
- `update_interval` - Selection (hourly/daily/weekly)
- `update_hours` - Char (comma separated hours)
- `update_days` - Char (comma separated weekdays)
- `timezone` - Selection

#### Status (computed)
- `state` - Selection (active/error/inactive)
- `last_sync_date` - Datetime
- `last_rate` - Float
- `last_raw_value` - Char
- `last_error` - Text
- `execution_count` - Integer
- `success_count` - Integer
- `error_count` - Integer

### currency.rate.log

- `source_id` - Many2one to currency.rate.source
- `execution_date` - Datetime
- `state` - Selection (success/error)
- `raw_value` - Extracted raw string
- `processed_rate` - Float
- `error_message` - Text
- `error_traceback` - Text
- `http_status_code` - Integer
- `http_response_size` - Integer
- `duration` - Float (seconds)
- `rates_created` - Integer
- `rates_updated` - Integer
- `company_ids` - Many2many (companies affected)

---

## Changelog

| Date | Change |
|------|--------|
| 2024-12-06 | Initial plan created |
| 2024-12-06 | Module structure created |
| 2024-12-06 | All models implemented (currency.rate.source, currency.rate.log, res.config.settings) |
| 2024-12-06 | All views created (tree, kanban, form, search for sources and logs) |
| 2024-12-06 | Test extraction wizard implemented |
| 2024-12-06 | Security groups and access rules created |
| 2024-12-06 | Cron jobs for rate updates and log cleanup |
| 2024-12-06 | Demo data with BNA, ECB API, and XPath examples |
| 2024-12-06 | README.md documentation completed |
| 2024-12-06 | Python syntax validation passed - ready for testing |

