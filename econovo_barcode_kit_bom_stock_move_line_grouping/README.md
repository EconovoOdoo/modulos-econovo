# Econovo Barcode Kit/BOM Stock Move Line Grouping

## Overview

This module enhances the Odoo 17 stock barcode app to intelligently group kit/BOM components together, providing a cleaner and more intuitive user experience when processing pickings containing kits. **Now with full support for nested grouping** - lot/serial number groups within kit groups!

**Key Features:**
- Groups kit components regardless of source location (e.g., components in Shelf A, B, C appear as one kit)
- **Nested lot/serial grouping** - Preserves Odoo's native lot/serial grouping within kit groups
- Independent collapse/expand for each grouping level (kit → lot groups → individual lines)
- Displays kit name with component count badge instead of individual component names
- Hides source location in collapsed view when components are in multiple locations
- Shows individual component locations when expanded
- Visual distinction with blue borders and subtle background
- Warns if kit components go to different destinations
- Proper completion styling (green background) for completed lines in nested groups
- Fully compatible with `stock_barcode_mrp` (kit explosion)

## Problem Solved

### Before (Standard Odoo Behavior)

When processing a picking with a kit stored across multiple locations:

```
📦 Kit Component 1 (Product A)
   From: Shelf A → To: WH/Stock
   
📦 Kit Component 2 (Product B)
   From: Shelf B → To: WH/Stock
   
📦 Kit Component 3 (Product C - LOT001)
   From: Shelf C → To: WH/Stock
   
📦 Kit Component 3 (Product C - LOT002)
   From: Shelf C → To: WH/Stock
```

**Issues:**
- User doesn't know these are part of the same kit
- No visual grouping or indication of relationship
- Lot-tracked products shown separately even when they should be grouped
- Cluttered interface with many individual lines

### After (With This Module)

```
🧊 My Awesome Kit  [3 components]
   From: 3 locations → To: WH/Stock
   ▼ Click to expand
   
   └─ 📦 Kit Component 1 (Product A)
      From: Shelf A → To: WH/Stock
      
   └─ 📦 Kit Component 2 (Product B)
      From: Shelf B → To: WH/Stock
      
   └─ 📦 Product C  [2 lines]  ← Nested lot group
      From: Shelf C → To: WH/Stock
      ▼ Click to expand
      
      ├─ 📦 Product C - LOT001
      │  From: Shelf C → To: WH/Stock
      │
      └─ 📦 Product C - LOT002
         From: Shelf C → To: WH/Stock
```

**Benefits:**
- Clear visual grouping with kit name at top level
- Nested lot/serial grouping preserved within kits
- Each level can be independently collapsed/expanded
- Collapsed view shows component/line count without clutter
- Source location abstracted when multiple locations (shows "3 locations")
- Expand to see individual component details or lot numbers
- Blue border/background for easy kit identification
- Green completion styling works correctly at all nesting levels

## Installation

### Prerequisites

- Odoo 17.0 Enterprise Edition
- Modules required:
  - `stock_barcode` (Enterprise)
  - `mrp` (Manufacturing)
  - `stock_barcode_mrp` (Enterprise)

### Steps

1. Copy this module to your addons path:
   ```bash
   cp -r econovo_barcode_kit_bom_stock_move_line_grouping /path/to/odoo/addons/
   ```

2. Update apps list:
   - Go to Apps menu
   - Click "Update Apps List"

3. Install the module:
   - Search for "Econovo Barcode Kit Grouping"
   - Click "Install"

4. No configuration needed - works automatically!

## Usage

### Creating a Kit Product

1. **Create a BoM with type "Kit":**
   - Go to Manufacturing > Products > Products
   - Create or edit a product (e.g., "Computer Kit")
   - Go to "Bill of Materials" tab
   - Click "Create" and set:
     - BoM Type: **Kit**
     - Components: Add all components (e.g., Mouse, Keyboard, Monitor)

2. **Stock the components in different locations** (optional):
   - Mouse: 10 units in WH/Stock/Shelf A
   - Keyboard: 10 units in WH/Stock/Shelf B
   - Monitor: 10 units in WH/Stock/Shelf C

3. **Create a delivery order with the kit:**
   - Sales > Orders > Create
   - Add the kit product (e.g., "Computer Kit")
   - Confirm order
   - Go to Delivery

4. **Process with barcode app:**
   - Click "Barcode" button on picking
   - You'll see components grouped under "Computer Kit" 🎉

### Visual Indicators

#### Kit Group (Collapsed)
```
╔════════════════════════════════════════════╗
║ 🧊 Computer Kit  [3 components]            ║
║ ↗ 3 locations → WH/Output                  ║
║                                   [▼]      ║
╚════════════════════════════════════════════╝
```

#### Kit Group (Expanded)
```
╔════════════════════════════════════════════╗
║ 🧊 Computer Kit  [3 components]            ║
║ ↗ 3 locations → WH/Output          [▲]    ║
╠════════════════════════════════════════════╣
║   └─ 📦 Mouse                              ║
║      ↗ WH/Stock/Shelf A → WH/Output       ║
║      Qty: 1.00 Unit(s)                     ║
║                                            ║
║   └─ 📦 Keyboard                           ║
║      ↗ WH/Stock/Shelf B → WH/Output       ║
║      Qty: 1.00 Unit(s)                     ║
║                                            ║
║   └─ 📦 Monitor                            ║
║      ↗ WH/Stock/Shelf C → WH/Output       ║
║      Qty: 1.00 Unit(s)                     ║
╚════════════════════════════════════════════╝
```

