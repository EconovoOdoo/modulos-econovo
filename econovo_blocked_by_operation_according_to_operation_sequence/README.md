# Econovo Operations Dependency by Sequence

This module enhances the manufacturing process in Odoo 17 by allowing automatic configuration of operation dependencies based on their sequence in bills of materials (BOMs). It ensures that manufacturing operations follow a predefined sequence by automatically setting up the "Blocked By" relationships between operations.

## Features

- Adds a button to automatically set operation dependencies based on sequence when `allow_operation_dependencies` is enabled
- Configures each operation to be blocked by the previous operation in the sequence
- Creates a clear manufacturing workflow based on operation sequence
- Provides a wizard for bulk configuration of multiple BOMs at once
- Includes option to enable operation dependencies for BOMs that don't have it yet

## Usage

### Individual BOM Configuration
1. Enable operation dependencies on a BOM by checking the "Allow Operation Dependencies" checkbox
2. Define your operations and set their sequence numbers
3. Click the "Set Dependencies by Sequence" button above the operations list
4. The system will automatically configure each operation to be blocked by the previous operation in the sequence

### Bulk Configuration
1. Select multiple BOMs from the list view
2. Use the "Set Dependencies by Sequence" action from the Action menu
3. In the wizard, you can choose to enable dependencies for BOMs that don't have them enabled
4. Confirm to process all selected BOMs

## Technical Details

The module extends the `mrp.bom` model and adds:

1. A new action method `action_set_operation_dependencies` that:
   - Sorts operations by sequence
   - Clears any existing dependency relationships
   - Sets each operation to be blocked by the previous operation in the sequence

2. A wizard for bulk processing multiple BOMs:
   - Handles multiple BOMs in a batch process
   - Optionally enables dependencies for BOMs that don't have them
   - Provides feedback on processed BOMs

## Compatibility

- Odoo 17.0

## Dependencies

- Manufacturing (`mrp`) module

## Author

- Econovo

## License

- AGPL-3
