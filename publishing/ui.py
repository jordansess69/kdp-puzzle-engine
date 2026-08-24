"""Tkinter Publishing Manager UI kept out of the puzzle creator module."""
from __future__ import annotations

import os
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk

from .database import MARKETPLACES
from .marketplaces import PUBLISHERS
from .etsy_bundles import ETSY_STORE_NAME
from .readiness import PREPARED_FOLDER_NAMES, format_history, marketplace_rows, next_actions, online_state_text, whats_left
from integrations.publication import PublicationRecord

DISPLAY = {"amazon": "Amazon", "etsy": "Etsy", "ingram": "Ingram", "website": "Website", "lulu": "Lulu", "bookvault": "BookVault", "barnes_noble": "B&N"}
STATUS_VALUES = ("Not Prepared", "Ready", "Uploaded", "Published", "Error", "Needs Review")
# Buyer-facing platform names for the Hub readiness grid; keys follow the
# canonical database.MARKETPLACES order so all seven rows always render.
DISPLAY_GRID = {
    "amazon": "Amazon KDP",
    "etsy": "Etsy",
    "ingram": "IngramSpark",
    "website": "Website / Direct",
    "lulu": "Lulu",
    "bookvault": "BookVault",
    "barnes_noble": "Barnes & Noble Press",
}
# Validator phrases that are advice about other printers' cover templates,
# never blockers; keeping them separate stops advisories masquerading as failures.
ADVISORY_ISSUE_HINTS = ("reference-only", "template")


def split_issues(issues: list[str]) -> tuple[list[str], list[str]]:
    """Split validator output into hard blockers and advisory template notes."""
    blockers: list[str] = []
    advisories: list[str] = []
    for issue in issues:
        low = issue.casefold()
        (advisories if any(hint in low for hint in ADVISORY_ISSUE_HINTS) else blockers).append(issue)
    return blockers, advisories


def draft_action_enabled(row: dict | None) -> bool:
    """True only when the selected readiness row may offer the Etsy draft action.

    Gating is deliberately strict: Etsy row only, a prepared folder on disk,
    and never when a human already confirmed Uploaded/Published.
    """
    if not row:
        return False
    return (
        row.get("key") == "etsy"
        and bool(row.get("has_local_folder"))
        and row.get("status") not in ("Uploaded", "Published")
    )


def integration_info_for(key: str) -> dict | None:
    """Discovery metadata for one marketplace key (None when unknown).

    Backed by the integration registry so the UI never hardcodes per-platform
    branching: mode (api/export_only/manual), status (active/planned) and
    truthful capabilities all come from one source.
    """
    from integrations.registry import get_integration_info

    return get_integration_info(key)


def export_action_enabled(row: dict | None, info: dict | None) -> bool:
    """Capability-driven gate for 'Generate Export Package'.

    Enabled only for a channel whose registered integration is an ACTIVE
    export-only adapter advertising can_export_package, with a prepared
    folder to export from.  Human-confirmed records stay untouchable.
    """
    if not row or not info:
        return False
    return (
        info.get("mode") == "export_only"
        and info.get("status") == "active"
        and bool(info.get("capabilities", {}).get("can_export_package"))
        and bool(row.get("has_local_folder"))
        and row.get("status") not in ("Uploaded", "Published")
    )


def selected_book_overview(product, book: dict) -> str:
    """The one-line overview from the canonical MasterProduct read model.

    Raw catalog fields are still available to callers; this helper simply
    proves the Hub's displayed identity flows through the universal model.
    """
    meta = book.get("metadata") or {}
    details: list[str] = []
    if product.subtitle:
        details.append(str(product.subtitle))
    if product.series:
        details.append(f"Series: {product.series}")
    theme = str(meta.get("theme") or "").strip()
    if theme:
        details.append(f"Theme: {theme}")
    pages = int(product.page_count or 0)
    details.append(f"{pages} page{'s' if pages != 1 else ''}")
    details.append(f"ISBN: {product.isbn or 'not assigned'}")
    return "  |  ".join(details)


def _format_bytes(size) -> str:
    try:
        size = int(size)
    except (TypeError, ValueError):
        return ""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def artifact_summary_lines(product) -> list[str]:
    """Read-only artifact manifest lines; never computes hashes here."""
    lines: list[str] = []
    for artifact in product.artifacts:
        position = f"#{artifact.position} " if artifact.position else ""
        size = _format_bytes(artifact.file_size) or "size unknown"
        checksum = artifact.checksum or "Not calculated"
        label = f" — {artifact.label}" if artifact.label else ""
        lines.append(
            f"{position}{artifact.purpose.value}: {os.path.basename(artifact.path)}"
            f" [{artifact.media_type or 'unknown type'}, {size}, checksum: {checksum}]{label}"
        )
        lines.append(f"    {artifact.path}")
    return lines


def render_master_product_text(product) -> str:
    """Full read-only inspector text for the canonical product.

    Sections: Identity / Metadata / Commercial / Print / Artifacts /
    Source.  Contains no credentials by construction - MasterProduct cannot
    carry them.
    """
    def line(label: str, value) -> str:
        text = str(value).strip() if value is not None else ""
        return f"{label}: {text if text else '—'}"

    sections = [
        "IDENTITY",
        line("  Internal product ID", product.internal_product_id),
        line("  SKU", product.sku),
        line("  Revision", product.revision),
        "",
        "METADATA",
        line("  Title", product.title),
        line("  Subtitle", product.subtitle),
        line("  Series", product.series),
        line("  Author/Creator", product.author),
        line("  Brand/Imprint", product.brand),
        line("  Language", product.language),
        line("  Product type", product.product_type),
        line("  Target audience", product.target_audience),
        line("  Categories", "; ".join(product.categories)),
        line("  Keywords", "; ".join(product.keywords)),
        line("  Tags", ", ".join(product.tags)),
        "",
        "COMMERCIAL",
        line("  Price", f"{product.price:.2f} {product.currency}" if product.price is not None else ""),
        line("  Publication date", product.publication_date),
        line("  Copyright", product.copyright_notice),
        "",
        "PRINT",
        line("  ISBN", product.isbn),
        line("  Page count", product.page_count or ""),
        line("  Trim size", product.trim_size),
        line("  Bleed", f'{product.bleed_inches}"' if product.bleed_inches is not None else ""),
        "",
        "ARTIFACTS" + ("" if product.artifacts else "  (none found)"),
        *artifact_summary_lines(product),
        "",
        "SOURCE / REVISION",
        line("  Source reference", product.source_reference),
        line("  Generated at", product.generated_at),
        line("  AI disclosure", product.ai_disclosure or "Not set"),
    ]
    return "\n".join(sections)


def marketplace_row_values(record, row_label: str, readiness_label: str) -> tuple:
    """Treeview values derived from the PublicationRecord view.

    Output is byte-identical to the previous raw-row rendering, so adopting
    the domain model changes nothing the user can see.
    """
    return (
        row_label,
        record.listing_status or "Not Prepared",
        readiness_label,
        record.remote_id or "—",
        "Saved link" if record.remote_url else "—",
        record.updated_at[:16].replace("T", " ") or "—",
    )


def apply_export_outcome(db, book_id: str, marketplace: str, result) -> None:
    """Persist ONLY automation-owned state after an export attempt.

    The human-owned status/external_id/url columns and their audit trail are
    never touched: an export package is preparation, not publication.
    """
    if result.success:
        db.set_integration_state(book_id, marketplace, "exported")
    else:
        db.record_integration_event(book_id, marketplace, "export_failed", result.message)


class MasterProductDialog(tk.Toplevel):
    """Read-only canonical product inspector ("View Master Product")."""

    def __init__(self, parent, service, book: dict) -> None:
        super().__init__(parent)
        from integrations.factory import MasterProductFactory

        self.title("Master Product")
        self.geometry("760x620"); self.minsize(600, 420)
        self.configure(background="#1f1f1f"); self.transient(parent)
        root = ttk.Frame(self, padding=18, style="Publish.TFrame"); root.pack(fill="both", expand=True)
        root.rowconfigure(1, weight=1); root.columnconfigure(0, weight=1)
        title = (book.get("metadata") or {}).get("title") or "book"
        ttk.Label(root, text=f'Master Product — {title}', style="Publish.Title.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        box = tk.Text(root, wrap="word", state="disabled", background="#292929",
                      foreground="#d9f5ee", relief="flat", padx=12, pady=10)
        box.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(root, orient="vertical", command=box.yview)
        scroll.grid(row=1, column=1, sticky="ns"); box.configure(yscrollcommand=scroll.set)
        ttk.Button(root, text="Close", command=self.destroy, style="Publish.Action.TButton").grid(row=2, column=0, sticky="e", pady=(10, 0))
        try:
            product = MasterProductFactory.from_book_record(book)
            text = render_master_product_text(product)
        except Exception as exc:
            text = (f"The master product could not be built from this catalog record.\n\n"
                    f"Details: {exc}")
        box.configure(state="normal"); box.delete("1.0", "end"); box.insert("end", text); box.configure(state="disabled")


def publishing_counts_line(rows: list[dict]) -> str:
    """One truthful status line, e.g. '2 of 7 published · 1 uploaded'."""
    counts = whats_left(rows)
    parts = [f"{counts['published']} of {counts['total']} published"]
    if counts["uploaded"]:
        parts.append(f"{counts['uploaded']} uploaded")
    if counts["ready_to_upload"]:
        parts.append(f"{counts['ready_to_upload']} ready to upload")
    if counts["needs_items"]:
        parts.append(f"{counts['needs_items']} need items")
    if counts["needs_attention"]:
        parts.append(f"{counts['needs_attention']} need attention")
    return " · ".join(parts)


