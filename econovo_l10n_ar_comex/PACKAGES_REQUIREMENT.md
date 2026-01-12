# Packages Feature Requirement

## Why This Module Requires Packages

The `econovo_l10n_ar_comex` module uses Odoo's native package system (`stock.quant.package`) 
to track shipping containers instead of implementing a custom container model.

### Benefits of Using Native Packages

1. **Automatic Location Tracking**: Packages automatically track their current location 
   as they move through stock operations
2. **Product-Container Linkage**: Products are linked to containers via `quant_ids` 
   (stock quants)
3. **Native Stock Integration**: All standard Odoo stock operations work seamlessly
4. **Barcode Support**: Built-in barcode scanning for package operations
5. **Less Custom Code**: Leverage Odoo's existing infrastructure instead of 
   reinventing the wheel

### How It's Enabled

The module automatically enables the "Packages" feature for COMEX users by including 
the `stock.group_tracking_lot` group as an **implied group** in the COMEX User group.

**File**: `security/econovo_l10n_ar_comex_groups.xml`

```xml
<record id="group_comex_user" model="res.groups">
    <field name="name">User</field>
    <field name="category_id" ref="module_category_comex"/>
    <field name="implied_ids" eval="[(4, ref('base.group_user')), 
                                      (4, ref('stock.group_tracking_lot'))]"/>
    <field name="comment">Can view and create COMEX operations. 
                          Requires Packages feature for container tracking.</field>
</record>
```

### What This Means for Users

- When a user is assigned the "COMEX User" role, they automatically get the 
  "Packages" permission
- The Inventory > Products > Packages menu becomes visible
- Package operations appear in stock picking forms
- Users can create, view, and manage packages (shipping containers)

### Alternative Manual Enablement

If you prefer to enable packages manually instead:

1. Go to **Inventory > Configuration > Settings**
2. Enable **Packages** under "Operations"
3. Click "Save"

This is functionally equivalent to the automatic enablement via implied groups.

### Technical Details

**Group**: `stock.group_tracking_lot`  
**Model**: `stock.quant.package`  
**Configuration Setting**: `group_stock_tracking_lot` (in `res.config.settings`)

The `stock.quant.package` model exists in the base `stock` module but its full 
functionality (menus, operations, etc.) is only visible when this group is enabled.

### Verification

To verify the feature is enabled:

```python
# Check if current user has package permissions
self.env.user.has_group('stock.group_tracking_lot')

# Check if packages menu is visible
self.env.ref('stock.menu_action_quant_package', raise_if_not_found=False)
```

Or via UI:
1. Go to **Inventory > Products** menu
2. Check if "Packages" submenu is visible
3. Go to a stock picking
4. Check if "Put in Pack" button appears (for detailed operations)

## Migration Considerations

If migrating from an older version that used a custom `comex.shipment.container` model:

1. The new system uses `stock.quant.package` with COMEX-specific fields added via 
   inheritance
2. Old container data should be migrated to packages
3. All relationships (`comex_shipment_id`, `comex_container_number`, etc.) are 
   preserved with the `comex_` prefix
4. Location tracking is now automatic via the native package system

See `MIGRATION_CONTAINERS_TO_PACKAGES.md` for detailed migration guide.
