# Econovo - Stock Barcode Inventory Hide Quantity to Count

## Overview

This module adds a "blind count" feature to Odoo's Barcode app for inventory adjustments. When enabled, it hides the expected quantity (quantity on hand) from operators, forcing them to perform a true blind count without being influenced by the system's expected values.

## Features

- **Configurable blind count mode**: Enable or disable via Inventory Settings
- **Visual feedback**: Shows "?" instead of actual quantities when blind count is active
- **Hidden "Set Full Quantity" button**: Prevents operators from auto-filling with real stock values
- **Per-company setting**: Each company can have its own configuration
- **Non-disruptive**: Default behavior matches standard Odoo (quantities shown)

## Visual Behavior

### Quantity Display

| Mode | Before Counting | After Counting |
|------|-----------------|----------------|
| **Normal** (Show Quantity enabled) | `0 / 15` | `12 / 15` |
| **Blind Count** (Show Quantity disabled) | `? / ?` | `12 / ?` |

### Button Layout

| Mode | Buttons Available |
|------|-------------------|
| **Normal** | `[✏️ Edit]` `[Set]` `[-1]` `[+1]` |
| **Blind Count** | `[✏️ Edit]` `[-1]` `[+1]` |

> **Note**: The "Set Full Quantity" button is hidden in blind count mode because it would auto-fill with the real stock quantity, breaking the anonymity of the count.

## Configuration

1. Go to **Inventory > Configuration > Settings**
2. Scroll to the **Barcode** section
3. Find the **Show Quantity to Count** checkbox:
   - ✅ **Checked** (default): Normal behavior - expected quantity is visible
   - ☐ **Unchecked**: Blind count mode - expected quantity is hidden as "?"
4. Click **Save**

## Technical Details

### Dependencies

- `stock_barcode` (Odoo Enterprise)

### Modified Components

| Component | Type | Description |
|-----------|------|-------------|
| `res.company` | Python Model | Stores `show_quantity_to_count` field |
| `res.config.settings` | Python Model | Exposes setting in Inventory configuration |
| `StockBarcodeController` | Controller | Passes configuration to JavaScript frontend |
| `BarcodeQuantModel` | JavaScript | Controls quantity demand display and Set button visibility |
| `LineQuantity` | OWL Template | Displays "?" when quantity is hidden |

### How It Works

1. The configuration is stored at company level (`res.company.show_quantity_to_count`)
2. When the Barcode app loads, the controller passes this setting in the `groups` data
3. The JavaScript patch:
   - Modifies `getQtyDemand()` to return `false` when blind count is active
   - Overrides `displaySetButton` to return `false`, hiding the auto-fill button
4. The OWL template shows "/ ?" instead of the actual quantity when `qtyDemand` is `false`

## Compatibility

- **Odoo Version**: 17.0
- **Edition**: Enterprise (requires `stock_barcode` module)
- **License**: AGPL-3

## Author

- **Jose D. Leonett**
- **Website**: https://github.com/josedleonett

## Changelog

### 17.0.1.0.0

- Initial release
- Added blind count feature for inventory adjustments
- Configurable via Inventory Settings