#### Warning: Multiple Destinations
```
╔════════════════════════════════════════════╗
║ 🧊 Fragmented Kit  [3 components]          ║
║ ⚠️ Multiple destinations                   ║
║ ↗ 2 locations → 3 locations       [▼]     ║
╚════════════════════════════════════════════╝
```
*Yellow border indicates components go to different destinations*

## Technical Details

### Architecture

#### Backend (Python)
- **Model:** `stock.picking`
- **Method Override:** `_get_stock_barcode_data()`
- **Exposed Fields:**
  - `stock.move.description_bom_line` (e.g., "Computer Kit - 1/3")
  - `stock.move.bom_line_id` (link to mrp.bom.line)

#### Frontend (JavaScript)
- **Model Patch:** `BarcodePickingModel`
- **Methods:**
  - `groupKey(line)` - Modified to group by kit instead of location
  - `get groupedLines` - Adds kit metadata (name, count, locations)

#### UI (XML/SCSS)
- **Template:** Extends `stock_barcode.GroupedLineComponent`
- **Component:** `KitGroupedLineComponent`
- **Styles:** Blue borders, badges, indentation

### Grouping Logic

#### Standard Odoo Grouping Key
```javascript
groupKey(line) {
    return `${product_id}_${location_id}_${move_id}_${location_dest_id}`;
}
```

#### Kit Grouping Key (This Module)
```javascript
groupKey(line) {
    if (move.description_bom_line) {
        const kitName = move.description_bom_line.replace(/\s*-\s*\d+\/\d+\s*$/, '');
        return `kit_${kitName}_${move_id}_${location_dest_id}`;
        // ⚠️ Note: location_id excluded to allow multi-location grouping
    }
    return super.groupKey(line); // Standard behavior for non-kits
}
```

### Metadata Added to Grouped Lines

```javascript
{
    is_kit_group: true,
    kit_name: "Computer Kit",
    component_count: 3,
    has_multiple_source_locations: true,
    source_location_count: 3,
    has_multiple_dest_locations: false,
    dest_location_count: 1,
}
```

## Compatibility

### Modules
- ✅ Compatible with `stock_barcode_mrp` (kit explosion)
- ✅ Compatible with `mrp_workorder` (work orders)
- ✅ Compatible with custom location restrictions
- ⚠️ May need adjustments for custom barcode flows

### Odoo Versions
- **Tested:** Odoo 17.0 Enterprise
- **Not compatible:** Odoo 16.0 or lower (different architecture)

## Troubleshooting

### Kit Not Grouping

**Symptom:** Components show as individual lines

**Possible Causes:**
1. BoM type is not "Kit" (must be type `phantom`)
   - Solution: Edit BoM, set type to "Kit"

2. Module not installed
   - Solution: Check Apps > Installed, search "Econovo Barcode Kit"

3. Cache issue
   - Solution: Restart Odoo server, clear browser cache

### Missing Kit Name

**Symptom:** Grouped line shows first component name instead of kit name

**Possible Causes:**
1. `description_bom_line` not computed
   - Solution: Check if BOM has `display_name` or `product_id`

2. Backend not exposing field
   - Solution: Check if `stock.picking._get_stock_barcode_data()` includes `stock.move` records

### Styling Not Applied

**Symptom:** No blue borders or custom styles

**Possible Causes:**
1. SCSS not loaded
   - Solution: Check browser console for asset loading errors
   - Solution: Update assets: `odoo-bin -u econovo_barcode_kit_bom_stock_move_line_grouping`

2. CSS cache
   - Solution: Clear browser cache, hard refresh (Ctrl+Shift+R)

## Development

### File Structure
```
econovo_barcode_kit_bom_stock_move_line_grouping/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── stock_picking.py (backend field exposure)
├── static/src/
│   ├── models/
│   │   └── barcode_picking_model.js (grouping logic)
│   ├── components/
│   │   ├── kit_grouped_line.xml (template)
│   │   └── kit_grouped_line.js (component)
│   └── scss/
│       └── kit_barcode.scss (styles)
└── README.md
```

### Extending This Module

#### Add Custom Metadata

Edit `static/src/models/barcode_picking_model.js`:

```javascript
get groupedLines() {
    const lines = super.groupedLines;
    for (const line of lines) {
        if (line.is_kit_group) {
            // Add your custom metadata
            line.my_custom_field = calculateSomething(line);
        }
    }
    return lines;
}
```

#### Customize Styling

Edit `static/src/scss/kit_barcode.scss`:

```scss
.o_barcode_kit_group {
    border-left-color: #28a745; // Green instead of blue
}
```

#### Add Fields to Backend

Edit `models/stock_picking.py`:

```python
def _get_stock_barcode_data(self):
    data = super()._get_stock_barcode_data()
    moves = self.move_ids
    if moves:
        move_fields = ['id', 'description_bom_line', 'bom_line_id', 'my_custom_field']
        move_data = moves.read(move_fields, load=False)
        data['records']['stock.move'].extend(move_data)
    return data
```

## License

AGPL-3

## Author

**Jose D. Leonett**
- GitHub: https://github.com/josedleonett
- Module: econovo_barcode_kit_bom_stock_move_line_grouping

## Support

For issues, feature requests, or contributions:
1. Open an issue on GitHub
2. Submit a pull request
3. Contact the author

---

**Version:** 17.0.1.0.0  
**Last Updated:** 2024
