# Econovo MRP BOM Cost Summary

## Overview

Adds a **collapsible cost summary section** at the bottom of the BOM Overview
(`mrp_bom_report` client action) that displays:

- **Component costs grouped by product category** — 3-level drill-down:
  Category → Component Product → Parent product usages
- **Operation costs grouped by work center** — with inline parent product
  traceability
- **Dual currency** — All amounts shown in ARS (company currency) and USD
- **Grand total** — Combined components + operations cost

## Dependencies

- `mrp` (Manufacturing)
- `product` (Product)

No dependency on any other Econovo module.

## Installation

1. Copy this module folder into your Odoo 17 addons path
2. Update the module list: Settings → Technical → Update Apps List
3. Search for "Econovo MRP BOM Cost Summary" and install

## Usage

1. Navigate to **Manufacturing → Products → Bills of Materials**
2. Select a BOM and click **BOM Overview**
3. The cost summary section appears automatically below the BOM table
4. Click the fold/unfold carets to drill down into categories, products, and
   work centers

## Author

Jose D. Leonett — [https://github.com/josedleonett](https://github.com/josedleonett)

## License

AGPL-3
