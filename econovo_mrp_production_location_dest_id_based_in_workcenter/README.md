# Econovo MRP Production Location Dest ID Based in Workcenter

This module extends Odoo's manufacturing functionality to allow setting destination locations for finished products at the workcenter level instead of just at the production order level.

## Features

- **Workcenter-level destination configuration**: Each workcenter can be configured with a specific destination location for finished products
- **Automatic location assignment**: Production orders automatically use the destination location from the **last** workcenter that has one configured
- **Manufacturing logic**: Using the last workcenter makes manufacturing sense as the final operation determines where finished products should be stored
- **Fallback behavior**: If no workcenter has a destination configured, the standard Odoo behavior is maintained
- **Visual indicators**: Production orders show which workcenter destination is being used
- **Search and filtering**: Find workcenters and production orders based on destination location usage

## Installation

1. Copy this module to your Odoo addons directory
2. Update the addon list: `Settings > Apps > Update Apps List`
3. Install the module: Search for "Econovo MRP Production Location Dest ID Based in Workcenter" and click Install

## Testing

The module includes unit tests to verify functionality:

```bash
# Run specific module tests
odoo-bin -d your_database -i econovo_mrp_production_location_dest_id_based_in_workcenter --test-enable --stop-after-init

# Run only this module's tests
odoo-bin -d your_database --test-tags econovo_mrp_production_location_dest_id_based_in_workcenter --stop-after-init
```

## Configuration

### Setting up Workcenter Destinations

1. Go to **Manufacturing > Configuration > Work Centers**
2. Open a work center you want to configure
3. In the **Locations** section, set the **Destination Location** field
4. Save the work center

### Using in Production Orders

When you create a manufacturing order that uses a routing with configured workcenters:

1. The system will automatically check all workcenters in the routing
2. If any workcenter has a destination location configured, the **last** one in the routing sequence will be used as the destination for finished products
3. The last workcenter with a destination location takes precedence (this makes manufacturing sense as the final operation determines final storage)
4. If no workcenter has a destination configured, the standard location from the operation type is used

## Technical Details

### Field Analysis

The module extends the standard `mrp.production.location_dest_id` field computation by overriding the `_compute_locations` method to prioritize workcenter destinations.

**Priority Order:**
1. **Last workcenter destination** (if configured) - NEW BEHAVIOR
2. Default location from operation type
3. Warehouse stock location (fallback)

### Key Logic Implementation

```python
# Uses LAST workcenter with destination (not first)
for workorder in production.workorder_ids:
    if workorder.workcenter_id.location_dest_id:
        workcenter_dest = workorder.workcenter_id.location_dest_id
        # Don't break - continue to find the LAST workcenter
```

**Important Notes:**
- During manufacturing order **merge operations**, workorders may not exist yet when the MO is created
- The `default_get()` method ensures locations have initial values from picking_type or warehouse defaults
- Once workorders are created (during `action_confirm()`), the `_compute_locations()` method automatically re-executes
- Workcenter destinations are then applied, overriding the initial default values
- This two-phase approach ensures no NULL violations while maintaining full workcenter functionality

### Integration Points

- Overrides `mrp.production._compute_locations()` method
- Adds `workcenter_location_dest_id` computed field for transparency
- Maintains compatibility with existing manufacturing workflows
- Respects company security and location access rules

## Business Benefits

1. **Improved Manufacturing Flow**: Last operation determines final storage location
2. **Flexible Location Management**: Different workcenters can direct products to appropriate storage areas
3. **Quality Control Integration**: QC operations can direct products to inspection areas
4. **Warehouse Optimization**: Better organization of finished goods by production stage

## Author and License

- **Author**: Jose D. Leonett
- **Website**: https://github.com/josedleonett
- **License**: AGPL-3
- **Version**: 17.0.1.2.0

## Changelog

### v17.0.1.2.0 (2025-10-30)

**Bug Fixes:**
- **Fixed**: Resolved `KeyError: <id>` when editing `location_dest_id` field in workcenter form view
- **Root Cause**: Native Odoo's `_compute_workorder_count()` method uses `self._ids` which includes `NewId` objects during form onchange. When the method calls `_read_group()`, it returns real database IDs, causing a KeyError when trying to access `result[real_id]` with NewId keys
- **Solution**: Override `_compute_workorder_count()` method to filter out NewId records before database queries. Only process records with real database IDs and set default values for unsaved records
- **Impact**: 
  - ✅ Can now edit `location_dest_id` in both form and list views without errors
  - ✅ Workorder counts remain accurate for all saved workcenters
  - ✅ New workcenters show zero counts until saved (expected behavior)
  - ✅ Handles all edge cases (new records, form edits, list edits)
  - ⚠️ Contains ~80 lines of Odoo core code (necessary to fix the bug properly)
- **Alternative Attempted**: Empty `@api.onchange('location_dest_id')` method did not prevent cascade recomputation in Odoo 17 Enterprise. Override was necessary.

### v17.0.1.1.0 (2025-10-30)

**Bug Fixes:**
- **Fixed**: Resolved `NotNullViolation` error on `location_src_id` during manufacturing order merge operations
- **Root Cause**: Computed fields `_compute_locations()` were not triggered before database INSERT during merge, leaving location fields NULL
- **Solution**: Added `default_get()` override to ensure location fields always have values during record creation
- **Impact**: Merge operations (`action_merge()`) now work correctly in all scenarios
- **Compatibility**: No functionality loss - workcenter destinations still work correctly and are automatically re-applied when workorders are created

**Technical Details:**
- Override `default_get()` method to provide default values for `location_src_id` and `location_dest_id` before database INSERT
- Always compute fallback location from warehouse when picking_type defaults are not available
- Compute field `_compute_locations()` still maintains workcenter destination logic after workorders are created
- Maintains full compatibility with existing manufacturing workflows and workcenter destination logic

### v17.0.1.0.0

**Initial Release:**
- Workcenter-level destination location configuration
- Automatic location assignment using LAST workcenter
- Fallback to standard Odoo behavior when no workcenter destination configured
- Visual indicators and search capabilities

## Support

For issues and feature requests, please contact Jose D. Leonett.
