# Currency Rate Live Update

Universal currency/asset rate updater for Odoo 17 from any web source using multiple extraction methods.

## Features

- **Agnostic Design:** Works for any country, currency, or asset (USD, EUR, GBP, Bitcoin, Gold, etc.)
- **Multiple Extraction Methods:**
  - **Automatic:** Smart detection of currency values
  - **Regex:** Regular expression patterns
  - **XPath:** XML/HTML path expressions  
  - **JSONPath:** JSON API data extraction
  - **CSS Selector:** Web element selection
- **Multi-company Support:** Updates rates for all or selected companies
- **Flexible Scheduling:** Configure execution frequency, days, and time restrictions
- **Complete Logging:** Execution history with error tracking and performance metrics
- **Validation:** Rate range limits and change percentage validation
- **Odoo.sh Compatible:** No iframes, no CSP restrictions

## Installation

1. Copy the module to your Odoo addons folder
2. Update the apps list
3. Install "Currency Rate Live Update"

### Optional Dependencies

For enhanced JSONPath support:
```bash
pip install jsonpath-ng
```

## Configuration

### Creating a Rate Source

1. Go to **Invoicing > Configuration > Currency Rate Sources > Rate Sources**
2. Click **Create**
3. Configure the source:
   - **Name:** Descriptive name (e.g., "USD - Central Bank")
   - **Currency:** Target currency to update
   - **Source URL:** Web page or API endpoint
   - **Extraction Method:** Choose the appropriate method

### Extraction Methods

#### Automatic Detection
Best for simple pages with clearly labeled rates. Configure keywords to help locate the value.

#### Regex (Regular Expressions)
For complex text patterns:
```
Pattern: Dolar[^0-9]*([0-9]+[.,][0-9]+)
Group: 1
```

#### XPath
For HTML/XML documents:
```
//table[@id='rates']//tr[contains(.,'USD')]/td[2]/text()
```

#### JSONPath
For JSON API responses:
```
$.data.rates.USD.value
```

#### CSS Selector
For web page elements:
```
table.rates tr.usd td.value
```

### Decimal Formats

The module supports multiple decimal formats:
- **es_AR (1.234,56):** Spanish/Latin American
- **en_US (1,234.56):** US/UK
- **de_DE (1.234,56):** German
- **fr_FR (1 234,56):** French
- **ch_CH (1'234.56):** Swiss
- **in_IN (1,23,456.78):** Indian

### Validation Settings

Configure validation to prevent invalid rates:
- **Min/Max Rate:** Acceptable rate range
- **Max Variation %:** Maximum change from previous rate
- **Validation Action:** Warn, Skip, or Use Last Rate

### Scheduling

Configure automatic updates:
- **Frequency:** Hourly, Daily, Weekly, or Custom
- **Weekdays Only:** Skip weekends
- **Skip Holidays:** (Future feature)

## Testing

Before activating a source, use the **Test Extraction** button to:
1. Verify the URL is accessible
2. Check the extraction pattern works
3. Preview the processed rate
4. Compare with current rate

## Multi-Company

By default, rates are updated for all companies without a parent company. 
You can select specific companies in the **Companies** tab.

## Logs

View execution history at:
**Invoicing > Configuration > Currency Rate Sources > Update Logs**

Logs include:
- Execution time and duration
- HTTP response details
- Raw and processed values
- Error messages and tracebacks

## Demo Data

The module includes demo sources for:
- USD - Banco Nacion Argentina (Regex)
- EUR - Banco Nacion Argentina (Regex)
- USD - European Central Bank API (JSONPath)
- GBP - X-Rates (XPath)

## Technical Information

### Models

| Model | Description |
|-------|-------------|
| `currency.rate.source` | Main configuration model |
| `currency.rate.log` | Execution history |

### Scheduled Actions

| Cron | Frequency | Description |
|------|-----------|-------------|
| Update Rates | Hourly | Execute active sources |
| Cleanup Logs | Daily | Remove old log entries |

### Security Groups

| Group | Access |
|-------|--------|
| Currency Rate Live User | Read-only access, can trigger updates |
| Currency Rate Live Manager | Full access to configuration |

## License

AGPL-3

## Author

Jose D. Leonett  
https://github.com/josedleonett
