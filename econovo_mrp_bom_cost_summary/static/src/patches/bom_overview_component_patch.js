/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { BomOverviewComponent } from
    "@mrp/components/bom_overview/mrp_bom_overview";

patch(BomOverviewComponent.prototype, {
    setup() {
        super.setup(...arguments);
        Object.assign(this.state, {
            costSummary: false,
            secondaryCurrency: false,
        });
    },

    async getBomData() {
        const bomData = await super.getBomData(...arguments);
        this.state.secondaryCurrency = bomData.secondary_currency || false;
        this.state.costSummary = this._computeCostSummary(
            this.state.bomData,
            this.state.secondaryCurrency
        );
        return bomData;
    },

    /**
     * Traverses the recursive bomData tree and aggregates:
     * - Component costs by category -> product -> parent usages (3-level)
     * - Operation costs by work center with inline parent reference
     *
     * @param {Object} data - The recursive BOM data tree (state.bomData)
     * @param {Object|false} secondaryCurrency - USD currency info or false
     * @returns {Object|false} Cost summary object or false if empty
     */
    _computeCostSummary(data, secondaryCurrency) {
        const categoryMap = {};
        const workcenterMap = {};
        this._collectCosts(data, categoryMap, workcenterMap);

        const rate = secondaryCurrency ? secondaryCurrency.rate : 0;

        // Convert categoryMap products from nested maps to sorted arrays
        const categories = Object.values(categoryMap)
            .map((cat) => {
                const products = Object.values(cat.products)
                    .sort((a, b) => b.total - a.total);
                return { ...cat, products };
            })
            .sort((a, b) => b.total - a.total);
        const workcenters = Object.values(workcenterMap).sort(
            (a, b) => b.total - a.total
        );

        if (categories.length === 0 && workcenters.length === 0) {
            return false;
        }

        const totalComponents = categories.reduce((s, c) => s + c.total, 0);
        const totalProdCost = categories.reduce(
            (s, c) => s + c.prod_cost_total, 0
        );
        const totalOperations = workcenters.reduce((s, w) => s + w.total, 0);
        const totalDuration = workcenters.reduce(
            (s, w) => s + w.total_duration, 0
        );
        const totalBom = totalComponents + totalOperations;
        const totalProd = totalProdCost + totalOperations;

        // Compute percentages and USD for categories -> products -> usages
        for (const cat of categories) {
            cat.percentage = totalComponents
                ? (cat.total / totalComponents) * 100
                : 0;
            cat.total_usd = rate ? cat.total * rate : false;
            cat.prod_cost_total_usd = rate
                ? cat.prod_cost_total * rate
                : false;
            for (const prod of cat.products) {
                prod.percentage = totalComponents
                    ? (prod.total / totalComponents) * 100
                    : 0;
                prod.total_usd = rate ? prod.total * rate : false;
                prod.prod_cost_total_usd = rate
                    ? prod.prod_cost_total * rate
                    : false;
                for (const usage of prod.usages) {
                    usage.percentage = totalComponents
                        ? (usage.total / totalComponents) * 100
                        : 0;
                    usage.total_usd = rate ? usage.total * rate : false;
                    usage.prod_cost_usd = rate
                        ? usage.prod_cost * rate
                        : false;
                }
            }
        }
        // Compute percentages and USD for workcenters -> items
        for (const wc of workcenters) {
            wc.percentage = totalOperations
                ? (wc.total / totalOperations) * 100
                : 0;
            wc.total_usd = rate ? wc.total * rate : false;
            for (const item of wc.items) {
                item.percentage = totalOperations
                    ? (item.total / totalOperations) * 100
                    : 0;
                item.total_usd = rate ? item.total * rate : false;
            }
        }

        return {
            categories,
            workcenters,
            totals: {
                components: totalComponents,
                components_usd: rate ? totalComponents * rate : false,
                prod_cost: totalProdCost,
                prod_cost_usd: rate ? totalProdCost * rate : false,
                operations: totalOperations,
                operations_usd: rate ? totalOperations * rate : false,
                operations_duration: totalDuration,
                total: totalBom,
                total_usd: rate ? totalBom * rate : false,
                total_prod: totalProd,
                total_prod_usd: rate ? totalProd * rate : false,
            },
            currency_id: data.currency_id,
        };
    },

    /**
     * Recursively walks the BOM tree collecting leaf component and
     * operation costs, tracking parent product for traceability.
     *
     * @param {Object} node - Current BOM tree node
     * @param {Object} categoryMap - Accumulator for category groupings
     * @param {Object} workcenterMap - Accumulator for workcenter groupings
     * @param {number} [ancestorCostShare=1.0] - Accumulated cost_share
     *   factor from ancestor BOM nodes (for byproduct cost adjustments)
     */
    _collectCosts(node, categoryMap, workcenterMap, ancestorCostShare = 1.0) {
        // The current node IS the product being manufactured.
        // Its components and operations belong to this parent.
        const parentName = node.name;
        const parentProductId = node.product_id;

        // Capture the current node's own route info so Level 3 rows
        // can display how the parent itself is sourced.
        const parentRouteInfo = {
            route_name: node.route_name || "",
            route_detail: node.route_detail || "",
            route_type: node.route_type || "",
            bom_id: node.bom_id || false,
        };

        // When a BOM has byproducts, Odoo multiplies the node total by
        // cost_share (< 1.0).  We must apply the same factor to every
        // leaf cost we collect so the summary matches the BOM total.
        const nodeCostShare =
            node.cost_share !== undefined && node.cost_share !== null
                ? node.cost_share
                : 1.0;
        const effectiveCostShare = ancestorCostShare * nodeCostShare;

        // Collect operations at this BOM level (with parent context inline)
        if (node.operations) {
            for (const op of node.operations) {
                const wcId = op.workcenter_id || 0;
                const wcName = op.workcenter_name || _t("Unknown");
                if (!workcenterMap[wcId]) {
                    workcenterMap[wcId] = {
                        id: wcId,
                        name: wcName,
                        total: 0,
                        total_duration: 0,
                        items: [],
                    };
                }
                const adjustedCost = (op.bom_cost || 0) * effectiveCostShare;
                const opDuration = op.quantity || 0;
                workcenterMap[wcId].total += adjustedCost;
                workcenterMap[wcId].total_duration += opDuration;
                workcenterMap[wcId].items.push({
                    name: op.operation_name || op.name,
                    link_id: op.link_id || false,
                    duration: opDuration,
                    total: adjustedCost,
                    parent_name: parentName,
                    parent_product_id: parentProductId,
                });
            }
        }

        // Process components
        if (node.components) {
            for (const comp of node.components) {
                if (comp.type === "bom" && comp.components) {
                    // Sub-BOM: recurse — the child's own cost_share will
                    // be applied on the next level of recursion.
                    this._collectCosts(
                        comp, categoryMap, workcenterMap, effectiveCostShare
                    );
                } else {
                    // Leaf component: add to category -> product -> usages
                    const catId = comp.categ_id || 0;
                    const catName = comp.categ_name || _t("Uncategorized");
                    if (!categoryMap[catId]) {
                        categoryMap[catId] = {
                            id: catId,
                            name: catName,
                            total: 0,
                            prod_cost_total: 0,
                            products: {},
                        };
                    }
                    const adjustedCost =
                        (comp.bom_cost || 0) * effectiveCostShare;
                    const adjustedProdCost =
                        (comp.prod_cost || 0) * effectiveCostShare;
                    const cat = categoryMap[catId];
                    cat.total += adjustedCost;
                    cat.prod_cost_total += adjustedProdCost;

                    // Group by product within category
                    const prodId = comp.product_id;
                    if (!cat.products[prodId]) {
                        cat.products[prodId] = {
                            product_id: prodId,
                            name: comp.name,
                            link_id: comp.link_id || prodId,
                            link_model: comp.link_model || "product.product",
                            total: 0,
                            prod_cost_total: 0,
                            usages: [],
                        };
                    }
                    const product = cat.products[prodId];
                    product.total += adjustedCost;
                    product.prod_cost_total += adjustedProdCost;

                    // Aggregate usages by parent product
                    // (same component may appear multiple times in same parent)
                    const existingUsage = product.usages.find(
                        (u) => u.parent_product_id === parentProductId
                    );
                    if (existingUsage) {
                        existingUsage.quantity += comp.quantity || 0;
                        existingUsage.total += adjustedCost;
                        existingUsage.prod_cost += adjustedProdCost;
                    } else {
                        product.usages.push({
                            parent_product_id: parentProductId,
                            parent_name: parentName,
                            quantity: comp.quantity || 0,
                            uom_name: comp.uom_name,
                            total: adjustedCost,
                            prod_cost: adjustedProdCost,
                            lead_time: comp.lead_time || false,
                            route_name: comp.route_name || "",
                            route_detail: comp.route_detail || "",
                            route_type: comp.route_type || "",
                            bom_id: comp.bom_id || false,
                            parent_route_name: parentRouteInfo.route_name,
                            parent_route_detail: parentRouteInfo.route_detail,
                            parent_route_type: parentRouteInfo.route_type,
                            parent_bom_id: parentRouteInfo.bom_id,
                        });
                    }
                }
            }
        }
    },
});
