# Econovo User Warehouse Restriction

**Permission Matrix System for Odoo 17**

## 🎯 Features

✅ **Granular Control**: 10 permission flags per user, per warehouse  
✅ **Per-Warehouse Blacklist**: Location restrictions specific to each warehouse  
✅ **Special Modes**: Full Control & View Only for quick configuration  
✅ **Transit Control**: Per-user transit location bypass  
✅ **Flexible Matrix**: Different permissions per warehouse for same user

---

## 📊 Permission Matrix (10 Flags)

### Special Modes

| Flag | Description | Effect |
|------|-------------|--------|
| `full_control` | Administrator mode | Auto-enables all 10 flags |
| `view_only` | Read-only access | Blocks all write operations |

### Warehouse-Level Permissions

| Flag | Description | Use Case |
|------|-------------|----------|
| `allow_as_source` | Use warehouse as stock source | Required for outbound transfers |
| `allow_as_destination` | Use warehouse as stock destination | Required for inbound transfers |
| `allow_inventory_adjustment` | Perform inventory adjustments | Required for stock corrections |

### Operation-Level Permissions

| Flag | Description | Use Case |
|------|-------------|----------|
| `allow_create_picking` | Create new pickings | Required to initiate transfers |
| `allow_write_picking` | Modify existing pickings | Required to edit draft transfers |
| `allow_delete_picking` | Delete pickings | Required to cancel transfers |

### Location Restrictions

| Flag | Description | Use Case |
|------|-------------|----------|
| `blocked_location_ids` | Per-warehouse location blacklist | Block access to QC, High Value zones |
| `allow_transit` | Bypass transit location restrictions | Allow access to shared transit areas |

---

## 🚀 Use Cases

### 1. Full Control (Single Warehouse)

**Scenario**: Warehouse operator with complete access to WH1

```
User: John Doe
Warehouse: WH1
full_control: True
```

**Result**: John has all 10 permissions enabled for WH1

---

### 2. Source Only (Redistribute Stock)

**Scenario**: Regional manager can redistribute stock FROM WH1 to any destination

```
User: Regional Manager
Warehouse: WH1
allow_as_source: True
allow_as_destination: False
allow_create_picking: True
allow_write_picking: True
```

**Result**: Can move stock OUT of WH1, but cannot receive INTO WH1

---

### 3. View Only (Auditor)

**Scenario**: Auditor needs read-only access to inventory

```
User: Auditor
Warehouse: WH1
view_only: True
```

**Result**: Can view all inventory records, cannot create/modify/delete

---

### 4. Quality Control Restrictions

**Scenario**: Warehouse operator cannot access QC zone

```
User: Warehouse Operator
Warehouse: WH1
full_control: True
blocked_location_ids: [WH1/QC Zone, WH1/High Value]
```

**Result**: Full access to WH1 EXCEPT QC and High Value locations

---

### 5. Multi-Warehouse (Different Permissions)

**Scenario**: Supervisor with different permissions per warehouse

```
User: Supervisor
WH1: full_control=True → Full admin access
WH2: allow_as_source=True, allow_as_destination=False → Redistribute only
WH3: view_only=True → Read-only audit
```

**Result**: Granular control across multiple warehouses

---

## ⚙️ Configuration

### Automatic Setup (Installation)

Upon module installation, the system automatically:

1. **Assigns restriction group** to all existing inventory users
2. **Creates Full Control permissions** for all system administrators
3. **Auto-assigns group** to all newly created inventory users

**Security Model (Restrictive by Default)**:
- ✅ Users **WITH** permissions configured: Access granted per matrix
- ❌ Users **WITHOUT** permissions configured: **NO access to any warehouse**
- ✅ System Administrators: **Bypass ALL restrictions** (unrestricted access)

**Important**: After installation, you MUST configure permissions for all users. 
Users without permission records will be locked out of all warehouses.

### Method 1: Per-Warehouse Configuration

1. Go to **Inventory → Configuration → Warehouses**
2. Select a warehouse
3. Click **"User Permissions"** tab
4. Add users with granular permission flags

### Method 2: Centralized Matrix View

1. Go to **Inventory → Configuration → User Warehouse Permissions**
2. View/edit all permissions in a matrix table
3. Filter by user, warehouse, or permission flags

---

## 🏗️ Architecture

### Permission Matrix Model

**warehouse.user.permission**: Core model with 10 flags per user/warehouse

- **SQL Constraint**: unique_user_warehouse (one permission record per user/warehouse)
- **Python Constraints**: _check_special_modes_consistency (validates conflicts)
- **Helper Methods**: 8 methods for permission checking (has_source_permission, has_destination_permission, etc.)

### Record Rules (8 total)

1. **warehouse.user.permission** - Own records only
2. **stock.picking.type** - Filter by permission existence
3. **stock.location** - Location access control
4. **stock.warehouse** - Filter by permission existence
5. **stock.picking** - Filter by permission existence
6. **stock.quant** - With transit support
7. **stock.move** - Source/destination validation
8. **stock.move.line** - Source/destination validation

### Python Constraints

**stock.move._check_warehouse_transfer_permission()**:
- Hierarchical validation: Warehouse access → Location blacklist → Transit bypass
- Uses `permission.has_source_permission()`, `has_destination_permission()`
- Checks `blocked_location_ids` with `allow_transit` bypass

### Domain Restrictions

**stock.picking._onchange_location_id()**:
- Filters source locations (`allow_as_source=True`)
- Filters destination locations (`allow_as_destination=True`)
- Excludes `blocked_location_ids` from dropdowns

---

## 🐛 Troubleshooting

### User Cannot Access Warehouse

**Symptom**: "No permission record found for this warehouse"

**Solution**:
1. Go to Warehouse → "User Permissions" tab
2. Add user with appropriate permission flags
3. Ensure at least `allow_as_source=True` or `allow_as_destination=True`

---

### Cannot Access Specific Location

**Symptom**: "This location is in your blacklist"

**Solution**:
1. Check `permission.blocked_location_ids` for that warehouse
2. Remove location from blacklist
3. OR enable `allow_transit=True` if it's a transit location

---

## 📝 Changelog

### v17.0.1.0.0 (2025-11-22) - INITIAL RELEASE

**Added:**
- warehouse.user.permission model (10 flags)
- Special modes (Full Control, View Only)
- Per-warehouse location blacklist
- Transit location bypass
- 8 record rules with permission matrix
- Python constraints for warehouse transfer validation
- Centralized permission matrix view
- Per-warehouse permission configuration

---

## 👥 Credits

**Author**: Jose D. Leonett  
**Website**: https://github.com/josedleonett  
**License**: AGPL-3

---

## 📞 Support

For issues, questions, or feature requests:
- GitHub Issues: https://github.com/josedleonett/econovo_user_warehouse_restriction
- Email: odoo@econovo.com

---

**Last Updated**: 2025-11-22  
**Module Version**: v17.0.1.0.0  
**Odoo Version**: 17.0
