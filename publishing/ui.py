"""Tkinter Publishing Manager UI kept out of the puzzle creator module."""
from __future__ import annotations

import os
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from .database import MARKETPLACES
from .marketplaces import PUBLISHERS
from .etsy_bundles import ETSY_STORE_NAME

DISPLAY = {"amazon": "Amazon", "etsy": "Etsy", "ingram": "Ingram", "website": "Website", "lulu": "Lulu", "bookvault": "BookVault", "barnes_noble": "B&N"}
STATUS_VALUES = ("Not Prepared", "Ready", "Uploaded", "Published", "Error", "Needs Review")


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

    def _build(self) -> None:
        root = ttk.Frame(self, padding=(24, 20), style="Publish.TFrame"); root.pack(fill="both", expand=True); root.columnconfigure(0, weight=1); root.rowconfigure(4, weight=1)
        heading = ttk.Frame(root, style="Publish.TFrame"); heading.grid(row=0, column=0, sticky="ew"); heading.columnconfigure(0, weight=1)
        ttk.Label(heading, text="Publishing Manager", style="Publish.Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(heading, text="Upload status", command=self.open_upload_status, style="Publish.Action.TButton").grid(row=0, column=1, sticky="e", padx=(0, 8))
        ttk.Button(heading, text="Create Etsy bundle", command=self.open_etsy_bundle_builder, style="Publish.Action.TButton").grid(row=0, column=2, sticky="e", padx=(0, 8))
        ttk.Button(heading, text="New book", command=self.start_new_book, style="Publish.Primary.TButton").grid(row=0, column=3, sticky="e")
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
        filters = ttk.Frame(root, style="Publish.TFrame"); filters.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(filters, text="Find a book", style="Publish.TLabel").pack(side="left"); search = ttk.Entry(filters, textvariable=self.filter_text, width=34, style="Publish.TEntry"); search.pack(side="left", padx=(7, 16)); search.bind("<KeyRelease>", lambda _event: self.refresh())
        ttk.Label(filters, text="Marketplace", style="Publish.TLabel").pack(side="left"); combo = ttk.Combobox(filters, textvariable=self.market_filter, values=("All marketplaces", *[DISPLAY[key] for key in MARKETPLACES]), state="readonly", width=16, style="Publish.TCombobox"); combo.pack(side="left", padx=7); combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        ttk.Button(filters, text="Scan prepared folders", command=self.scan_local_status, style="Publish.Action.TButton").pack(side="right")
        ttk.Button(filters, text="Sync catalog", command=lambda: self.refresh(sync=True), style="Publish.Action.TButton").pack(side="right", padx=(0, 6))
        columns = ("book", "series", "theme", "pages", "isbn", *MARKETPLACES, "updated")
        self.tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="extended", style="Publish.Treeview")
        labels = {"book": "Book", "series": "Series", "theme": "Theme", "pages": "Pages", "isbn": "ISBN", "updated": "Last Updated", **DISPLAY}
        widths = {"book": 220, "series": 130, "theme": 115, "pages": 55, "isbn": 110, "updated": 125, **{key: 92 for key in MARKETPLACES}}
        for key in columns: self.tree.heading(key, text=labels[key]); self.tree.column(key, width=widths[key], anchor="w" if key in ("book", "series", "theme") else "center")
        self.tree.grid(row=4, column=0, sticky="nsew"); scroll = ttk.Scrollbar(root, orient="vertical", command=self.tree.yview); scroll.grid(row=4, column=1, sticky="ns"); self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<Double-1>", lambda _event: self.open_book())
        actions = ttk.Frame(root, style="Publish.TFrame"); actions.grid(row=5, column=0, sticky="ew", pady=(12, 0))
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
        ttk.Label(root, textvariable=self.status, wraplength=1150, style="Publish.Status.TLabel").grid(row=6, column=0, sticky="ew", pady=(10, 0))

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
        ready = sum(1 for _book, _market, status in report if status == "Ready")
        if ready == len(report):
            self.status.set(f"Prepared {ready} marketplace package(s). Your selected book files and listing information are ready to review.")
            return
        names = ", ".join(book["metadata"].get("title", "This book") for book in books[:2])
        self.status.set(f"Nothing was created for {names} because the print package is incomplete. Select the book and choose “Why not KDP ready?” for the exact fix. Do not delete anything.")

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
    def __init__(self, parent, service, book: dict, on_saved) -> None:
        super().__init__(parent); self.service, self.book, self.on_saved = service, book, on_saved
        self.title("Upload status"); self.geometry("850x590"); self.minsize(700, 500); self.configure(background="#1f1f1f"); self.transient(parent)
        self.marketplace = tk.StringVar(value="amazon"); self.status_value = tk.StringVar(); self.external_id = tk.StringVar(); self.url = tk.StringVar(); self.updated = tk.StringVar()
        self._build(); self._load_record()

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
