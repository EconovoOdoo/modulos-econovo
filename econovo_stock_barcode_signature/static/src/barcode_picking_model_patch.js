/** @odoo-module **/

import BarcodePickingModel from '@stock_barcode/models/barcode_picking_model';
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

/**
 * Patch the picking model to expose the signature requirement to the UI and
 * to persist the captured signature.
 *
 * BarcodePickingBatchModel (module stock_barcode_picking_batch) extends this
 * same class, so a Batch Transfer inherits this behavior without any extra
 * code: `resModel` is then 'stock.picking.batch' and `signaturePickingIds`
 * returns every underlying transfer instead of a single one.
 */
patch(BarcodePickingModel.prototype, {
    get displaySignButton() {
        return Boolean(
            this.record && this.config &&
            this.config.barcode_require_signature &&
            this.record.state !== 'cancel'
        );
    },

    /**
     * IDs of the stock.picking records the signature must be written on.
     * A Batch Transfer has no signature field of its own: the same
     * signature is stored on every transfer it contains, representing a
     * single custody handoff (e.g. a carrier picking up several orders,
     * possibly for different customers) rather than a proof of delivery
     * per customer.
     */
    get signaturePickingIds() {
        if (this.resModel === 'stock.picking.batch') {
            return this.record.picking_ids;
        }
        return [this.resId];
    },

    async uploadSignature(signatureData) {
        const pickingIds = this.signaturePickingIds;
        if (!pickingIds || !pickingIds.length) {
            return;
        }
        await this.orm.write('stock.picking', pickingIds, { signature: signatureData });
        this.notification(_t("Signature saved"), { type: "success" });
    },
});
