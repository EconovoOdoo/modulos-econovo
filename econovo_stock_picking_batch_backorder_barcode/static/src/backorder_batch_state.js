/** @odoo-module **/

import { reactive } from "@odoo/owl";

/**
 * Shared between the barcode picking model and the backorder dialog: only one
 * backorder dialog can be open at a time, so a single state is enough.
 */
export const backorderBatchState = reactive({
    create: false,
    show: false,
});
