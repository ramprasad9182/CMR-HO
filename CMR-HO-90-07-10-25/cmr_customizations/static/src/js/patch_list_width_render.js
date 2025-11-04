/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

function measureTextWidth(text, font) {
    if (!measureTextWidth._canvas) {
        measureTextWidth._canvas = document.createElement("canvas");
        measureTextWidth._ctx = measureTextWidth._canvas.getContext("2d");
    }
    const ctx = measureTextWidth._ctx;
    ctx.font = font;
    return ctx.measureText(text || "").width || 0;
}

patch(ListRenderer.prototype, {
    computeColumnWidthsFromContent(allowedWidth) {
        let columnWidths = super.computeColumnWidthsFromContent(allowedWidth);

        const table = this.tableRef?.el;
        if (!table) {
            return columnWidths;
        }

        const headers = [...table.querySelectorAll("thead th")];
        const rows = table.querySelectorAll("tbody tr");

        headers.forEach((th, i) => {
            if (
                th.classList.contains("o_list_button") ||
                th.classList.contains("o_optional_columns_dropdown") ||
                th.classList.contains("o_list_controller")
            ) {
                return;
            }

            const cs = window.getComputedStyle(th);
            const font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;

            const headerText = (th.innerText || "").trim();
            const headerWidth = measureTextWidth(headerText, font);

            let contentWidth = 0;
            rows.forEach((row) => {
                const td = row.querySelector(`td:nth-child(${i + 1})`);
                if (!td) return;

                let txt = (td.innerText || "").trim();
                if (!txt) {
                    const input = td.querySelector("input,textarea,select");
                    if (input) {
                        txt = (input.value || input.textContent || "").trim();
                    }
                }
                const w = measureTextWidth(txt, font);
                if (w > contentWidth) {
                    contentWidth = w;
                }
            });

            let maxWidth = Math.max(headerWidth, contentWidth);

            const PADDING = 10;
            const MIN_COL = 12;
            const px = Math.max(Math.ceil(maxWidth + PADDING), MIN_COL);

            columnWidths[i] = Math.max(px, columnWidths[i] || 0);

            th.style.width = columnWidths[i] + "px";
            th.style.minWidth = columnWidths[i] + "px";
        });

        return columnWidths;
    },
});
