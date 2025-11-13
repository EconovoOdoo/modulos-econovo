# Testing Guide

## Manual Testing Checklist

### Prerequisites
- [ ] Odoo 17 EE instance running
- [ ] Module installed and updated
- [ ] Manufacturing module (mrp) installed
- [ ] Stock Barcode module (stock_barcode) installed

### Test Case 1: Single-Location Kit

**Setup:**
1. Create a product "Test Kit A"
2. Create a BoM with type "Kit":
   - Component 1: Mouse (1 unit) - Location: WH/Stock
   - Component 2: Keyboard (1 unit) - Location: WH/Stock
   - Component 3: Monitor (1 unit) - Location: WH/Stock
3. Ensure all components have stock in WH/Stock

**Test Steps:**
1. Create a delivery order with "Test Kit A" (qty: 1)
2. Open barcode app
3. **Expected Result:**
   - Components grouped under "Test Kit A"
   - Badge shows "3 components"
   - Blue border around kit group
   - Source location shows "WH/Stock" (single location)
4. Click expand button
5. **Expected Result:**
   - Shows 3 individual components
   - Each shows "WH/Stock → WH/Output"
   - Components are indented with dotted line

**Pass Criteria:** ✅ / ❌

---

### Test Case 2: Multi-Location Kit

**Setup:**
1. Create a product "Test Kit B"
2. Move components to different locations:
   - Mouse: 5 units in WH/Stock/Shelf A
   - Keyboard: 5 units in WH/Stock/Shelf B
   - Monitor: 5 units in WH/Stock/Shelf C
3. Create a BoM with type "Kit" (same as Test Case 1)

**Test Steps:**
1. Create a delivery order with "Test Kit B" (qty: 1)
2. Open barcode app
3. **Expected Result (Collapsed View):**
   - Components grouped under "Test Kit B"
   - Badge shows "3 components"
   - Source location shows "3 locations" (not specific shelves)
   - Destination shows "WH/Output"
4. Click expand button
5. **Expected Result (Expanded View):**
   - Mouse shows "Shelf A → WH/Output"
   - Keyboard shows "Shelf B → WH/Output"
   - Monitor shows "Shelf C → WH/Output"
   - Each component clearly shows its source

**Pass Criteria:** ✅ / ❌

---

### Test Case 3: Multiple Kits in Same Picking

**Setup:**
1. Create two kits: "Kit A" and "Kit B"
2. Both kits have components in different locations

**Test Steps:**
1. Create a delivery order with:
   - Kit A (qty: 2)
   - Kit B (qty: 1)
2. Open barcode app
3. **Expected Result:**
   - Two separate kit groups visible
   - "Kit A" shows "6 components" (2 kits × 3 components)
   - "Kit B" shows "3 components"
   - Both have blue borders

**Pass Criteria:** ✅ / ❌

---

### Test Case 4: Kit with Different Destination Locations (Edge Case)

**Setup:**
1. Create a kit where components go to different destinations
   - Manually edit move lines to set different destination locations
   - Component 1 → WH/Output
   - Component 2 → WH/Packing Zone
   - Component 3 → WH/Quality Control

**Test Steps:**
1. Open barcode app
2. **Expected Result:**
   - Kit still grouped (grouped by move_id)
   - Warning badge: "⚠️ Multiple destinations"
   - Yellow border instead of blue
3. Expand kit
4. **Expected Result:**
   - Each component shows its specific destination

**Pass Criteria:** ✅ / ❌

---

### Test Case 5: Mixed Picking (Kits + Regular Products)

**Setup:**
1. Create a delivery order with:
   - 1x "Test Kit A"
   - 5x "Regular Product X" (not a kit)
   - 2x "Regular Product Y" (not a kit)

**Test Steps:**
1. Open barcode app
2. **Expected Result:**
   - Kit components grouped with blue border
   - Regular products shown normally (standard Odoo behavior)
   - No visual grouping for regular products
   - Clear distinction between kits and regular products

**Pass Criteria:** ✅ / ❌

---

### Test Case 6: Compatibility with stock_barcode_mrp

**Setup:**
1. Ensure `stock_barcode_mrp` module is installed
2. Create a kit with "is_kits" product checkbox enabled

**Test Steps:**
1. Create a delivery order with kit
2. Open barcode app
3. Kit should be grouped (our module)
4. Click "Validate" without scanning
5. **Expected Result:**
   - stock_barcode_mrp should show popup: "Kit will be replaced with components"
   - After confirmation, kit explodes
   - Components remain grouped (because description_bom_line persists)

**Pass Criteria:** ✅ / ❌

---

### Test Case 7: Performance with Large Kits

**Setup:**
1. Create a kit with 20+ components
2. Components spread across 10+ locations

**Test Steps:**
1. Create a delivery order with this large kit
2. Open barcode app
3. **Expected Result:**
   - Grouping happens quickly (< 1 second)
   - Collapsed view shows "20 components" and "10 locations"
   - No lag when expanding/collapsing
4. Expand and collapse multiple times
5. **Expected Result:**
   - Smooth animations
   - No JavaScript errors in console

**Pass Criteria:** ✅ / ❌

---

## Automated Testing (Future)

### Unit Tests (Python)

