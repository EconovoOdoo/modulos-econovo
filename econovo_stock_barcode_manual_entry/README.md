# Stock Barcode Manual Entry

## Overview

This module adds a **manual barcode entry button** to the Stock Barcode main menu, allowing users to type barcodes manually without requiring a physical scanner or mobile camera.

## Features

- 🔤 **Manual Entry Button**: Visible button on the main barcode screen
- ♻️ **Reuses Existing Components**: Uses Odoo's built-in `ManualBarcodeScanner` dialog
- 🔌 **Low Coupling**: Minimal changes to original code for easy maintenance
- 📱 **Mobile Friendly**: Works on both desktop and mobile devices
- 🚀 **Lightweight**: No additional models or database changes

## Installation

1. Place the module in your Odoo addons path
2. Update the app list
3. Install "Stock Barcode Manual Entry"

## Usage

1. Navigate to the **Barcode** application
2. On the main screen, click the **"Manual Entry"** button (keyboard icon)
3. Type the barcode in the dialog
4. Click **Apply** or press **Enter**

## Technical Details

### Implementation Approach

This module uses **Odoo's recommended extension patterns**:

1. **OWL Patch**: Extends `MainMenu` component prototype to add the `openManualBarcodeEntry` method
2. **Template Inheritance**: Uses `t-inherit-mode="extension"` to add the button to the existing template
3. **Component Reuse**: Leverages the existing `ManualBarcodeScanner` component from `stock_barcode`

### File Structure

```
econovo_stock_barcode_manual_entry/
├── __init__.py
├── __manifest__.py
├── README.md
└── static/
    └── src/
        ├── main_menu_patch.js      # OWL patch for MainMenu
        ├── main_menu_patch.xml     # Template extension
        └── main_menu_patch.scss    # Button styling
```

### Migration Notes

This module is designed for **easy migration** to future Odoo versions:

- Uses standard OWL patching mechanism
- Template inheritance with XPath is version-independent
- No modification of core files
- Minimal dependencies

**When migrating**, verify:
1. The `ManualBarcodeScanner` component path hasn't changed
2. The `MainMenu` component still exists with the same structure
3. The XPath selector for the template still matches

## Compatibility

- **Odoo Version**: 17.0
- **Dependencies**: `stock_barcode` (Enterprise)
- **License**: AGPL-3

## Author

- **Jose D. Leonett**
- GitHub: [josedleonett](https://github.com/josedleonett)

## Changelog

### 17.0.1.0.0 (Initial Release)
- Added manual barcode entry button to main menu
- Implemented using OWL patch and template inheritance
- Added responsive styling
