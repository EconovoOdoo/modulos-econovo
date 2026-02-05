# Argentina COMEX Operations for Odoo 17

[![License: AGPL-3](https://img.shields.io/badge/License-AGPL--3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Odoo Version](https://img.shields.io/badge/Odoo-17.0-purple.svg)](https://www.odoo.com)
[![Version](https://img.shields.io/badge/version-17.0.4.1.0-blue.svg)](https://github.com/josedleonett)

Comprehensive management of international trade operations (COMEX - Comercio Exterior) for Argentina with automated tribute tax calculation and full regulatory compliance.

## 🚀 Key Features

### Tribute & Tax Management
- ✅ **Automatic Tax Calculation**: Tax Groups system (IVA 21%, IIGG 6%, IIBB 3%)
- ✅ **Smart Invoice Creation**: Generate tribute invoices directly from customs clearance
- ✅ **Bidirectional Sync**: Edit amounts in invoice or clearance - changes sync automatically
- ✅ **Configurable Mappings**: Product and keyword-based tribute field mapping
- ✅ **Audit Trail**: Comprehensive parsing logs for configuration refinement

### Core COMEX Operations
- 📋 **Dynamic Workflow**: Kanban-style stages (similar to CRM/Project)
- 🚢 **Multi-Shipment Support**: Track multiple shipments and containers per operation
- 📦 **Container Management**: Full tracking with package integration
- 🔄 **Purchase Order Integration**: Automatic PO linking and data synchronization

### Customs Clearance Management
- 📄 **Despacho de Aduana**: Complete customs clearance workflow
- 💰 **MULC Operations**: BCRA forex operations tracking
- 🏛️ **ARCA Compliance**: Support for Argentine customs procedures
- 🌐 **Multi-Port Support**: Buenos Aires, Rosario, and other major ports

### Stock & Logistics Integration
- 🏭 **Transit Locations**: Hierarchical COMEX locations (En Viaje, Puerto, Zona Franca, Depósito Fiscal)
- 🔀 **Automatic Routing**: Purchase receipts redirected to COMEX transit locations
- 📍 **Full Traceability**: Track products through entire import lifecycle
- 📦 **Package Support**: Native Odoo package system for container tracking

## 📥 Installation

### Prerequisites
- Odoo 17.0 Enterprise (tested) or Community
- Argentine Localization (l10n_ar) installed and configured
- Access to Settings > Technical menu (Developer mode)

### Installation Steps

1. **Download Module**
   ```bash
   cd /path/to/odoo/addons
   git clone https://github.com/josedleonett/econovo_l10n_ar_comex.git
   ```

2. **Update Apps List**
   - Go to `Apps > Update Apps List`
   - Search for "Argentina COMEX"
   - Click **Install**

3. **Automatic Setup**
   - Module creates default workflow stages
   - Configures initial tribute products and mappings
   - Sets up tax groups for automatic calculation

> **Note**: The COMEX User group automatically enables the "Packages" feature in Inventory for container tracking.

## ⚙️ Quick Start Configuration

### Step 1: Configure Default Tribute Vendor

**Required for invoice creation**

1. Go to `Settings > General Settings`
2. Scroll to **COMEX Configuration** section
3. Set **Default Tribute Vendor**: Select or create vendor (e.g., "Aduana Argentina", "DGA")
4. Set **Default Document Type**: Select "Despacho de Importación (66)" or similar
5. Click **Save**

### Step 2: Verify Tax Groups

**Tax groups created automatically during installation**

1. Go to `Accounting > Configuration > Taxes`
2. Search for "Import" to find COMEX taxes:
   - **Import Tributes (Tax Group)** - Composite group
   - **IVA Import 21%** - Purchase tax
   - **IIGG Perception 6%** - Purchase tax
   - **IIBB Perception 3%** - Purchase tax

3. **Verify Configuration**:
   - All taxes should be type "Purchase"
   - Tax Computation: "Percentage of Price"
   - Tax Group has 3 children taxes

> **Important**: Do NOT modify tax structure unless necessary. The system is pre-configured for Argentine import operations.

### Step 3: Review Tribute Products

**Products for invoice line creation (created during installation)**

1. Go to `COMEX > Configuration > Tribute Product Mappings`
2. Verify 3 active mappings exist:
   - **DIE - Derecho de Importación** → `amount_duties`
   - **Tasa Estadística** → `amount_statistics`
   - **Servicios de Guarda** → `amount_fees`

3. **Check Product Configuration**:
   - Each product should have `Supplier Taxes` = "Import Tributes (Tax Group)"
   - Product Type: Service or Consumable
   - Expense Account: Configured correctly

### Step 4: Optional Keyword Mappings

**For automatic invoice line parsing (fallback when no product match)**

1. Go to `COMEX > Configuration > Tribute Keyword Mappings`
2. Review existing keywords:
   - "die", "derecho de importación", "arancel" → `amount_duties`
   - "tasa estadística", "estadística" → `amount_statistics`
   - "servicio de guarda", "almacenaje" → `amount_fees`

3. **Add Custom Keywords** (optional):
   - Click **New**
   - Enter keyword text (e.g., "DIM" for import duties)
   - Select Match Type: "Contains", "Starts with", "Ends with", "Exact", or "Regex"
   - Select Tribute Field
   - Set Priority (higher = checked first)
   - Check "Stop on Match" to prevent multiple matches

### Step 5: Test Workflow

**Create your first tribute invoice**

1. **Create Customs Clearance**:
   - Go to `COMEX > Customs > Customs Clearances`
   - Click **New**
   - Fill basic info (Operation, Dispatch Number)
   - Enter tribute amounts:
     - Import Duties (DIE): `20,000.00`
     - Statistics Fee: `5,500.00`
     - Other Fees: `5,000.00`
   - **Save**

2. **Generate Invoice**:
   - Click **Create Tribute Invoice** button
   - System creates invoice with:
     - 3 base amount lines (DIE, Statistics, Guard)
     - 6 automatic tax lines (IVA, IIGG, IIBB for each base)
   - Invoice linked to clearance automatically

3. **Verify Automatic Calculation**:
   - Expected amounts:
     - DIE: $20,000 → IVA $4,200, IIGG $1,200, IIBB $600
     - Statistics: $5,500 → IVA $1,155, IIGG $330, IIBB $165
     - Fees: $5,000 → No taxes (services)
   - **Total Invoice**: Base $30,500 + Taxes $7,650 = **$38,150**

4. **Test Bidirectional Sync**:
   - Open linked invoice
   - Change DIE amount from $20,000 → $25,000
   - Save invoice
   - Return to clearance → `amount_duties` now shows $25,000 ✓
   - Tax lines recalculated automatically ✓

## 📖 Usage Guide

### Creating an Import Operation

1. **Navigate**: `COMEX > Operations > Imports`
2. **Create**: Click **New**
3. **Fill Details**:
   - Supplier/Exporter
   - Import Type (Definitive/Temporary)
   - Commercial Agreement (if applicable)
4. **Link Purchase Orders**: Add in "Purchase Orders" tab
5. **Track Progress**: Move through stages via Kanban

### Managing Shipments

1. From COMEX Operation, go to **Shipments** tab
2. Click **Add a line** or **Create**
3. Enter:
   - Container details (type, seal number)
   - Carrier and tracking reference
   - ETD/ETA dates
   - Incoterm
4. System creates `stock.quant.package` for container tracking

### Customs Clearance Workflow

1. **Create Clearance**: From operation or standalone
2. **Enter Tribute Amounts**: DIE, Statistics, Fees
3. **Link Vendor Bill** (optional): For parsing existing invoices
4. **Create Tribute Invoice**: Generate or link invoice
5. **Process**: Amounts sync automatically with invoice

### Parsing Existing Invoices

If you have an existing vendor bill with tribute charges:

1. Link vendor bill to clearance via `Vendor Bill (DI)` field
2. System automatically parses invoice lines:
   - Matches products against mappings
   - Falls back to keyword matching
   - Populates tribute fields automatically
3. View **Parsing Logs** to see match results
4. Refine mappings if needed for unmatched lines

## 🔧 Advanced Configuration

### Multi-Company Setup

1. Enable multi-company mode
2. Configure tribute products per company (if needed)
3. Set company-specific tax rates
4. Configure default vendors per company in Settings

### Custom Tax Rates

While not recommended, you can adjust tax rates:

1. Go to `Accounting > Configuration > Taxes`
2. Edit individual taxes (IVA, IIGG, IIBB)
3. Change percentage in "Amount" field
4. **Warning**: Affects all future calculations

### Adding New Tribute Fields

Currently supported fields:
- `amount_duties` (DIE)
- `amount_statistics` (Statistics Fee)
- `amount_fees` (Other Fees/Guard Service)

To add more fields, contact development team or modify:
- `comex.tribute.field` model
- `comex_customs_clearance.py` compute/inverse methods
- Tax data and product mappings

## 🏗️ Technical Architecture

### Key Models

| Model | Purpose |
|-------|---------|
| `comex.operation` | Main import/export operation tracking |
| `comex.operation.stage` | Configurable Kanban workflow stages |
| `comex.shipment` | Individual cargo shipments |
| `comex.customs.clearance` | Despacho de aduana management |
| `comex.mulc` | BCRA forex operations |
| `comex.tribute.product.mapping` | Product → tribute field mappings |
| `comex.tribute.keyword.mapping` | Keyword → tribute field mappings |
| `comex.tribute.parse.log` | Invoice parsing audit trail |

### Bidirectional Sync Pattern

Tribute amount fields use **Smart Computed with Inverse**:

```python
amount_duties = fields.Monetary(
    compute='_compute_tribute_amounts',  # Read from invoice
    inverse='_inverse_amount_duties',    # Write to invoice
    store=True,                          # Searchable
)
```

**Behavior**:
- When invoice linked: Amounts compute from invoice lines (single source of truth)
- When no invoice: Fields editable manually (preserved for invoice creation)
- Editing clearance WITH invoice: Updates invoice line via inverse method
- Editing invoice: Triggers clearance recompute via depends decorator

### Tax Group System

**Structure**:
```
Import Tributes (Tax Group)
├── IVA Import 21% (tax on price)
├── IIGG Perception 6% (tax on price)
└── IIBB Perception 3% (tax on price)
```

Applied to DIE and Statistics products → Automatic calculation on invoice.

## 📋 Troubleshooting

### Invoice Not Creating

**Problem**: "Configure default tribute vendor" error

**Solution**:
1. Go to `Settings > General Settings`
2. Set Default Tribute Vendor in COMEX Configuration
3. Save and retry

### Amounts Not Syncing

**Problem**: Changes in invoice don't reflect in clearance

**Solution**:
1. Refresh clearance form (F5)
2. Check parse logs for errors
3. Verify invoice is saved (not draft without save)
4. Update module if using old version

### Wrong Tax Calculation

**Problem**: Tax amounts don't match expected

**Solution**:
1. Verify tax rates in `Accounting > Taxes`
2. Check product has correct `Supplier Taxes` field set
3. Ensure tax group contains all 3 taxes
4. Recalculate by editing invoice line amount

### Unmatched Invoice Lines

**Problem**: Parse logs show many unmatched lines

**Solution**:
1. Review `COMEX > Configuration > Parsing Logs`
2. Add keyword mappings for common patterns
3. Update product mappings if product names changed
4. Use regex for complex patterns

## 🛣️ Roadmap

### Planned Features (Phase 5+)
- [ ] Export operations workflow
- [ ] ARCA web service integration
- [ ] BCRA MULC automatic rate fetching
- [ ] SIM/SIRA integration
- [ ] NCM code management and validation
- [ ] Multi-currency landed cost allocation
- [ ] Enhanced reporting and analytics

### Current Development
- [x] **Phase 4.1**: Tax Groups and automatic calculation ✅
- [x] Bidirectional sync clearance ↔ invoice ✅
- [x] Product and keyword-based mappings ✅
- [x] Parse log audit system ✅

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Follow [Odoo Coding Guidelines](https://www.odoo.com/documentation/17.0/contributing/development/coding_guidelines.html)
4. Commit changes (`git commit -m '[TAG] module: Description'`)
5. Push to branch (`git push origin feature/AmazingFeature`)
6. Open a Pull Request

### Coding Standards
- Follow Odoo 17 patterns (compute+inverse for bidirectional fields)
- Use English for code and comments
- Add docstrings to all methods
- Keep diffs minimal in stable versions
- Test with real Argentine import scenarios

## 📄 License

This module is licensed under **AGPL-3**. See the [LICENSE](LICENSE) file for full details.

## 👨‍💻 Author

**Jose D. Leonett**
- GitHub: [@josedleonett](https://github.com/josedleonett)
- Website: https://github.com/josedleonett

## 💬 Support

For issues, questions, or feature requests:
- Use GitHub [Issues](https://github.com/josedleonett/econovo_l10n_ar_comex/issues)
- Include Odoo version, module version, and detailed error description
- Attach logs when reporting bugs

## 🙏 Acknowledgments

- Odoo Community for excellent documentation
- Argentine COMEX professionals for real-world requirements
- Contributors and testers

---

**Made with ❤️ for Argentine import/export operations**
