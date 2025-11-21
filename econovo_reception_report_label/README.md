# Econovo Reception Report Label

Custom reception report labels for Odoo 17 with enhanced barcode support.

## Features

- Product barcode (large, prominent)
- Origin operation barcode (picking where product was received)
- Destination operation barcode (picking where product will be delivered)
- Delivery information (sale order, manufacturing order, or partner)
- Quantity and lot/serial number display

## Label Layout

The label is optimized for Dymo Label Sheet (100×70mm) and includes:

1. **Header**: Company logo and print date/time
2. **Product Section**: Large barcode, internal reference, and product name
3. **Flow Table**: Three-row table showing:
   - DE (Origin): Source picking operation with barcode
   - HACIA (Destination): Target picking operation with barcode (or location if no picking)
   - ENTREGAR (Deliver to): Sale order/Manufacturing order/Partner information
4. **Footer**: Quantity with UoM and lot/serial numbers

## Usage

This module extends the standard Odoo reception report (`action_view_reception_report`) which appears when validating a receipt.

The labels are printed when you click "Print Labels" in the reception report wizard.

## Technical Details

- **Model**: `stock.move`
- **Inherits**: `stock.report_reception_report_label`
- **Paper Format**: Custom 100×70mm (exclusive for reception labels)
- **Font**: JetBrainsMono (monospace for better barcode readability)
- **Barcode Engine**: Code128 with custom sizing (product: 850x140px, flow: 700x150px)

## Author

Jose D. Leonett - https://github.com/josedleonett

## License

AGPL-3
