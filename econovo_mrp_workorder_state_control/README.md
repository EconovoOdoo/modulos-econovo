# MRP Workorder State Control (Odoo 19 Backport)

## Description

This module backports **Odoo 19** functionality that allows flexible workorder state changes, including the ability to revert work orders from `done` to `ready`.

## Implementation

This module is an **EXACT COPY** of Odoo 19 code:
- `set_state()` method copied verbatim
- `state` field redefined without `readonly=True`
- `action_mark_as_done()` method added as alias of `button_finish`

## Features

✅ **Identical implementation to Odoo 19**
- 100% compatible source code with Odoo 19
- No proprietary modifications
- Easy to migrate when upgrading to Odoo 19

✅ **Flexible state control**
- Change workorders between any state
- Revert from `done` → `ready` → `progress`
- Mass actions from list view

✅ **Security**
- Specific permission group: `MRP Workorder State Manager`
- Confirmation before reverting states
- Only authorized users can modify states

## Use Cases

1. **Error correction**: Revert a workorder mistakenly marked as done
2. **Reprocessing**: Re-process an operation that didn't meet quality standards
3. **Operational flexibility**: Adjust production flow according to shop floor needs

## Installation

1. Copy the module to the addons folder:
   ```
   modulos-econovo/econovo_mrp_workorder_state_control/
   ```

2. Update app list in Odoo

3. Install the "MRP Workorder State Control" module

4. Assign the "MRP Workorder State Manager" group to authorized users

## Usage

### From Form View

1. Open a workorder in `done` state
2. Click the **"⟲ Revert to Ready"** button
3. Confirm the action
4. The workorder will return to `ready` state
5. You can restart it with **"▶ Set to Progress"**

### From List View (Mass Actions)

1. Select multiple workorders
2. Click one of the header buttons:
   - **Set to Ready**
   - **Set to Progress**
   - **Set to Done**
3. The change will be applied to all selected records

## Differences with Odoo 17 Base

| Aspect | Odoo 17 Base | This Module (Odoo 19) |
|---------|--------------|----------------------|
| `state` field | `readonly=True` | `readonly=False` |
| `set_state()` method | ❌ Does not exist | ✅ Exists |
| Revert `done` → `ready` | ❌ Not allowed | ✅ Allowed |
| `action_mark_as_done()` | ❌ Does not exist | ✅ Exists |

## Warnings

⚠️ **IMPORTANT**: This module allows modifying the state of already completed workorders. Use with caution:

- Only grant permissions to trusted users
- May generate inconsistencies if reverting a workorder that already processed inventory
- Review the Manufacturing Order state before reverting

## Compatibility

- **Odoo 17**: ✅ Fully compatible
- **Odoo 18**: ✅ Compatible (although not necessary)
- **Odoo 19**: ✅ Native functionality (module not necessary)

## Source Code

The `set_state()` method is copied from Odoo 19 commit:
- **Commit**: `3f10d3c31b9d8aa65f4006f899afea5fb26b6719`
- **File**: `odoo/addons/mrp/models/mrp_workorder.py`
- **Message**: "[IMP] mrp : simplify workorder compute state"

## Author

- **Jose D. Leonett**
- **GitHub**: https://github.com/josedleonett
- **License**: AGPL-3

## Support

To report bugs or request features, create an issue in the repository.

## Changelog

### Version 17.0.1.0.0 (2025-12-19)
- Initial version
- Exact backport of Odoo 19 functionality
- `set_state()` method implemented
- Security group created
- Views with action buttons added