def whats_left_text(rows: list[dict]) -> str:
    """Headline counts plus capped plain-English next steps for one book."""
    counts = whats_left(rows)
    lines = [f"{counts['published']} of {counts['total']} marketplaces published."]
    if counts["uploaded"]:
        lines.append(f"{counts['uploaded']} uploaded — confirm each live listing, then mark it Published.")
    if counts["ready_to_upload"]:
        lines.append(f"{counts['ready_to_upload']} prepared package(s) waiting to be uploaded.")
    if counts["needs_items"]:
        lines.append(f"{counts['needs_items']} marketplace(s) still need required items.")
    if counts["needs_attention"]:
        lines.append(f"{counts['needs_attention']} marketplace(s) recorded an error.")
    actions = next_actions(rows)
    if actions:
        lines.append("")
        lines.append("Next steps:")
        lines.extend(f"• {action}" for action in actions)
    return "\n".join(lines)


class PublishingManagerDialog(tk.Toplevel):
    def __init__(self, parent, service, sync_catalog, open_recommendation=None, create_package=None, new_book=None) -> None:
        super().__init__(parent); self.parent, self.service, self.sync_catalog = parent, service, sync_catalog
        self.open_recommendation = open_recommendation
        self.create_package = create_package
        self.new_book = new_book
        self.title("Publishing Manager"); self.geometry("1320x820"); self.minsize(1040, 660)
        self.configure(background="#1f1f1f")
        self.filter_text = tk.StringVar(); self.market_filter = tk.StringVar(value="All marketplaces"); self.status = tk.StringVar(value="Sync your existing books to start the publishing catalog.")
        self.rows: dict[str, dict] = {}; self.recommendations: dict[str, dict] = {}
        self._setup_styles(); self._build(); self.refresh(sync=True)

    def _setup_styles(self) -> None:
        """Give this separate window the same calm, modern dark look as Book Studio."""
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        bg, panel, raised, text, muted, border, primary = "#1f1f1f", "#252525", "#2c2c2c", "#f2f2f2", "#b7b7b7", "#424242", "#10a37f"
        style.configure("Publish.TFrame", background=bg)
        style.configure("Publish.Card.TFrame", background=panel)
        style.configure("Publish.TLabel", background=bg, foreground=text, font=("Segoe UI", 9))
        style.configure("Publish.Title.TLabel", background=bg, foreground=text, font=("Segoe UI", 20, "bold"))
        style.configure("Publish.Subtitle.TLabel", background=bg, foreground=muted, font=("Segoe UI", 10))
        style.configure("Publish.BookTitle.TLabel", background=bg, foreground=text, font=("Segoe UI", 14, "bold"))
        style.configure("Publish.Status.TLabel", background=raised, foreground="#d9f5ee", padding=(12, 9), font=("Segoe UI", 9))
        style.configure("Publish.Card.TLabelframe", background=panel, borderwidth=1, relief="solid", bordercolor=border)
        style.configure("Publish.Card.TLabelframe.Label", background=panel, foreground=text, font=("Segoe UI", 10, "bold"))
        style.configure("Publish.TEntry", fieldbackground="#303030", foreground=text, insertcolor=text, bordercolor=border)
        style.configure("Publish.TCombobox", fieldbackground="#303030", background=panel, foreground=text, arrowcolor=text)
        style.map("Publish.TCombobox", fieldbackground=[("readonly", "#303030")], foreground=[("readonly", text)])
        style.configure("Publish.Treeview", background="#242424", fieldbackground="#242424", foreground=text, rowheight=29, bordercolor=border)
        style.map("Publish.Treeview", background=[("selected", "#0c755c")], foreground=[("selected", "#ffffff")])
        style.configure("Publish.Treeview.Heading", background="#343434", foreground=text, font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("Publish.Treeview.Heading", background=[("active", "#414141")])
        style.configure("Publish.Primary.TButton", background=primary, foreground="#ffffff", padding=(12, 8), font=("Segoe UI", 9, "bold"), borderwidth=0)
        style.map("Publish.Primary.TButton", background=[("active", "#0b896a")])
        style.configure("Publish.Action.TButton", background="#343434", foreground=text, padding=(10, 7), font=("Segoe UI", 9), borderwidth=0)
        style.map("Publish.Action.TButton", background=[("active", "#414141")])
        style.configure("Publish.TNotebook", background=bg, borderwidth=0, tabmargins=(0, 6, 0, 0))
        style.configure("Publish.TNotebook.Tab", background="#303030", foreground=muted, padding=(16, 8), font=("Segoe UI", 9, "bold"))
        style.map("Publish.TNotebook.Tab", background=[("selected", panel)], foreground=[("selected", text)])

    def _build(self) -> None:
        root = ttk.Frame(self, padding=(24, 20), style="Publish.TFrame"); root.pack(fill="both", expand=True); root.columnconfigure(0, weight=1); root.rowconfigure(3, weight=1)
        heading = ttk.Frame(root, style="Publish.TFrame"); heading.grid(row=0, column=0, sticky="ew"); heading.columnconfigure(0, weight=1)
        ttk.Label(heading, text="Publishing Manager", style="Publish.Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(heading, text="Upload status", command=self.open_upload_status, style="Publish.Action.TButton").grid(row=0, column=1, sticky="e", padx=(0, 8))
        ttk.Button(heading, text="Create Etsy bundle", command=self.open_etsy_bundle_builder, style="Publish.Action.TButton").grid(row=0, column=2, sticky="e", padx=(0, 8))
        ttk.Button(heading, text="Marketplace connections", command=self.open_marketplace_connections, style="Publish.Action.TButton").grid(row=0, column=3, sticky="e", padx=(0, 8))
        ttk.Button(heading, text="New book", command=self.start_new_book, style="Publish.Primary.TButton").grid(row=0, column=4, sticky="e")
        ttk.Label(root, text="Your book catalog, next-step recommendations, and safe marketplace preparation in one place. Each completed book includes a Master Release folder with its platform-by-platform handoffs.", style="Publish.Subtitle.TLabel", wraplength=1150).grid(row=1, column=0, sticky="w", pady=(3, 16))
        recommended = ttk.Labelframe(root, text="Recommended next books", padding=12, style="Publish.Card.TLabelframe")
        recommended.grid(row=2, column=0, sticky="ew", pady=(0, 10)); recommended.columnconfigure(0, weight=1)
        ttk.Label(recommended, text="These are the strongest places to start from your own checked library. New books appear before completed packages that are ready to prepare.", style="Publish.TLabel", wraplength=1080).grid(row=0, column=0, sticky="w", pady=(0, 8))
        rec_columns = ("book", "topic", "puzzles", "next", "why")
        self.recommendation_tree = ttk.Treeview(recommended, columns=rec_columns, show="headings", height=4, selectmode="browse", style="Publish.Treeview")
        rec_labels = {"book": "Recommended book", "topic": "Topic", "puzzles": "Puzzles", "next": "Next step", "why": "Why it is a good start"}
        rec_widths = {"book": 290, "topic": 190, "puzzles": 70, "next": 120, "why": 430}
        for key in rec_columns:
            self.recommendation_tree.heading(key, text=rec_labels[key]); self.recommendation_tree.column(key, width=rec_widths[key], anchor="w" if key not in ("puzzles",) else "center")
        self.recommendation_tree.grid(row=1, column=0, sticky="ew")
        self.recommendation_tree.bind("<Double-1>", lambda _event: self.open_recommended_book())
        rec_actions = ttk.Frame(recommended); rec_actions.grid(row=2, column=0, sticky="ew", pady=(7, 0))
        ttk.Button(rec_actions, text="Open selected book", command=self.open_recommended_book, style="Publish.Action.TButton").pack(side="left")
        ttk.Button(rec_actions, text="Create complete package", command=self.create_recommended_package, style="Publish.Primary.TButton").pack(side="left", padx=6)
        ttk.Button(rec_actions, text="Refresh", command=self.refresh, style="Publish.Action.TButton").pack(side="left", padx=6)
        # Structural Hub foundation: existing widgets keep their logic and
        # simply live inside the Catalog tab; the Selected Book tab stays a
        # placeholder until later steps add readiness content.
        self.notebook = ttk.Notebook(root, style="Publish.TNotebook"); self.notebook.grid(row=3, column=0, sticky="nsew")
        catalog_tab = ttk.Frame(self.notebook, style="Publish.TFrame")
        selected_tab = ttk.Frame(self.notebook, style="Publish.TFrame")
        self.notebook.add(catalog_tab, text="Catalog")
        self.notebook.add(selected_tab, text="Selected Book")
        catalog_tab.columnconfigure(0, weight=1); catalog_tab.rowconfigure(1, weight=1)
        selected_tab.columnconfigure(0, weight=1); selected_tab.rowconfigure(0, weight=1)
        self.selected_empty_text = tk.StringVar(value="Select a book from the Catalog tab to view publishing readiness and marketplace actions.")
        self.selected_empty = ttk.Label(selected_tab, textvariable=self.selected_empty_text, style="Publish.Subtitle.TLabel", wraplength=760, justify="center", anchor="center")
        self.selected_empty.grid(row=0, column=0, sticky="nsew")
        self.selected_content = ttk.Frame(selected_tab, style="Publish.TFrame")
        self._build_selected_content()
        filters = ttk.Frame(catalog_tab, style="Publish.TFrame"); filters.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(filters, text="Find a book", style="Publish.TLabel").pack(side="left"); search = ttk.Entry(filters, textvariable=self.filter_text, width=34, style="Publish.TEntry"); search.pack(side="left", padx=(7, 16)); search.bind("<KeyRelease>", lambda _event: self.refresh())
        ttk.Label(filters, text="Marketplace", style="Publish.TLabel").pack(side="left"); combo = ttk.Combobox(filters, textvariable=self.market_filter, values=("All marketplaces", *[DISPLAY[key] for key in MARKETPLACES]), state="readonly", width=16, style="Publish.TCombobox"); combo.pack(side="left", padx=7); combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        ttk.Button(filters, text="Scan prepared folders", command=self.scan_local_status, style="Publish.Action.TButton").pack(side="right")
        ttk.Button(filters, text="Sync catalog", command=lambda: self.refresh(sync=True), style="Publish.Action.TButton").pack(side="right", padx=(0, 6))
        columns = ("book", "series", "theme", "pages", "isbn", *MARKETPLACES, "updated")
        self.tree = ttk.Treeview(catalog_tab, columns=columns, show="headings", selectmode="extended", style="Publish.Treeview")
        labels = {"book": "Book", "series": "Series", "theme": "Theme", "pages": "Pages", "isbn": "ISBN", "updated": "Last Updated", **DISPLAY}
        widths = {"book": 220, "series": 130, "theme": 115, "pages": 55, "isbn": 110, "updated": 125, **{key: 92 for key in MARKETPLACES}}
        for key in columns: self.tree.heading(key, text=labels[key]); self.tree.column(key, width=widths[key], anchor="w" if key in ("book", "series", "theme") else "center")
        self.tree.grid(row=1, column=0, sticky="nsew"); scroll = ttk.Scrollbar(catalog_tab, orient="vertical", command=self.tree.yview); scroll.grid(row=1, column=1, sticky="ns"); self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<Double-1>", lambda _event: self.open_book())
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.refresh_selected_view())
        actions = ttk.Frame(catalog_tab, style="Publish.TFrame"); actions.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(actions, text="Book details", command=self.open_book, style="Publish.Action.TButton").pack(side="left")
        ttk.Button(actions, text="Open Master Release Folder", command=self.open_selected_master, style="Publish.Action.TButton").pack(side="left", padx=6)
        ttk.Button(actions, text="Create complete package", command=self.create_selected_package, style="Publish.Primary.TButton").pack(side="left", padx=6)
        ttk.Button(actions, text="Why not KDP ready?", command=self.show_kdp_readiness, style="Publish.Action.TButton").pack(side="left", padx=6)
        ttk.Button(actions, text="Prepare KDP", command=lambda: self.prepare(["amazon"]), style="Publish.Primary.TButton").pack(side="left")
        ttk.Button(actions, text="Prepare Etsy", command=lambda: self.prepare(["etsy"]), style="Publish.Action.TButton").pack(side="left", padx=6)
        ttk.Button(actions, text="Prepare Ingram", command=lambda: self.prepare(["ingram"]), style="Publish.Action.TButton").pack(side="left")
        ttk.Button(actions, text="Prepare website", command=lambda: self.prepare(["website"]), style="Publish.Action.TButton").pack(side="left", padx=6)
        ttk.Button(actions, text="Prepare all", command=lambda: self.prepare(list(MARKETPLACES)), style="Publish.Action.TButton").pack(side="left")
        ttk.Button(actions, text="ISBN manager", command=lambda: ISBNManagerDialog(self, self.service), style="Publish.Action.TButton").pack(side="right")
        ttk.Label(root, textvariable=self.status, wraplength=1150, style="Publish.Status.TLabel").grid(row=4, column=0, sticky="ew", pady=(10, 0))

    def _build_selected_content(self) -> None:
        """Real Selected Book pane: overview, What's left, readiness grid, actions."""
        self.selected_book = None; self.selected_market_key = ""; self.marketplace_row_map: dict[str, dict] = {}
        # Set while the readiness grid rebuilds: ttk delivers <<TreeviewSelect>>
        # asynchronously for programmatic delete/clear, and those echoes must
        # not be mistaken for the user clicking an empty area.
        self._market_rebuilding = False
        root = self.selected_content
        root.columnconfigure(0, weight=1); root.rowconfigure(2, weight=1)
        overview = ttk.Labelframe(root, text="Book overview", padding=12, style="Publish.Card.TLabelframe"); overview.grid(row=0, column=0, sticky="ew"); overview.columnconfigure(0, weight=1)
        self.sel_title = tk.StringVar(value=""); self.sel_detail = tk.StringVar(value=""); self.sel_path = tk.StringVar(value=""); self.sel_counts = tk.StringVar(value="")
        ttk.Label(overview, textvariable=self.sel_title, style="Publish.BookTitle.TLabel").grid(row=0, column=0, sticky="w")
        # Read-only canonical product inspector (Universal Publishing adoption).
        ttk.Button(overview, text="View Master Product", command=self._open_master_product, style="Publish.Action.TButton").grid(row=0, column=1, sticky="e")
        ttk.Label(overview, textvariable=self.sel_detail, style="Publish.TLabel", wraplength=1080).grid(row=1, column=0, sticky="w", pady=(3, 0))
        ttk.Label(overview, textvariable=self.sel_path, style="Publish.Subtitle.TLabel", wraplength=1080, justify="left").grid(row=2, column=0, sticky="w", pady=(3, 0))
        ttk.Label(overview, textvariable=self.sel_counts, style="Publish.Status.TLabel", wraplength=1080).grid(row=3, column=0, sticky="ew", pady=(8, 0))
        left = ttk.Labelframe(root, text="What's left?", padding=12, style="Publish.Card.TLabelframe"); left.grid(row=1, column=0, sticky="ew", pady=(10, 0)); left.columnconfigure(0, weight=1)
        self.whats_left_box = tk.Text(left, height=8, wrap="word", state="disabled", background="#292929", foreground="#d9f5ee", relief="flat", padx=10, pady=8)
        self.whats_left_box.grid(row=0, column=0, sticky="ew")
        grid_frame = ttk.Labelframe(root, text="Marketplace readiness (select a row for actions)", padding=12, style="Publish.Card.TLabelframe"); grid_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        grid_frame.columnconfigure(0, weight=1); grid_frame.rowconfigure(0, weight=1)
        columns = ("platform", "status", "readiness", "listing", "link", "updated")
        self.market_tree = ttk.Treeview(grid_frame, columns=columns, show="headings", height=7, selectmode="browse", style="Publish.Treeview")
        heads = {"platform": "Platform", "status": "Status", "readiness": "Readiness", "listing": "Listing ID", "link": "Live link", "updated": "Updated"}
        widths = {"platform": 190, "status": 110, "readiness": 300, "listing": 130, "link": 100, "updated": 140}
        for key in columns:
            anchor = "w" if key in ("platform", "readiness") else "center"
            self.market_tree.heading(key, text=heads[key]); self.market_tree.column(key, width=widths[key], anchor=anchor)
        self.market_tree.tag_configure("attention", foreground="#ffb46b")
        self.market_tree.tag_configure("ok", foreground="#9fe8c6")
        self.market_tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(grid_frame, orient="vertical", command=self.market_tree.yview); scroll.grid(row=0, column=1, sticky="ns"); self.market_tree.configure(yscrollcommand=scroll.set)
        self.market_tree.bind("<<TreeviewSelect>>", lambda _event: self._on_marketplace_row_selected())
        self.sel_error_detail = tk.StringVar(value="")
        ttk.Label(grid_frame, textvariable=self.sel_error_detail, style="Publish.Subtitle.TLabel", wraplength=1080, justify="left").grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        # Truthful online-integration line (e.g. "a draft listing was created on
        # Etsy — it is NOT published").  Empty until an automated flow runs.
        self.sel_online_detail = tk.StringVar(value="")
        ttk.Label(grid_frame, textvariable=self.sel_online_detail, style="Publish.Subtitle.TLabel", wraplength=1080, justify="left").grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        bar = ttk.Frame(root, style="Publish.TFrame"); bar.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        specs = (
            ("prepare", "Prepare", self._prepare_selected_marketplace, "Publish.Primary.TButton"),
            ("validate", "Validate", self._validate_selected_marketplace, "Publish.Action.TButton"),
            ("folder", "Open prepared folder", self._open_prepared_folder, "Publish.Action.TButton"),
            ("site", "Open publisher site", self._open_publisher_site, "Publish.Action.TButton"),
            ("listing", "Open saved live listing", self._open_saved_listing, "Publish.Action.TButton"),
            ("record", "Record listing / update status", self._open_record_listing, "Publish.Primary.TButton"),
            ("draft", "Create Etsy draft", self._create_etsy_draft, "Publish.Action.TButton"),
            ("export", "Generate Export Package", self._generate_export_package, "Publish.Action.TButton"),
            ("history", "View history", self._open_marketplace_history, "Publish.Action.TButton"),
        )
        self.market_buttons: dict[str, ttk.Button] = {}
        for name, label, command, style_name in specs:
            button = ttk.Button(bar, text=label, command=command, style=style_name, state="disabled")
            button.pack(side="left", padx=(0, 6))
            self.market_buttons[name] = button
        ttk.Label(bar, text="Actions never publish anything automatically.", style="Publish.Subtitle.TLabel").pack(side="right")

    def refresh_selected_view(self) -> None:
        """Mirror the catalog selection into the Selected Book tab (no tab switching)."""
        books = self._selected()
        if len(books) != 1:
            self.selected_content.grid_remove(); self.selected_empty.grid()
            if len(books) > 1:
                self.selected_empty_text.set("Multiple books are selected. Catalog batch actions still apply; select exactly one book to see its detailed publishing readiness and marketplace actions.")
            else:
                self.selected_empty_text.set("Select a book from the Catalog tab to view publishing readiness and marketplace actions.")
            self.selected_book, self.selected_market_key, self.marketplace_row_map = None, "", {}
            self.master_product = None
            self.publication_records = {}
            return
        book = books[0]; self.selected_book = book
        self.selected_content.grid(); self.selected_empty.grid_remove()
        meta = book["metadata"]
        # Canonical read model for this selection (Universal Publishing adoption):
        # display identity flows through MasterProduct; raw records stay available
        # to the service calls below.
        from integrations.factory import MasterProductFactory

        try:
            product = MasterProductFactory.from_book_record(book)
            self.master_product = product
        except Exception:
            self.master_product = None
        self.sel_title.set(meta.get("title") or "Untitled book")
        self.sel_detail.set(selected_book_overview(self.master_product, book) if self.master_product else "")
        package = str(book.get("package_path") or "")
        self.sel_path.set(f"Master package: {package}" if package else "Source theme only — create the complete package to unlock marketplace preparation.")
        records = self.service.db.marketplace_records(book["book_id"])
        rows = marketplace_rows(book, records)
        self.marketplace_row_map = {row["key"]: row for row in rows}
        # Domain views over the authoritative rows (no second persistence layer):
        self.publication_records = {
            key: PublicationRecord.from_marketplace_record(
                book["book_id"], key, {**record, "marketplace": key, "book_id": book["book_id"]},
                {"integration_state": record.get("integration_state", ""),
                 "idempotency_key": record.get("idempotency_key", ""),
                 "external_sku": record.get("external_sku", ""),
                 "last_synced_at": record.get("last_synced_at", "")})
            for key, record in records.items()
        }
        self.sel_counts.set(publishing_counts_line(rows))
        self.whats_left_box.configure(state="normal"); self.whats_left_box.delete("1.0", "end"); self.whats_left_box.insert("end", whats_left_text(rows)); self.whats_left_box.configure(state="disabled")
        self.market_tree.selection_remove(*self.market_tree.selection())
        self.market_tree.delete(*self.market_tree.get_children())
        self._market_rebuilding = True
        try:
            for row in rows:
                attention = row["status"] in ("Error", "Needs Review") or bool(row["error_message"])
                tag = "attention" if attention else ("ok" if row["indicator"] == "ok" else "")
                values = marketplace_row_values(
                    self.publication_records.get(row["key"]),
                    DISPLAY_GRID.get(row["key"], row["label"]), row["readiness_label"])
                self.market_tree.insert("", "end", iid=row["key"], tags=(tag,) if tag else (), values=values)
            # Keep the user's marketplace row across refreshes (after Prepare,
            # saving a listing, etc.) so async selection echoes land somewhere
            # stable instead of wiping the action bar state.
            previous_key = self.selected_market_key
            if previous_key in self.marketplace_row_map:
                self.market_tree.selection_set(previous_key)
            else:
                previous_key = ""
            self.selected_market_key = previous_key
        finally:
            self._market_rebuilding = False
        self._set_market_error_detail(); self._update_market_actions()

    def _on_marketplace_row_selected(self) -> None:
        if self._market_rebuilding:
            return
        selection = self.market_tree.selection()
        self.selected_market_key = selection[0] if selection else ""
        self._set_market_error_detail()
        self._update_market_actions()

    def _set_market_error_detail(self) -> None:
        """One shared truth for the attention and online lines under the grid."""
        row = self.marketplace_row_map.get(self.selected_market_key)
        if not row:
            self.sel_error_detail.set("")
        elif row["error_message"]:
            self.sel_error_detail.set(f"Attention — {row['label']}: {row['error_message']}")
        else:
            blockers, _advisories = split_issues(row["issues"])
            self.sel_error_detail.set(f"Needs items — {blockers[0]}" if blockers else "")
        self.sel_online_detail.set(online_state_text(row.get("integration_state", "")) if row else "")

    def _update_market_actions(self) -> None:
        """Enable each action only when the selected record actually supports it."""
        row = self.marketplace_row_map.get(self.selected_market_key)
        enabled = {
            "prepare": bool(row),
            "validate": bool(row),
            "folder": bool(row and row["has_local_folder"]),
            "site": bool(row and row["portal_url"]),
            "listing": bool(row and row["url"]),
            "record": bool(row),
            "draft": draft_action_enabled(row) and not getattr(self, "_draft_in_progress", False),
            "export": export_action_enabled(row, integration_info_for(row["key"] if row else "")) and not getattr(self, "_export_in_progress", False),
            "history": bool(row),
        }
        for name, button in self.market_buttons.items():
            button.configure(state="normal" if enabled[name] else "disabled")

    def _current_market_row(self) -> dict | None:
        return self.marketplace_row_map.get(self.selected_market_key)

    def _prepare_selected_marketplace(self) -> None:
        if self._current_market_row():
            self.prepare([self.selected_market_key])

    def _validate_selected_marketplace(self) -> None:
        """Re-run the platform validator read-only; advisories stay advisory."""
        row = self._current_market_row()
        if not row:
            return
        sections: list[str] = []
        if row["status"] in ("Uploaded", "Published"):
            sections.append(f"This marketplace is already recorded as {row['status']}; this check looks at local files and saved details only.")
        blockers, advisories = split_issues(row["issues"])
        sections.append("Required before preparing:\n• " + "\n• ".join(blockers) if blockers else "All required items are present for preparation.")
        if advisories:
            sections.append("Advisory notes (these do not block preparation):\n• " + "\n• ".join(advisories))
        messagebox.showinfo(f"Validation — {row['label']}", "\n\n".join(sections), parent=self)

    def _open_prepared_folder(self) -> None:
        row = self._current_market_row(); book = self.selected_book
        if not row or not book:
            return
        package = str(book.get("package_path") or "")
        folder = os.path.join(package, PREPARED_FOLDER_NAMES.get(row["key"], row["key"])) if package else ""
        if folder and os.path.isdir(folder):
            os.startfile(folder); self.status.set(f"Opened the prepared {row['label']} folder. Nothing was uploaded or changed.")
        else:
            messagebox.showinfo("No prepared folder yet", f"The prepared {row['label']} folder does not exist yet. Click Prepare first — this creates files only, it never uploads.", parent=self)

    def _open_publisher_site(self) -> None:
        row = self._current_market_row()
        if not row:
            return
        if row["portal_url"]:
            webbrowser.open(row["portal_url"])
            self.status.set(f"Opened the official {row['label']} portal in your browser. Signing in and uploading stay entirely in your hands.")
        else:
            messagebox.showinfo("No seller portal", "This channel has no seller portal. Sell it directly from your own website store.", parent=self)

    def _open_saved_listing(self) -> None:
        row = self._current_market_row()
        if not row:
            return
        if row["url"]:
            webbrowser.open(row["url"])
        else:
            messagebox.showinfo("No saved link yet", "Paste and save the public listing link first — use “Record listing / update status” once the listing is live.", parent=self)

    def _open_record_listing(self) -> None:
        if self.selected_book and self._current_market_row():
            UploadStatusDialog(self, self.service, self.selected_book, self.refresh, initial_marketplace=self.selected_market_key)

    def _open_marketplace_history(self) -> None:
        if self.selected_book and self._current_market_row():
            MarketplaceHistoryDialog(self, self.service, self.selected_book, initial_marketplace=self.selected_market_key)

    def open_marketplace_connections(self) -> None:
        MarketplaceConnectionsDialog(self)

    def _create_etsy_draft(self) -> None:
        """Run the draft-only Etsy automation in a background thread.

        The remote work itself lives in integrations.etsy.draft_service (fully
        tested offline); this handler only guards double-clicks, keeps the UI
        responsive, and reports the truthful result.
        """
        row = self._current_market_row()
        book = self.selected_book
        if not row or not book:
            return
        if getattr(self, "_draft_in_progress", False):
            return
        if not book.get("package_path"):
            messagebox.showinfo("Prepare first", "Create the complete package and choose Prepare Etsy before creating an online draft.", parent=self)
            return
        self._draft_in_progress = True
        button = self.market_buttons.get("draft")
        if button is not None:
            button.configure(state="disabled")
        self.status.set("Connecting to Etsy to create the DRAFT listing… Nothing will be published.")

        service = self.service

        def work():
            from integrations.etsy.draft_service import EtsyDraftService

            try:
                return EtsyDraftService().create_or_resume(service, book)
            except Exception as exc:  # last-resort net so the UI never dies silently
                from integrations.etsy.draft_service import DraftResult

                return DraftResult(ok=False, message=f"Unexpected problem: {exc}")

        def done(result):
            self._draft_in_progress = False
            self.refresh()
            title = "Etsy draft" if result.ok else "Etsy draft needs attention"
            if result.ok:
                messagebox.showinfo(title, result.message + ("\n\nEvents:\n• " + "\n• ".join(result.events) if result.events else ""), parent=self)
            else:
                messagebox.showwarning(title, result.message, parent=self)

        def runner():
            result = work()
            self.after(0, lambda: done(result))

        threading.Thread(target=runner, daemon=True).start()

    def _open_master_product(self) -> None:
        book = self.selected_book
        if not book:
            return
        MasterProductDialog(self, self.service, book)

    def _generate_export_package(self) -> None:
        """Run the registered export-only adapter in a background thread.

        Writes a local handoff folder only. On success the automation-owned
        integration_state becomes "exported"; human-owned statuses are never
        touched (an export package is preparation, not publication).
        """
        row = self._current_market_row()
        book = self.selected_book
        if not row or not book or getattr(self, "_export_in_progress", False):
            return
        info = integration_info_for(row["key"])
        if not export_action_enabled(row, info):
            messagebox.showinfo(
                "Export not available yet",
                f"{row['label']} does not offer an automated export package yet.",
                parent=self)
            return

        self._export_in_progress = True
        button = self.market_buttons.get("export")
        if button is not None:
            button.configure(state="disabled")
        self.status.set(f"Building the {row['label']} export package… Files are written locally only.")

        service = self.service

        def work():
            from integrations.factory import MasterProductFactory
            from integrations.registry import get_export_integration

            try:
                export_key = info.get("export_key") or row["key"]
                adapter = get_export_integration(export_key)
                if adapter is None:
                    from integrations.results import PublishResult

                    return PublishResult.failure("No export adapter is registered for this marketplace.")
                product = MasterProductFactory.from_book_record(book)
                destination = Path(service.output) / "exports" / export_key
                return adapter.export_package(product, destination)
            except Exception as exc:  # last-resort net so the UI never dies silently
                from integrations.results import PublishResult

                return PublishResult.failure(f"Unexpected problem while building the export package: {exc}")

        def done(result):
            self._export_in_progress = False
            apply_export_outcome(self.service.db, book["book_id"], row["key"], result)
            self.refresh()
            folder = str(getattr(result, "recovery", {}).get("folder", "")) if isinstance(getattr(result, "recovery", None), dict) else ""
            if result.success:
                self.status.set(f"{row['label']} export package ready at {result.artifact_path}. Nothing was uploaded.")
                open_now = messagebox.askyesno(
                    "Export package ready",
                    f"{result.message}\n\nOpen the folder now?", parent=self)
                if open_now:
                    target = folder or str(result.artifact_path)
                    if os.path.isdir(target):
                        os.startfile(target)
                    else:
                        messagebox.showinfo("Folder moved", f"The folder is no longer here:\n{target}", parent=self)
            else:
                self.status.set(f"The {row['label']} export could not be built: {result.message}")
                messagebox.showwarning("Export needs attention", result.message, parent=self)

        def runner():
            result = work()
            self.after(0, lambda: done(result))

        threading.Thread(target=runner, daemon=True).start()

    def refresh(self, sync: bool = False) -> None:
        if sync:
            count = self.sync_catalog(); self.status.set(f"Synced {count} theme records into the Publishing Manager. Existing metadata locks were preserved.")
        selected_market = next((key for key, label in DISPLAY.items() if label == self.market_filter.get()), "")
        query = self.filter_text.get().casefold().strip(); self.rows.clear(); self.tree.delete(*self.tree.get_children())
        for book in self.service.db.list_books():
            meta, statuses = book["metadata"], book["statuses"]
            haystack = " ".join(str(meta.get(key) or "") for key in ("title", "series", "theme")).casefold()
            if query and query not in haystack: continue
            if selected_market and statuses.get(selected_market) == "Not Prepared": continue
            iid = book["book_id"]; self.rows[iid] = book
            self.tree.insert("", "end", iid=iid, values=(meta.get("title", ""), meta.get("series", ""), meta.get("theme", ""), meta.get("page_count", 0), meta.get("isbn", ""), *[statuses.get(key, "Not Prepared") for key in MARKETPLACES], book.get("updated_at", "")[:16].replace("T", " ")))
        self.recommendations.clear(); self.recommendation_tree.delete(*self.recommendation_tree.get_children())
        for item in self.service.recommended_books():
            book = item["book"]; iid = book["book_id"]; self.recommendations[iid] = item
            self.recommendation_tree.insert("", "end", iid=iid, values=(book["metadata"].get("title", ""), item["topic"], item["puzzles"] or "—", item["action"], item["reason"]))
        self.refresh_selected_view()

    def open_recommended_book(self) -> None:
        selected = self.recommendation_tree.selection()
        if not selected:
            messagebox.showwarning("Choose a recommendation", "Choose a recommended book first.", parent=self); return
        item = self.recommendations.get(selected[0])
        if not item:
            return
        book = item["book"]
        if item["action"] == "Prepare package":
            self.tree.selection_set(book["book_id"]); self.tree.focus(book["book_id"])
            self.status.set("This package is already created. It is selected below; choose Prepare KDP when you are ready.")
            return
        if self.open_recommendation:
            self.destroy()
            self.open_recommendation(book)
            return
        self.status.set("Open this title from Word Search tools to create its full package.")

    def start_new_book(self) -> None:
        if not self.new_book:
            messagebox.showinfo("New book", "Open Book Studio and choose New Book to start a guided project.", parent=self)
            return
        self.destroy()
        self.new_book()

    def open_etsy_bundle_builder(self) -> None:
        EtsyBundleDialog(self, self.service, self.refresh)

    def scan_local_status(self) -> None:
        found = self.service.detect_local_marketplace_status(); self.refresh()
        self.status.set(f"Checked local production folders. Marked {found} newly prepared marketplace handoff(s) as ready; uploaded and published records were left untouched.")

    def open_upload_status(self) -> None:
        books = self._selected()
        if len(books) != 1:
            messagebox.showinfo("Choose one book", "Choose one book in the catalog first, then open Upload status to record its exact marketplace link or ID.", parent=self); return
        UploadStatusDialog(self, self.service, books[0], self.refresh)

    def _request_complete_package(self, book: dict) -> None:
        if not self.create_package:
            messagebox.showinfo("Create package", "Open this saved theme in Word Search tools, then select Review & Create Package.", parent=self)
            return
        self.destroy()
        self.create_package(book)

    def create_recommended_package(self) -> None:
        selected = self.recommendation_tree.selection()
        if not selected:
            messagebox.showwarning("Choose a recommendation", "Choose a recommended book first.", parent=self); return
        item = self.recommendations.get(selected[0])
        if item:
            self._request_complete_package(item["book"])

    def create_selected_package(self) -> None:
        books = self._selected()
        if not books:
            messagebox.showwarning("Choose a book", "Choose one saved book first.", parent=self); return
        if len(books) > 1:
            messagebox.showwarning("Choose one book", "Create one complete package at a time so the final proof and package folder stay clear.", parent=self); return
        self._request_complete_package(books[0])

    def _selected(self) -> list[dict]: return [self.rows[item] for item in self.tree.selection() if item in self.rows]

    def open_selected_master(self) -> None:
        books = self._selected()
        if not books:
            messagebox.showwarning("Choose a book", "Choose one completed book first.", parent=self); return
        if len(books) > 1:
            messagebox.showwarning("Choose one book", "Open one Master Release folder at a time.", parent=self); return
        package = str(books[0].get("package_path") or "")
        master = os.path.join(package, "MASTER_RELEASE_PACKAGE") if package else ""
        if master and os.path.isdir(master):
            os.startfile(master)
            self.status.set("Opened the Master Release folder. Start with 00_READ_ME_FIRST.txt.")
        elif package and os.path.isdir(package):
            self.status.set("This completed package needs a Master Release folder. Click Sync catalog, then try again.")
        else:
            self.status.set("This is a saved theme, not a completed package yet. Choose Create complete package first.")

    def prepare(self, marketplaces: list[str]) -> None:
        books = self._selected()
        if not books: messagebox.showwarning("Choose a book", "Select one or more books first.", parent=self); return
        report = self.service.prepare_many([book["book_id"] for book in books], marketplaces); self.refresh()
        # Imported here so this truthful-reporting change stays confined to
        # this method; readiness.py holds the shared classification logic.
        from .readiness import classify_prepare_report
        buckets = classify_prepare_report(report)
        parts: list[str] = []
        made = buckets["prepared"]
        if made:
            parts.append(f"Prepared {len(made)} marketplace package(s). They are ready to review and upload.")
        confirmed: dict[tuple[str, str], None] = {}
        for _book_id, marketplace, prior in buckets["already_confirmed"]:
            confirmed.setdefault((marketplace, prior))
        for marketplace, prior in confirmed:
            parts.append(f"{PUBLISHERS[marketplace].label} is already recorded as {prior}. Nothing was changed and your saved listing details remain intact.")
        if buckets["needs_review"]:
            parts.append(f"{len(buckets['needs_review'])} marketplace package(s) still need required items. Select the book and choose “Why not KDP ready?” for the exact fix. Your files were not changed.")
        if buckets["errors"]:
            first_book, first_market, message = buckets["errors"][0]
            parts.append(f"Preparation failed for {PUBLISHERS[first_market].label}: {message} Nothing was deleted.")
        if buckets["other"]:
            parts.append(f"{len(buckets['other'])} result(s) need a closer look. Open Upload status for the exact confirmed records.")
        self.status.set(" ".join(parts) if parts else "Nothing needed preparing.")

    def show_kdp_readiness(self) -> None:
        books = self._selected()
        if not books:
            messagebox.showwarning("Choose a book", "Select one book first, then I will explain its KDP readiness.", parent=self); return
        book = books[0]
        issues = PUBLISHERS["amazon"].validate(book)
        title = book["metadata"].get("title", "This book")
        if not issues:
            messagebox.showinfo("Ready to prepare for KDP", f"{title} has both required print files and its basic contributor details. Click Prepare KDP to make an upload folder, then run KDP Print Previewer before publishing.", parent=self)
            return
        friendly = []
        for issue in issues:
            if "interior PDF" in issue or "cover PDF" in issue:
                friendly.append("Create the complete package from Word Search tools. This makes both the interior PDF and the full KDP cover wrap.")
            elif "author" in issue:
                friendly.append("Open Book Details and enter your contributor name (Jordan M. Slade), not the Slade Puzzles brand.")
            else:
                friendly.append(issue)
        unique = list(dict.fromkeys(friendly))
        messagebox.showinfo("What this book needs", f"{title} is not ready for KDP yet.\n\nWhat to do next:\n• " + "\n• ".join(unique) + "\n\nYour saved theme and current files are safe—do not delete them.", parent=self)

    def open_book(self) -> None:
        selected = self._selected()
        if not selected: messagebox.showwarning("Choose a book", "Select a book first.", parent=self); return
        BookPublishingDialog(self, self.service, selected[0], self.refresh)


class UploadStatusDialog(tk.Toplevel):
    """One truthful record per marketplace: local prep, upload, then live link."""
    def __init__(self, parent, service, book: dict, on_saved, initial_marketplace: str = "") -> None:
        super().__init__(parent); self.service, self.book, self.on_saved = service, book, on_saved
        self.initial_marketplace = initial_marketplace
        self.title("Upload status"); self.geometry("850x590"); self.minsize(700, 500); self.configure(background="#1f1f1f"); self.transient(parent)
        self.marketplace = tk.StringVar(value="amazon"); self.status_value = tk.StringVar(); self.external_id = tk.StringVar(); self.url = tk.StringVar(); self.updated = tk.StringVar()
        self._build(); self._apply_initial_marketplace(); self._load_record()

    def _apply_initial_marketplace(self) -> None:
        """Pre-select one marketplace when opened from a Hub readiness row."""
        if self.initial_marketplace in MARKETPLACES:
            self.market_combo.set(f"{DISPLAY[self.initial_marketplace]}|{self.initial_marketplace}")

    def _build(self) -> None:
        root = ttk.Frame(self, padding=22, style="Publish.TFrame"); root.pack(fill="both", expand=True); root.columnconfigure(1, weight=1)
        title = self.book["metadata"].get("title", "Book")
        ttk.Label(root, text="Upload status", style="Publish.Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(root, text=title, style="Publish.Subtitle.TLabel", wraplength=760).grid(row=1, column=0, columnspan=3, sticky="w", pady=(3, 12))
        note = ("This screen records only what you confirm. “Ready” means the local upload folder exists. "
                "After you upload, paste the ASIN, listing ID, or live link here. The app will never guess that a book is live.")
        ttk.Label(root, text=note, style="Publish.Status.TLabel", wraplength=760).grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 16))
        ttk.Label(root, text="Marketplace", style="Publish.TLabel").grid(row=3, column=0, sticky="w", pady=7)
        choices = [f"{DISPLAY[key]}|{key}" for key in MARKETPLACES]
        self.market_combo = ttk.Combobox(root, values=choices, state="readonly", style="Publish.TCombobox", width=28)
        self.market_combo.grid(row=3, column=1, sticky="w", pady=7); self.market_combo.set(f"{DISPLAY['amazon']}|amazon")
        self.market_combo.bind("<<ComboboxSelected>>", lambda _event: self._load_record())
        ttk.Label(root, text="Progress", style="Publish.TLabel").grid(row=4, column=0, sticky="w", pady=7)
        ttk.Combobox(root, textvariable=self.status_value, values=STATUS_VALUES, state="readonly", style="Publish.TCombobox", width=28).grid(row=4, column=1, sticky="w", pady=7)
        ttk.Label(root, text="ASIN, listing ID, or product ID", style="Publish.TLabel").grid(row=5, column=0, sticky="w", pady=7)
        ttk.Entry(root, textvariable=self.external_id, style="Publish.TEntry").grid(row=5, column=1, columnspan=2, sticky="ew", pady=7)
        ttk.Label(root, text="Live listing link", style="Publish.TLabel").grid(row=6, column=0, sticky="w", pady=7)
        ttk.Entry(root, textvariable=self.url, style="Publish.TEntry").grid(row=6, column=1, columnspan=2, sticky="ew", pady=7)
        ttk.Label(root, textvariable=self.updated, style="Publish.Subtitle.TLabel").grid(row=7, column=0, columnspan=3, sticky="w", pady=(4, 14))
        self.summary = tk.Text(root, height=8, wrap="word", state="disabled", background="#292929", foreground="#d9f5ee", relief="flat", padx=10, pady=10)
        self.summary.grid(row=8, column=0, columnspan=3, sticky="nsew"); root.rowconfigure(8, weight=1)
        actions = ttk.Frame(root, style="Publish.TFrame"); actions.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        ttk.Button(actions, text="Save confirmed status", command=self.save, style="Publish.Primary.TButton").pack(side="right")
        ttk.Button(actions, text="Open saved link", command=self.open_link, style="Publish.Action.TButton").pack(side="right", padx=6)

    def _marketplace_key(self) -> str:
        return self.market_combo.get().rsplit("|", 1)[-1]

    def _load_record(self) -> None:
        key = self._marketplace_key(); record = self.service.db.marketplace_records(self.book["book_id"])[key]
        self.status_value.set(record["status"]); self.external_id.set(record["external_id"]); self.url.set(record["url"])
        stamp = record["updated_at"].replace("T", " ") if record["updated_at"] else "No confirmed record saved yet."
        self.updated.set(f"Last saved: {stamp}")
        package = str(self.book.get("package_path") or "")
        folder = {"amazon": "kdp", "barnes_noble": "barnes_noble"}.get(key, key)
        local = os.path.join(package, folder) if package else ""
        local_text = "Local upload folder found." if local and os.path.isdir(local) else "No local upload folder found yet."
        self.summary.configure(state="normal"); self.summary.delete("1.0", "end")
        self.summary.insert("end", f"{DISPLAY[key]}: {record['status']}\n\n{local_text}\n\nUse “Uploaded” only after the files are accepted by the marketplace. Use “Published” after the public listing is visible. Paste the exact listing link so it can be opened later from here.")
        self.summary.configure(state="disabled")

    def save(self) -> None:
        key, status = self._marketplace_key(), self.status_value.get()
        if not status:
            messagebox.showwarning("Choose progress", "Choose the current marketplace progress before saving.", parent=self); return
        link = self.url.get().strip()
        if link and not link.startswith(("https://", "http://")):
            messagebox.showwarning("Check link", "Paste a full link beginning with https:// or http://.", parent=self); return
        self.service.db.update_marketplace_record(self.book["book_id"], key, status, self.external_id.get(), link)
        self.book = self.service.db.get_book(self.book["book_id"]); self._load_record(); self.on_saved()
        messagebox.showinfo("Status saved", f"Saved the confirmed {DISPLAY[key]} status for this book.", parent=self)

    def open_link(self) -> None:
        link = self.url.get().strip()
        if not link:
            messagebox.showinfo("No link yet", "Paste and save the public listing link first.", parent=self); return
        webbrowser.open(link)


