# Argentina COMEX Operations for Odoo 17

[![License: AGPL-3](https://img.shields.io/badge/License-AGPL--3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Odoo Version](https://img.shields.io/badge/Odoo-17.0-purple.svg)](https://www.odoo.com)

Comprehensive management of international trade operations (COMEX - Comercio Exterior) 
for Argentina, with full integration with purchase orders, stock movements, and 
Argentine regulatory requirements.

## Features

### Core Functionality
- **Dynamic Stage Management**: Kanban-style workflow similar to CRM/Project
- **Multi-Shipment Support**: Track multiple shipments per operation
- **Transit Location Hierarchy**: COMEX-specific stock locations for goods in transit
- **Bidirectional Date Sync**: Automatic synchronization between COMEX, PO, and pickings

### Regulatory Compliance
- **MULC Operations**: Track foreign exchange operations per BCRA regulations
- **Customs Clearances**: Manage despachos de aduana with ARCA integration
- **NCM Codes**: Support for Mercosur nomenclature (future enhancement)

### Stock Integration
- **Transit Locations**: Hierarchical structure for:
  - En Viaje (In Transit - Sea/Air)
  - Puerto (Ports - Buenos Aires, Rosario, etc.)
  - Zona Franca (Free Zones)
  - Depósito Fiscal (Fiscal Warehouses)
- **Automatic Picking Redirection**: Purchase receipts redirected to COMEX locations
- **Full Traceability**: Track products through entire COMEX lifecycle

## Installation

1. Place the module in your Odoo addons path
2. Update the module list: `Apps > Update Apps List`
3. Search for "COMEX" and install

### Dependencies
- base
- mail
- purchase_stock
- sale_stock
- stock
- account
- contacts

## Configuration

### Initial Setup
1. Go to **COMEX > Configuration > Stages** to customize workflow stages
2. Configure transit locations in **Inventory > Configuration > Locations**
3. Set up COMEX partners (Customs Brokers, Freight Forwarders)

### User Groups
- **COMEX User**: Can create and manage operations
- **COMEX Manager**: Full access including stage configuration
- **COMEX Administrator**: Multi-company access

## Usage

### Creating an Import Operation
1. Go to **COMEX > Operations > Imports**
2. Create new operation with supplier details
3. Link purchase orders to the operation
4. Track shipments through stages via Kanban

### Linking Purchase Orders
- From Purchase Order: Click "Create COMEX" button
- From COMEX Operation: Add purchase orders in the related tab

### Stage Transitions
- Drag cards in Kanban view to change stages
- System validates pending pickings before stage change
- Internal transfers are created automatically for stock movements

## Technical Notes

### Key Models
- `comex.operation`: Main operation tracking
- `comex.operation.stage`: Configurable workflow stages
- `comex.shipment`: Individual cargo shipments
- `comex.customs.clearance`: Despacho de aduana
- `comex.mulc`: BCRA forex operations

### Stock Location Structure
```
COMEX (view)
├── En Viaje (view)
│   ├── Marítimo (transit)
│   └── Aéreo (transit)
├── Puerto (view)
│   ├── Buenos Aires (transit)
│   └── Rosario (transit)
├── Zona Franca (view)
│   ├── La Plata (transit)
│   └── Tierra del Fuego (transit)
└── Depósito Fiscal (view)
    ├── Exolgan (transit)
    ├── Terminal 4 (transit)
    └── Ezeiza (transit)
```

## Roadmap

- [ ] NCM code management and validation
- [ ] ARCA web service integration
- [ ] BCRA MULC automatic rate fetching
- [ ] Export operations (Phase 2)
- [ ] SIM/SIRA integration
- [ ] Multi-currency cost allocation

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit 
pull requests to the development branch.

## License

This module is licensed under AGPL-3. See the [LICENSE](LICENSE) file for details.

## Authors

- **Jose D. Leonett** - Initial development
- GitHub: [@josedleonett](https://github.com/josedleonett)

## Support

For issues and feature requests, please use the GitHub issue tracker.
