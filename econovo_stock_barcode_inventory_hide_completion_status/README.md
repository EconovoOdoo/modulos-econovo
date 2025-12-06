# Econovo - Stock Barcode Inventory Hide Completion Status

## Overview

This module adds a configuration option to hide the visual completion status (green/red feedback) during inventory adjustments in the Barcode app. When enabled, lines appear with a neutral background, and counted lines are highlighted with a yellow color - allowing operators to track their progress without knowing if their count is correct.

**Important**: This feature only applies to **Inventory Adjustments**, not to picking operations.

## Features

- **Configurable completion status visibility**: Enable or disable via Inventory Settings
- **Neutral line styling**: Uncounted lines appear with neutral background
- **Yellow highlight for counted lines**: Lines with qty > 0 are highlighted in yellow
- **Per-company setting**: Each company can have its own configuration
- **Inventory adjustments only**: Does not affect picking operations
- **Non-disruptive**: Default behavior matches standard Odoo (completion status shown)

## Visual Behavior

| Mode | Line Appearance |
|------|-----------------|
| **Normal** (Show Completion Status enabled) | ✅ Green if complete, 🔴 Red/Cream if incomplete |
| **Hidden** (Show Completion Status disabled) | ⬜ Neutral for uncounted, 🟡 Yellow for counted (qty > 0) |

## Configuration

1. Go to **Inventory > Configuration > Settings**
2. Scroll to the **Barcode** section
3. Find the **Show Completion Status** checkbox:
   - ✅ **Checked** (default): Normal behavior - green/red visual feedback
   - ☐ **Unchecked**: Blind mode - neutral/yellow without completion feedback
4. Click **Save**

## Use Cases

- **Blind counting**: Combined with the "Hide Quantity to Count" module, provides a complete blind counting experience
- **Unbiased validation**: Prevents operators from being influenced by visual completion status
- **Progress tracking**: Yellow highlighting lets operators see which lines they've already counted
- **Training**: Useful for training new operators without revealing if their counts are correct

## Technical Details

### Dependencies

- `stock_barcode` (Odoo Enterprise)

### Modified Components

| Component | Type | Description |
|-----------|------|-------------|
| `res.company` | Python Model | Stores `show_completion_status` field |
| `res.config.settings` | Python Model | Exposes setting in Inventory configuration |
| `StockBarcodeController` | Controller | Passes configuration to JavaScript frontend |
| `LineComponent` | JavaScript | Controls line CSS classes based on setting |
| `line.scss` | SCSS | Defines neutral and counted line styling |

### CSS Classes

| Class | Applied When | Color |
|-------|--------------|-------|
| `o_line_neutral` | Completion status hidden | Neutral cream (`#fcf9f2`) |
| `o_line_counted` | Line has qty_done > 0 | Yellow (`rgba(255, 255, 90, 0.5)`) |

### How It Works

1. The configuration is stored at company level (`res.company.show_completion_status`)
2. When the Barcode app loads, the controller passes this setting in the `groups` data
3. The JavaScript patch checks if `resModel === 'stock.quant'` (inventory adjustments only)
4. The `componentClasses` getter returns:
   - `o_line_neutral` for all lines when hidden
   - `o_line_counted` additionally when `qtyDone > 0`
5. The SCSS applies the corresponding background colors

## Compatibility

- **Odoo Version**: 17.0
- **Edition**: Enterprise (requires `stock_barcode` module)
- **License**: AGPL-3

## Related Modules

- `econovo_stock_barcode_inventory_hide_quantity_to_count`: Hides expected quantities for blind counting

## Author

- **Jose D. Leonett**
- **Website**: https://github.com/josedleonett

## Changelog

### 17.0.1.0.0

- Initial release
- Added completion status visibility toggle
- Neutral line styling when completion status is hidden
