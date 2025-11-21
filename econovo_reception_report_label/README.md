# Econovo Reception Report Label

Custom reception report labels for Odoo 17 with enhanced barcode support.

## Features

- Product barcode (large, prominent)
- Origin operation barcode (picking where product was received)
- Destination operation barcode (picking where product will be delivered)
- Delivery information (sale order, manufacturing order, or partner)
- Quantity and lot/serial number display

## Label Layout

The label is optimized for 100×70mm thermal labels and includes:

1. **Header**: Company logo and print date/time
2. **Product Section**: Large barcode (850×140px), internal reference, and product name
3. **Flow Table**: Three-row table showing:
   - DE (Origin): Source picking operation with barcode (700×150px)
   - RESERVADO PARA (Reserved for): Target picking operation with barcode (700×150px)
   - ENTREGAR (Deliver to): Sale order/Manufacturing order/Partner information
4. **Footer**: Horizontal layout with quantity, UoM, and lot/serial numbers

## Usage

This module extends the standard Odoo reception report (`action_view_reception_report`) which appears when validating a receipt.

The labels are printed when you click "Print Labels" in the reception report wizard.

## Technical Details

- **Model**: `stock.move`
- **Inherits**: `stock.report_reception_report_label`
- **Paper Format**: 100×70mm thermal label
- **Barcode Engine**: Code128 via QWeb barcode widget
  - Product barcode: 850×140px
  - Flow barcodes (origin/destination): 700×150px
- **Fonts**: JetBrainsMono, DejaVuSansMono, PlusJakartaSans
- **Layout**: Fixed heights, overflow:hidden, flexbox with row direction in footer
- **Optimizations**: 
  - Removed conflicting width properties to prevent overflow
  - Reduced line-height to eliminate extra spacing
  - Footer elements use horizontal layout (flex-direction:row) with 2mm gap

## Author

Jose D. Leonett - https://github.com/josedleonett

## License

AGPL-3