```python
# tests/test_stock_picking.py

from odoo.tests import TransactionCase

class TestBarcodeKitGrouping(TransactionCase):
    
    def setUp(self):
        super().setUp()
        # Create test products, BOMs, locations
        
    def test_get_stock_barcode_data_includes_bom_fields(self):
        """Test that description_bom_line is included in barcode data"""
        picking = self._create_picking_with_kit()
        data = picking._get_stock_barcode_data()
        
        self.assertIn('stock.move', data['records'])
        moves = data['records']['stock.move']
        
        # Find kit component move
        kit_move = next(m for m in moves if m.get('description_bom_line'))
        
        self.assertTrue(kit_move['description_bom_line'])
        self.assertIn(' - ', kit_move['description_bom_line'])  # "Kit Name - 1/3"
    
    def test_bom_fields_format(self):
        """Test that description_bom_line has correct format"""
        picking = self._create_picking_with_kit()
        data = picking._get_stock_barcode_data()
        
        # Should match pattern: "Kit Name - X/Y"
        import re
        pattern = r'^.+ - \d+/\d+$'
        
        for move in data['records']['stock.move']:
            if move.get('description_bom_line'):
                self.assertRegex(move['description_bom_line'], pattern)
```

### Integration Tests (JavaScript/QUnit)

```javascript
// static/tests/barcode_kit_grouping_tests.js

QUnit.module('Barcode Kit Grouping');

QUnit.test('groupKey ignores location_id for kits', function (assert) {
    const model = new BarcodePickingModel(...);
    
    const kitLine1 = {
        move_id: 1,
        location_id: {id: 10},  // Shelf A
        location_dest_id: {id: 20},
        move_id: {description_bom_line: "My Kit - 1/3"}
    };
    
    const kitLine2 = {
        move_id: 1,
        location_id: {id: 11},  // Shelf B (different!)
        location_dest_id: {id: 20},
        move_id: {description_bom_line: "My Kit - 2/3"}
    };
    
    const key1 = model.groupKey(kitLine1);
    const key2 = model.groupKey(kitLine2);
    
    // Should be same key despite different source locations
    assert.strictEqual(key1, key2);
    assert.ok(key1.startsWith('kit_'));
});

QUnit.test('kit metadata added to grouped lines', function (assert) {
    const model = new BarcodePickingModel(...);
    model.load(testData);  // Data with kit
    
    const lines = model.groupedLines;
    const kitLine = lines.find(l => l.is_kit_group);
    
    assert.ok(kitLine, "Kit group should exist");
    assert.strictEqual(kitLine.kit_name, "My Kit");
    assert.strictEqual(kitLine.component_count, 3);
    assert.ok(kitLine.has_multiple_source_locations);
});
```

---

## Debugging Tips

### Check if Module is Loaded

**Browser Console:**
```javascript
// Check if patch is applied
odoo.__DEBUG__.services['web.core'].patch_map.get('BarcodePickingModel')

// Check if components are registered
odoo.__DEBUG__.services['web.core'].registry.get('stock_barcode.GroupedLineComponent')
```

### Inspect Barcode Data

**Backend (Python debugger):**
```python
# Add breakpoint in stock_picking.py
def _get_stock_barcode_data(self):
    data = super()._get_stock_barcode_data()
    
    # Check if stock.move records exist
    import pdb; pdb.set_trace()
    
    moves = data['records'].get('stock.move', [])
    for move in moves:
        print(f"Move {move['id']}: {move.get('description_bom_line')}")
```

**Frontend (Browser Console):**
```javascript
// Access model instance
const model = odoo.__DEBUG__.services['barcode.picking.model'];

// Inspect grouped lines
console.table(model.groupedLines.map(l => ({
    name: l.kit_name || l.product_id?.display_name,
    is_kit: l.is_kit_group,
    components: l.component_count,
    sources: l.source_location_count
})));
```

### Common Issues

**Issue:** Kit not grouping
- Check: `move.description_bom_line` exists in barcode data
- Check: BoM type is "Kit" (type='phantom')
- Check: Module updated after code changes

**Issue:** Styling not applied
- Check: Assets loaded (Network tab)
- Check: Browser console for CSS errors
- Clear: Odoo assets cache and browser cache

**Issue:** JavaScript errors
- Check: Patch syntax correct
- Check: super.method() called where needed
- Check: Variable names match Odoo's structure

---

## Test Results Template

```
=================================
ECONOVO BARCODE KIT GROUPING
Test Results
=================================

Date: _______________
Tester: _______________
Odoo Version: 17.0._____
Module Version: 17.0.1.0.0

Test Case 1: Single-Location Kit          [ ]  PASS  [ ]  FAIL
Test Case 2: Multi-Location Kit            [ ]  PASS  [ ]  FAIL
Test Case 3: Multiple Kits in Picking      [ ]  PASS  [ ]  FAIL
Test Case 4: Different Destinations        [ ]  PASS  [ ]  FAIL
Test Case 5: Mixed Picking                 [ ]  PASS  [ ]  FAIL
Test Case 6: stock_barcode_mrp Compat      [ ]  PASS  [ ]  FAIL
Test Case 7: Large Kit Performance         [ ]  PASS  [ ]  FAIL

Notes:
_______________________________________________
_______________________________________________
_______________________________________________

Overall Result:  [ ]  PASS  [ ]  FAIL
```
