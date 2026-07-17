# Econovo - Kiosk Mode for Window Actions

Generic, reusable "kiosk / wall-display" framework for Odoo window
actions (`ir.actions.act_window`). Turns any existing list/kanban/...
action into a full-screen, auto-refreshing screen (kitchen-display
style) directly from the action's own form view - no custom
development needed per view or model.

## What this module does

- Adds a **"Kiosco"** tab to the Window Action form view
  (Settings > Technical > Actions > Actions > Window Actions, with
  developer mode enabled).
- Reuses Odoo's own standard web client renderer - any view type the
  action already supports works as-is.
- Two refresh strategies, selectable per action:
  - **Real Time**: pushed through Odoo's bus, no polling. Backed by
    two automatically managed Automated Actions per watched model
    (`base.automation`, visible under Settings > Technical >
    Automation > Automated Actions, tagged internally so this module
    can tell them apart from rules created manually).
  - **Interval**: simple periodic refresh (`kiosk_refresh_interval`
    seconds).
- Optionally hides the floating Discuss chat window popups while a
  kiosk screen is active (`kiosk_hide_chat_window`, on by default), so
  an incoming private message to the logged-in kiosk user is never
  shown on the shared wall screen.
- Hides breadcrumbs, pager and the cog/action menu (bulk actions like
  Export/Archive/Delete) while in kiosk mode. The search bar
  (omnisearch: filters, group by, favorites) is intentionally left
  visible, and no custom font size or color scheme is applied - the
  view looks like standard Odoo, just without navigation/bulk-action
  chrome.

## What this module deliberately does NOT do

- It does not provide a public/no-login access mode. A kiosk screen
  requires a real, logged-in Odoo user session in the kiosk browser
  (an existing user managed manually by IT - this module does not
  create or provision any user).
- It does not automate the Windows/browser/monitor launcher setup
  (PowerToys, scheduled task, etc.) - that is expected to be handled
  outside Odoo, simply pointing the kiosk browser at the `kiosk_url`
  described below.
- It does not ship any specific kiosk screen pre-configured. Enabling
  kiosk mode on a given action is a one-time manual configuration step
  (see below), not something this module does automatically for any
  particular action/model.

## How to enable kiosk mode on an action

1. Enable developer mode.
2. Go to **Settings > Technical > Actions > Actions > Window Actions**
   and open the action you want to turn into a kiosk screen (or
   duplicate an existing one first, if you don't want to alter the
   original action used for normal navigation/menus).
3. Open the new **Kiosco** tab:
   - Tick **Kiosk Mode** (this also forces the action's *Target* to
     *Fullscreen*, which hides the top menu bar).
   - Choose **Refresh Mode**: *Real Time* (default) or *Interval*.
   - If *Interval*, set **Refresh Interval (seconds)**.
   - Leave **Hide Chat Window** ticked unless this specific screen
     should still show Discuss popups.
4. Copy the **Kiosk URL** field's value.
5. In the kiosk PC's browser (already logged in as the dedicated kiosk
   user, in its own browser profile), open that URL in kiosk/full-screen
   mode. Everything from that point on (window management, autostart,
   monitor placement) is handled by the existing PowerToys + scheduled
   task setup - out of scope for this module.

## Real-time refresh - how it works under the hood

When at least one action has **Kiosk Mode** + **Real Time** enabled for
a given model, this module ensures two Automated Actions exist for that
model (created on save, cleaned up automatically once no kiosk action
needs them anymore, including on save/delete of the action itself):

- Trigger **On save** (create or write).
- Trigger **On deletion**.

Both call `env['ir.actions.act_window']._kiosk_notify(model._name)`,
which sends a signal-only bus message (`kiosk_refresh` channel per
model, no record data in the payload) to every kiosk screen currently
watching that model. Each kiosk screen then reloads its own action with
its own domain/context - a change in one model can cause more than one
kiosk screen (with different domains on the same model) to refresh;
this is expected and considered an acceptable trade-off given the low
volume of changes expected on the target screens.

As a safety net (a screen can stay open unattended for many hours), a
kiosk screen in Real Time mode also force-refreshes every 5 minutes and
whenever the bus reconnects, in case a notification was ever missed.

Separately, the kiosk client re-checks the live `kiosk_enabled` /
`kiosk_refresh_mode` / `kiosk_refresh_interval` values every 10 seconds
(via `get_kiosk_state`), regardless of refresh mode. This is
intentionally decoupled from the data-refresh cadence above: disabling
Kiosk Mode on the action record does not itself notify the bus (only
writes on the *watched model* do), so without this fast, independent
check a screen could keep showing kiosk chrome for as long as its data-
refresh interval (or the 5 minute safety net) after being turned off.

## Uninstalling

Automated Actions created by this module are tagged via
`base.automation.kiosk_managed_model` and are cleaned up automatically
as soon as no pager/cog-menu are hidden via CSS
  (`static/src/kiosk/kiosk_mode.scss`) rather than by not rendering
  them at all. Functionally equivalent for the end user, but a future
  refinement could instead drive Odoo's own `display.controlPanel` /
  `env.config.noBreadcrumbs` mechanisms for a "cleaner" hide.
- Dynamic/user-dependent domains or contexts (`uid`, current company,
  etc.) on a kiosk action behave according to whichever user is
  actually logged into the kiosk browser - review the action's
  domain/context before enabling kiosk mode on it.
- `ir.actions.act_window` has no `company_id` of its own; in a
  multi-company database, make sure the action's own domain already
  scopes the data correctly for the kiosk's logged-in user.
- The web client caches the loaded action definition per browser tab
  (`action_service.js` `actionCache`) until a full page reload. Any
  `ir.actions.act_window` field OTHER than the kiosk_* ones (e.g.
  `res_model`, `domain`) can therefore go stale in a tab that already
  displayed that action if it is edited afterwards - a hard reload of
  that tab is the only fix. The kiosk_* fields themselves are exempt
  from this: they are always re-read fresh through the
  `get_kiosk_state` RPC (see `ir_actions_act_window.py` and
  `kiosk_chrome_service.js`), specifically to avoid a kiosk screen (or
  an admin testing in their own tab) getting stuck applying kiosk
  chrome/refresh after `kiosk_enabled` was uncheckednt company,
  etc.) on a kiosk action behave according to whichever user is
  actually logged into the kiosk browser - review the action's
  domain/context before enabling kiosk mode on it.
- `ir.actions.act_window` has no `company_id` of its own; in a
  multi-company database, make sure the action's own domain already
  scopes the data correctly for the kiosk's logged-in user.
