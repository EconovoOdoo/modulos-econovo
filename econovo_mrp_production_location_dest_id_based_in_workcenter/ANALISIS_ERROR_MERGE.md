# Deep Analysis: NotNullViolation on location_src_id During MO Merge

## Error Summary

```
psycopg2.errors.NotNullViolation: el valor null para la columna «location_src_id» viola la restricción not null
DETAIL: La fila que falla contiene (3708, 0, 107197, 1, null, 13, null, null, 9185, null, 1, 3726, null, null, 2, 2, OSEYS/MO/03708, 0, OSEYS/MO/03681,OSEYS/MO/03685, ...)
```

**Context**: Error occurs during `action_merge()` execution on `mrp.production` when merging multiple manufacturing orders.

---

## Root Cause Analysis

### 1. Native Odoo Code Flow (action_merge)

**File**: `d:\Odoo\ODOO-SRC\odoo-17e\odoo\addons\mrp\models\mrp_production.py` (lines 2328-2343)

```python
def action_merge(self):
    self._pre_action_split_merge_hook(merge=True)
    products = set([(production.product_id, production.bom_id) for production in self])
    product_id, bom_id = products.pop()
    users = set([production.user_id for production in self])
    if len(users) == 1:
        user_id = users.pop()
    else:
        user_id = self.env.user

    origs = self._prepare_merge_orig_links()
    dests = {}
    for move in self.move_finished_ids:
        dests.setdefault(move.byproduct_id.id, []).extend(move.move_dest_ids.ids)

    # CRITICAL LINE - Creates new MO with minimal data
    production = self.env['mrp.production'].with_context(
        default_picking_type_id=self.picking_type_id.id
    ).create({
        'product_id': product_id.id,
        'bom_id': bom_id.id,
        'picking_type_id': self.picking_type_id.id,
        'product_qty': sum(production.product_uom_qty for production in self),
        'product_uom_id': product_id.uom_id.id,
        'user_id': user_id.id,
        'origin': ",".join(sorted([production.name for production in self])),
    })
```

**Key Observations**:
1. **No `location_src_id` or `location_dest_id` passed** to `create()`
2. **Relies on computed fields** `_compute_locations()` to set these values
3. **Uses context**: `default_picking_type_id` to help computation

### 2. Native _compute_locations() Behavior

**File**: `d:\Odoo\ODOO-SRC\odoo-17\odoo\addons\mrp\models\mrp_production.py` (lines 355-362)

```python
@api.depends('picking_type_id')
def _compute_locations(self):
    for production in self:
        if not production.picking_type_id.default_location_src_id or not production.picking_type_id.default_location_dest_id:
            company_id = production.company_id.id if (production.company_id and production.company_id in self.env.companies) else self.env.company.id
            fallback_loc = self.env['stock.warehouse'].search([('company_id', '=', company_id)], limit=1).lot_stock_id
        production.location_src_id = production.picking_type_id.default_location_src_id.id or fallback_loc.id
        production.location_dest_id = production.picking_type_id.default_location_dest_id.id or fallback_loc.id
```

**Expected Behavior**:
- If `picking_type_id` has default locations → use them
- Otherwise → use warehouse `lot_stock_id` as fallback

### 3. Our Module's Override

**File**: `econovo_mrp_production_location_dest_id_based_in_workcenter\models\mrp_production.py` (lines 35-63)

```python
@api.depends('picking_type_id', 'workorder_ids', 'workorder_ids.workcenter_id.location_dest_id')
def _compute_locations(self):
    """Override the original method to consider workcenter destination locations"""
    for production in self:
        # First, apply the standard logic to get fallback location if needed
        if not production.picking_type_id.default_location_src_id or not production.picking_type_id.default_location_dest_id:
            company_id = production.company_id.id if (production.company_id and production.company_id in self.env.companies) else self.env.company.id
            fallback_loc = self.env['stock.warehouse'].search([('company_id', '=', company_id)], limit=1).lot_stock_id
        else:
            fallback_loc = None  # ⚠️ PROBLEM HERE!
        
        # Set source location (unchanged from standard behavior)
        if production.picking_type_id.default_location_src_id:
            production.location_src_id = production.picking_type_id.default_location_src_id
        elif fallback_loc:
            production.location_src_id = fallback_loc  # ⚠️ But fallback_loc is None!
```

