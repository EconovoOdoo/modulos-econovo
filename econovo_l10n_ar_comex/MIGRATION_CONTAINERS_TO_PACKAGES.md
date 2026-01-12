# Migration: COMEX Containers to Native Odoo Packages

## Overview

This document explains the migration from custom `comex.shipment.container` model to native Odoo `stock.quant.package` with COMEX-specific extensions.

## Why This Migration?

### Problems with Custom Container Model
1. **No automatic location tracking** - Had to manually update `current_location_id`
2. **No stock integration** - Containers couldn't be linked to actual products/quants
3. **No native movements** - Couldn't use Odoo's stock transfer system
4. **Duplicate logic** - Had to reimplement features already in Odoo

### Benefits of Native Packages
1. ✅ **Automatic location tracking** - `package.location_id` updates automatically with stock moves
2. ✅ **Product-container linkage** - Products inside containers via `package.quant_ids`
3. ✅ **Native stock movements** - Use standard pickings to move containers
4. ✅ **Barcode support** - Native barcode scanning for containers
5. ✅ **Less custom code** - Leverage Odoo's existing infrastructure

## Technical Implementation

### New Models

#### 1. `stock.quant.package` (Inherited)
**Purpose**: Extend native packages for COMEX container tracking

**New Fields**:
- `comex_shipment_id` (Many2one): Link to COMEX shipment
- `comex_operation_id` (Related): Link to COMEX operation
- `comex_container_number` (Char): Container number (e.g., MAEU1234567)
- `comex_seal_number` (Char): Customs seal number
- `comex_volume` (Float): Container volume in m³
- `comex_weight_net` (Float): Net weight (products only)
- `comex_weight_gross` (Float, Computed): Gross weight (net + tare)
- `comex_weight_tare` (Float, Computed): Container tare weight (from package_type)
- `is_comex_container` (Boolean, Computed): Identifies COMEX containers

**Key Methods**:
- `create()`: Auto-sets package name from container_number
- `name_get()`: Custom display format
- `action_view_comex_shipment()`: Smart button to view shipment
- `action_view_stock_moves()`: Smart button to view stock movements

#### 2. `stock.package.type` (Inherited)
**Purpose**: Classify shipping containers

**New Fields**:
- `is_comex_container` (Boolean): Identifies container package types
- `container_size` (Selection): 20', 40', 45' foot containers
- `container_category` (Selection): GP, HC, RF, OT, FR, TK

### Predefined Container Types

11 standard container types with real specifications:

| Code | Name | Dimensions (LxWxH) | Tare Weight | Max Weight | Volume |
|------|------|-------------------|-------------|------------|---------|
| 20GP | 20' General Purpose | 5.90 x 2.35 x 2.39 m | 2,200 kg | 28,280 kg | 33.2 m³ |
| 20HC | 20' High Cube | 5.90 x 2.35 x 2.70 m | 2,300 kg | 27,400 kg | 37.4 m³ |
| 20RF | 20' Reefer | 5.45 x 2.29 x 2.27 m | 3,000 kg | 27,400 kg | 28.3 m³ |
| 20OT | 20' Open Top | 5.90 x 2.35 x 2.39 m | 2,400 kg | 28,280 kg | 33.2 m³ |
| 40GP | 40' General Purpose | 12.03 x 2.35 x 2.39 m | 3,800 kg | 28,600 kg | 67.5 m³ |
| 40HC | 40' High Cube | 12.03 x 2.35 x 2.70 m | 3,900 kg | 28,600 kg | 76.3 m³ |
| 40RF | 40' Reefer | 11.56 x 2.29 x 2.27 m | 4,800 kg | 27,700 kg | 60.1 m³ |
| 40RF-HC | 40' Reefer High Cube | 11.56 x 2.29 x 2.50 m | 5,000 kg | 29,500 kg | 66.2 m³ |
| 40OT | 40' Open Top | 12.03 x 2.35 x 2.39 m | 4,000 kg | 28,600 kg | 67.5 m³ |
| 40FR | 40' Flat Rack | 12.08 x 2.44 x 2.13 m | 5,000 kg | 40,000 kg | 62.9 m³ |
| 45HC | 45' High Cube | 13.55 x 2.35 x 2.70 m | 4,800 kg | 27,600 kg | 86.0 m³ |

## User Workflow

### Creating COMEX Containers

**Option 1: From Shipment Form**
1. Open COMEX Operation → Shipments
2. Select/Create a shipment
3. Go to "Containers" tab
4. Click "Add a line"
5. Fill container details:
   - Container Number: MAEU1234567
   - Package Type: 40' High Cube Container
   - Seal Number: SEAL001
   - Weights and volume

**Option 2: From Containers Menu**
1. COMEX → Configuration → Containers
2. Create new package
3. Set COMEX fields (shipment, container number, etc.)

### Assigning Products to Containers

In purchase order picking (or any COMEX picking):

1. Open the picking
2. Click "Detailed Operations" tab
3. For each line, set **Destination Package** = Container Number
4. Validate the picking

