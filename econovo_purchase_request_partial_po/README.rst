=====================================
Econovo - Purchase Request Partial PO
=====================================

.. !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! This file is structured following OCA conventions but is maintained !!
   !! outside of the OCA repository. Do not use the OCA generator on it.  !!
   !! source digest: sha256:econovo                                       !!
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3

|badge1| |badge2|

This module extends the OCA ``purchase_request`` workflow so that a single
Purchase Request can be fulfilled by **more than one supplier**, even when:

* The company has *Lock Confirmed Orders* enabled
  (``res.company.po_lock = 'lock'``) — confirming the first PO would
  otherwise set ``purchase_state = 'done'`` on the PR line and block any
  further PO creation.
* Purchase Orders were generated from ``stock.rule`` / Manufacturing
  Orders (subcontracting flows) and therefore have **no allocation
  records**, leaving ``pending_qty_to_receive`` equal to the original
  requested qty.
* The user manually edits PO line quantities after creation.

**Table of contents**

.. contents::
   :local:

Use case
========

A requester creates ``PR0001`` for 21 units of product *X*. The buyer
decides to split the fulfilment between two suppliers (11 + 10). Without
this module, after confirming the first PO of 11 units the system raises
*"The purchase has already been completed"* and the buyer cannot create
the second PO.

After installing this module:

#. The first PO is created for 11 units (RFQ wizard pre-filled with 21).
   The buyer edits it to 11 and confirms.
#. The buyer opens the wizard again on the PR. The wizard now pre-fills
   ``10`` (real pending qty), not ``21``.
#. A second PO is created for the remaining 10 units to the second
   supplier, even if the first PO is already in ``done`` (Locked) state.

Features
========

#. **Relaxed completion gate**: the wizard's
   ``_check_valid_request_line`` no longer blocks when the PR line is in
   ``done`` state if there is still real pending qty.
#. **Realistic pending qty**: the wizard pre-fills each item with
   ``product_qty - sum(active PO lines)`` instead of
   ``product_qty - qty_received``. This works even when no allocations
   exist (PR lines linked from ``stock.rule``).
#. **Auto-skip of completed/cancelled lines**: opening the wizard from
   the PR header no longer creates rows with qty 0 for lines that are
   already fully purchased or cancelled.
#. **Over-purchase warning**: a non-blocking warning is shown when the
   user enters a qty larger than the real pending qty.

Configuration
=============

No configuration required. Install the module and the new behaviour is
active for every user who already has access to the
``Create Purchase Order`` wizard.

Known issues / Roadmap
======================

* Returns that decrease physically received qty are not propagated back
  into "pending to purchase" (same limitation as upstream).
* The wizard still supports only **one supplier per execution**: to
  split between two suppliers the buyer must run the wizard twice.
* No pessimistic lock is taken on the PR while the wizard is open, so
  concurrent buyers could over-allocate.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/josedleonett>`_.

Credits
=======

Authors
~~~~~~~

* Jose D. Leonett

Maintainers
~~~~~~~~~~~

This module is maintained by Econovo.
