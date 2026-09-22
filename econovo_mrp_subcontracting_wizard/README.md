# Econovo MRP Subcontracting Wizard

Assisted externalization and internalization of manufacturing operations, riding entirely on
Odoo's native subcontracting engine.

## Overview

Odoo's native subcontracting works at the **product** level: a Bill of Materials of type
`Subcontracting` is a black box and, by design, cannot contain operations
(`mrp.bom._check_subcontracting_no_operation`). Subcontracting a single step of a longer route
therefore requires splitting the route into several Bills of Materials with intermediate
products in between — a lot of manual, error-prone setup when hundreds of parts share the same
outsourced step.

This module automates that setup while leaving the native purchase / delivery / receipt /
invoicing / valuation flow completely untouched.

## Features

- **Operation categories**: a short code (`ZN`, `PL`, `CL`...) per manufacturing operation, used
  to name the generated intermediate products consistently.
- **Externalization assistant**: splits a route around the chosen operation, generating only the
  intermediate products that are actually needed, configuring the vendor and the purchase route,
  and applying the subcontractor resupply route to every component delivered to the vendor.
- **Internalization assistant**: merges the chain back into a single in-house Bill of Materials,
  preserving the **current** content — components added while the operation was outsourced are
  kept, not rolled back.
- **Subcontracting chains dashboard**: one record per chain with its Bills of Materials,
  intermediate products, component checklist, related ECOs, purchases, receipts and resupplies.
- **Bulk mode**: processes large selections in chunks, one transaction per batch, reporting
  errors per record without aborting the run.

## How the route is split

The number of Bills of Materials and intermediate products depends only on where the
externalized operation sits in the route:

| Operations before | Operations after | Bills of Materials | Intermediate products |
|---|---|---|---|
| none | none | 1 (subcontract) | 0 |
| none | yes | 2 | 1 |
| yes | none | 2 | 1 |
| yes | yes | 3 | 2 |

The suffix of an intermediate product is always the category code of the **last operation
actually performed** to reach that state. For a route `Laser Cutting -> Bending -> Zinc Plating`
with Zinc Plating outsourced, the part delivered to the vendor is `CODE-PL` (it has just been
bent) and what comes back is the real final product `CODE`, with no suffix.

## Requirements

- Odoo 17.0 Enterprise (depends on `mrp_plm`).
- `mrp_subcontracting`, `purchase_stock`, `econovo_mrp_plm_enforce_eco`.
- The *Subcontracting* setting enabled in Manufacturing, and *Resupply Subcontractors* enabled
  on the warehouses used.

## Configuration

1. Manufacturing > Configuration > Operation Categories: create one category per operation that
   may be outsourced.
2. Assign the category on the operations of the Bills of Materials.
3. Give the users who will run the assistants the *Operation Subcontracting / Manager* group.

## PLM integration

Every individual externalization and internalization is registered as a real Engineering Change
Order. The ECO type is picked by the user on each run — nothing is hardcoded. Two modes are
available:

- **Create the ECO already applied**: the assistant moves the ECO to a stage allowing changes to
  be applied and calls the standard `action_apply()`. Who skipped the approval circuit is
  recorded on the chain and in the ECO chatter.
- **Create the ECO and follow the approval circuit**: the chain is built on the Bill of Materials
  revision and stays archived until a human applies the ECO, so a pending approval never leaves
  a half-live chain behind.

Bulk mode does **not** create Engineering Change Orders. Because it writes directly on Bills of
Materials that the PLM guard locks, it is restricted to the *Operation Subcontracting / Manager*
group and elevates privileges only around the structural writes performed by the engine.