**THE BUG**:
```python
Line 45:  else:
Line 46:      fallback_loc = None
```

**When this fails**:
1. `picking_type_id` has both default locations set (normal case)
2. `fallback_loc` is set to `None` (line 46)
3. During merge, `workorder_ids` are **not yet created** (created after MO creation)
4. Falls into `elif fallback_loc:` which is **False** (line 52)
5. **`location_src_id` remains unset** → NULL → Database constraint violation

### 4. Why This Works in Normal Creation but Fails in Merge

| Scenario | Workorders Exist? | picking_type Default? | Result |
|----------|-------------------|----------------------|--------|
| **Normal MO creation** | ✅ Created by BoM | ✅ Yes | Works (workcenter dest or picking default) |
| **Merge operation** | ❌ Not yet created | ✅ Yes | **FAILS** - No fallback, `location_src_id` = NULL |

**Timeline During Merge**:
```
1. action_merge() calls create() with minimal data
2. create() triggers _compute_locations()
3. _compute_locations() runs BEFORE workorders are created
4. No workorders → No workcenter destinations
5. fallback_loc = None (because picking_type has defaults)
6. Neither workcenter dest NOR fallback available
7. location_src_id remains NULL
8. Database INSERT fails with NOT NULL constraint violation
```

---

## Solution Alternatives

### ✅ Solution 1: Fix Fallback Logic (RECOMMENDED - Minimal Change)

**Strategy**: Always compute fallback location, only skip using it if picking_type has defaults

**Advantages**:
- ✅ Minimal code change (2 lines)
- ✅ Maintains all existing functionality
- ✅ Follows Odoo best practices
- ✅ No side effects
- ✅ Easier to understand and maintain

**Implementation**:

```python
@api.depends('picking_type_id', 'workorder_ids', 'workorder_ids.workcenter_id.location_dest_id')
def _compute_locations(self):
    """Override the original method to consider workcenter destination locations"""
    for production in self:
        # ALWAYS compute fallback location (needed for merge scenarios)
        if not production.picking_type_id.default_location_src_id or not production.picking_type_id.default_location_dest_id:
            company_id = production.company_id.id if (production.company_id and production.company_id in self.env.companies) else self.env.company.id
            fallback_loc = self.env['stock.warehouse'].search([('company_id', '=', company_id)], limit=1).lot_stock_id
        else:
            # FIX: Still compute fallback but don't use it by default
            company_id = production.company_id.id if (production.company_id and production.company_id in self.env.companies) else self.env.company.id
            fallback_loc = self.env['stock.warehouse'].search([('company_id', '=', company_id)], limit=1).lot_stock_id
        
        # Set source location with proper fallback chain
        if production.picking_type_id.default_location_src_id:
            production.location_src_id = production.picking_type_id.default_location_src_id
        elif fallback_loc:  # Now fallback_loc is ALWAYS available
            production.location_src_id = fallback_loc
        else:
            # Ultimate fallback - should never happen but defensive programming
            production.location_src_id = False
        
        # For destination location, check if any workcenter has a custom destination
        workcenter_dest = None
        for workorder in production.workorder_ids:
            if workorder.workcenter_id.location_dest_id:
                workcenter_dest = workorder.workcenter_id.location_dest_id
        
        # Set destination location with proper priority and fallback
        if workcenter_dest:
            production.location_dest_id = workcenter_dest
        elif production.picking_type_id.default_location_dest_id:
            production.location_dest_id = production.picking_type_id.default_location_dest_id
        elif fallback_loc:  # Now fallback_loc is ALWAYS available
            production.location_dest_id = fallback_loc
        else:
            # Ultimate fallback
            production.location_dest_id = False
```

