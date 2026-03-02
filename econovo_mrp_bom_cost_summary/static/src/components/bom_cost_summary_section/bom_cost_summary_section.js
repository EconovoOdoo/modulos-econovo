/** @odoo-module **/

import { formatFloat, formatMonetary } from "@web/views/fields/formatters";
import { Component, useState } from "@odoo/owl";

export class BomCostSummarySection extends Component {
    setup() {
        this.formatFloat = formatFloat;

        // Initialize fold state: categories (level 1), products (level 2), workcenters
        const foldState = {};
        for (const cat of this.props.data.categories) {
            foldState[`cat_${cat.id}`] = true;
            for (const prod of cat.products) {
                foldState[`prod_${cat.id}_${prod.product_id}`] = true;
            }
        }
        for (const wc of this.props.data.workcenters) {
            foldState[`wc_${wc.id}`] = true;
        }
        this.state = useState(foldState);
    }

    // ---- Handlers ----

    toggleCategory(categId) {
        const key = `cat_${categId}`;
        this.state[key] = !this.state[key];
    }

    toggleProduct(categId, productId) {
        const key = `prod_${categId}_${productId}`;
        this.state[key] = !this.state[key];
    }

    toggleWorkcenter(wcId) {
        const key = `wc_${wcId}`;
        this.state[key] = !this.state[key];
    }

    // ---- Getters ----

    get data() {
        return this.props.data;
    }

    get currencyId() {
        return this.data.currency_id;
    }

    get secondaryCurrency() {
        return this.props.secondaryCurrency;
    }

    get hasSecondary() {
        return !!this.secondaryCurrency;
    }

    get showUom() {
        return this.props.showOptions.uom;
    }

    isCategoryFolded(categId) {
        return this.state[`cat_${categId}`];
    }

    isProductFolded(categId, productId) {
        return this.state[`prod_${categId}_${productId}`];
    }

    isWorkcenterFolded(wcId) {
        return this.state[`wc_${wcId}`];
    }

    // ---- Formatters ----

    fmtMoney(val) {
        return formatMonetary(val, { currencyId: this.currencyId });
    }

    fmtUsd(val) {
        if (!this.hasSecondary || val === false) {
            return "";
        }
        return formatMonetary(val, { currencyId: this.secondaryCurrency.id });
    }

    fmtPct(val) {
        return formatFloat(val, { digits: [false, 1] }) + "%";
    }

    fmtDuration(minutes) {
        const h = Math.floor(minutes / 60);
        const m = Math.round(minutes % 60);
        return h > 0 ? `${h}h ${m}min` : `${m}min`;
    }
}

BomCostSummarySection.template =
    "econovo_mrp_bom_cost_summary.BomCostSummarySection";
BomCostSummarySection.props = {
    data: Object,
    showOptions: Object,
    precision: Number,
    secondaryCurrency: { type: [Object, Boolean], optional: true },
};