class EtsyBundleDialog(tk.Toplevel):
    """Build a compliant Etsy digital bundle from finished customer PDFs."""
    def __init__(self, parent, service, on_created) -> None:
        super().__init__(parent); self.service, self.on_created = service, on_created
        self.title("Create Etsy Bundle"); self.geometry("920x650"); self.minsize(760, 520); self.configure(background="#1f1f1f"); self.transient(parent)
        self.title_value = tk.StringVar(value=f"{ETSY_STORE_NAME} Printable Puzzle Book Bundle")
        self.price = tk.StringVar(value="12.99"); self.status = tk.StringVar(value="Choose two or more completed books. Only buyer-ready digital PDFs are shown.")
        self.books = {book["book_id"]: book for book in service.etsy_bundle_candidates()}; self._build()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=22, style="Publish.TFrame"); root.pack(fill="both", expand=True); root.columnconfigure(1, weight=1); root.rowconfigure(3, weight=1)
        ttk.Label(root, text="Create Etsy bundle", style="Publish.Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(root, text="This creates buyer-ready ZIP download file(s), a bundle cover, and an Etsy listing kit. It does not touch your original book packages.", style="Publish.Subtitle.TLabel", wraplength=820).grid(row=1, column=0, columnspan=2, sticky="w", pady=(3, 14))
        ttk.Label(root, text="Bundle title", style="Publish.TLabel").grid(row=2, column=0, sticky="w", pady=5); ttk.Entry(root, textvariable=self.title_value, style="Publish.TEntry").grid(row=2, column=1, sticky="ew", pady=5)
        columns = ("book", "puzzles", "theme", "pages")
        self.tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="extended", height=12, style="Publish.Treeview")
        for key, label, width in (("book", "Completed book", 390), ("puzzles", "Puzzles", 75), ("theme", "Theme", 200), ("pages", "Pages", 75)):
            self.tree.heading(key, text=label); self.tree.column(key, width=width, anchor="w" if key in ("book", "theme") else "center")
        self.tree.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(10, 12))
        for book_id, book in self.books.items():
            meta = book["metadata"]; self.tree.insert("", "end", iid=book_id, values=(meta.get("title", ""), meta.get("puzzle_count", ""), meta.get("theme", ""), meta.get("page_count", "")))
        ttk.Label(root, text="Suggested Etsy price", style="Publish.TLabel").grid(row=4, column=0, sticky="w", pady=5); ttk.Entry(root, textvariable=self.price, width=12, style="Publish.TEntry").grid(row=4, column=1, sticky="w", pady=5)
        actions = ttk.Frame(root, style="Publish.TFrame"); actions.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Create buyer-ready Etsy bundle", command=self.create, style="Publish.Primary.TButton").pack(side="right")
        ttk.Label(root, textvariable=self.status, style="Publish.Status.TLabel", wraplength=820).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def create(self) -> None:
        selected = list(self.tree.selection())
        if len(selected) < 2:
            messagebox.showwarning("Choose books", "Choose at least two completed books for this Etsy bundle.", parent=self); return
        title = self.title_value.get().strip()
        if not title:
            messagebox.showwarning("Add a title", "Give the Etsy bundle a buyer-facing title.", parent=self); return
        try:
            price = float(self.price.get())
            if price <= 0: raise ValueError
        except ValueError:
            messagebox.showwarning("Check price", "Enter a positive price, for example 12.99.", parent=self); return
        try:
            folder, details = self.service.create_etsy_bundle(title, selected, price)
        except Exception as exc:
            messagebox.showerror("Bundle needs attention", str(exc), parent=self); return
        self.on_created()
        self.status.set(f"Bundle created with {len(details['books'])} books. Open the folder and upload the ZIP file(s) listed in ETSY_LISTING_KIT.txt.")
        os.startfile(folder)