**Changes**:
1. **Lines 44-46**: Always compute `fallback_loc` (removed conditional None assignment)
2. **Lines 52 & 63**: Added ultimate fallback `False` (defensive programming)

**Test Cases**:
```python
# Test 1: Normal MO creation with workcenter destination
# Expected: Uses workcenter location_dest_id

# Test 2: Normal MO creation without workcenter destination  
# Expected: Uses picking_type defaults

# Test 3: Merge MOs with workcenter destination (after workorders created)
# Expected: Uses workcenter location_dest_id

# Test 4: Merge MOs WITHOUT workorders yet created
# Expected: Uses picking_type defaults (no NULL)

# Test 5: Merge MOs with no picking_type defaults
# Expected: Uses warehouse fallback location
```

---

### ✅ Solution 2: Extend action_merge() (COMPREHENSIVE - Full Control)

**Strategy**: Override `action_merge()` to explicitly set locations before calling super

**Advantages**:
- ✅ Complete control over merge behavior
- ✅ Can implement custom merge logic for workcenters
- ✅ Explicit location assignment before database insert
- ✅ Can handle complex scenarios (e.g., merging MOs with different workcenter destinations)

**Disadvantages**:
- ⚠️ More code to maintain
- ⚠️ Duplicates some native Odoo logic
- ⚠️ Higher risk of breaking on Odoo upgrades
- ⚠️ Needs to handle workcenter destination merging logic

**Implementation**:

```python
def action_merge(self):
    """Override to ensure locations are properly set during merge"""
    # Store original merged MOs data before they're cancelled
    merged_mos_data = []
    for mo in self:
        merged_mos_data.append({
            'location_src_id': mo.location_src_id.id,
            'location_dest_id': mo.location_dest_id.id,
            'workcenter_destinations': [
                (wo.workcenter_id.id, wo.workcenter_id.location_dest_id.id)
                for wo in mo.workorder_ids
                if wo.workcenter_id.location_dest_id
            ]
        })
    
    # Call native merge (creates new MO)
    result = super().action_merge()
    
    # Get the newly created MO
    if isinstance(result, dict) and result.get('res_id'):
        new_mo = self.env['mrp.production'].browse(result['res_id'])
        
        # Ensure locations are properly set
        # Priority 1: Use first merged MO's locations as base
        if merged_mos_data:
            base_data = merged_mos_data[0]
            
            # Set source location if not already set
            if not new_mo.location_src_id:
                new_mo.location_src_id = base_data['location_src_id']
            
            # For destination: check if we should use workcenter destination
            # after workorders are created
            workcenter_dest = None
            for wo in new_mo.workorder_ids:
                if wo.workcenter_id.location_dest_id:
                    workcenter_dest = wo.workcenter_id.location_dest_id
            
            if workcenter_dest:
                new_mo.location_dest_id = workcenter_dest
            elif not new_mo.location_dest_id:
                # Check if any merged MO had workcenter destinations
                all_workcenter_dests = []
                for mo_data in merged_mos_data:
                    all_workcenter_dests.extend(mo_data['workcenter_destinations'])
                
                if all_workcenter_dests:
                    # Use the last workcenter destination from merged MOs
                    last_dest_id = all_workcenter_dests[-1][1]
                    new_mo.location_dest_id = last_dest_id
                else:
                    # Use base location
                    new_mo.location_dest_id = base_data['location_dest_id']
    
    return result
```

**Additional Features**:
- Preserves workcenter destination logic from merged MOs
- Handles cases where workorders are created after merge
- Explicit location assignment prevents NULL violations
- Logs can be added for debugging

