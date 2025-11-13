# Quick Start Guide

## 5-Minute Installation & Demo

### Step 1: Install Module (1 minute)

```bash
# 1. Copy module to addons path (if not already there)
cd /path/to/odoo/addons
# Module should be at: addons/econovo_barcode_kit_bom_stock_move_line_grouping/

# 2. Restart Odoo (if needed)
sudo systemctl restart odoo

# 3. Update apps list
# Go to Apps menu > Update Apps List

# 4. Install module
# Search "Econovo Barcode Kit" > Install
```

### Step 2: Create Demo Kit (2 minutes)

**2.1 Create Kit Product**
```
Inventory > Products > Products > Create

Name: Demo Computer Kit
Type: Storable Product
```

**2.2 Create BoM**
```
Product Form > Bill of Materials tab > Create

BoM Type: Kit (IMPORTANT!)
Components:
  - Mouse (qty: 1)
  - Keyboard (qty: 1)  
  - Monitor (qty: 1)
  
Save
```

**2.3 Add Stock to Components** (optional for multi-location demo)
```
Inventory > Products > Products

For each component (Mouse, Keyboard, Monitor):
  - On Hand: Update Quantity
    * Location: WH/Stock/Shelf A (Mouse: 10 units)
    * Location: WH/Stock/Shelf B (Keyboard: 10 units)
    * Location: WH/Stock/Shelf C (Monitor: 10 units)
```

### Step 3: Test in Barcode App (2 minutes)

**3.1 Create Delivery Order**
```
Sales > Orders > Create

Customer: Any customer
Order Lines: 
  - Product: Demo Computer Kit
  - Quantity: 1

Confirm Sale
```

**3.2 Open Barcode App**
```
Delivery Order > Barcode button (top-right)

You should see:
┌──────────────────────────────────────┐
│ 🧊 Demo Computer Kit  [3 components] │
│ ↗ 3 locations → WH/Output     [▼]   │
└──────────────────────────────────────┘
(Blue border, kit icon, component count)
```

**3.3 Expand Kit**
```
Click the [▼] button

You should see:
┌──────────────────────────────────────┐
│ 🧊 Demo Computer Kit  [3 components] │
│ ↗ 3 locations → WH/Output     [▲]   │
├──────────────────────────────────────┤
│   └─ 📦 Mouse                        │
│      ↗ Shelf A → WH/Output          │
│                                      │
│   └─ 📦 Keyboard                     │
│      ↗ Shelf B → WH/Output          │
│                                      │
│   └─ 📦 Monitor                      │
│      ↗ Shelf C → WH/Output          │
└──────────────────────────────────────┘
```

### Expected Behavior

✅ **What You Should See:**
- Kit components grouped with blue border
- Kit name "Demo Computer Kit" displayed (not component names)
- Badge showing "3 components"
- Collapsed view shows "3 locations" (hides specific shelves)
- Expanded view shows each component's actual location
- Smooth expand/collapse animation
- Indented component list with dotted line

❌ **What You Should NOT See:**
- Individual ungrouped component lines
- Three separate "Mouse", "Keyboard", "Monitor" entries
- No visual distinction from regular products

---

## Troubleshooting Quick Fixes

### Issue: Components Not Grouped

**Fix 1: Check BoM Type**
```
Manufacturing > Products > Bill of Materials
Edit your BoM > BoM Type must be "Kit"
(NOT "Manufacture this product")
```

**Fix 2: Reinstall Module**
```
Apps > Search "Econovo Barcode Kit" > Uninstall > Install
Restart Odoo server
Clear browser cache (Ctrl+Shift+R)
```

### Issue: No Blue Border / Styling Missing

**Fix: Update Assets**
```bash
# Terminal:
./odoo-bin -u econovo_barcode_kit_bom_stock_move_line_grouping -d your_database

# Or via UI:
Apps > Econovo Barcode Kit > Upgrade
Settings > Technical > User Interface > Assets > Clear Cache
```

### Issue: JavaScript Errors

**Fix: Check Browser Console**
```
Press F12 > Console tab
Look for errors containing "barcode" or "econovo"

Common issues:
- Module not loaded: Restart Odoo server
- Patch conflict: Disable conflicting custom modules
- Asset not found: Run `odoo-bin -u module_name`
```

---

## Next Steps

1. **Read Full Documentation:** [README.md](README.md)
2. **Run Full Tests:** [TESTING.md](TESTING.md)
3. **Customize Styling:** [static/src/scss/kit_barcode.scss](static/src/scss/kit_barcode.scss)
4. **Report Issues:** https://github.com/josedleonett

---

## Production Deployment Checklist

Before deploying to production:

- [ ] Tested with real kit products (not just demo data)
- [ ] Verified multi-location kits work correctly
- [ ] Checked compatibility with existing custom modules
- [ ] Confirmed no JavaScript errors in browser console
- [ ] Validated performance with large kits (10+ components)
- [ ] Tested with warehouse operators (user acceptance)
- [ ] Backed up database before installation
- [ ] Scheduled installation during low-traffic hours
- [ ] Prepared rollback plan if issues occur

---

**Happy Kit Grouping! 🧊📦**