class BookPublishingDialog(tk.Toplevel):
    def __init__(self, parent, service, book: dict, on_saved) -> None:
        super().__init__(parent); self.service, self.book, self.on_saved = service, book, on_saved
        self.title(f"Publish: {book['metadata'].get('title', 'Book')}"); self.geometry("940x680"); self.minsize(760, 540); self.configure(background="#1f1f1f")
        self.vars = {key: tk.StringVar(value=str(book["metadata"].get(key) or "")) for key in ("title", "subtitle", "author", "series", "isbn")}; self.locked = tk.BooleanVar(value=bool(book.get("metadata_locked"))); self._build()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=22, style="Publish.TFrame"); root.pack(fill="both", expand=True); root.columnconfigure(1, weight=1); root.rowconfigure(7, weight=1)
        ttk.Label(root, text="Book publishing details", style="Publish.Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        for row, key in enumerate(("title", "subtitle", "author", "series", "isbn"), 1):
            ttk.Label(root, text=key.replace("_", " ").title(), style="Publish.TLabel").grid(row=row, column=0, sticky="w", pady=4); ttk.Entry(root, textvariable=self.vars[key], style="Publish.TEntry").grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Label(root, text="Description", style="Publish.TLabel").grid(row=6, column=0, sticky="nw", pady=4); self.description = tk.Text(root, height=8, wrap="word", background="#303030", foreground="#f2f2f2", insertbackground="#f2f2f2", relief="flat", padx=8, pady=8); self.description.grid(row=6, column=1, columnspan=2, sticky="nsew", pady=4); self.description.insert("1.0", self.book["metadata"].get("description", ""))
        self.status_box = tk.Text(root, height=10, wrap="word", state="disabled", background="#292929", foreground="#d9f5ee", relief="flat", padx=10, pady=10); self.status_box.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=(12, 0)); self._show_statuses()
        actions = ttk.Frame(root, style="Publish.TFrame"); actions.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        ttk.Checkbutton(actions, text="Lock metadata (automatic sync will not overwrite it)", variable=self.locked).pack(side="left")
        ttk.Button(actions, text="Save metadata", command=self.save, style="Publish.Primary.TButton").pack(side="right")
        ttk.Button(actions, text="Upload status…", command=self.open_upload_status, style="Publish.Action.TButton").pack(side="right", padx=6)
        ttk.Button(actions, text="Open Master Release Folder", command=self.open_master_package, style="Publish.Action.TButton").pack(side="right", padx=6)
        ttk.Button(actions, text="Open package", command=self.open_package, style="Publish.Action.TButton").pack(side="right")

    def _show_statuses(self) -> None:
        self.status_box.configure(state="normal"); self.status_box.delete("1.0", "end")
        meta = self.book["metadata"]; self.status_box.insert("end", f"Pages: {meta.get('page_count', 0)} | Trim: {meta.get('trim_size', '8.5x11')} | Theme: {meta.get('theme', '')}\nContent check: {meta.get('production_status', 'Needs content check')}\n\n")
        for key in MARKETPLACES: self.status_box.insert("end", f"{DISPLAY[key]}: {self.book['statuses'].get(key, 'Not Prepared')}\n")
        self.status_box.configure(state="disabled")

    def save(self) -> None:
        meta = dict(self.book["metadata"])
        for key, var in self.vars.items(): meta[key] = var.get().strip()
        meta["description"] = self.description.get("1.0", "end-1c").strip(); self.service.db.save_metadata(self.book["book_id"], meta, self.locked.get())
        if meta["isbn"]: self.service.db.assign_isbn(meta["isbn"], self.book["book_id"], meta["title"], "User-owned ISBN")
        self.book = self.service.db.get_book(self.book["book_id"]); self._show_statuses(); self.on_saved(); messagebox.showinfo("Saved", "Your master metadata record is saved.", parent=self)

    def open_upload_status(self) -> None:
        UploadStatusDialog(self, self.service, self.book, self._after_upload_status)

    def _after_upload_status(self) -> None:
        self.book = self.service.db.get_book(self.book["book_id"]); self._show_statuses(); self.on_saved()

    def open_package(self) -> None:
        path = self.book.get("package_path")
        if path and os.path.isdir(path): os.startfile(path)
        else: messagebox.showinfo("No package", "Create a complete book package first, then sync this catalog.", parent=self)

    def open_master_package(self) -> None:
        path = self.book.get("package_path")
        master = os.path.join(path, "MASTER_RELEASE_PACKAGE") if path else ""
        if master and os.path.isdir(master):
            os.startfile(master)
        elif path and os.path.isdir(path):
            messagebox.showinfo("Master folder pending", "Open Publishing Manager and choose Sync catalog. It will create this book's Master Release Package without changing the book files.", parent=self)
        else:
            messagebox.showinfo("No package", "Create a complete book package first. The Master Release Package is created automatically with it.", parent=self)