**Test Cases**:
```python
# Test 1: Merge 2 MOs with same workcenter destination
# Expected: New MO uses that workcenter destination

# Test 2: Merge 2 MOs with different workcenter destinations
# Expected: New MO uses last workcenter destination (or implements business logic)

# Test 3: Merge MOs without workcenter destinations
# Expected: New MO uses picking_type defaults

# Test 4: Merge MOs from different picking types
# Expected: Error (already handled by _pre_action_split_merge_hook)
```

---

## Recommendation

**Use Solution 1 (Fix Fallback Logic)** because:

1. **Minimal Risk**: Only 2-line change in one method
2. **Addresses Root Cause**: Always ensures `fallback_loc` is available
3. **Maintains Compatibility**: No changes to merge behavior or other modules
4. **Easier Maintenance**: Less code to maintain during Odoo upgrades
5. **Defensive Programming**: Adds ultimate `False` fallback for edge cases

**When to consider Solution 2**:
- If you need custom workcenter destination merging logic
- If multiple MOs have conflicting workcenter destinations
- If you want explicit control over merge behavior
- If you need detailed merge operation logging

---

## Implementation Steps (Solution 1 - RECOMMENDED)

### Step 1: Modify mrp_production.py

```bash
# File: models/mrp_production.py
# Lines to modify: 44-46 and 52, 63
```

### Step 2: Add Unit Tests

```python
# File: tests/test_mrp_production_merge.py

def test_merge_without_workorders(self):
    """Test merging MOs when workorders are not yet created"""
    mo1 = self.create_mo({'product_qty': 10})
    mo2 = self.create_mo({'product_qty': 20})
    
    merged_mo = (mo1 | mo2).action_merge()
    
    self.assertTrue(merged_mo.location_src_id, "location_src_id must not be NULL")
    self.assertTrue(merged_mo.location_dest_id, "location_dest_id must not be NULL")
```

### Step 3: Update Documentation

```markdown
# File: README.md

## Bug Fixes

### v17.0.1.1.0 (2025-10-29)
- **Fix**: Resolved NULL violation on `location_src_id` during MO merge operations
- **Cause**: Fallback location was not computed when picking_type had default locations
- **Impact**: Merge operations now work correctly even when workorders are not yet created
```

### Step 4: Update Manifest

```python
# File: __manifest__.py
'version': '17.0.1.1.0',  # Increment version
```

---

## Testing Checklist

- [ ] Normal MO creation with workcenter destination
- [ ] Normal MO creation without workcenter destination  
- [ ] Merge 2 MOs in DRAFT state
- [ ] Merge 2 MOs in CONFIRMED state
- [ ] Merge MOs with different picking types (should error - native validation)
- [ ] Merge MOs with same workcenter destination
- [ ] Merge MOs without workcenter destinations
- [ ] Split MO and verify locations preserved
- [ ] Upgrade module and verify no database errors
- [ ] Check performance (warehouse search query)

---

## Risk Assessment

| Aspect | Solution 1 | Solution 2 |
|--------|-----------|-----------|
| **Code Changes** | Minimal (2 lines) | Moderate (40+ lines) |
| **Risk Level** | 🟢 LOW | 🟡 MEDIUM |
| **Maintenance** | 🟢 Easy | 🟡 Moderate |
| **Upgrade Impact** | 🟢 Minimal | 🟡 Moderate |
| **Testing Effort** | 🟢 Low | 🟡 High |
| **Debugging** | 🟢 Straightforward | 🟡 Complex |

---

## Conclusion

**Solution 1** is the optimal choice for fixing this bug:
- Addresses the root cause directly
- Minimal code changes reduce regression risk
- Maintains all existing functionality
- Easy to test and validate
- Safe for production deployment

**Next Steps**:
1. Implement Solution 1 changes
2. Add unit tests for merge scenarios
3. Test in development environment
4. Update documentation and version
5. Commit with descriptive message: `[FIX] Resolve NULL location_src_id during MO merge`
6. Deploy to production after thorough testing
