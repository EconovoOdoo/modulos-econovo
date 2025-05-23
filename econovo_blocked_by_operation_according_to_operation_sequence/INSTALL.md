# Installation and Configuration Guide

## Installation

1. Download the module files to your Odoo addons folder
2. Update the module list in Odoo
3. Install the "Econovo Operations Dependency by Sequence" module

```
# Alternative installation via command line
cd /path/to/your/odoo
python -m odoo -d your_database -i econovo_blocked_by_operation_according_to_operation_sequence
```

## Configuration

No special configuration is needed. The module adds its functionality automatically to the Bills of Materials.

### Using the Module

1. Go to Manufacturing > Products > Bills of Materials
2. Create or edit a Bill of Materials
3. Check the "Allow Operation Dependencies" checkbox
4. Add operations with sequence numbers to your BOM
5. Click the "Set Dependencies by Sequence" button to automatically configure dependencies

### Using Bulk Configuration

For multiple Bills of Materials:
1. Go to Manufacturing > Products > Bills of Materials
2. Select multiple BOMs from the list view
3. Click the "Set Dependencies by Sequence" option in the Action menu
4. In the wizard, you can optionally enable dependencies for BOMs that don't have them yet
5. Click "Confirm" to process all selected BOMs

### Verification

To verify that dependencies were set correctly:
1. Go to your Manufacturing > Operations menu
2. Select an operation that should have dependencies
3. Check the "Blocked By" field to see which operations block it

## Troubleshooting

Common issues and solutions:

1. **Button Not Visible**: Ensure "Allow Operation Dependencies" is checked on the BOM
2. **Dependencies Not Working**: Make sure operations have proper sequence numbers
3. **Errors When Setting Dependencies**: Verify there are no circular dependencies in your operations
4. **Multiple BOMs Processing**: Some BOMs might be skipped if they don't have "Allow Operation Dependencies" checked

## Getting Support

If you encounter any issues, please contact Econovo at info@econovo.es
