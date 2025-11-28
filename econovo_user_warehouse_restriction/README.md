# Econovo - User Warehouse Restriction

Granular warehouse access control with 10-flag permission matrix per user/warehouse.

## Features

- **Permission Matrix**: 10 granular flags per user per warehouse
- **Special Modes**: Full Control (admin) and View Only (read-only)
- **Location Blacklist**: Block specific locations per user/warehouse
- **Transit Control**: Per-user transit location bypass
- **MRP Compatible**: Works with manufacturing operations

## Permission Flags

| Flag | Description |
|------|-------------|
| `full_control` | Administrator mode - enables all permissions |
| `view_only` | Read-only access - blocks all write operations |
| `allow_as_source` | Use warehouse as stock source (outbound) |
| `allow_as_destination` | Use warehouse as destination (inbound) |
| `allow_inventory_adjustment` | Perform inventory adjustments |
| `allow_create_picking` | Create new transfers |
| `allow_write_picking` | Modify existing transfers |
| `allow_delete_picking` | Delete/cancel transfers |
| `allow_transit` | Access transit locations |
| `blocked` | Block all access to warehouse |

## Configuration

### Method 1: From Warehouse
1. Inventory → Configuration → Warehouses
2. Select warehouse → "User Permissions" tab
3. Add users with desired permissions

### Method 2: Centralized View
1. Inventory → Configuration → User Warehouse Permissions
2. Manage all permissions in matrix view

## Recommended Profiles

### Warehouse Operator
```
allow_as_source: ✓
allow_as_destination: ✓
allow_create_picking: ✓
allow_write_picking: ✓
allow_transit: ✓
```

### Manufacturing User
```
allow_as_source: ✓
allow_as_destination: ✓
allow_write_picking: ✓
allow_transit: ✓
```

### Auditor (Read-Only)
```
view_only: ✓
```

### Warehouse Manager
```
full_control: ✓
```

## Technical Details

- **Models**: `warehouse.user.permission`, extensions to `stock.warehouse`, `res.users`, `stock.move`
- **Security**: 10 record rules + Python constraints
- **Validation**: SQL-level (record rules) + Python-level (constraints)
- **Hook**: `post_init_hook` auto-assigns admin permissions on install

## Compatibility

- Odoo 17.0 Community Edition
- Compatible with: `stock`, `mrp`, `stock_picking_batch`

## Author

**Jose D. Leonett**  
GitHub: https://github.com/josedleonett

## License

AGPL-3
