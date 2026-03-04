/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import {
    formatFloat,
    formatFloatTime,
    formatMonetary,
} from "@web/views/fields/formatters";
import { Component, useState, useEffect, onWillUpdateProps } from "@odoo/owl";

export class BomCostSummarySection extends Component {
    setup() {
        this.actionService = useService("action");
        this.formatFloat = formatFloat;
        this.formatFloatTime = formatFloatTime;

        // Initialize fold state recursively for category tree nodes
        const foldState = {};
        const initCategoryFold = (nodes) => {
            for (const node of nodes) {
                foldState[`cat_${node.id}`] = true;
                for (const prod of node.products) {
                    foldState[`prod_${node.id}_${prod.product_id}`] = true;
                }
                initCategoryFold(node.children);
            }
        };
        initCategoryFold(this.props.data.categories);
        for (const wc of this.props.data.workcenters) {
            foldState[`wc_${wc.id}`] = true;
        }
        this.state = useState(foldState);

        // When the data tree is replaced (e.g. qty / warehouse / variant change),
        // preserve all existing fold/unfold choices and only add NEW keys
        // (defaulting to unfolded) so the user's current view state is kept.
        onWillUpdateProps((nextProps) => {
            if (nextProps.data !== this.props.data) {
                const newKeys = new Set();
                const collectKeys = (nodes) => {
                    for (const node of nodes) {
                        newKeys.add(`cat_${node.id}`);
                        for (const prod of node.products) {
                            newKeys.add(`prod_${node.id}_${prod.product_id}`);
                        }
                        collectKeys(node.children);
                    }
                };
                collectKeys(nextProps.data.categories);
                for (const wc of nextProps.data.workcenters) {
                    newKeys.add(`wc_${wc.id}`);
                }
                // Remove stale keys (items no longer in the tree)
                for (const key of Object.keys(this.state)) {
                    if (!newKeys.has(key)) {
                        delete this.state[key];
                    }
                }
                // Add new keys as unfolded (false) — preserves existing choices
                for (const key of newKeys) {
                    if (!(key in this.state)) {
                        this.state[key] = false;
                    }
                }
            }
        });

        // Listen to overviewBus events for expand-all / fold-all.
        // The bus is provided by BomCostSummaryView (and BomOverviewComponent)
        // via useSubEnv; it may be absent when the component is rendered
        // in isolation (e.g. tests), so we guard with optional chaining.
        useEffect(() => {
            const bus = this.env.overviewBus;
            if (!bus) {
                return;
            }
            const onUnfoldAll = () => this.expandAll();
            const onFoldAll   = () => this.foldAll();
            bus.addEventListener("unfold-all", onUnfoldAll);
            bus.addEventListener("fold-all",   onFoldAll);
            return () => {
                bus.removeEventListener("unfold-all", onUnfoldAll);
                bus.removeEventListener("fold-all",   onFoldAll);
            };
        }, () => []);
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

    /**
     * Collapses all category, product, and workcenter rows.
     * Called via overviewBus "fold-all" event or directly.
     */
    foldAll() {
        for (const key of Object.keys(this.state)) {
            this.state[key] = true;
        }
    }

    /**
     * Expands all category, product, and workcenter rows.
     * Called via overviewBus "unfold-all" event or directly.
     */
    expandAll() {
        for (const key of Object.keys(this.state)) {
            this.state[key] = false;
        }
    }

    /**
     * Opens a native Odoo form dialog for the given record.
     *
     * @param {number|false} resId - Record ID
     * @param {string} resModel - Model name
     */
    openFormDialog(resId, resModel) {
        if (!resId) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: resModel,
            res_id: resId,
            views: [[false, "form"]],
            target: "new",
        });
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

    get showCosts() {
        return this.props.showOptions.costs;
    }

    get showCostsUsd() {
        return this.hasSecondary && this.showCosts;
    }

    get showLeadTimes() {
        return this.props.showOptions.leadTimes;
    }

    get showAvailabilities() {
        return this.props.showOptions.availabilities;
    }

    get showOperations() {
        return this.props.showOptions.operations;
    }

    /**
     * Returns the Bootstrap text-color class for a given availability_state.
     *
     * @param {string} state
     * @returns {string}
     */
    availabilityClass(state) {
        switch (state) {
            case "available":   return "text-success";
            case "expected":    return "text-warning";
            case "unavailable": return "text-danger";
            default:            return "";
        }
    }

    get showUom() {
        return this.props.showOptions.uom;
    }

    isCategoryFolded(categId) {
        return this.state[`cat_${categId}`];
    }

