# Econovo Location Labels

Print individual location barcode labels in DYMO 100×50mm and 100×70mm formats for Odoo 17.

## 📋 Features

- **Individual Location Printing**: Print labels directly from location form view with a single click
- **Batch Printing**: Select multiple locations and print labels via wizard
- **Two Label Sizes**: 
  - 100×50mm (compact format)
  - 100×70mm (detailed format with more spacing)
- **Clean Minimalist Layout**: 
  - Company logo
  - Warehouse name
  - Location name (large, bold)
  - Barcode with automatic symbology detection
  - Complete location path
- **DYMO Compatible**: Optimized for DYMO label printers
- **Professional Design**: Responsive layout adapts to both label sizes

## 📦 Installation

1. Copy the `econovo_location_labels` folder to your Odoo addons directory
2. Update the apps list: `Settings → Apps → Update Apps List`
3. Search for "Econovo Location Labels"
4. Click **Install**

## 🚀 Usage

### Individual Location Print

1. Navigate to **Inventory → Configuration → Locations**
2. Open any location record
3. Click the **"Print Location Label"** button in the header
4. Select your preferred format:
   - DYMO Location 100×50mm (compact)
   - DYMO Location 100×70mm (detailed)
5. Click **Print**

### Batch Printing (Multiple Locations)

1. Navigate to **Inventory → Configuration → Locations**
2. Select multiple locations from the list view (checkbox)
3. Click **Action → Print → Choose Label Layout**
4. Select your preferred format
5. Click **Print**

## 📐 Label Layout

### 100×50mm Format (Compact)
```
┌────────────────────────────────────┐
│ [LOGO]                  WAREHOUSE  │
├────────────────────────────────────┤
│          LOCATION-NAME             │
│                                    │
│      ██████████████████            │
│      LOCATION/BARCODE              │
├────────────────────────────────────┤
│ WH/Stock/Sector/Location           │
└────────────────────────────────────┘
```

### 100×70mm Format (Detailed)
```
┌────────────────────────────────────┐
│ [LOGO]                  WAREHOUSE  │
├────────────────────────────────────┤
│                                    │
│          LOCATION-NAME             │
│                                    │
│      ██████████████████            │
│      LOCATION/BARCODE              │
│                                    │
├────────────────────────────────────┤
│                                    │
│ WH/Stock/Sector/Location           │
└────────────────────────────────────┘
```

## 🔧 Technical Details

- **Odoo Version**: 17.0
- **Dependencies**: `stock`
- **Models Extended**: `stock.location`
- **Wizard Pattern**: Inherits `product.label.layout`
- **Report Engine**: QWeb PDF
- **Styling**: Custom SCSS for precise dimensions

## 📝 Configuration

No additional configuration required. The module works out of the box once installed.

**Note**: Ensure your locations have barcodes assigned for optimal results. Locations without barcodes will display "No Barcode" on the label.

## 🐛 Troubleshooting

### Labels not printing at correct size
- Verify your printer settings match the paper format (100×50mm or 100×70mm)
- Check printer DPI is set to 96
- Ensure "Fit to page" is disabled in print dialog

### Barcode not scanning
- Ensure the location has a valid barcode assigned
- Check barcode symbology is supported by your scanner
- Increase label size if needed (use 100×70mm format)

### Logo not appearing
- Verify your company has a logo configured in `Settings → Companies`
- Check logo image format (PNG/JPG recommended)

## 👤 Author

**Jose D. Leonett**
- Website: [https://github.com/josedleonett](https://github.com/josedleonett)

## 📄 License

AGPL-3

---

## 🔄 Version History

### Version 17.0.1.0.0
- Initial release
- Support for 100×50mm labels
- Support for 100×70mm labels
- Individual and batch printing
- Minimalist layout with logo
- Barcode auto-detection

---

**Econovo Location Labels** - Simplify your warehouse location management with professional barcode labels.