class ISBNManagerDialog(tk.Toplevel):
    """Read-only safety view: ISBN assignment happens on each Book Details screen."""
    def __init__(self, parent, service) -> None:
        super().__init__(parent); self.service = service; self.title("ISBN Manager"); self.geometry("760x440"); self.minsize(620, 350); self.configure(background="#1f1f1f")
        root = ttk.Frame(self, padding=22, style="Publish.TFrame"); root.pack(fill="both", expand=True); root.columnconfigure(0, weight=1); root.rowconfigure(2, weight=1)
        ttk.Label(root, text="ISBN manager", style="Publish.Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(root, text="Assign an ISBN in Book Details. This list prevents one ISBN from being assigned to two different books. A KDP-provided ISBN should remain KDP-specific.", style="Publish.Subtitle.TLabel", wraplength=700).grid(row=1, column=0, sticky="w", pady=(3, 12))
        tree = ttk.Treeview(root, columns=("isbn", "title", "format", "source", "date"), show="headings", style="Publish.Treeview")
        for key, label, width in (("isbn", "ISBN", 150), ("title", "Title", 280), ("format", "Format", 100), ("source", "Source", 140), ("date", "Assigned", 130)):
            tree.heading(key, text=label); tree.column(key, width=width, anchor="w")
        tree.grid(row=2, column=0, sticky="nsew")
        for item in service.db.list_isbns(): tree.insert("", "end", values=(item.get("isbn", ""), item.get("title", ""), item.get("format", ""), item.get("source", ""), str(item.get("assigned_at", ""))[:16].replace("T", " ")))


class MarketplaceHistoryDialog(tk.Toplevel):
    """Human-readable, newest-first audit trail for one book's marketplaces."""

    def __init__(self, parent, service, book: dict, initial_marketplace: str = "") -> None:
        super().__init__(parent); self.service, self.book = service, book
        self.title(f"Publishing history — {book['metadata'].get('title', 'Book')}"); self.geometry("800x560"); self.minsize(640, 420)
        self.configure(background="#1f1f1f"); self.transient(parent)
        choices = ["All marketplaces"] + [f"{DISPLAY_GRID[key]}|{key}" for key in MARKETPLACES]
        default = f"{DISPLAY_GRID[initial_marketplace]}|{initial_marketplace}" if initial_marketplace in MARKETPLACES else "All marketplaces"
        self.market_choice = tk.StringVar(value=default)
        root = ttk.Frame(self, padding=20, style="Publish.TFrame"); root.pack(fill="both", expand=True); root.columnconfigure(0, weight=1); root.rowconfigure(3, weight=1)
        ttk.Label(root, text="Publishing history", style="Publish.Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(root, text=book["metadata"].get("title", ""), style="Publish.Subtitle.TLabel", wraplength=740).grid(row=1, column=0, sticky="w", pady=(3, 10))
        picker = ttk.Frame(root, style="Publish.TFrame"); picker.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(picker, text="Marketplace", style="Publish.TLabel").pack(side="left")
        combo = ttk.Combobox(picker, textvariable=self.market_choice, values=choices, state="readonly", width=26, style="Publish.TCombobox")
        combo.pack(side="left", padx=7); combo.bind("<<ComboboxSelected>>", lambda _event: self.reload())
        ttk.Button(picker, text="Refresh", command=self.reload, style="Publish.Action.TButton").pack(side="left")
        self.count_var = tk.StringVar(value=""); ttk.Label(picker, textvariable=self.count_var, style="Publish.Subtitle.TLabel").pack(side="right")
        self.history_box = tk.Text(root, wrap="word", state="disabled", background="#292929", foreground="#d9f5ee", relief="flat", padx=12, pady=10)
        self.history_box.grid(row=3, column=0, sticky="nsew")
        ttk.Button(root, text="Close", command=self.destroy, style="Publish.Action.TButton").grid(row=4, column=0, sticky="e", pady=(10, 0))
        self.reload()

    def _marketplace_key(self) -> str:
        value = self.market_choice.get()
        return value.rsplit("|", 1)[-1] if "|" in value else ""

    def reload(self) -> None:
        key = self._marketplace_key()
        entries = self.service.db.audit_history(book_id=self.book["book_id"], marketplace=key or None)
        label = DISPLAY_GRID.get(key, key) if key else ""
        self.count_var.set(f"{len(entries)} recorded change(s)" + (f" — {label}" if label else ""))
        self.history_box.configure(state="normal"); self.history_box.delete("1.0", "end")
        self.history_box.insert("end", format_history(entries))
        self.history_box.configure(state="disabled")


class _StoredEtsyCredentialProvider:
    """Credential provider reading env vars first, then Windows Credential Manager."""

    def load(self):
        from integrations.etsy.session import load_credentials

        return load_credentials()


class MarketplaceConnectionsDialog(tk.Toplevel):
    """One calm place to connect, test, or forget marketplace credentials.

    Secrets are stored ONLY in the Windows Credential Manager (never in files,
    never in this catalog database).  The dialog reports what it knows without
    ever displaying a secret value.
    """

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.title("Marketplace connections"); self.geometry("760x540"); self.minsize(620, 430)
        self.configure(background="#1f1f1f"); self.transient(parent)
        root = ttk.Frame(self, padding=22, style="Publish.TFrame"); root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1); root.rowconfigure(3, weight=1)
        ttk.Label(root, text="Marketplace connections", style="Publish.Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            root,
            text=("Connect your Etsy shop so the app can create DRAFT listings for you — it never publishes, "
                  "prices, or deletes anything. Credentials are kept in Windows Credential Manager on this "
                  "computer. Other channels keep using their own seller portals and your manual uploads."),
            style="Publish.Subtitle.TLabel", wraplength=700).grid(row=1, column=0, sticky="w", pady=(4, 12))
        self.status_box = tk.Text(root, height=12, wrap="word", state="disabled", background="#292929",
                                  foreground="#d9f5ee", relief="flat", padx=10, pady=10)
        self.status_box.grid(row=2, column=0, sticky="ew")
        self.detail_box = tk.Text(root, height=8, wrap="word", state="disabled", background="#292929",
                                  foreground="#b7b7b7", relief="flat", padx=10, pady=10)
        self.detail_box.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        actions = ttk.Frame(root, style="Publish.TFrame"); actions.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        ttk.Button(actions, text="Close", command=self.destroy, style="Publish.Action.TButton").pack(side="right")
        ttk.Button(actions, text="Forget stored Etsy credentials", command=self.forget_etsy, style="Publish.Action.TButton").pack(side="right", padx=6)
        ttk.Button(actions, text="Connect / reconnect Etsy…", command=self.connect_etsy, style="Publish.Primary.TButton").pack(side="right", padx=6)
        ttk.Button(actions, text="Test Etsy connection", command=self.test_etsy, style="Publish.Action.TButton").pack(side="left")
        self.refresh_status()

    # -- status rendering -------------------------------------------------------

    def refresh_status(self) -> None:
        try:
            from integrations.etsy.session import load_credentials

            creds = load_credentials()
            lines = [
                "Etsy",
                f"  App keystring : {'stored' if creds.api_keystring else 'missing'}",
                f"  Shared secret : {'stored' if creds.shared_secret else 'not stored (optional)'}",
                f"  Access token  : {'stored' if creds.access_token else 'missing'}",
                f"  Refresh token : {'stored' if creds.refresh_token else 'missing'}",
                "",
            ]
        except Exception as exc:  # storage problems must never crash the Hub
            lines = [f"Etsy — could not read stored credentials safely ({exc}).", ""]
        lines.append("Amazon KDP / IngramSpark / Lulu / BookVault / Barnes & Noble")
        lines.append("  No API connections yet — upload through each official seller portal as usual.")
        self.status_box.configure(state="normal"); self.status_box.delete("1.0", "end")
        self.status_box.insert("end", "\n".join(lines))
        self.status_box.configure(state="disabled")

    def _set_detail(self, text: str) -> None:
        self.detail_box.configure(state="normal"); self.detail_box.delete("1.0", "end")
        self.detail_box.insert("end", text); self.detail_box.configure(state="disabled")

    # -- actions -----------------------------------------------------------------

    def test_etsy(self) -> None:
        from integrations.etsy.connection import EtsyIntegration

        integration = EtsyIntegration(credential_provider=_StoredEtsyCredentialProvider())
        self._set_detail("Testing the Etsy connection…")
        def runner():
            report = integration.test_connection()
            self.after(0, lambda: self._set_detail(report.message))
        threading.Thread(target=runner, daemon=True).start()

    def connect_etsy(self) -> None:
        EtsyConnectDialog(self, on_done=self.refresh_status)

    def forget_etsy(self) -> None:
        from integrations.etsy.session import forget_credentials

        if not messagebox.askyesno(
                "Forget Etsy connection",
                "Remove the stored Etsy credentials from Windows Credential Manager on this computer?\n\n"
                "Prepared files and catalog records stay exactly as they are.",
                parent=self):
            return
        forgotten = forget_credentials()
        self.refresh_status()
        self._set_detail("Stored Etsy credentials removed." if forgotten
                         else "There were no stored Etsy credentials to remove.")


class EtsyConnectDialog(tk.Toplevel):
    """Guided OAuth connection: browser approval, paste the redirect back.

    Etsy requires an HTTPS callback that exactly matches the app registration,
    so desktop flow is: open the approval page, approve, then paste the URL
    the browser landed on.  Only ``shops_r listings_r listings_w`` scopes are
    requested — never the destructive ``listings_d``.
    """

    def __init__(self, parent, on_done=None) -> None:
        super().__init__(parent)
        self.parent_dialog = parent; self.on_done = on_done
        self.pkce = None; self.oauth_state = ""; self.keystring_value = ""
        self.title("Connect Etsy"); self.geometry("720x600"); self.minsize(600, 520)
        self.configure(background="#1f1f1f"); self.transient(parent)
        root = ttk.Frame(self, padding=22, style="Publish.TFrame"); root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1); root.rowconfigure(7, weight=1)
        ttk.Label(root, text="Connect your Etsy shop", style="Publish.Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            root,
            text=("Step 1 · Open etsy.com/developers/your-apps and copy your app's keystring and shared secret.\n"
                  "Step 2 · Make sure one callback URL is registered there (must start with https://).\n"
                  "Step 3 · Fill the three boxes below, open the approval page, then paste the address your "
                  "browser lands on after you approve."),
            style="Publish.Subtitle.TLabel", wraplength=660, justify="left").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))
        rows = (("App keystring", "keystring"), ("Shared secret", "shared_secret"), ("Callback URL", "callback"))
        self.vars = {}
        for row_index, (label, name) in enumerate(rows, start=2):
            ttk.Label(root, text=label, style="Publish.TLabel").grid(row=row_index, column=0, sticky="w", pady=5)
            var = tk.StringVar(value="https://" if name == "callback" else "")
            entry = ttk.Entry(root, textvariable=var, show="•" if name == "shared_secret" else "", style="Publish.TEntry")
            entry.grid(row=row_index, column=1, sticky="ew", pady=5)
            self.vars[name] = var
        ttk.Label(root, text=self._scope_text(), style="Publish.Status.TLabel", wraplength=650).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 8))
        self.open_button = ttk.Button(root, text="Open Etsy approval page", command=self.open_approval, style="Publish.Primary.TButton")
        self.open_button.grid(row=6, column=0, columnspan=2, sticky="w")
        self.paste_var = tk.StringVar(value="")
        ttk.Label(root, text="Pasted redirect URL", style="Publish.TLabel").grid(row=7, column=0, sticky="nw", pady=(12, 5))
        paste_entry = ttk.Entry(root, textvariable=self.paste_var, style="Publish.TEntry")
        paste_entry.grid(row=7, column=1, sticky="ew", pady=(12, 0))
        self.finish_button = ttk.Button(root, text="Finish connecting", command=self.finish_connect, style="Publish.Primary.TButton", state="disabled")
        self.finish_button.grid(row=8, column=1, sticky="e", pady=(10, 0))
        self.result_box = tk.Text(root, height=7, wrap="word", state="disabled", background="#292929",
                                  foreground="#d9f5ee", relief="flat", padx=10, pady=10)
        self.result_box.grid(row=9, column=0, columnspan=2, sticky="nsew", pady=(12, 0))

    @staticmethod
    def _scope_text() -> str:
        from integrations.etsy.auth import DRAFT_SCOPES

        return (
            "Permissions requested: " + ", ".join(DRAFT_SCOPES) + ".\n"
            "This app can create drafts and attach your PDF/image; it can never publish, edit live listings, or delete anything."
        )

    def _set_result(self, text: str) -> None:
        self.result_box.configure(state="normal"); self.result_box.delete("1.0", "end")
        self.result_box.insert("end", text); self.result_box.configure(state="disabled")

    def open_approval(self) -> None:
        import secrets

        from integrations.etsy.auth import (
            DRAFT_SCOPES,
            build_authorization_url,
            generate_pkce_pair,
        )
        from integrations.errors import IntegrationError

        keystring = self.vars["keystring"].get().strip()
        callback = self.vars["callback"].get().strip()
        if not keystring:
            messagebox.showwarning("Add the keystring", "Paste your app's keystring from etsy.com/developers first.", parent=self)
            return
        if not callback.lower().startswith("https://"):
            messagebox.showwarning("HTTPS callback needed", "Etsy only accepts callback URLs that start with https:// and match your app registration exactly.", parent=self)
            return
        try:
            self.pkce = generate_pkce_pair()
            self.oauth_state = secrets.token_urlsafe(16)
            url = build_authorization_url(client_id=keystring, redirect_uri=callback,
                                          code_challenge=self.pkce.challenge,
                                          state=self.oauth_state, scopes=DRAFT_SCOPES)
        except IntegrationError as exc:
            messagebox.showwarning("Check details", exc.message, parent=self)
            return
        self.keystring_value = keystring
        webbrowser.open(url)
        self.finish_button.configure(state="normal")
        self._set_result("The Etsy approval page opened in your browser.\n"
                         "Approve access, then copy the full address your browser lands on and paste it here.")

    def finish_connect(self) -> None:
        from integrations.etsy.auth import extract_state_and_code
        from integrations.errors import IntegrationError
        from integrations.etsy.session import (
            EtsyCredentials,
            exchange_authorization_code,
            save_credentials,
        )

        pasted = self.paste_var.get().strip()
        if not pasted or self.pkce is None:
            messagebox.showwarning("Not ready", "Open the approval page and approve access first, then paste the redirect URL.", parent=self)
            return
        state, code, error = extract_state_and_code(pasted)
        if error:
            self._set_result(f"Etsy reported: {error}. Nothing was saved; you can close this window or start again.")
            return
        if not code:
            messagebox.showwarning("That link looks incomplete", "Paste the full address from the browser address bar after approving (it contains ?code=…).", parent=self)
            return
        if not state or state != self.oauth_state:
            messagebox.showwarning("Start again", "This approval does not match the request that was opened. For safety, nothing was saved — press “Open Etsy approval page” and try once more.", parent=self)
            return
        shared_secret = self.vars["shared_secret"].get().strip()
        callback = self.vars["callback"].get().strip()
        self.finish_button.configure(state="disabled")
        self._set_result("Exchanging the approval code with Etsy…")

        def work():
            tokens = exchange_authorization_code(
                client_id=self.keystring_value,
                authorization_code=code,
                code_verifier=self.pkce.verifier,
                redirect_uri=callback,
            )
            save_credentials(EtsyCredentials(
                api_keystring=self.keystring_value,
                shared_secret=shared_secret,
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
            ))
            return tokens

        def runner():
            outcome = {}

            def execute():
                try:
                    outcome["tokens"] = work()
                except Exception as exc:  # classified or not, the UI must show it safely
                    outcome["error"] = exc
                self.after(0, done)

            threading.Thread(target=execute, daemon=True).start()

        def done():
            error = outcome.get("error")
            if error is not None:
                self.finish_button.configure(state="normal")
                if isinstance(error, IntegrationError):
                    self._set_result(f"Etsy refused the exchange ({error.message}). Nothing was changed.")
                else:
                    self._set_result(f"Unexpected problem: {error} Nothing was changed.")
                return
            tokens = outcome["tokens"]
            scope_note = f" Approved permissions: {tokens.scope}." if tokens.scope else ""
            self._set_result("Etsy connected successfully." + scope_note +
                             "\nDrafts can now be created from the Selected Book tab — publishing stays entirely in your hands.")
            if self.on_done:
                self.on_done()

        runner()
