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
        const initByproductCategoryFold = (nodes) => {
            for (const node of nodes) {
                foldState[`bpcat_${node.id}`] = true;
                for (const prod of node.products) {
                    foldState[`bpprod_${node.id}_${prod.product_id}`] = true;
                }
                initByproductCategoryFold(node.children);
            }
        };
        initByproductCategoryFold(this.props.data.byproductCategories || []);
        for (const wc of this.props.data.workcenters) {
            foldState[`wc_${wc.id}`] = true;
            for (let i = 0; i < wc.items.length; i++) {
                foldState[`op_${wc.id}_${i}`] = true;
            }
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
                const collectByproductKeys = (nodes) => {
                    for (const node of nodes) {
                        newKeys.add(`bpcat_${node.id}`);
                        for (const prod of node.products) {
                            newKeys.add(`bpprod_${node.id}_${prod.product_id}`);
                        }
                        collectByproductKeys(node.children);
                    }
                };
                collectByproductKeys(nextProps.data.byproductCategories || []);
                for (const wc of nextProps.data.workcenters) {
                    newKeys.add(`wc_${wc.id}`);
                    for (let i = 0; i < wc.items.length; i++) {
                        newKeys.add(`op_${wc.id}_${i}`);
                    }
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

    toggleByproductCategory(categId) {
        const key = `bpcat_${categId}`;
        this.state[key] = !this.state[key];
    }

    toggleByproductProduct(categId, productId) {
        const key = `bpprod_${categId}_${productId}`;
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

    get showPerformance() {
        return this.props.showOptions.performance;
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

    /**
     * Returns a flat ordered list of rows for the byproduct category/product/
     * usage section, mirroring flatCategoryRows but for byproductCategories.
     *
     * @returns {Array}
     */
    get flatByproductCategoryRows() {
        const rows = [];
        const flatten = (nodes) => {
            for (const node of nodes) {
                rows.push({ type: 'category', node, depth: node.depth,
                    rowKey: `bpcat_${node.id}` });
                if (!this.isByproductCategoryFolded(node.id)) {
                    flatten(node.children);
                    for (const prod of node.products) {
                        rows.push({ type: 'product', node, prod, depth: node.depth + 1,
                            rowKey: `bpprod_${node.id}_${prod.product_id}` });
                        if (!this.isByproductProductFolded(node.id, prod.product_id)) {
                            for (const usage of prod.usages) {
                                rows.push({ type: 'usage', node, prod, usage,
                                    depth: node.depth + 1,
                                    rowKey: `bpusage_${node.id}_${prod.product_id}_${usage.parent_product_id}` });
                            }
                        }
                    }
                }
            }
        };
        flatten(this.data.byproductCategories || []);
        return rows;
    }

    isProductFolded(categId, productId) {
        return this.state[`prod_${categId}_${productId}`];
    }

    isWorkcenterFolded(wcId) {
        return this.state[`wc_${wcId}`];
    }

    toggleOperation(wcId, opIdx) {
        const key = `op_${wcId}_${opIdx}`;
        this.state[key] = !this.state[key];
    }

    isOperationFolded(wcId, opIdx) {
        const key = `op_${wcId}_${opIdx}`;
        return key in this.state ? this.state[key] : true;
    }

    isByproductCategoryFolded(categId) {
        return this.state[`bpcat_${categId}`];
    }

    isByproductProductFolded(categId, productId) {
        return this.state[`bpprod_${categId}_${productId}`];
    }

    /**
     * Returns the number of direct children nested inside a byproduct
     * category node (sub-categories + products).
     *
     * @param {Object} node - Byproduct category tree node
     * @returns {number}
     */
    byproductCategoryCount(node) {
        return node.children.length + node.products.length;
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

    fmtMinPerUd(duration, qty) {
        if (!duration || !qty) return "—";
        return formatFloat(duration / qty, { digits: [false, 2] });
    }

    fmtUdPerHr(duration, qty) {
        if (!duration || !qty) return "—";
        return formatFloat((qty * 60) / duration, { digits: [false, 2] });
    }

    /**
     * Returns a JSON string for data-tooltip-info for a named column.
     * All user-facing strings pass through _t() so they are translated.
     *
     * @param {string} key - Logical key for the column/cell
     * @param {string} [curName] - Local currency name (when needed)
     * @param {string} [usdName] - Secondary currency name (when needed)
     * @returns {string} JSON string
     */
    colTooltip(key, curName, usdName) {
        const T = _t;
        const tips = {
            "qty": {
                title: T("Quantity / UoM"),
                lines: [
                    T("Usage: qty consumed per unit of the finished product"),
                    T("Product: sum across all usages (\u2014 when UoMs differ)"),
                ],
            },
            "pct_components": {
                title: T("% of Components total"),
                lines: [
                    T("= row BOM Cost \u00f7 Subtotal Components \u00d7 100"),
                    T("Applies to Categories, Products and Usages"),
                    T("Subtotal: Subtotal Components \u00f7 Grand Total \u00d7 100"),
                ],
            },
            "pct_operations": {
                title: T("% of Operations total"),
                lines: [
                    T("= row BOM Cost \u00f7 Subtotal Operations \u00d7 100"),
                    T("Applies to Work Centers and Operations"),
                    T("Subtotal: Subtotal Operations \u00f7 Grand Total \u00d7 100"),
                ],
            },
            "free_on_hand": {
                title: T("Stock availability"),
                lines: [
                    T("Free to Use = On Hand \u2212 Reserved (virtual_available)"),
                    T("On Hand = total physical quantity in storage"),
                    T("Source: stock.quant"),
                ],
            },
            "availability": {
                title: T("Availability status vs. required qty"),
                lines: [
                    T("Available: Free to Use \u2265 required quantity"),
                    T("Partial: some stock, but insufficient"),
                    T("Not Available: no usable stock"),
                ],
            },
            "lead_time": {
                title: T("Lead time (days)"),
                lines: [
                    T("Supplier or manufacturing lead time in calendar days"),
                    T("Derived from the replenishment route of each component"),
                ],
            },
            "lead_time_ops": {
                title: T("Manufacturing lead time (days)"),
                lines: [
                    T("Lead time linked to this work center or routing step"),
                ],
            },
            "route": {
                title: T("Replenishment route"),
                lines: [
                    T("e.g. Buy, Manufacture, MTO, Resupply"),
                    T("May include vendor name or sub-route detail"),
                ],
            },
            "route_ops": {
                title: T("Manufacturing route"),
                lines: [
                    T("Replenishment or manufacturing route for this operation"),
                ],
            },
            "bom_cost": {
                title: T("BOM Cost contribution"),
                lines: [
                    T("Usage: qty \u00d7 unit cost \u00d7 production factor"),
                    T("Product: \u03a3 BOM Costs of all usages"),
                    T("Category: \u03a3 BOM Costs of products + child categories"),
                    T("Includes nested sub-assembly costs recursively"),
                ],
            },
            "bom_cost_ops": {
                title: T("BOM Cost contribution (Operations)"),
                lines: [
                    T("Operation: (duration \u00f7 60) \u00d7 work center cost/hour"),
                    T("Work Center: \u03a3 BOM Costs of all its operations"),
                ],
            },
            "bom_cost_usd": {
                title: T("BOM Cost (secondary currency)"),
                lines: [
                    T("BOM Cost converted using the company exchange rate"),
                    T("= BOM Cost (local) \u00d7 rate(local \u2192 secondary)"),
                ],
            },
            "prod_cost": {
                title: T("Product catalogue cost"),
                lines: [
                    T("Usage: qty \u00d7 product.standard_price"),
                    T("Product: \u03a3 Product Costs of all usages"),
                    T("Category: \u03a3 down the category tree"),
                    T("Does NOT include operations or overhead"),
                ],
            },
            "prod_cost_usd": {
                title: T("Product Cost (secondary currency)"),
                lines: [
                    T("Product Cost converted using the company exchange rate"),
                    T("= Product Cost (local) \u00d7 rate(local \u2192 secondary)"),
                ],
            },
            "subtotal_bom_cost": {
                title: T("TOTAL BOM COST \u2014 Components"),
                lines: [
                    T("= \u03a3 (qty \u00d7 unit_cost \u00d7 production_factor)"),
                    T("for all components at the requested quantity"),
                    T("Includes nested sub-assembly costs recursively"),
                ],
            },
            "subtotal_prod_cost": {
                title: T("TOTAL PRODUCT COST \u2014 Components"),
                lines: [
                    T("= \u03a3 (qty \u00d7 component.standard_price) per DIRECT component"),
                    T("For sub-assemblies: uses the sub-product\u2019s standard_price,"),
                    T("not the sum of its internal leaf material costs"),
                    T("Same semantics as native Odoo BOM Overview Product Cost column"),
                ],
            },
            "subtotal_ops_cost": {
                title: T("TOTAL BOM COST \u2014 Operations"),
                lines: [
                    T("= \u03a3 ((duration \u00f7 60) \u00d7 wc_cost_per_hour)"),
                    T("Duration in minutes; rate from work center settings"),
                ],
            },
            "pct_byproducts": {
                title: T("% LdM / % Val. (subproductos)"),
                lines: [
                    T("% LdM: BOM Cost de fila \u00f7 Subtotal BOM Cost de subproductos \u00d7 100"),
                    T("  0% cuando cost_share = 0% en la l\u00ednea de subproducto de la LdM"),
                    T("% Val.: Costo Producto de fila \u00f7 Subtotal Costo Producto de subproductos \u00d7 100"),
                    T("  Distribuci\u00f3n del valor recuperable de cat\u00e1logo; siempre significativo"),
                ],
            },
            "bom_cost_byproducts": {
                title: T("Byproduct BOM Cost (cost_share allocation)"),
                lines: [
                    T("= BOM Total \u00d7 byproduct cost_share%"),
                    T("This amount is subtracted from the Grand Total BOM Cost"),
                    T("Zero when cost_share = 0% on the BOM byproduct line"),
                ],
            },
            "prod_cost_byproducts": {
                title: T("Byproduct recoverable value"),
                lines: [
                    T("= qty \u00d7 product.standard_price of the byproduct"),
                    T("The catalogue value recovered by selling or reusing it"),
                    T("Independent of cost_share \u2014 always reflects market value"),
                ],
            },
            "subtotal_byproducts_cost": {
                title: T("TOTAL Byproducts BOM Cost (cost_share allocation)"),
                lines: [
                    T("= \u03a3 (BOM Total \u00d7 byproduct cost_share%) across all BOM levels"),
                    T("Subtracted from Grand Total BOM Cost"),
                    T("Zero when all byproducts have cost_share = 0%"),
                ],
            },
            "subtotal_byproducts_prod_cost": {
                title: T("Recoverable value of byproducts"),
                lines: [
                    T("BOM Cost: cost_share portion allocated to byproducts"),
                    T("= Gross BOM \u00d7 \u03a3 byproduct cost_share%"),
                    T("Product Cost: \u03a3 (qty \u00d7 standard_price) of byproducts"),
                    T("Deducted from gross totals to obtain net cost"),
                ],
            },
            "subtotal_byproducts_prod_cost_note": {
                title: T("Byproduct market value (independent of cost_share)"),
                lines: [
                    T("= \u03a3 (qty \u00d7 standard_price) of each byproduct"),
                    T("This value is always shown regardless of the cost_share% setting"),
                    T("If cost_share = 0%: the BoM Cost column reads \u24280 but this column"),
                    T("still shows the full catalogue value \u2014 byproducts are not"),
                    T("reducing manufacturing cost but may still be sold/reused"),
                ],
            },
            "net_prod": {
                title: T("Net cost after byproduct recovery"),
                lines: [
                    T("BOM Cost: Gross BOM \u2212 allocated byproduct bom_cost"),
                    T("= mirrors native Odoo BOM Overview \u2018BoM Cost\u2019"),
                    T("Product Cost: Gross Product Cost \u2212 byproduct standard prices"),
                    T("Can be negative when byproducts are worth more than inputs"),
                ],
            },
            "grand_total": {
                title: T("Gross totals before byproduct recovery"),
                lines: [
                    T("BOM Cost = \u03a3 Components (bom_cost) + \u03a3 Operations"),
                    T("Product Cost = standard_price of the finished product \u00d7 quantity"),
                    T("Identical to native Odoo BOM Overview \u2018Product Cost\u2019 column"),
                    T("Note: does not equal the sum of body section subtotals (those show"),
                    T("bottom-up component costs for per-category analysis)"),
                ],
            },
            "grand_total_prod": {
                title: T("Grand Total Product Cost"),
                lines: [
                    T("= standard_price of the FINISHED product \u00d7 quantity produced"),
                    T("This is the catalogue price stored on the finished product itself,"),
                    T("NOT the sum of the Product Cost column in the components section"),
                    T("(which shows per-component catalogue values for purchase analysis)"),
                    T("To compare: BoM Cost = what it costs to MAKE; Product Cost = what"),
                    T("it costs to BUY the finished product at its standard price"),
                ],
            },
            "duration": {
                title: T("Duration (minutes)"),
                lines: [
                    T("Operation: manufacturing operation duration in minutes"),
                    T("Work Center: sum of all its operation durations"),
                ],
            },
            "min_per_ud": {
                title: T("Time cycle: min/ud"),
                lines: [
                    T("= duration ÷ quantity produced"),
                    T("'—' when duration = 0"),
                ],
            },
            "ud_per_hr": {
                title: T("Production rate: ud/hr"),
                lines: [
                    T("= (qty × 60) ÷ duration"),
                    T("Higher = faster throughput"),
                    T("'—' when duration = 0"),
                ],
            },
            "op_components": {
                title: T("Components consumed in this operation"),
                lines: [
                    T("Set via 'Consumed in Operation' on BOM line"),
                    T("Components without assignment not shown here"),
                ],
            },
            "cant_prod": {
                title: T("Qty. produced"),
                lines: [
                    T("Quantity of finished product linked to this operation"),
                    T("= parent BOM quantity at this level"),
                ],
            },
            "cant_consu": {
                title: T("Qty. consumed"),
                lines: [
                    T("Quantity and unit of measure of the component"),
                    T("consumed in this operation"),
                ],
            },
        };
        const tip = tips[key];
        if (!tip) {
            return "";
        }
        return JSON.stringify(tip);
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
