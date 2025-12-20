# Econovo MRP BOM Analysis

## Overview

This module provides comprehensive Bill of Materials (BOM) analysis for manufacturing operations, enabling cost breakdown analysis with grouping capabilities using native Odoo tree views.

## Features

### Core Functionality
- **Recursive BOM Explosion**: Analyzes all BOM levels recursively, showing the complete component hierarchy
- **Native Grouping**: Group components by category, product, origin type, level, or supplier
- **Inline Editing**: Edit costs and quantities directly in the tree view with automatic synchronization
- **Cost Analysis**: View cost share percentages, cost variations, and totals

### Key Metrics
- **Cost Share %**: Shows what percentage of total cost each component represents
- **Cost Variation %**: Tracks price changes from previous analysis
- **Total Costs**: In local currency and USD (if configured)
- **Stock Availability**: Shows on-hand, forecasted, and free quantities

### Origin Types
Components can be categorized by origin type on their product category:
- **Raw Material**: Base materials for production
- **Commercial**: Purchased ready-made components
- **Subassembly**: Components with their own BOM
- **Component**: Generic production components
- **Consumable**: Non-storable consumables
- **Service**: Service-type products

## Usage

### Accessing Component Analysis
1. Navigate to **Manufacturing > Products > Bills of Materials**
2. Open a BOM form
3. Click the **Analysis** smart button in the top-right
4. The analysis is generated automatically on first access

### Regenerating Analysis
- Click the **Regenerate Analysis** button in the BOM form header
- This deletes existing analysis and creates fresh data from current BOM

### Grouping and Filtering
Use the search bar to:
- Group by category, product, origin type, level, or supplier
- Filter by subassemblies, component levels, cost impact, etc.

### Editing Components
Editable fields that sync with original records:
- **BOM Qty**: Updates the quantity in `mrp.bom.line`
- **Unit Cost**: Updates `standard_price` on `product.product`
- **Cost USD**: Updates `standard_price_usd` if available
- **Sale Price**: Updates `list_price` on product
- **Weight**: Updates `weight` on product

### View Types
- **Tree View**: Main analysis with editable columns and multi-edit support
- **Pivot View**: Cross-tabulation by category and origin type
- **Graph View**: Pie chart for cost distribution

## Configuration

### Setting Origin Types
1. Navigate to **Settings > Technical > Categories** or **Inventory > Configuration > Product Categories**
2. Edit a category and set the **Origin Type** field
3. All products in that category will inherit this classification

## Technical Details

### Models
- `bom.component.analysis`: Main analysis model
- `mrp.bom` (inherited): Adds smart button and regeneration action
- `product.category` (inherited): Adds `origin_type` selection field

### Dependencies
- `mrp`: Manufacturing module
- `mrp_account`: Manufacturing accounting
- `stock`: Inventory management
- `product`: Product management

## License

AGPL-3

## Author

Jose D. Leonett - [GitHub](https://github.com/josedleonett)
