/** @odoo-module */
import { Component, useState, onMounted, onWillUnmount, onWillUpdateProps } from "@odoo/owl";
const { useRef, useExternalListener } = owl;

const toIds = (arr, key = "id") =>
    (arr || [])
        .map((x) => (x && typeof x === "object" ? x[key] : x))
        .filter((v) => v !== null && v !== undefined);

export class MultiSelect extends Component {
    static template = "x_multi.MultiSelect";
    static props = {
        options: { type: Array, optional: true },
        value: { type: Array, optional: true },
        onChange: { type: Function, optional: true },
        placeholder: { type: String, optional: true },
        valueKey: { type: String, optional: true },
        labelKey: { type: String, optional: true },
        closeOnSelect: { type: Boolean, optional: true },
        maxChips: { type: Number, optional: true },
    };

    setup() {
        this.vKey = this.props.valueKey || "id";
        this.lKey = this.props.labelKey || "name";
        this.root = useRef("root");   // <div class="o-ms" t-ref="root">
        this.panel = useRef("panel"); // <div class="o-ms-panel" t-ref="panel"

        this.state = useState({
            open: false,
            query: "",
            loading: false,
            selected: new Set(toIds(this.props.value, this.vKey)),
            options: Array.isArray(this.props.options) ? this.props.options : [],
        });

        onWillUpdateProps((next) => {
            this.vKey = next.valueKey || "id";
            this.lKey = next.labelKey || "name";

            const nextSet = new Set(toIds(next.value, this.vKey));

            if (
                nextSet.size !== this.state.selected.size ||
                [...nextSet].some((id) => !this.state.selected.has(id))
            ) {
                this.state.selected = nextSet;
            }

            if (Array.isArray(next.options)) {
                this.state.options = next.options;
            }
        });

        this._outside = (ev) => {
            const root = this.el;
            if (root && !root.contains(ev.target)) {
                this.closePanel();
            }
        };

        this._onFocusOut = () => {
            setTimeout(() => {
                const root = this.el;
                const active = document.activeElement;
                if (root && active && !root.contains(active)) {
                    this.closePanel();
                }
            }, 0);
        };

        const isInside = (el, t) => !!el && (el === t || el.contains(t));
        const handleOutside = (ev) => {
            const r = this.root.el;
            const p = this.panel.el; // may be null when closed
            const t = ev.target;
            if (!r) return;
            if (isInside(r, t) || isInside(p, t)) return; // click happened inside → ignore
            this.closePanel();
         };

        onMounted(() => {
            document.addEventListener("pointerdown", this._outside, true);
            this.el?.addEventListener("focusout", this._onFocusOut, true);
        });

        onWillUnmount(() => {
            document.removeEventListener("pointerdown", this._outside, true);
            this.el?.removeEventListener("focusout", this._onFocusOut, true);
        });
        // Close on any mouse/touch press (left, middle, right)
        useExternalListener(window, "pointerdown", handleOutside, { capture: true });
        // Extra: right-click context menu on some browsers
        useExternalListener(window, "contextmenu", handleOutside, { capture: true });
        // Optional: also close when focus moves away via keyboard (Tab)
        useExternalListener(window, "focusin", handleOutside, { capture: true });

    }
    // --- getters ---
    get selectedChips() {
        const labelById = new Map((this.state.options || []).map((o) => [o[this.vKey], o[this.lKey]]));
        return [...this.state.selected]
            .map((id) => ({ id, label: labelById.get(id) ?? String(id) }))
            .filter((x) => x.label);
    }
    get filteredOptions() {
        const q = (this.state.query || "").toLowerCase();
        const opts = this.state.options || [];
        return q ? opts.filter((o) => String(o[this.lKey] || "").toLowerCase().includes(q)) : opts;
    }
    // --- helpers ---
    _emit() {
        this.props.onChange?.([...this.state.selected]);
    }

    get selectedChips() {
      const labelById = new Map((this.state.options || []).map(o => [o[this.vKey], o[this.lKey]]));
      return [...this.state.selected]
        .filter(id => id !== 0) // never show "All…" chip
        .map(id => ({ id, label: labelById.get(id) ?? String(id) }))
        .filter(x => x.label);
    }

    // --- UI actions ---
    onInput = () => {}; // bound via t-model; no body needed
    focusInput = () => this.refs?.input?.focus();
    openPanel  = () => { this.state.open = true; };
    closePanel = () => {
        if (this.state.open) {
            this.state.open = false;
            this.state.query = "";
        }
    };

    add = (id) => {
        this.state.selected.add(id);
        this._emit();
        if (this.props.closeOnSelect !== false) {
            this.closePanel();
        } else {
            this.state.query = "";
            this.focusInput();
        }
    };

    remove = (id) => {
        this.state.selected.delete(id);
        this._emit();
        if (this.props.closeOnSelect !== false) {
            this.closePanel();
        } else {
            this.focusInput();
        }
    };

    clearAll = () => {
        this.state.selected.clear();
        this._emit();
        this.closePanel();
    };

    onFieldClick = (ev) => {
        this.openPanel();
        this.focusInput();
        ev.stopPropagation();
    };


    onKeydown = (ev) => {
      if (ev.key === "Enter") {
        ev.preventDefault();
        const q = (this.state.query || "").toLowerCase();
        const first = (this.state.options || []).find(
          (o) => !this.state.selected.has(o[this.vKey]) &&
                 String(o[this.lKey] || "").toLowerCase().includes(q)
        );
        if (first) this.add(first[this.vKey]);
      }
      if (ev.key === "Backspace" && !this.state.query && this.state.selected.size) {
        ev.preventDefault();
        const last = [...this.state.selected].pop();
        this.remove(last);
      }
      if (ev.key === "Escape") this.closePanel();
    };

    closePanel() {
      this.state.open = false;
    }
}