    /**
     * Returns the number of direct children (sub-categories + products)
     * nested immediately inside the given category node.
     *
     * @param {Object} node - Category tree node
     * @returns {number}
     */
    categoryCount(node) {
        return node.children.length + node.products.length;
    }

    /**
     * Returns a flat ordered list of rows for the category/product/usage
     * section, computed from the category tree and current fold state.
     *
     * This avoids recursive t-call in the template, which causes OWL's
     * virtual DOM patcher to misplace rows after fold/unfold cycles.
     *
     * Each row has: { type, rowKey, node, depth } and optionally
     * prod and usage fields for the respective row types.
     *
     * @returns {Array}
     */
    get flatCategoryRows() {
        const rows = [];
        const flatten = (nodes) => {
            for (const node of nodes) {
                rows.push({ type: 'category', node, depth: node.depth,
                    rowKey: `cat_${node.id}` });
                if (!this.isCategoryFolded(node.id)) {
                    flatten(node.children);
                    for (const prod of node.products) {
                        rows.push({ type: 'product', node, prod, depth: node.depth + 1,
                            rowKey: `prod_${node.id}_${prod.product_id}` });
                        if (!this.isProductFolded(node.id, prod.product_id)) {
                            for (const usage of prod.usages) {
                                rows.push({ type: 'usage', node, prod, usage,
                                    depth: node.depth + 1,
                                    rowKey: `usage_${node.id}_${prod.product_id}_${usage.parent_product_id}` });
                            }
                        }
                    }
                }
            }
        };
        flatten(this.data.categories);
        return rows;
    }

    isProductFolded(categId, productId) {
        return this.state[`prod_${categId}_${productId}`];
    }

    isWorkcenterFolded(wcId) {
        return this.state[`wc_${wcId}`];
    }

    /**
     * Returns the aggregated lead time for a product. If all usages
     * share the same lead_time value, returns that value; otherwise
     * returns false (mixed lead times cannot be summarised).
     *
     * @param {Object} prod - Product summary object
     * @returns {number|false}
     */
    productLeadTime(prod) {
        const usagesWithLt = prod.usages.filter(
            (u) => u.lead_time !== false && u.lead_time !== undefined
        );
        if (!usagesWithLt.length) {
            return false;
        }
        const first = usagesWithLt[0].lead_time;
        if (usagesWithLt.every((u) => u.lead_time === first)) {
            return first;
        }
        return false;
    }

    /**
     * Returns the route label for a product if all usages share the
     * same route_name.  Returns false when routes differ.
     *
     * @param {Object} prod - Product summary object
     * @returns {{route_name: string, route_detail: string}|false}
     */
    productRoute(prod) {
        const usagesWithRoute = prod.usages.filter((u) => u.route_name);
        if (!usagesWithRoute.length) {
            return false;
        }
        const firstName = usagesWithRoute[0].route_name;
        const allSame = usagesWithRoute.every((u) => u.route_name === firstName);
        if (!allSame) {
            return false;
        }
        return {
            route_name: firstName,
            route_detail: usagesWithRoute[0].route_detail || "",
            route_type: usagesWithRoute[0].route_type || "",
            bom_id: usagesWithRoute[0].bom_id || false,
        };
    }

    /**
     * Navigate to the source of a route (e.g. open the child BoM for
     * "manufacture" routes).  Mirrors native BomOverviewLine.goToRoute.
     *
     * @param {string} routeType - "manufacture" or "buy"
     * @param {number|false} bomId - Child BoM ID for manufacture routes
     */
    goToRoute(routeType, bomId) {
        if (routeType === "manufacture" && bomId) {
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "mrp.bom",
                res_id: bomId,
                views: [[false, "form"]],
                target: "current",
            });
        }
    }

    /**
     * Returns the aggregated quantity for a product, but only when all
     * usages share the same UoM.  Mixed UoMs cannot be summed.
     *
     * @param {Object} prod - Product summary object
     * @returns {{quantity: number, uom_name: string}|false}
     */
    productQuantity(prod) {
        if (!prod.usages.length) {
            return false;
        }
        const firstUom = prod.usages[0].uom_name;
        const allSame = prod.usages.every((u) => u.uom_name === firstUom);
        if (!allSame) {
            return false;
        }
        const total = prod.usages.reduce((s, u) => s + (u.quantity || 0), 0);
        return { quantity: total, uom_name: firstUom };
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

    fmtLeadTime(days) {
        if (days === false || days === undefined) {
            return "";
        }
        return `${days} ${_t("Days")}`;
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
