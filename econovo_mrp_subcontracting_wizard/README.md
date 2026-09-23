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
  and applying Odoo's *Resupply Subcontractor on Order* route to every component delivered to the
  vendor.
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

## Usage

### Where the menus are

Everything lives under the **Manufacturing** app. The whole *Operation Subcontracting* menu and
the *Operation Categories* menu are only visible to members of the *Operation Subcontracting /
Manager* group — if you do not see them, the group is missing.

| What | Menu |
|---|---|
| Operation categories | Manufacturing > Configuration > **Operation Categories** |
| Externalization assistant | Manufacturing > Operations > Operation Subcontracting > **Externalize an Operation** |
| Bulk mode | Manufacturing > Operations > Operation Subcontracting > **Bulk Externalization / Internalization** |
| Chains dashboard | Manufacturing > Operations > Operation Subcontracting > **Subcontracting Chains** |
| Internalization assistant | No menu of its own — **Internalize Operation** button in the header of a chain |

A Bill of Materials that belongs to a chain also shows a **Subcontracting Chain** smart button
that opens the chain directly.

### Shortcuts from the operations themselves

The assistants do not have to be reached from the menu. The same wizards are available wherever
an operation is visible, so that planners can act without leaving what they are looking at:

| From | What you get |
|---|---|
| Operation form (Manufacturing > Operations > Operations) | **Externalize Operation** button in the header, prefilled with that Bill of Materials and operation |
| Operations list, with records ticked | **Externalize** / **Internalize** buttons in the list header — one record opens the individual assistant, several open the bulk one already loaded |
| Bill of Materials form, *Operations* tab | **Externalize Operation** button on each row, next to *Archive Operation* |
| Operation category form | **Operations** smart button listing every operation of that category, ready to be ticked and processed |

Because an externalized operation is removed from the Bill of Materials (Odoo forbids operations
on a subcontracted one), **Internalize** works on the operations that stayed in-house: it resolves
the chain they belong to and internalizes that chain.

Selections spanning several companies are refused, and so are operations whose Bill of Materials
is already subcontracted — internalize it first.

### Externalizing one operation

1. Open Manufacturing > Operations > Operation Subcontracting > **Externalize an Operation**.
2. *What to externalize*: pick the **Bill of Materials**, then the **Operation to Externalize**.
   Leaving the operation empty subcontracts the whole product instead of a single step.
3. *To whom*: pick the **Subcontractor**, the **Warehouse** that will ship the components, and
   optionally the **Subcontracting Price** and *Replenish on Order (MTO)*.
4. Choose the **ECO Type** and the **PLM Registration** mode (see *PLM integration* below).
5. Press **Next**. The assistant shows the prechecks, a preview of the resulting Bills of
   Materials and intermediate products, and the list of components that will be delivered to the
   subcontractor with their resupply route status. Correct anything and press **Back** if needed.
6. Press **Externalize**. The chain record opens.

If a precheck fails — typically an operation without an operation category, or a warehouse
without *Resupply Subcontractors* — the assistant blocks and tells you exactly what to fix.

### Externalizing the same product again

A chain covers **one** outsourcing cycle and is never reused. Once it has been internalized it
becomes a read-only record of what happened, and externalizing the same operation again creates a
new chain.

Nothing has to be looked up to do so: the shortcuts above already act on the live Bill of
Materials, and intermediate products are reused by internal reference instead of being duplicated,
so the second cycle produces the same `CODE-XX` part as the first one.

### Internalizing it back

1. Open the chain from Manufacturing > Operations > Operation Subcontracting > **Subcontracting
   Chains** (or from the smart button on the Bill of Materials).
2. Press **Internalize Operation** in the header.
3. Pick the **Work Center** where the operation will be performed again, the **ECO Type** and the
   **PLM Registration** mode, then press **Next**.
4. Review the merged route: the resulting operations (including the one coming back in-house) and
   the resulting components. Untick **Keep** on any component that should not survive the merge.
5. Press **Internalize**.

The merge preserves the **current** content of the chain: components added while the operation
was outsourced are kept.

### Bulk mode

1. Open Manufacturing > Operations > Operation Subcontracting > **Bulk Externalization /
   Internalization**.
2. Choose the **Mode**, the **Company**, and the filters (operation category, subcontractor,
   warehouse...), then press **Select Records** to load the matching Bills of Materials or chains.
3. Set **Records per Run** (default 25) and press **Process Next Batch** repeatedly until the
   progress bar reaches 100%. Each batch is a separate transaction and each record is isolated,
   so one failure does not abort the run.
4. Failed records keep their error message; fix the cause and press **Retry Errors**.

Bulk mode applies the changes directly, **without** creating Engineering Change Orders. Use the
individual assistants when the change has to go through the PLM approval circuit.

### Maintenance

The chain form has a **Re-check Components** button that refreshes the resupply route checklist.
Chains with components missing that route are flagged in the list view — fix them, because
without the route Odoo silently never delivers the component to the subcontractor.

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
