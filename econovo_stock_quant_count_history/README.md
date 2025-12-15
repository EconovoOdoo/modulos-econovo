# Inventory Count History

Track inventory counts (both applied and non-applied) in Odoo 17.

## Features

- **Automatic tracking**: When applying inventory adjustments via "Aplicar", a history record is created automatically
- **Manual tracking**: Save counts without applying using the "Save count to history" button
- **Full audit trail**: User, datetime, quantities, differences, warehouse, and more
- **Dedicated menu**: View all counts in Inventory > Reporting > Count History
- **Multi-company support**: Users only see counts from their companies
- **Non-invasive design**: Uses `super()` extension patterns for easy migration to Odoo 18+

## Installation

1. Copy the `econovo_stock_quant_count_history` folder to your Odoo addons path
2. Update the apps list: Settings > Apps > Update Apps List
3. Install the module: Search for "Inventory Count History" and click Install

## Usage

### Viewing Count History

1. Navigate to **Inventory > Reporting > Count History**
2. Use filters to find specific counts (by product, location, warehouse, state, date)
3. Group by various fields for analysis

### Recording Counts

#### Automatic (on Apply)

1. Go to **Inventory > Operations > Inventory Adjustments**
2. Select products and set the counted quantity
3. Click **Aplicar** - a history record is created automatically with state "Applied"

#### Manual (without applying)

1. Go to **Inventory > Operations > Inventory Adjustments**
2. Select products and set the counted quantity
3. Click **Save count to history** - a history record is created with state "Saved"
4. The count is recorded but no inventory adjustment is made

### Viewing History per Product/Location

1. Go to **Inventory > Operations > Inventory Adjustments**
2. Open a quant's form view
3. Click the **Counts** stat button to see all counts for that specific quant

## Technical Details

### Models

- `stock.quant.count.history`: Main model storing count history
- `stock.quant` (inherited): Added methods and fields for integration

### Fields

| Field | Type | Description |
|-------|------|-------------|
| name | Char | Sequence: COUNT/YYYY/NNNNNN |
| company_id | Many2one | Company |
| quant_id | Many2one | Original quant (nullable if deleted) |
| product_id | Many2one | Product |
| location_id | Many2one | Storage location |
| warehouse_id | Many2one | Computed from location |
| lot_id | Many2one | Lot/Serial number |
| package_id | Many2one | Package |
| owner_id | Many2one | Owner |
| quantity_on_hand | Float | Quantity before count |
| quantity_counted | Float | Counted quantity |
| difference | Float | Computed: counted - on_hand |
| user_id | Many2one | User who counted |
| count_datetime | Datetime | When the count was recorded |
| state | Selection | saved / applied |
| was_applied | Boolean | True if adjustment actually applied |
| notes | Text | Optional notes |
| product_uom_id | Many2one | Unit of measure |

### Security

- **Inventory User**: Read-only access
- **Stock Manager**: Full CRUD access
- Multi-company record rule applied

### States

- **Saved**: Count was recorded manually without applying adjustment
- **Applied**: Count was recorded when applying inventory adjustment

### Non-Invasive Code Pattern

The module extends `stock.quant` using `super()`:

```python
def action_apply_inventory(self):
    # Capture values BEFORE applying
    history_vals_list = [...]
    
    # Call original method
    result = super().action_apply_inventory()
    
    # Create history AFTER successful application
    self.env['stock.quant.count.history'].create(history_vals_list)
    
    return result
```

This pattern ensures:
- Original functionality is preserved
- History is only created after successful operations
- Easy to extend in child modules
- Compatible with future Odoo versions

## Translations

Spanish (Argentina) translations included.

## Testing

Run tests with:

```powershell
Set-Location D:\Odoo\ODOO-SRC; .\odoo-manager.ps1 -Action test-ce -TestModule "econovo_stock_quant_count_history"
```

## License

AGPL-3

## Author

Jose D. Leonett - https://github.com/josedleonett
