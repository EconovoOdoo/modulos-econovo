# Econovo MRP Operations Multilevel Filter

## Overview

Adds a contextual action to the **Manufacturing > Configuration > Operations**
list (`mrp.routing.workcenter`) to drill down into a multi-level Bill of
Materials: select one or more operations and reopen the same list filtered to
their BOM(s) plus every sub-BOM used by their components, at any depth.

## Why

The generic Operations list shows every routing operation across every BOM in
a single flat list, with no way to scope it to a specific product's full
component tree. There is no stored recursive relation between BOMs (a
component's own BOM is only known through `mrp.bom.line.child_bom_id`), so
native filters/`child_of` domains cannot express "this BOM and all its
sub-assemblies".

Example: selecting an operation of "Bicycle" and running this action shows
every operation of Bicycle, plus every operation of the Wheel BOM, plus every
operation of any other sub-assembly used anywhere in that tree.

## Usage

1. Go to **Manufacturing > Configuration > Operations**.
2. Tick the checkbox of one or more operations belonging to the BOM(s) you
   want to explode (e.g. an operation of "Bicycle").
3. Open the **Actions** (gear) menu and click **Multi-level Operations**.
4. The list reopens filtered to `bom_id in (selected BOM(s) + every sub-BOM
   used by their components, at any depth)`. Standard list filters, group by
   and export are still available on the result.

## Technical Details

### Models

* `mrp.bom` (inherited): adds `_get_multilevel_bom_ids()`, a recursive helper
  that walks `bom_line_ids.child_bom_id` (the same relation Odoo's own
  "Structure and Cost" report uses to explode a multi-level BOM) and returns
  this/these BOM(s) plus every sub-BOM found at any depth. Already visited
  BOMs are skipped, so shared sub-assemblies and circular references cannot
  cause an infinite loop.
* `mrp.routing.workcenter` (inherited): adds
  `action_view_multilevel_operations()`, bound as a contextual
  `ir.actions.server` on the list view, which computes the recursive BOM set
  for the selected operation(s) and reopens the same model/view with a
  `bom_id in (...)` domain.

### Multi-company

No extra company filtering is added: `child_bom_id` is a core field already
scoped by the current company context, and standard multi-company record
rules on `mrp.bom`/`mrp.routing.workcenter` still apply when the resulting
action searches/reads records, exactly as they do on the native Operations
list.

## Dependencies

* `mrp`: Manufacturing module

## License

AGPL-3

## Author

Jose D. Leonett - [GitHub](https://github.com/josedleonett)
