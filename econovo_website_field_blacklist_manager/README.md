# Econovo Website Field Blacklist Manager

## What it does

Lets an administrator **whitelist model fields** so they show up in the Odoo
Website Form Builder (drag & drop → "Existing Field").

By default Odoo hides many fields with `website_form_blacklisted=True` in their
Python definition. Trying to flip that attribute from the UI raises:

> Las propiedades de los campos base no se pueden modificar de esta forma.
> Modifiquelas mediante codigo Python, de preferencia a traves de un modulo
> personalizado.

This module exposes a configuration screen under **Website › Configuration ›
Form Builder Whitelist** to select model + field pairs. The change is applied to
the live registry and re-applied on every worker startup through
`_register_hook`, so it survives restarts and module updates.

## Typical usage

1. Install the module.
2. Go to **Website › Configuration › Form Builder Whitelist › Create**.
3. Pick, for example:
   - Model: `crm.lead`
   - Field: `partner_assigned_id`
4. Save. The field becomes available in the form builder.
5. Edit the page, drag a Field, mark "Existing Field" and select it.
6. Configure a domain if needed
   (e.g. `[("grade_id.name","=","Concesionario externo basico")]`).

## Restore the blacklist

- Archive the record (`active=False`) → the field is blocked again.
- Delete the record → same effect.

## Multi-worker

After create/write/unlink the module calls `registry.signal_changes()` so other
workers reload the registry on the next request. On Odoo.sh or any multi-worker
deployment the change becomes effective within seconds without a manual restart.

## Compatibility

- Odoo 17.0
- Depends on: `website`

## License

AGPL-3
