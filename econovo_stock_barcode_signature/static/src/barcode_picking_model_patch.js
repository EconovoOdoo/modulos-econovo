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
 * code: `resModel`/`resId` are then 'stock.picking.batch' and the batch's
 * own id. econovo_stock_picking_batch_signature adds signature/signed_by to
 * stock.picking.batch and cascades them to every transfer it contains (a
 * single custody handoff, e.g. a carrier picking up several orders,
 * possibly for different customers, rather than a proof of delivery per
 * customer), so writing directly on `resModel` works uniformly for both a
 * single Transfer and a Batch Transfer.
 */
patch(BarcodePickingModel.prototype, {
    get displaySignButton() {
        return Boolean(
            this.record && this.config &&
            this.config.barcode_require_signature &&
            this.record.state !== 'cancel'
        );
    },

    async uploadSignature(name, signatureData) {
        const vals = { signature: signatureData };
        if (name) {
            vals.signed_by = name;
        }
        await this.orm.write(this.resModel, [this.resId], vals);
        this.notification(_t("Signature saved"), { type: "success" });
    },
});
