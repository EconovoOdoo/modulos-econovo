# Stock Quant Relocate Permission

## Description

This module allows users without the **Inventory Administrator** role to use the **"Relocate"** button in the Quants view (`stock.quant`).

## Problem it solves

In standard Odoo, the "Relocate" button is only visible and usable by users with the `stock.group_stock_manager` group (Inventory Administrator). This can be too restrictive when you want operational users to be able to relocate stock without granting them all administration permissions.

## Solution

The module creates a specific permission group called **"Can Relocate Inventory Stock"** that:

1. Makes the "Relocate" button visible for users in the group
2. Grants the necessary permissions on the `stock.quant.relocate` wizard

## Affected locations

The "Relocate" button appears in:

- **Inventory → Reports → Locations** (`stock.view_stock_quant_tree_editable` view for Administrators)
- **Inventory → Reports → Locations** (`stock.view_stock_quant_tree` view for Users - **button added by this module**)
- **Inventory → Operations → Inventory Adjustments** (`stock.view_stock_quant_tree_inventory_editable` view)
- **Products → On Hand Quantity** (uses `stock.view_stock_quant_tree` for Users - **button added by this module**)

## Installation

1. Copy the module to the addons folder
2. Update the application list
3. Install the module "Stock Quant Relocate Permission"

## Configuration

1. Go to **Settings → Users & Companies → Users**
2. Select the desired user
3. In the **"Extra Rights"** section, enable **"Can Relocate Inventory Stock"**
4. Save

## Prerequisites

The user must have at least the **"User"** role in Inventory (`stock.group_stock_user`) to access the views where the button appears.

## Technical information

| Aspect | Detail |
|--------|--------|
| Technical name | `econovo_stock_quant_relocate_permission` |
| Version | 17.0.1.0.0 |
| Dependencies | `stock` |
| License | AGPL-3 |

### Created group

| XML ID | Name |
|--------|------|
| `econovo_stock_quant_relocate_permission.group_stock_quant_relocate` | Can Relocate Inventory Stock |

### Granted permissions

| Model | Read | Write | Create | Delete |
|-------|------|-------|--------|--------|
| `stock.quant.relocate` | ✅ | ✅ | ✅ | ❌ |

## Author

- **Jose D. Leonett**
- GitHub: [josedleonett](https://github.com/josedleonett)

## License

This module is licensed under AGPL-3.
