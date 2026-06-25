# PLM Enforce ECO Workflow

Forces non-admin Manufacturing users to go through the PLM Engineering Change
Order (ECO) workflow when modifying Bills of Materials that are already in
production use.

## Profiles

| Profile | Groups | Behaviour |
|---------|--------|-----------|
| Read-only | `mrp.group_mrp_user` | Reads all BoMs. No write. |
| **Controlled Editor** | `econovo_mrp_plm_enforce_eco.group_plm_controlled_editor` (implies `mrp.group_mrp_user` and `mrp_plm.group_plm_user`) | Reads, creates, edits BoMs without MOs, edits revisions via ECO, applies ECOs, deletes unused BoMs. |
| MRP Administrator | `mrp.group_mrp_manager` (+ optional `mrp_plm.group_plm_manager`) | Full access. |

## What the controlled editor can do

* Create new BoMs (manual form or Excel import).
* Edit a BoM **as long as it has not been used in any Manufacturing Order**.
* Edit a BoM if a related ECO is in `confirmed` or `progress` state.
* Edit the revision BoM (`active=False`) attached to an ECO.
* Apply an ECO they validated (the apply flow runs as sudo internally).
* Delete a BoM only if it is active and not used in any MO.

## What the controlled editor cannot do

* Edit a BoM that is already used in production without opening an ECO.
* Delete a BoM used in production or a revision still attached to an ECO.
* Edit the `active` flag of a production BoM outside the ECO flow.

## Mass action

A "Crear ECO" action is added to the BoM list. Selecting one or several
production-ready BoMs and running the action creates a draft ECO for each one
and opens the resulting records.

## Technical notes

* The `mo_count` field added to `mrp.bom` is computed on demand and supports
  the `= 0` / `!= 0` search needed by the record rule. It is not stored.
* The `apply_new_version()` override on `mrp.bom` simply calls
  `super(..., self.sudo())` so that the controlled editor can deactivate the
  previous active BoM as part of the validated PLM flow.
* Two record rules are defined: one for write (broad), one for unlink
  (stricter: only active BoMs without MOs).

## Migration from a previous manual setup

If a manual group / ACLs / rules were created in a database before installing
this module, after install reassign the affected users from the manual group
to `group_plm_controlled_editor` and then remove the manual records.
