"""
AutoCraft — POE1 Cluster Jewel Crafter
GUI entry point (tkinter)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import re
import csv
import subprocess

from src.crafter import CraftSession

CONFIG_FILE       = os.path.join(os.path.dirname(__file__), "config.json")
CLUSTER_MODS_FILE = os.path.join(os.path.dirname(__file__), "data", "cluster_mods.json")

CURRENCY_SLOTS = [
    ("transmutation", "Orb of Transmutation"),
    ("alteration",    "Orb of Alteration"),
    ("augmentation",  "Orb of Augmentation"),
    ("regal",         "Regal Orb"),
    ("exalted",       "Exalted Orb"),
    ("scouring",      "Orb of Scouring"),
]

# ── Palette ────────────────────────────────────────────────────────────────
BG       = "#0f172a"   # slate-900  — fond principal
SURFACE  = "#1e293b"   # slate-800  — cartes
SURFACE2 = "#334155"   # slate-700  — éléments surélevés
BORDER   = "#475569"   # slate-600  — bordures
TEXT     = "#f1f5f9"   # slate-100  — texte principal
MUTED    = "#94a3b8"   # slate-400  — texte secondaire
DIM      = "#64748b"   # slate-500  — texte très discret
INPUT    = "#0f172a"   # fond des champs
SEL      = "#4338ca"   # indigo-700 — sélection listbox
ACCENT   = "#818cf8"   # indigo-400 — accent / hover

BLUE     = "#60a5fa"   # blue-400   — préfixes
BLUE_BG  = "#0c1929"
BLUE_SEL = "#1e3a5f"
ORANGE   = "#fb923c"   # orange-400 — suffixes
ORANGE_BG = "#1a0d00"
ORANGE_SEL = "#4a2000"

BTN_START = "#166534"   # green-800
BTN_START_H = "#15803d"
BTN_STOP  = "#991b1b"   # red-800
BTN_STOP_H = "#b91c1c"
BTN_PAUSE = "#92400e"   # amber-800
BTN_PAUSE_H = "#b45309"

# ── Fonts ──────────────────────────────────────────────────────────────────
F_UI    = ("Segoe UI", 9)
F_BOLD  = ("Segoe UI", 9, "bold")
F_MONO  = ("Consolas", 9)
F_SMALL = ("Segoe UI", 8)
F_TITLE = ("Segoe UI", 10, "bold")


# ── Module-level helpers ───────────────────────────────────────────────────

def _win_cursor_pos():
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "Add-Type -AssemblyName System.Windows.Forms;"
             "$p=[System.Windows.Forms.Cursor]::Position;"
             "Write-Host \"$($p.X),$($p.Y)\""],
            capture_output=True, text=True, timeout=3,
        )
        x, y = result.stdout.strip().split(",")
        return int(x), int(y)
    except Exception:
        return 0, 0


def _capture_position_popup(parent_window, label, on_captured):
    win = tk.Toplevel(parent_window)
    win.title("Capture de position")
    win.geometry("320x90")
    win.resizable(False, False)
    win.attributes("-topmost", True)
    win.configure(bg=SURFACE)

    tk.Label(win, text=f"Placer la souris sur : {label}",
             bg=SURFACE, fg=TEXT, font=F_UI, wraplength=300).pack(pady=(14, 4))
    cd_var = tk.StringVar(value="Capture dans 3s…")
    tk.Label(win, textvariable=cd_var, bg=SURFACE, fg=ACCENT,
             font=("Segoe UI", 11, "bold")).pack()

    def do_countdown(n):
        if n > 0:
            cd_var.set(f"Capture dans {n}s…")
            win.after(1000, do_countdown, n - 1)
        else:
            x, y = _win_cursor_pos()
            on_captured(x, y)
            cd_var.set(f"✓  Capturé : ({x}, {y})")
            win.after(900, win.destroy)

    do_countdown(3)


# ── Application ────────────────────────────────────────────────────────────

class AutoCraftApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AutoCraft — POE1 Cluster Jewel")
        self.configure(bg=BG)
        self.minsize(740, 520)
        self.resizable(True, True)
        self._session = None

        self._csv_rows       = []
        self._csv_full_path  = ""
        self._pos_vars       = {}
        self._item_positions = []

        self._g_pos_vars       = {}
        self._g_item_positions = []
        self._g_enchants_data  = []
        self._g_prefix_data    = []
        self._g_suffix_data    = []

        self._cluster_mods_data = self._load_cluster_mods()

        self._setup_theme()
        self._build_ui()
        self._load_config()
        self._bind_hotkeys()

    # ── Theme ─────────────────────────────────────────────────────────────

    def _setup_theme(self):
        s = ttk.Style(self)
        s.theme_use("clam")

        s.configure(".",
            background=BG, foreground=TEXT, font=F_UI,
            troughcolor=SURFACE2, bordercolor=BORDER,
            darkcolor=SURFACE, lightcolor=SURFACE,
            relief="flat", focuscolor="")

        s.configure("TFrame",    background=BG)
        s.configure("TLabel",    background=BG, foreground=TEXT)
        s.configure("TPanedwindow", background=BG)

        # Notebook principal
        s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=[0, 0, 0, 0])
        s.configure("TNotebook.Tab",
            background=SURFACE, foreground=MUTED,
            padding=[18, 8], font=F_UI, borderwidth=0)
        s.map("TNotebook.Tab",
            background=[("selected", SURFACE2), ("active", SURFACE2)],
            foreground=[("selected", TEXT),     ("active",  TEXT)])

        # Scrollbar
        s.configure("TScrollbar",
            background=SURFACE2, troughcolor=SURFACE, borderwidth=0,
            arrowsize=10, arrowcolor=DIM, gripcount=0)
        s.map("TScrollbar",
            background=[("active", ACCENT), ("pressed", ACCENT)])

        # Separator
        s.configure("TSeparator", background=SURFACE2)

    # ── Widget factories ───────────────────────────────────────────────────

    def _btn(self, parent, text, cmd, style="normal", width=None, font=None):
        palettes = {
            "normal":   (SURFACE2, TEXT,        ACCENT,       TEXT),
            "capture":  ("#1e3a5f", "#93c5fd",  "#1e40af",    "#93c5fd"),
            "danger":   ("#4c0519", "#fda4af",  "#881337",    "#fda4af"),
            "ghost":    (SURFACE,   MUTED,       SURFACE2,     TEXT),
            "start":    (BTN_START, "#86efac",  BTN_START_H,  "#86efac"),
            "stop":     (BTN_STOP,  "#fca5a5",  BTN_STOP_H,   "#fca5a5"),
            "pause":    (BTN_PAUSE, "#fde68a",  BTN_PAUSE_H,  "#fde68a"),
        }
        bg, fg, hbg, hfg = palettes.get(style, palettes["normal"])
        kw = dict(
            text=text, command=cmd,
            bg=bg, fg=fg, relief="flat", bd=0,
            font=font or F_UI, cursor="hand2",
            padx=12, pady=6,
            activebackground=hbg, activeforeground=hfg,
        )
        if width:
            kw["width"] = width
        b = tk.Button(parent, **kw)
        b.bind("<Enter>", lambda e: b.config(bg=hbg, fg=hfg))
        b.bind("<Leave>", lambda e: b.config(bg=bg,  fg=fg))
        return b

    def _entry(self, parent, var, width=6, mono=True):
        return tk.Entry(
            parent, textvariable=var, width=width,
            bg=INPUT, fg=TEXT, insertbackground=TEXT,
            selectbackground=SEL, selectforeground=TEXT,
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=ACCENT,
            font=F_MONO if mono else F_UI,
        )

    def _listbox(self, parent, height=5, fg=TEXT, bg=None, sel_bg=None, **kw):
        return tk.Listbox(
            parent, height=height, font=F_MONO,
            bg=bg or INPUT, fg=fg,
            selectbackground=sel_bg or SEL, selectforeground=TEXT,
            activestyle="none", relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=ACCENT,
            **kw,
        )

    def _lbl(self, parent, text, fg=TEXT, font=None, bg=None):
        return tk.Label(parent, text=text, fg=fg,
                        bg=bg or parent.cget("bg"), font=font or F_UI)

    def _section(self, parent, title, accent=ACCENT):
        """Card sombre avec header titré et bande colorée sur le côté gauche."""
        outer = tk.Frame(parent, bg=SURFACE)
        outer.pack(fill="x", padx=10, pady=(0, 8))

        hdr = tk.Frame(outer, bg=SURFACE2, height=36)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=accent, width=4).pack(side="left", fill="y")
        tk.Label(hdr, text=title, bg=SURFACE2, fg=TEXT,
                 font=F_BOLD, padx=12).pack(side="left", fill="y")

        body = tk.Frame(outer, bg=SURFACE, padx=14, pady=10)
        body.pack(fill="x")
        return body

    def _scrollable(self, parent):
        """Canvas scrollable avec fond thémé. Retourne l'inner Frame."""
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=BG)
        cw = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cw, width=e.width))

        def _mw(ev):
            canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _mw))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        return inner

    def _currency_grid(self, parent, pos_vars, capture_fn):
        """6 slots en 2 colonnes de 3."""
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(anchor="w")

        col_l = tk.Frame(row, bg=SURFACE)
        col_r = tk.Frame(row, bg=SURFACE)
        col_l.pack(side="left", anchor="n")
        col_r.pack(side="left", anchor="n", padx=(24, 0))

        for i, (key, label) in enumerate(CURRENCY_SLOTS):
            frame = col_l if i < 3 else col_r
            ri    = i if i < 3 else i - 3
            xv, yv = tk.IntVar(value=0), tk.IntVar(value=0)
            pos_vars[key] = (xv, yv)

            tk.Label(frame, text=label, width=21, anchor="w",
                     bg=SURFACE, fg=MUTED, font=F_UI).grid(row=ri, column=0, pady=4, sticky="w")
            tk.Label(frame, text="X", bg=SURFACE, fg=DIM, font=F_SMALL).grid(row=ri, column=1, padx=(8, 2))
            self._entry(frame, xv, width=5).grid(row=ri, column=2)
            tk.Label(frame, text="Y", bg=SURFACE, fg=DIM, font=F_SMALL).grid(row=ri, column=3, padx=(6, 2))
            self._entry(frame, yv, width=5).grid(row=ri, column=4)
            self._btn(frame, "Capturer", lambda k=key: capture_fn(k),
                      style="capture").grid(row=ri, column=5, padx=(8, 0), pady=4)

    # ── UI principale ──────────────────────────────────────────────────────

    def _build_ui(self):
        notebook = self._notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        self._tab_crafts = tk.Frame(notebook, bg=BG)
        self._tab_log    = tk.Frame(notebook, bg=BG)
        notebook.add(self._tab_crafts, text="  Craft  ")
        notebook.add(self._tab_log,    text="  Log  ")

        self._crafts_notebook = ttk.Notebook(self._tab_crafts)
        self._crafts_notebook.pack(fill="both", expand=True, pady=(6, 0))

        self._tab_double = tk.Frame(self._crafts_notebook, bg=BG)
        self._tab_guided = tk.Frame(self._crafts_notebook, bg=BG)
        self._crafts_notebook.add(self._tab_double, text="  Double Passifs  ")
        self._crafts_notebook.add(self._tab_guided, text="  Cluster Guidé  ")

        self._build_double_tab()
        self._build_guided_tab()
        self._build_log_tab()
        self._build_bottom_bar()

    # ── Onglet Double Passifs ──────────────────────────────────────────────

    def _build_double_tab(self):
        inner = self._scrollable(self._tab_double)
        inner.pack_configure()

        # padding top
        tk.Frame(inner, bg=BG, height=8).pack()

        # ── Items ────────────────────────────────────────────────────────
        body = self._section(inner, "Items à crafter")

        lbf = tk.Frame(body, bg=SURFACE)
        lbf.pack(fill="x")
        self._item_pos_listbox = self._listbox(lbf, height=3)
        isc = ttk.Scrollbar(lbf, command=self._item_pos_listbox.yview)
        self._item_pos_listbox.configure(yscrollcommand=isc.set)
        self._item_pos_listbox.pack(side="left", fill="both", expand=True)
        isc.pack(side="right", fill="y")

        bf = tk.Frame(body, bg=SURFACE)
        bf.pack(anchor="w", pady=(8, 0))
        self._btn(bf, "+ Ajouter",    self._add_item_position).pack(side="left", padx=(0, 6))
        self._btn(bf, "− Supprimer",  self._remove_item_position, style="danger").pack(side="left")

        # ── Currencies ───────────────────────────────────────────────────
        body = self._section(inner, "Currencies  ·  clic → 3s → capture souris")
        self._currency_grid(body, self._pos_vars, self._capture_position)

        # ── CSV ──────────────────────────────────────────────────────────
        body = self._section(inner, "Combinaisons CSV", accent="#f59e0b")

        top = tk.Frame(body, bg=SURFACE)
        top.pack(fill="x", pady=(0, 8))
        self._csv_path_var = tk.StringVar(value="")
        self._entry(top, self._csv_path_var, width=36, mono=False).pack(side="left", padx=(0, 8))
        self._btn(top, "Charger CSV", self._load_csv).pack(side="left", padx=(0, 6))
        self._btn(top, "Effacer",     self._clear_csv, style="danger").pack(side="left")

        lbf2 = tk.Frame(body, bg=SURFACE)
        lbf2.pack(fill="x")
        self._csv_listbox = self._listbox(lbf2, height=4, selectmode="single")
        csc = ttk.Scrollbar(lbf2, command=self._csv_listbox.yview)
        self._csv_listbox.configure(yscrollcommand=csc.set)
        self._csv_listbox.pack(side="left", fill="both", expand=True)
        csc.pack(side="right", fill="y")
        self._csv_listbox.bind("<<ListboxSelect>>", self._on_csv_select)
        tk.Label(body, text="Cliquer une ligne pour pré-remplir les Notables",
                 bg=SURFACE, fg=DIM, font=F_SMALL).pack(anchor="w", pady=(6, 0))

        # ── Notables ─────────────────────────────────────────────────────
        body = self._section(inner, "Notables requis  ·  nom exact, un par ligne")

        self._notables_text = tk.Text(
            body, height=4, font=F_MONO,
            bg=INPUT, fg=TEXT, insertbackground=TEXT,
            selectbackground=SEL, selectforeground=TEXT,
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        self._notables_text.pack(fill="x")

        self._notables_warning_var = tk.StringVar(value="")
        tk.Label(body, textvariable=self._notables_warning_var,
                 bg=SURFACE, fg="#fbbf24", font=F_SMALL).pack(anchor="w", pady=(4, 0))
        tk.Label(body, text="Ex : Rote Reinforcement, Herculean Form, …",
                 bg=SURFACE, fg=DIM, font=F_SMALL).pack(anchor="w")

        # ── Options ──────────────────────────────────────────────────────
        body = self._section(inner, "Options")

        self._delay_min = tk.DoubleVar(value=0.15)
        self._delay_max = tk.DoubleVar(value=0.45)
        self._max_iter  = tk.IntVar(value=5000)

        rf = tk.Frame(body, bg=SURFACE)
        rf.pack(anchor="w")
        tk.Label(rf, text="Délai", bg=SURFACE, fg=MUTED, font=F_UI).pack(side="left")
        self._entry(rf, self._delay_min, width=5).pack(side="left", padx=(8, 0))
        tk.Label(rf, text="s  →", bg=SURFACE, fg=DIM, font=F_UI).pack(side="left", padx=4)
        self._entry(rf, self._delay_max, width=5).pack(side="left")
        tk.Label(rf, text="s", bg=SURFACE, fg=DIM, font=F_UI).pack(side="left", padx=(4, 24))
        tk.Label(rf, text="Itérations max", bg=SURFACE, fg=MUTED, font=F_UI).pack(side="left")
        self._entry(rf, self._max_iter, width=7).pack(side="left", padx=(8, 0))

        tk.Frame(inner, bg=BG, height=12).pack()

    # ── Onglet Cluster Guidé ───────────────────────────────────────────────

    def _build_guided_tab(self):
        inner = self._scrollable(self._tab_guided)

        tk.Frame(inner, bg=BG, height=8).pack()

        # ── Taille ───────────────────────────────────────────────────────
        body = self._section(inner, "Taille de cluster", accent="#a78bfa")

        self._g_size_var = tk.StringVar(value="Medium")
        sz = tk.Frame(body, bg=SURFACE)
        sz.pack(anchor="w")
        for size in ("Large", "Medium", "Small"):
            tk.Radiobutton(
                sz, text=size, variable=self._g_size_var, value=size,
                command=self._on_guided_size_change,
                bg=SURFACE, fg=TEXT, selectcolor=INPUT,
                activebackground=SURFACE, activeforeground=ACCENT,
                font=F_UI, cursor="hand2",
                indicatoron=True,
            ).pack(side="left", padx=(0, 20))

        # ── Enchant ──────────────────────────────────────────────────────
        body = self._section(inner, "Enchant  ·  implicit du cluster", accent="#38bdf8")

        ef = tk.Frame(body, bg=SURFACE)
        ef.pack(fill="x")
        self._g_enchant_listbox = self._listbox(ef, height=6, sel_bg="#1e3a5f", fg=TEXT)
        esc = ttk.Scrollbar(ef, command=self._g_enchant_listbox.yview)
        self._g_enchant_listbox.configure(yscrollcommand=esc.set)
        self._g_enchant_listbox.pack(side="left", fill="both", expand=True)
        esc.pack(side="right", fill="y")
        self._g_enchant_listbox.bind("<<ListboxSelect>>", self._on_guided_enchant_select)

        # ── Notables ─────────────────────────────────────────────────────
        body = self._section(inner, "Notables à cibler  ·  Ctrl+clic pour sélection multiple", accent=ACCENT)

        cols = tk.Frame(body, bg=SURFACE)
        cols.pack(fill="x")
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(2, weight=1)

        # Préfixes
        pf = tk.Frame(cols, bg=SURFACE)
        pf.grid(row=0, column=0, sticky="nsew")
        hpf = tk.Frame(pf, bg=BLUE_BG, height=28)
        hpf.pack(fill="x")
        hpf.pack_propagate(False)
        tk.Frame(hpf, bg=BLUE, width=3).pack(side="left", fill="y")
        tk.Label(hpf, text="Préfixes", bg=BLUE_BG, fg=BLUE,
                 font=F_BOLD, padx=10).pack(side="left", fill="y")
        pf_inner = tk.Frame(pf, bg=SURFACE)
        pf_inner.pack(fill="both", expand=True, pady=(4, 0))
        self._g_prefix_listbox = self._listbox(
            pf_inner, height=9, fg=BLUE, bg=BLUE_BG, sel_bg=BLUE_SEL,
            selectmode="multiple")
        ps = ttk.Scrollbar(pf_inner, command=self._g_prefix_listbox.yview)
        self._g_prefix_listbox.configure(yscrollcommand=ps.set)
        self._g_prefix_listbox.pack(side="left", fill="both", expand=True)
        ps.pack(side="right", fill="y")

        tk.Frame(cols, bg=BORDER, width=1).grid(row=0, column=1, sticky="ns", padx=8)

        # Suffixes
        sf = tk.Frame(cols, bg=SURFACE)
        sf.grid(row=0, column=2, sticky="nsew")
        hsf = tk.Frame(sf, bg=ORANGE_BG, height=28)
        hsf.pack(fill="x")
        hsf.pack_propagate(False)
        tk.Frame(hsf, bg=ORANGE, width=3).pack(side="left", fill="y")
        tk.Label(hsf, text="Suffixes", bg=ORANGE_BG, fg=ORANGE,
                 font=F_BOLD, padx=10).pack(side="left", fill="y")
        sf_inner = tk.Frame(sf, bg=SURFACE)
        sf_inner.pack(fill="both", expand=True, pady=(4, 0))
        self._g_suffix_listbox = self._listbox(
            sf_inner, height=9, fg=ORANGE, bg=ORANGE_BG, sel_bg=ORANGE_SEL,
            selectmode="multiple")
        ss = ttk.Scrollbar(sf_inner, command=self._g_suffix_listbox.yview)
        self._g_suffix_listbox.configure(yscrollcommand=ss.set)
        self._g_suffix_listbox.pack(side="left", fill="both", expand=True)
        ss.pack(side="right", fill="y")

        # ── Positions ────────────────────────────────────────────────────
        body = self._section(inner, "Positions", accent="#34d399")

        # Items
        tk.Label(body, text="Items à crafter",
                 bg=SURFACE, fg=MUTED, font=F_BOLD).pack(anchor="w", pady=(0, 6))
        ipf = tk.Frame(body, bg=SURFACE)
        ipf.pack(fill="x")
        self._g_item_pos_listbox = self._listbox(ipf, height=3)
        gisc = ttk.Scrollbar(ipf, command=self._g_item_pos_listbox.yview)
        self._g_item_pos_listbox.configure(yscrollcommand=gisc.set)
        self._g_item_pos_listbox.pack(side="left", fill="both", expand=True)
        gisc.pack(side="right", fill="y")

        ibf = tk.Frame(body, bg=SURFACE)
        ibf.pack(anchor="w", pady=(6, 14))
        self._btn(ibf, "+ Ajouter",   self._g_add_item_position).pack(side="left", padx=(0, 6))
        self._btn(ibf, "− Supprimer", self._g_remove_item_position, style="danger").pack(side="left")

        # Séparateur
        tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=(0, 12))

        # Currencies
        tk.Label(body, text="Currencies  ·  clic → 3s → capture souris",
                 bg=SURFACE, fg=MUTED, font=F_BOLD).pack(anchor="w", pady=(0, 8))
        self._currency_grid(body, self._g_pos_vars, self._g_capture_position)

        # ── Options ──────────────────────────────────────────────────────
        body = self._section(inner, "Options")

        self._g_delay_min = tk.DoubleVar(value=0.15)
        self._g_delay_max = tk.DoubleVar(value=0.45)
        self._g_max_iter  = tk.IntVar(value=5000)

        rf = tk.Frame(body, bg=SURFACE)
        rf.pack(anchor="w")
        tk.Label(rf, text="Délai", bg=SURFACE, fg=MUTED, font=F_UI).pack(side="left")
        self._entry(rf, self._g_delay_min, width=5).pack(side="left", padx=(8, 0))
        tk.Label(rf, text="s  →", bg=SURFACE, fg=DIM, font=F_UI).pack(side="left", padx=4)
        self._entry(rf, self._g_delay_max, width=5).pack(side="left")
        tk.Label(rf, text="s", bg=SURFACE, fg=DIM, font=F_UI).pack(side="left", padx=(4, 24))
        tk.Label(rf, text="Itérations max", bg=SURFACE, fg=MUTED, font=F_UI).pack(side="left")
        self._entry(rf, self._g_max_iter, width=7).pack(side="left", padx=(8, 0))

        tk.Frame(inner, bg=BG, height=12).pack()

        self._on_guided_size_change()

    # ── Onglet Log ─────────────────────────────────────────────────────────

    def _build_log_tab(self):
        parent = self._tab_log

        self._log_text = tk.Text(
            parent, state="disabled", font=F_MONO,
            bg="#0a0f1a", fg="#d4d4d4",
            insertbackground=TEXT,
            selectbackground=SEL, selectforeground=TEXT,
            relief="flat", bd=0,
            highlightthickness=0,
            width=72, height=24)
        scroll = ttk.Scrollbar(parent, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scroll.set)
        self._log_text.bind("<1>", lambda e: self._log_text.focus_set())
        self._log_text.bind("<Control-c>", self._copy_log_selection)

        scroll.pack(side="right", fill="y", pady=8, padx=(0, 8))
        self._log_text.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)

        bar = tk.Frame(parent, bg=BG)
        bar.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        self._btn(bar, "Copier tout", self._copy_log_all).pack(side="right")
        self._btn(bar, "Vider",       self._clear_log, style="danger").pack(side="right", padx=(0, 6))

    # ── Barre du bas ───────────────────────────────────────────────────────

    def _build_bottom_bar(self):
        bar = tk.Frame(self, bg=SURFACE2)
        bar.pack(fill="x", padx=0, pady=0, side="bottom")

        # ligne de séparation en haut de la barre
        tk.Frame(bar, bg=BORDER, height=1).pack(fill="x")

        inner = tk.Frame(bar, bg=SURFACE2)
        inner.pack(fill="x", padx=10, pady=8)

        self._btn_start = self._btn(
            inner, "▶  Démarrer  [F5]", self._start,
            style="start", width=18, font=F_BOLD)
        self._btn_stop  = self._btn(
            inner, "■  Arrêter  [F6]",  self._stop,
            style="stop",  width=16)
        self._btn_pause = self._btn(
            inner, "⏸  Pause  [F7]",    self._toggle_pause,
            style="pause", width=16)

        self._btn_start.pack(side="left", padx=(0, 6))
        self._btn_stop.pack(side="left",  padx=(0, 6))
        self._btn_pause.pack(side="left")
        self._btn_pause.config(state="disabled")

        self._status_var = tk.StringVar(value="En attente")
        tk.Label(inner, textvariable=self._status_var,
                 bg=SURFACE2, fg=DIM, font=F_SMALL).pack(side="right", padx=(6, 0))
        self._btn(inner, "Tester clipboard",   self._test_clipboard,
                  style="ghost").pack(side="right", padx=(0, 6))
        self._btn(inner, "Sauvegarder config", self._save_config,
                  style="ghost").pack(side="right", padx=(0, 6))

    # ── Callbacks Cluster Guidé ────────────────────────────────────────────

    def _on_guided_size_change(self):
        size = self._g_size_var.get()
        self._g_enchants_data = self._cluster_mods_data.get(size, [])
        self._g_enchant_listbox.delete(0, "end")
        for enchant in self._g_enchants_data:
            lines = enchant.get("enchant_text", [])
            text = " / ".join(l for l in lines if l)
            text = re.sub(r'(\d+)\s+%', r'\1%', text)
            self._g_enchant_listbox.insert("end", "  " + (text or enchant["enchant_slug"]))
        self._g_prefix_listbox.delete(0, "end")
        self._g_suffix_listbox.delete(0, "end")
        self._g_prefix_data = []
        self._g_suffix_data = []

    def _on_guided_enchant_select(self, event=None):
        sel = self._g_enchant_listbox.curselection()
        if not sel:
            return
        enchant  = self._g_enchants_data[sel[0]]
        notables = enchant.get("notables", [])

        self._g_prefix_listbox.delete(0, "end")
        self._g_suffix_listbox.delete(0, "end")
        self._g_prefix_data = []
        self._g_suffix_data = []

        for n in notables:
            label = f"  {n['name']}  (w:{n['weight']} lv:{n['level']})"
            if n.get("type") == "Prefix":
                self._g_prefix_listbox.insert("end", label)
                self._g_prefix_data.append(n["name"])
            else:
                self._g_suffix_listbox.insert("end", label)
                self._g_suffix_data.append(n["name"])

    # ── Capture positions — Onglet 1 ───────────────────────────────────────

    def _capture_position(self, key):
        label = next(l for k, l in CURRENCY_SLOTS if k == key)
        def on_captured(x, y):
            self._pos_vars[key][0].set(x)
            self._pos_vars[key][1].set(y)
        _capture_position_popup(self, label, on_captured)

    def _add_item_position(self):
        idx = len(self._item_positions) + 1
        def on_captured(x, y):
            self._item_positions.append((x, y))
            self._item_pos_listbox.insert("end", f"  Item {len(self._item_positions)}   ({x}, {y})")
        _capture_position_popup(self, f"Item {idx}", on_captured)

    def _remove_item_position(self):
        sel = self._item_pos_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self._item_pos_listbox.delete(idx)
        self._item_positions.pop(idx)
        self._item_pos_listbox.delete(0, "end")
        for i, (x, y) in enumerate(self._item_positions):
            self._item_pos_listbox.insert("end", f"  Item {i+1}   ({x}, {y})")

    # ── Capture positions — Onglet 2 ───────────────────────────────────────

    def _g_capture_position(self, key):
        label = next(l for k, l in CURRENCY_SLOTS if k == key)
        def on_captured(x, y):
            self._g_pos_vars[key][0].set(x)
            self._g_pos_vars[key][1].set(y)
        _capture_position_popup(self, label, on_captured)

    def _g_add_item_position(self):
        idx = len(self._g_item_positions) + 1
        def on_captured(x, y):
            self._g_item_positions.append((x, y))
            self._g_item_pos_listbox.insert("end", f"  Item {len(self._g_item_positions)}   ({x}, {y})")
        _capture_position_popup(self, f"Item {idx}", on_captured)

    def _g_remove_item_position(self):
        sel = self._g_item_pos_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self._g_item_pos_listbox.delete(idx)
        self._g_item_positions.pop(idx)
        self._g_item_pos_listbox.delete(0, "end")
        for i, (x, y) in enumerate(self._g_item_positions):
            self._g_item_pos_listbox.insert("end", f"  Item {i+1}   ({x}, {y})")

    # ── Start / Stop / Pause ───────────────────────────────────────────────

    def _start(self):
        active = self._crafts_notebook.index(self._crafts_notebook.select())
        if active == 0:
            if not self._validate():
                return
            cfg = self._build_config()
        else:
            if not self._validate_guided():
                return
            cfg = self._build_guided_config()

        self._save_config()
        self._session = CraftSession(
            config=cfg,
            log_callback=self._append_log,
            status_callback=lambda s: self._status_var.set(s),
        )
        self._session.start()
        self._btn_start.config(state="disabled")
        self._btn_pause.config(state="normal", text="⏸  Pause  [F7]")
        self._notebook.select(self._tab_log)
        self._window_was_unfocused = False
        self._poll_session()
        self._poll_window_focus()

    def _stop(self):
        if self._session:
            self._session.stop()
        self._btn_start.config(state="normal")
        self._btn_pause.config(state="disabled", text="⏸  Pause  [F7]")

    def _toggle_pause(self):
        if not self._session:
            return
        if self._session.is_paused():
            self._session.resume()
            self._btn_pause.config(text="⏸  Pause  [F7]")
            self._status_var.set("Running")
        else:
            self._session.pause()
            self._btn_pause.config(text="▶  Reprendre [F7]")
            self._status_var.set("En pause")

    def _poll_window_focus(self):
        if not (self._session and self._session.is_running()):
            return
        has_focus = self.focus_displayof() is not None
        if not has_focus:
            self._window_was_unfocused = True
        elif self._window_was_unfocused:
            self._stop()
            return
        self.after(250, self._poll_window_focus)

    def _poll_session(self):
        if self._session and self._session.is_running():
            self.after(500, self._poll_session)
        else:
            self._btn_start.config(state="normal")
            self._btn_pause.config(state="disabled", text="⏸  Pause  [F7]")

    # ── Validation & config — Onglet 1 ────────────────────────────────────

    def _validate(self):
        notables = self._get_notables()
        if not self._csv_rows and not notables:
            messagebox.showerror("Erreur", "Ajoute au moins un Notable requis.")
            return False
        if not self._item_positions:
            messagebox.showerror("Erreur", "Ajoute au moins une position d'item.")
            return False
        for k, label in CURRENCY_SLOTS:
            x, y = self._pos_vars[k][0].get(), self._pos_vars[k][1].get()
            if x == 0 and y == 0:
                if not messagebox.askyesno("Position manquante",
                                           f"La position « {label} » est (0, 0).\nContinuer quand même ?"):
                    return False
        return True

    def _build_config(self):
        positions = {k: (self._pos_vars[k][0].get(), self._pos_vars[k][1].get()) for k, _ in CURRENCY_SLOTS}
        manual = self._get_notables()
        if self._csv_rows:
            all_notables = list({n for combo in self._csv_rows for n in combo})
            combinations = self._csv_rows
        else:
            all_notables = manual
            combinations = [manual] if manual else []
        return {
            "positions":             positions,
            "item_positions":        self._item_positions,
            "required_notables":     all_notables,
            "required_combinations": combinations,
            "delay_min":             self._delay_min.get(),
            "delay_max":             self._delay_max.get(),
            "max_iterations":        self._max_iter.get(),
        }

    def _get_notables(self):
        raw = self._notables_text.get("1.0", "end").strip()
        return [l.strip() for l in raw.splitlines() if l.strip()]

    # ── Validation & config — Onglet 2 ────────────────────────────────────

    def _validate_guided(self):
        if not self._g_prefix_listbox.curselection() and not self._g_suffix_listbox.curselection():
            messagebox.showerror("Erreur", "Sélectionne au moins un notable.")
            return False
        if not self._g_item_positions:
            messagebox.showerror("Erreur", "Ajoute au moins une position d'item.")
            return False
        for k, label in CURRENCY_SLOTS:
            x, y = self._g_pos_vars[k][0].get(), self._g_pos_vars[k][1].get()
            if x == 0 and y == 0:
                if not messagebox.askyesno("Position manquante",
                                           f"La position « {label} » est (0, 0).\nContinuer quand même ?"):
                    return False
        return True

    def _build_guided_config(self):
        positions  = {k: (self._g_pos_vars[k][0].get(), self._g_pos_vars[k][1].get()) for k, _ in CURRENCY_SLOTS}
        prefix_sel = self._g_prefix_listbox.curselection()
        suffix_sel = self._g_suffix_listbox.curselection()
        selected   = ([self._g_prefix_data[i] for i in prefix_sel] +
                      [self._g_suffix_data[i]  for i in suffix_sel])
        return {
            "positions":             positions,
            "item_positions":        self._g_item_positions,
            "required_notables":     selected,
            "required_combinations": [selected] if selected else [],
            "delay_min":             self._g_delay_min.get(),
            "delay_max":             self._g_delay_max.get(),
            "max_iterations":        self._g_max_iter.get(),
        }

    # ── CSV helpers ────────────────────────────────────────────────────────

    def _load_csv(self):
        path = filedialog.askopenfilename(
            title="Charger un CSV de combinaisons",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self._load_csv_from_path(path)

    def _load_csv_from_path(self, path):
        try:
            self._csv_rows = []
            self._csv_listbox.delete(0, "end")
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    notables = [row.get(c, "").strip() for c in ("Notable1", "Notable2", "Notable3")]
                    notables = [n for n in notables if n]
                    if not notables:
                        continue
                    passives = row.get("Passives", "").strip()
                    avg      = row.get("AvgChaos", "").strip()
                    label    = "  " + " + ".join(notables)
                    if passives: label += f"  [{passives}]"
                    if avg:      label += f"  ~{avg}c"
                    self._csv_rows.append(notables)
                    self._csv_listbox.insert("end", label)
            self._csv_path_var.set(os.path.basename(path))
            self._csv_full_path = path
            self._notables_warning_var.set("⚠  CSV chargé — section Notables ignorée")
            self._notables_text.configure(state="disabled", bg="#1a1a0a")
        except Exception as e:
            messagebox.showerror("Erreur CSV", str(e))

    def _clear_csv(self):
        self._csv_rows = []
        self._csv_listbox.delete(0, "end")
        self._csv_path_var.set("")
        self._csv_full_path = ""
        self._notables_warning_var.set("")
        self._notables_text.configure(state="normal", bg=INPUT)

    def _on_csv_select(self, event):
        sel = self._csv_listbox.curselection()
        if not sel:
            return
        notables = self._csv_rows[sel[0]]
        self._notables_text.delete("1.0", "end")
        self._notables_text.insert("1.0", "\n".join(notables))

    # ── Persistence ────────────────────────────────────────────────────────

    def _save_config(self):
        data = {
            "positions":      {k: [self._pos_vars[k][0].get(), self._pos_vars[k][1].get()] for k, _ in CURRENCY_SLOTS},
            "item_positions":  [(x, y) for x, y in self._item_positions],
            "notables":        self._get_notables(),
            "csv_path":        self._csv_full_path,
            "delay_min":       self._delay_min.get(),
            "delay_max":       self._delay_max.get(),
            "max_iterations":  self._max_iter.get(),
            "guided": {
                "size":          self._g_size_var.get(),
                "positions":     {k: [self._g_pos_vars[k][0].get(), self._g_pos_vars[k][1].get()] for k, _ in CURRENCY_SLOTS},
                "item_positions": [(x, y) for x, y in self._g_item_positions],
                "delay_min":      self._g_delay_min.get(),
                "delay_max":      self._g_delay_max.get(),
                "max_iterations": self._g_max_iter.get(),
            },
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def _load_config(self):
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)

            for k, _ in CURRENCY_SLOTS:
                if k in data.get("positions", {}):
                    x, y = data["positions"][k]
                    self._pos_vars[k][0].set(x)
                    self._pos_vars[k][1].set(y)
            if "item_positions" in data:
                self._item_positions = [tuple(p) for p in data["item_positions"]]
                self._item_pos_listbox.delete(0, "end")
                for i, (x, y) in enumerate(self._item_positions):
                    self._item_pos_listbox.insert("end", f"  Item {i+1}   ({x}, {y})")
            csv_path = data.get("csv_path", "")
            if csv_path and os.path.exists(csv_path):
                self._load_csv_from_path(csv_path)
            if "notables" in data:
                self._notables_text.insert("1.0", "\n".join(data["notables"]))
            self._delay_min.set(data.get("delay_min", 0.15))
            self._delay_max.set(data.get("delay_max", 0.45))
            self._max_iter.set(data.get("max_iterations", 5000))

            guided = data.get("guided", {})
            if guided:
                if "size" in guided:
                    self._g_size_var.set(guided["size"])
                    self._on_guided_size_change()
                for k, _ in CURRENCY_SLOTS:
                    if k in guided.get("positions", {}):
                        x, y = guided["positions"][k]
                        self._g_pos_vars[k][0].set(x)
                        self._g_pos_vars[k][1].set(y)
                if "item_positions" in guided:
                    self._g_item_positions = [tuple(p) for p in guided["item_positions"]]
                    self._g_item_pos_listbox.delete(0, "end")
                    for i, (x, y) in enumerate(self._g_item_positions):
                        self._g_item_pos_listbox.insert("end", f"  Item {i+1}   ({x}, {y})")
                self._g_delay_min.set(guided.get("delay_min", 0.15))
                self._g_delay_max.set(guided.get("delay_max", 0.45))
                self._g_max_iter.set(guided.get("max_iterations", 5000))
        except Exception:
            pass

    # ── Log ────────────────────────────────────────────────────────────────

    def _append_log(self, msg):
        def _do():
            self._log_text.configure(state="normal")
            self._log_text.insert("end", msg + "\n")
            self._log_text.see("end")
            self._log_text.configure(state="disabled")
        self.after(0, _do)

    def _clear_log(self):
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    def _copy_log_selection(self, event=None):
        try:
            text = self._log_text.get("sel.first", "sel.last")
        except tk.TclError:
            text = self._log_text.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(text)
        return "break"

    def _copy_log_all(self):
        self.clipboard_clear()
        self.clipboard_append(self._log_text.get("1.0", "end"))

    def _test_clipboard(self):
        text = ""
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=2
            )
            text = result.stdout.strip()
        except Exception:
            pass
        self._append_log("=== Test clipboard ===")
        if text:
            self._append_log(text)
        else:
            self._append_log("(clipboard vide ou illisible)")
        from src.item_parser import parse_item_text
        item = parse_item_text(text)
        if item:
            self._append_log(f"→ Item détecté : {item.rarity} | {item.name}")
            self._append_log(f"  Mods : {item.all_mods}")
        else:
            self._append_log("→ Non reconnu comme item POE")

    # ── Hotkeys ────────────────────────────────────────────────────────────

    def _bind_hotkeys(self):
        try:
            from pynput import keyboard

            def on_press(key):
                try:
                    if key == keyboard.Key.f5:
                        self.after(0, self._start)
                    elif key == keyboard.Key.f6:
                        self.after(0, self._stop)
                    elif key == keyboard.Key.f7:
                        self.after(0, self._toggle_pause)
                except Exception:
                    pass

            listener = keyboard.Listener(on_press=on_press)
            listener.daemon = True
            listener.start()
        except Exception:
            pass

    # ── Data ───────────────────────────────────────────────────────────────

    def _load_cluster_mods(self):
        if os.path.exists(CLUSTER_MODS_FILE):
            try:
                with open(CLUSTER_MODS_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = AutoCraftApp()
    app.mainloop()
