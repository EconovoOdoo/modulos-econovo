# Sale Project Task Generation For Non-Service Products

Extends Odoo's native "Create on Order" (`service_tracking`) mechanism so a
Project and/or Task can be generated from a Sale Order line for **consumable
and storable products**, not only products of type *Service*.

## Problem

Odoo (`sale_project`) only lets a product generate a Project/Task from a
Sale Order when its Product Type is *Service*: the "Create on Order" field
is hidden for any other type, and the underlying `is_service` flag used
throughout `sale_project` is hard-coded to `product.type == 'service'`.
Businesses selling a physical product (equipment, hardware, ...) that still
needs follow-up work (installation, assembly, delivery coordination, ...)
have no way to trigger that same tracking.

## Solution

* "Create on Order" is shown and editable on every product type.
* `sale.order.line.is_service` is extended (not replaced) so a line whose
  product has a Service Tracking option configured also flows through
  `sale_project`'s existing generation pipeline. As a result, project/task
  creation, milestones, the analytic distribution fallback and (if
  `sale_timesheet` is installed) Timesheets hour allocation all keep working
  exactly as they do for real services, without duplicating that logic.
* The Product Type field can be changed afterwards without silently
  resetting the configured Service Tracking option.
* The "Projects"/"Tasks" smart buttons on the Sale Order show up for orders
  generated from tracked non-service lines too.
* Once a project/task has been generated, the product can no longer be
  swapped on the confirmed line, mirroring the safeguard already applied to
  services.

## Features

* Same 4 "Create on Order" options as native services:
  * **Nothing**: no project or task is created.
  * **Task**: a task is created in an existing project.
  * **Project & Task**: a new project is created with a task in it.
  * **Project**: a new project is created, without a task.

## Known limitations

* `sale.order.line.is_service` is a stored field. Pre-existing sale order
  lines created before this module was installed keep whatever value was
  computed at the time; only lines created (or recomputed) afterwards pick
  up the extended rule. This has no practical impact since project/task
  generation only ever happens once, at order confirmation time.
* The Project app's own "Sale Order Items" quick-create popup
  (`sale_project.sale_order_line_view_form_editable`) still restricts the
  product picker to Service products; this module only covers the Sales →
  Project direction described above.
* `sale_project`'s own test suite includes `test_sol_product_type_update`,
  which asserts that changing a product's type away from `service` clears
  its `is_service` flag even when Service Tracking is still configured on
  it. That assertion is deliberately no longer true once this module is
  installed (that is the point of the module), so that specific upstream
  test is expected to fail if `sale_project`'s test suite is re-run
  alongside this module — not a regression to fix.

## Requirements

* Module `sale_project` (core)