**What happens automatically**:
- Products are moved to the container
- `stock.quant` records created with `package_id`
- Package `location_id` updated to destination location
- If push rules exist, next picking is created automatically
- Container moves with the products through the workflow

### Tracking Container Location

Container location is **automatically tracked**:

```
Initial:     package.location_id = Shipment location (En Viaje)
After PO:    package.location_id = Puerto Buenos Aires (auto-updated)
After ARR:   package.location_id = Depósito Fiscal (auto-updated)
After NAC:   package.location_id = WH/Stock (auto-updated)
```

No need to manually update `current_location_id` anymore!

## Edge Cases & Validations

### Case 1: Package Without Shipment
**Scenario**: User creates a package without assigning `comex_shipment_id`

**Behavior**:
- `is_comex_container` = False (not computed as COMEX container)
- Package works as standard Odoo package
- Not visible in COMEX Containers menu
- Can be converted later by setting `comex_shipment_id`

**Validation**: None - this is valid for non-COMEX operations

### Case 2: Multiple Packages in Same Picking
**Scenario**: One picking has products going to 3 different containers

**Behavior**:
- Each move line can have different `result_package_id`
- Products automatically distributed to their assigned containers
- All packages move to the same destination location
- Each package tracks its contents independently via `quant_ids`

**Validation**: None - Odoo natively supports this

### Case 3: Package Location Mismatch
**Scenario**: Package `location_id` differs from shipment `current_location_id`

**Example**:
```python
shipment.current_location_id = "En Viaje"
package.location_id = "Puerto Buenos Aires"  # Already arrived
```

**Behavior**:
- Package location is **source of truth** (automatically updated by Odoo)
- Shipment `current_location_id` is informational/planning field
- No validation enforced

**Recommendation**: Update shipment location manually to match reality:
```python
shipment.current_location_id = package.location_id
```

### Case 4: Weight Validation (Net + Tare = Gross)
**Scenario**: User enters weights that don't add up correctly

**Current Behavior**:
- `comex_weight_tare` is computed from `package_type_id.max_weight` (if available)
- `comex_weight_gross` is computed as `comex_weight_net + comex_weight_tare`
- User can override `comex_weight_gross` by setting it directly

**Potential Issue**: User could enter inconsistent weights

**Solution** (optional constraint):
```python
@api.constrains('comex_weight_net', 'comex_weight_gross', 'comex_weight_tare')
def _check_weights(self):
    for package in self:
        if package.is_comex_container:
            if package.comex_weight_gross < package.comex_weight_net:
                raise ValidationError(_("Gross weight cannot be less than net weight"))
```

**Status**: Not implemented - allowing flexibility for data corrections

### Case 5: Container Number Format
**Scenario**: User enters invalid container number format

**Standard Format**: 
- 4 letters (owner code) + 7 digits + 1 check digit
- Example: MAEU1234567 ✅
- Invalid: ABC123 ❌

**Current Behavior**: No validation enforced

**Solution** (optional constraint):
```python
@api.constrains('comex_container_number')
def _check_container_number_format(self):
    import re
    pattern = r'^[A-Z]{4}[0-9]{7}$'
    for package in self:
        if package.comex_container_number:
            if not re.match(pattern, package.comex_container_number):
                raise ValidationError(_(
                    "Invalid container number format. "
                    "Expected: 4 letters + 7 digits (e.g., MAEU1234567)"
                ))
```

**Status**: Not implemented - allowing flexibility for non-standard cases

### Case 6: Package in Non-COMEX Picking
**Scenario**: COMEX container package is used in a non-COMEX picking

