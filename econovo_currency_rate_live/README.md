# Currency Rate Live Update

Universal currency/asset rate updater for Odoo 17 from any web source using multiple extraction methods.

## Features

- **Agnostic Design:** Works for any country, currency, or asset (USD, EUR, GBP, Bitcoin, Gold, etc.)
- **Currency Relationship:** Define source currency (what you're quoting) and target currency (reference)
- **Multiple Extraction Methods:**
  - **Automatic:** Smart detection of currency values
  - **Regex:** Regular expression patterns
  - **XPath:** XML/HTML path expressions  
  - **JSONPath:** JSON API data extraction
  - **CSS Selector:** Web element selection
- **Flexible Number Formats:** Predefined locale formats + custom separators
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

For CSS Selector support (usually included with lxml):
```bash
pip install cssselect
```

## Configuration

### Creating a Rate Source

1. Go to **Invoicing > Configuration > Currency Rate Sources > Rate Sources**
2. Click **Create**
3. Configure the source:
   - **Name:** Descriptive name (e.g., "USD - Bank Central")
   - **Source Currency:** Currency being quoted (e.g., USD)
   - **Target Currency:** Reference currency (e.g., ARS - defaults to company currency)
   - **Source URL:** Web page or API endpoint
   - **Extraction Method:** Choose the appropriate method

---

## Extraction Methods Reference

### CSS Selector

CSS selectors allow finding HTML elements using the same syntax used in CSS stylesheets or JavaScript (`querySelector`).

#### Configuration

| Field | Description |
|-------|-------------|
| CSS Selector | CSS selector expression |
| CSS Attribute | Attribute to extract (leave empty for text content) |
| Result Index | Which result to use if selector returns multiple elements (1-indexed) |

#### Examples by Use Case

**Select by ID:**
```
HTML:  <span id="rate-usd">1045.50</span>
CSS:   #rate-usd
Result: "1045.50"
```

**Select by Class:**
```
HTML:  <div class="price-value">43250.00</div>
CSS:   .price-value
Result: "43250.00"
```

**Select by Attribute:**
```
HTML:  <td data-currency="USD">1045.50</td>
CSS:   td[data-currency="USD"]
Result: "1045.50"
```

**Descendant of Element:**
```
HTML:  <div id="rates"><table><tr><td>1045.50</td></tr></table></div>
CSS:   #rates table tr td
Result: "1045.50"
```

**N-th Child:**
```
HTML:  <tr><td>USD</td><td>1015</td><td>1045.50</td></tr>
CSS:   tr td:nth-child(3)
Result: "1045.50"
```

#### Syntax Quick Reference

| Selector | Meaning |
|----------|---------|
| `element` | Select by tag name |
| `#id` | Select by ID |
| `.class` | Select by class |
| `[attribute]` | Elements that have the attribute |
| `[attr="value"]` | Attribute equals value |
| `[attr*="value"]` | Attribute contains value |
| `[attr^="value"]` | Attribute starts with value |
| `[attr$="value"]` | Attribute ends with value |
| `parent child` | Descendant (any level) |
| `parent > child` | Direct child |
| `elem1 + elem2` | Immediately following sibling |
| `elem1 ~ elem2` | Following siblings |
| `:first-child` | First child |
| `:last-child` | Last child |
| `:nth-child(n)` | N-th child (1-indexed) |
| `:nth-child(odd/even)` | Odd/even children |
| `:not(selector)` | Negation |
| `selector1, selector2` | Union (OR) |

---

### JSONPath

JSONPath allows navigating and extracting values from JSON responses using XPath-like syntax designed for JSON structures.

#### Configuration

| Field | Description |
|-------|-------------|
| JSONPath Expression | JSONPath expression to extract value |
| Result Index | Which result to use if expression returns an array (1-indexed) |

#### Examples by Use Case

**Simple API with Direct Value:**
```
JSON: {"rate": 1045.50, "currency": "USD"}
JSONPath: $.rate
Result: 1045.50
```

**Nested Structure:**
```
JSON: {"data": {"rates": {"USD": {"buy": 1015, "sell": 1045.50}}}}
JSONPath: $.data.rates.USD.sell
Result: 1045.50
```

**Array of Rates (by Index):**
```
JSON: {"rates": [{"code": "USD", "value": 1045}, {"code": "EUR", ...}]}
JSONPath: $.rates[0].value
Result: 1045
```

**Filter Array by Condition:**
```
JSON: {"rates": [{"code": "USD", "value": 1045}, {"code": "EUR", ...}]}
JSONPath: $.rates[?(@.code=='USD')].value
Result: 1045
```

**Cryptocurrency API (CoinGecko):**
```
JSON: {"bitcoin": {"usd": 43250.00, "usd_24h_change": -2.5}}
JSONPath: $.bitcoin.usd
Result: 43250.00
```

**Multiple Currencies (Open Exchange Rates):**
```
JSON: {"rates": {"ARS": 1045.50, "EUR": 0.92, "GBP": 0.79}}
JSONPath: $.rates.ARS
Result: 1045.50
```

#### Syntax Quick Reference

| Expression | Meaning |
|------------|---------|
| `$` | Root of JSON document |
| `.property` | Access property by name |
| `['property']` | Access property (alternative) |
| `[0]`, `[1]`, `[-1]` | Access array element by index |
| `[*]` | All array elements |
| `[0:5]` | Slice: elements 0 to 4 |
| `[?(@.x > 10)]` | Filter: elements where x > 10 |
| `[?(@.name)]` | Filter: elements that have 'name' property |
| `..property` | Recursive search for property |
| `@` | Current element (in filters) |
| `length` | Array length |

---

### XPath (XML Path Language)

XPath allows navigating HTML/XML document structure by selecting elements by position, attributes, content, or hierarchical relationships.

#### Configuration

| Field | Description |
|-------|-------------|
| XPath Expression | XPath expression to select element |
| XPath Attribute | Attribute to extract (leave empty for text content) |
| Result Index | Which result to use if XPath returns multiple elements (1-indexed) |

#### Examples by Use Case

**Table Cell by ID:**
```
HTML:  <table id="rates"><tr><td>USD</td><td>1045.50</td></tr></table>
XPath: //table[@id='rates']//tr/td[2]
Result: "1045.50"
```

**Table Cell by Content of Another Cell:**
```
HTML:  <tr><td>Bitcoin</td><td class="price">43250.00</td></tr>
XPath: //tr[td[contains(text(),'Bitcoin')]]/td[@class='price']
Result: "43250.00"
```

**Element with Specific Class:**
```
HTML:  <span class="rate-value">1045.50</span>
XPath: //span[@class='rate-value']
Result: "1045.50"
```

**Extract Attribute (Not Text):**
```
HTML:  <input id="rate" value="1045.50" />
XPath: //input[@id='rate']
Attribute: value
Result: "1045.50"
```

**Element Inside Specific Div:**
```
HTML:  <div id="billetes"><table>...<td>1045.50</td>...</table></div>
XPath: //div[@id='billetes']//tr[3]/td[2]
Result: "1045.50"
```

#### Syntax Quick Reference

| Expression | Meaning |
|------------|---------|
| `//` | Search at any level in document |
| `/` | Absolute path from root |
| `.` | Current node |
| `..` | Parent node |
| `@attribute` | Select attribute |
| `[@id='x']` | Filter by attribute equals value |
| `[1]`, `[2]` | Select by position (1-indexed) |
| `[last()]` | Last element |
| `text()` | Text content of node |
| `contains(a,b)` | True if 'a' contains 'b' |
| `starts-with(a,b)` | True if 'a' starts with 'b' |
| `normalize-space()` | Remove extra whitespace |
| `following-sibling` | Following siblings |
| `preceding-sibling` | Preceding siblings |
| `ancestor` | Ancestors (parents, grandparents...) |
| `descendant` | Descendants (children, grandchildren...) |

---

### Regular Expression (Regex)

Regular expressions allow defining text patterns to extract specific values from any textual content.

#### Configuration

| Field | Description |
|-------|-------------|
| Regex Pattern | Regular expression pattern with capture groups |
| Capture Group | Which capture group contains the rate value (1-indexed) |
| Ignore Case | Make pattern case-insensitive |
| Multiline | Make ^ and $ match line boundaries |
| Dotall | Make . match newline characters |

#### Examples by Use Case

**HTML Table with Currency and Value:**
```
HTML:  <td>USD</td><td>1.045,50</td>
Regex: USD</td>\s*<td>([0-9.,]+)</td>
Group: 1
Result: "1.045,50"
```

**JSON Embedded in HTML:**
```
HTML:  <script>var rate = {"usd": 1045.50};</script>
Regex: "usd"\s*:\s*([\d.]+)
Group: 1
Result: "1045.50"
```

**Plain Text with Label:**
```
Text: Bitcoin Price: $43,250.00 USD
Regex: Bitcoin Price:\s*\$?([\d,]+\.?\d*)
Group: 1
Result: "43,250.00"
```

**Multiple Values (Buy/Sell):**
```
HTML:  <td>Compra: 1.015,00</td><td>Venta: 1.045,50</td>
Regex: Compra:\s*([\d.,]+).*?Venta:\s*([\d.,]+)
Group: 2 (for sell price)
Result: "1.045,50"
```

#### Syntax Quick Reference

| Symbol | Meaning |
|--------|---------|
| `.` | Any character (except newline) |
| `\d` | Digit (0-9) |
| `\s` | Whitespace (space, tab, newline) |
| `\w` | Word character (a-z, A-Z, 0-9, _) |
| `*` | Zero or more repetitions |
| `+` | One or more repetitions |
| `?` | Zero or one repetition (optional) |
| `*?` `+?` | Non-greedy mode (minimal match) |
| `[abc]` | Any of: a, b, c |
| `[0-9]` | Range of digits |
| `(...)` | Capture group |
| `(?:...)` | Non-capturing group |
| `^` | Start of line |
| `$` | End of line |
| `\` | Escape special character (e.g., `\.` for literal dot) |

---

### Automatic Detection

The system automatically detects the response format and applies the most appropriate method.

#### Detection Flow

1. **Analyze HTTP Content-Type header:**
   - `application/json` -> JSONPath
   - `application/xml` or `text/xml` -> XPath
   - `text/html` -> Regex or CSS Selector

2. **For JSON:** Search for common fields (rate, value, price, cotizacion)

3. **For HTML:** Search for numeric patterns near the configured currency keyword

#### Configuration

| Field | Description |
|-------|-------------|
| Search Keyword | Keyword to search for (e.g., "USD", "Bitcoin", "dolar") |

#### Advantages
- No technical knowledge required
- Works for simple cases

#### Limitations
- Less precise than manual methods
- May fail on complex pages
- Not recommended for critical production use

---

## Decimal Formats

The module supports multiple decimal formats with predefined locales and custom option:

| Format | Example | Thousand Sep | Decimal Sep |
|--------|---------|--------------|-------------|
| `es_AR` (Argentine/Spanish) | 1.234,56 | `.` | `,` |
| `en_US` (US/International) | 1,234.56 | `,` | `.` |
| `de_DE` (German) | 1.234,56 | `.` | `,` |
| `fr_FR` (French) | 1 234,56 | ` ` | `,` |
| `ch_CH` (Swiss) | 1'234.56 | `'` | `.` |
| `in_IN` (Indian) | 1,23,456.78 | `,` | `.` |
| `custom` (Custom) | Specify separators manually | User defined | User defined |

### Custom Format

When selecting "Custom" format, you can specify:
- **Thousands Separator:** Character(s) used as thousands separator (leave empty if none)
- **Decimal Separator:** Character used as decimal separator (required)

---

## Validation Settings

Configure validation to prevent invalid rates:
- **Min/Max Rate:** Acceptable rate range
- **Max Variation %:** Maximum change from previous rate
- **Validation Action:** Skip, Log Error and Skip, or Use Last Rate

---

## Scheduling

Configure automatic updates:
- **Update Interval:** Hourly, Daily, or Weekly
- **Update Hours:** Specific hours to run (e.g., "9,12,18")
- **Update Weekdays:** Days to run (0=Monday, 6=Sunday)

---

## Testing

Before activating a source, use the **Test Extraction** button to:
1. Verify the URL is accessible
2. Check the extraction pattern works
3. Preview the extracted and processed rate
4. Compare with current rate

---

## Multi-Company

By default, rates are updated for all companies that have the **target currency** as their base currency and don't have a parent company.

You can also select specific companies in the **Companies** tab.

---

## Logs

View execution history at:
**Invoicing > Configuration > Currency Rate Sources > Update Logs**

Logs include:
- Execution time and duration
- HTTP response details
- Raw and processed values
- Error messages and tracebacks

---

## Demo Data

The module includes demo sources for:
- USD - Banco Nacion Argentina (Regex)
- EUR - Banco Nacion Argentina (Regex)
- USD - European Central Bank API (JSONPath)
- GBP - X-Rates (XPath)

---

## Technical Information

### Models

| Model | Description |
|-------|-------------|
| `currency.rate.source` | Main configuration model |
| `currency.rate.log` | Execution history |

### Key Fields

| Field | Description |
|-------|-------------|
| `source_currency_id` | Currency being quoted (e.g., USD) |
| `target_currency_id` | Reference currency (e.g., ARS) |

### Scheduled Actions

| Cron | Frequency | Description |
|------|-----------|-------------|
| Update Rates | Configurable | Execute active sources |
| Cleanup Logs | Daily | Remove old log entries |

### Security Groups

| Group | Access |
|-------|--------|
| Currency Rate Live User | Read-only access, can trigger updates |
| Currency Rate Live Manager | Full access to configuration |

---

## License

AGPL-3

## Author

Jose D. Leonett  
https://github.com/josedleonett