**Behavior**:
- Package moves normally (it's a standard Odoo package)
- Location updates automatically
- COMEX fields remain populated
- No validation prevents this

**Use Case**: Moving container from COMEX workflow to internal warehouse operations

**Recommendation**: If intentional, OK. If accidental, filter packages by `is_comex_container` in picking forms.

### Case 7: Deleting Shipment with Packages
**Scenario**: User tries to delete a shipment that has linked packages

**Current Behavior**:
- `package_ids` has `ondelete='set null'`
- Deleting shipment sets `package.comex_shipment_id = False`
- Packages become standard packages (not COMEX containers anymore)

**Alternative Behavior** (stricter):
```python
# In stock_quant_package.py
comex_shipment_id = fields.Many2one('comex.shipment', ondelete='restrict')

# This would prevent shipment deletion if packages exist
```

**Status**: Using `ondelete='set null'` for flexibility

### Case 8: Empty Container (No Products)
**Scenario**: Container package exists but has no products inside (`quant_ids` empty)

**Behavior**:
- Valid state - containers can be empty
- `comex_weight_net` should be 0 or manually entered
- Package still tracked through locations
- Can be filled later when products arrive

**Use Case**: Pre-registering containers before product arrival

### Case 9: Package Type Change After Assignment
**Scenario**: User changes `package_type_id` after products are assigned

**Behavior**:
- `comex_weight_tare` recalculated (computed field)
- `comex_weight_gross` recalculated (depends on tare)
- Package dimensions updated
- Products remain inside (no validation on max weight/volume)

**Potential Issue**: Container could exceed capacity

**Solution** (optional constraint):
```python
@api.constrains('quant_ids', 'package_type_id')
def _check_package_capacity(self):
    for package in self:
        if package.package_type_id and package.quant_ids:
            total_weight = sum(package.quant_ids.mapped('quantity'))
            if total_weight > package.package_type_id.max_weight:
                raise ValidationError(_(
                    "Total weight exceeds container capacity"
                ))
```

**Status**: Not implemented - Odoo doesn't natively validate this either

## Migration Path (If Needed)

If you had existing data in `comex.shipment.container`:

```python
# Migration script (NOT NEEDED for fresh install)
def migrate_containers_to_packages(env):
    Container = env['comex.shipment.container']
    Package = env['stock.quant.package']
    
    for container in Container.search([]):
        # Find package type by code
        package_type = env['stock.package.type'].search([
            ('name', 'ilike', container.container_type)
        ], limit=1)
        
        # Create package
        Package.create({
            'comex_shipment_id': container.shipment_id.id,
            'comex_container_number': container.container_number,
            'package_type_id': package_type.id,
            'comex_seal_number': container.seal_number,
            'comex_weight_gross': container.weight_gross,
            'comex_weight_net': container.weight_net,
            'comex_volume': container.volume,
            'location_id': container.shipment_id.current_location_id.id,
        })
    
    # Note: Product assignments would need separate logic
    # based on historical picking data
```

## Testing Checklist

- [ ] Create shipment with multiple containers
- [ ] Assign products to containers in picking
- [ ] Validate picking → verify package location updated
- [ ] Check `quant_ids` shows products inside container
- [ ] Use push rules → verify container moves automatically
- [ ] View container from shipment smart button
- [ ] View moves from container smart button
- [ ] Filter containers by shipment/location in menu
- [ ] Create package without shipment (non-COMEX package)
- [ ] Check weights calculation (tare from package type)
- [ ] Delete shipment → verify packages remain (shipment_id = False)
- [ ] Barcode scan container in picking

## API Examples

### Create COMEX Container Programmatically
```python
package = env['stock.quant.package'].create({
    'comex_shipment_id': shipment.id,
    'comex_container_number': 'MAEU1234567',
    'package_type_id': env.ref('econovo_l10n_ar_comex.package_type_40hc').id,
    'comex_seal_number': 'SEAL12345',
    'comex_weight_net': 22000,
    'comex_volume': 67.5,
})
# Name auto-set to "MAEU1234567"
# comex_weight_tare auto-computed from package_type (3900 kg for 40HC)
# comex_weight_gross auto-computed as 22000 + 3900 = 25900 kg
```

### Assign Products to Container in Picking
```python
picking = env['stock.picking'].browse(picking_id)
container = env['stock.quant.package'].search([
    ('comex_container_number', '=', 'MAEU1234567')
], limit=1)

for move in picking.move_ids:
    move.move_line_ids.write({
        'result_package_id': container.id
    })

picking.button_validate()
# Container location_id automatically updated to picking.location_dest_id
```

### Find All Containers in Transit
```python
packages = env['stock.quant.package'].search([
    ('is_comex_container', '=', True),
    ('location_id.usage', '=', 'transit')
])
```

### Get Products Inside Container
```python
container = env['stock.quant.package'].browse(package_id)
products = container.quant_ids.mapped('product_id')
total_qty = sum(container.quant_ids.mapped('quantity'))
```

## Files Changed

### Created
- `models/stock_quant_package.py` (207 lines)
- `models/stock_package_type.py` (37 lines)
- `data/stock_package_type_data.xml` (173 lines - 11 container types)
- `views/stock_quant_package_views.xml` (167 lines)
- `MIGRATION_CONTAINERS_TO_PACKAGES.md` (this file)

### Modified
- `models/comex_shipment.py`: Changed `container_ids` → `package_ids`, removed `ComexShipmentContainer` class
- `models/stock_picking.py`: Updated help text for `comex_shipment_container_count`
- `models/__init__.py`: Added imports for `stock_quant_package`, `stock_package_type`
- `__manifest__.py`: Added data file and view file
- `security/ir.model.access.csv`: Removed `comex.shipment.container` access rules
- `demo/comex_demo.xml`: Changed demo container to `stock.quant.package`
- `views/comex_shipment_views.xml`: Updated containers tab to use `package_ids`

### Deleted
- ❌ `comex.shipment.container` model (eliminated completely)

## Conclusion

This migration transforms COMEX containers from custom documentation records into fully-integrated stock management entities. The native package system provides automatic location tracking, seamless product linkage, and native barcode support - all while maintaining COMEX-specific data requirements.

The implementation is backward-compatible (old field names work through compute/related fields) and handles edge cases gracefully without overly restrictive validations.
