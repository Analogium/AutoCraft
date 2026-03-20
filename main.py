"""
AutoCraft — POE1 Cluster Jewel Crafter
GUI entry point (tkinter)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json
import os
import time
import csv

from src.crafter import CraftSession

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

CURRENCY_SLOTS = [
    ("transmutation", "Orb of Transmutation"),
    ("alteration",    "Orb of Alteration"),
    ("augmentation",  "Orb of Augmentation"),
    ("regal",         "Regal Orb"),
    ("exalted",       "Exalted Orb"),
    ("scouring",      "Orb of Scouring"),
]


class AutoCraftApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AutoCraft — POE1 Cluster Jewel")
        self.resizable(False, False)
        self._session: CraftSession | None = None
        self._csv_rows: list = []
        self._csv_full_path: str = ""

        # Position vars: slot_key -> (x_var, y_var)
        self._pos_vars: dict[str, tuple[tk.IntVar, tk.IntVar]] = {}
        self._item_positions: list = []

        self._build_ui()
        self._load_config()
        self._bind_hotkeys()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        notebook = self._notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self._tab_crafts = ttk.Frame(notebook)
        self._tab_log    = ttk.Frame(notebook)
        notebook.add(self._tab_crafts, text="  Craft  ")
        notebook.add(self._tab_log,    text="  Log  ")

        # Sub-notebook for craft modes
        self._crafts_notebook = ttk.Notebook(self._tab_crafts)
        self._crafts_notebook.pack(fill="both", expand=True)

        self._tab_double_cluster = ttk.Frame(self._crafts_notebook)
        self._crafts_notebook.add(self._tab_double_cluster,
                                  text="  Double Passifs Cluster Craft  ")

        self._build_config_tab()
        self._build_log_tab()
        self._build_bottom_bar()

    # ---- Config tab --------------------------------------------------

    def _build_config_tab(self):
        parent = self._tab_double_cluster
        row = 0

        # --- Item positions section ---
        ttk.Label(parent, text="Positions des items à crafter",
                  font=("Segoe UI", 9, "bold")).grid(
            row=row, column=0, columnspan=6, sticky="w", padx=8, pady=(10, 2))
        row += 1

        self._item_pos_listbox = tk.Listbox(parent, width=30, height=4,
                                             font=("Consolas", 8), activestyle="dotbox")
        item_scroll = ttk.Scrollbar(parent, orient="vertical", command=self._item_pos_listbox.yview)
        self._item_pos_listbox.configure(yscrollcommand=item_scroll.set)
        self._item_pos_listbox.grid(row=row, column=0, columnspan=4, padx=(12, 0), pady=2, sticky="w")
        item_scroll.grid(row=row, column=4, pady=2, sticky="ns")
        row += 1

        ttk.Button(parent, text="Ajouter position",
                   command=self._add_item_position).grid(row=row, column=0, columnspan=2,
                                                           padx=(12, 4), pady=2, sticky="w")
        ttk.Button(parent, text="Supprimer",
                   command=self._remove_item_position).grid(row=row, column=2, padx=4,
                                                              pady=2, sticky="w")
        row += 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=6, sticky="ew", padx=8, pady=6)
        row += 1

        # --- Positions section ---
        ttk.Label(parent, text="Positions (clic → 3s de délai → capture souris)",
                  font=("Segoe UI", 9, "bold")).grid(
            row=row, column=0, columnspan=4, sticky="w", padx=8, pady=(10, 2))
        row += 1

        for slot_key, slot_label in CURRENCY_SLOTS:
            x_var = tk.IntVar(value=0)
            y_var = tk.IntVar(value=0)
            self._pos_vars[slot_key] = (x_var, y_var)

            ttk.Label(parent, text=slot_label, width=22, anchor="w").grid(
                row=row, column=0, padx=(12, 4), pady=2, sticky="w")
            ttk.Label(parent, text="X:").grid(row=row, column=1, padx=2)
            ttk.Entry(parent, textvariable=x_var, width=6).grid(row=row, column=2, padx=2)
            ttk.Label(parent, text="Y:").grid(row=row, column=3, padx=2)
            ttk.Entry(parent, textvariable=y_var, width=6).grid(row=row, column=4, padx=2)

            btn = ttk.Button(parent, text="Capturer",
                             command=lambda k=slot_key: self._capture_position(k))
            btn.grid(row=row, column=5, padx=(6, 12), pady=2)
            row += 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=6, sticky="ew", padx=8, pady=6)
        row += 1

        # --- CSV Import section ---
        ttk.Label(parent, text="Import CSV de combinaisons",
                  font=("Segoe UI", 9, "bold")).grid(
            row=row, column=0, columnspan=6, sticky="w", padx=8, pady=(0, 2))
        row += 1

        self._csv_path_var = tk.StringVar(value="")
        ttk.Entry(parent, textvariable=self._csv_path_var, width=32, state="readonly").grid(
            row=row, column=0, columnspan=3, padx=(12, 4), pady=2, sticky="w")
        ttk.Button(parent, text="Charger CSV", command=self._load_csv).grid(
            row=row, column=3, padx=(0, 4), pady=2, sticky="w")
        ttk.Button(parent, text="Effacer", command=self._clear_csv).grid(
            row=row, column=4, padx=(0, 12), pady=2, sticky="w")
        row += 1

        self._csv_listbox = tk.Listbox(parent, width=60, height=5, font=("Consolas", 8),
                                       activestyle="dotbox", selectmode="single")
        csv_scroll = ttk.Scrollbar(parent, orient="vertical", command=self._csv_listbox.yview)
        self._csv_listbox.configure(yscrollcommand=csv_scroll.set)
        self._csv_listbox.grid(row=row, column=0, columnspan=5, padx=(12, 0), pady=2, sticky="w")
        csv_scroll.grid(row=row, column=5, padx=(0, 12), pady=2, sticky="ns")
        self._csv_listbox.bind("<<ListboxSelect>>", self._on_csv_select)
        row += 1

        ttk.Label(parent, text="Double-cliquer une ligne pour remplir les Notables",
                  foreground="gray", font=("Segoe UI", 8)).grid(
            row=row, column=0, columnspan=6, sticky="w", padx=12)
        row += 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=6, sticky="ew", padx=8, pady=6)
        row += 1

        # --- Required Notables section ---
        ttk.Label(parent, text="Notables requis (nom exact, un par ligne)",
                  font=("Segoe UI", 9, "bold")).grid(
            row=row, column=0, columnspan=5, sticky="w", padx=8, pady=(0, 2))
        row += 1

        self._notables_text = tk.Text(parent, width=46, height=4, font=("Consolas", 9))
        self._notables_text.grid(row=row, column=0, columnspan=6, padx=12, pady=2, sticky="w")
        row += 1

        self._notables_warning = ttk.Label(
            parent,
            text="⚠ CSV chargé — cette section est ignorée",
            foreground="#c07000", font=("Segoe UI", 8, "italic"))
        self._notables_warning.grid(row=row, column=0, columnspan=6, sticky="w", padx=12)
        self._notables_warning.grid_remove()  # hidden by default

        ttk.Label(parent, text="Exemples : Rote Reinforcement, Herculean Form, …",
                  foreground="gray", font=("Segoe UI", 8)).grid(
            row=row, column=0, columnspan=6, sticky="w", padx=12)
        row += 1

        ttk.Separator(parent, orient="horizontal").grid(
            row=row, column=0, columnspan=6, sticky="ew", padx=8, pady=6)
        row += 1

        # --- Delay & iterations ---
        ttk.Label(parent, text="Délai min (s):").grid(
            row=row, column=0, padx=(12, 4), pady=2, sticky="w")
        self._delay_min = tk.DoubleVar(value=0.15)
        ttk.Entry(parent, textvariable=self._delay_min, width=6).grid(
            row=row, column=1, columnspan=2, padx=2, sticky="w")

        ttk.Label(parent, text="Délai max (s):").grid(
            row=row, column=3, padx=4, pady=2, sticky="w")
        self._delay_max = tk.DoubleVar(value=0.45)
        ttk.Entry(parent, textvariable=self._delay_max, width=6).grid(
            row=row, column=4, padx=2, sticky="w")
        row += 1

        ttk.Label(parent, text="Itérations max:").grid(
            row=row, column=0, padx=(12, 4), pady=2, sticky="w")
        self._max_iter = tk.IntVar(value=5000)
        ttk.Entry(parent, textvariable=self._max_iter, width=8).grid(
            row=row, column=1, columnspan=2, padx=2, sticky="w")
        row += 1

    # ---- Log tab -----------------------------------------------------

    def _build_log_tab(self):
        parent = self._tab_log

        self._log_text = tk.Text(parent, state="disabled", font=("Consolas", 9),
                                 bg="#1e1e1e", fg="#d4d4d4", width=70, height=22)
        scroll = ttk.Scrollbar(parent, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scroll.set)

        self._log_text.bind("<1>", lambda e: self._log_text.focus_set())
        self._log_text.bind("<Control-c>", self._copy_log_selection)

        self._log_text.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scroll.pack(side="right", fill="y", pady=8, padx=(0, 8))

        btn_bar = ttk.Frame(parent)
        btn_bar.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        ttk.Button(btn_bar, text="Vider le log", command=self._clear_log).pack(side="right")
        ttk.Button(btn_bar, text="Copier tout", command=self._copy_log_all).pack(side="right", padx=(0, 6))

    # ---- Bottom bar --------------------------------------------------

    def _build_bottom_bar(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=(0, 8))

        self._btn_start = ttk.Button(bar, text="▶  Démarrer  [F5]",
                                     command=self._start, width=20)
        self._btn_stop  = ttk.Button(bar, text="■  Arrêter",
                                     command=self._stop, width=16)
        self._btn_pause = ttk.Button(bar, text="⏸  Pause  [F7]",
                                     command=self._toggle_pause, width=18, state="disabled")

        self._btn_start.pack(side="left", padx=(0, 6))
        self._btn_stop.pack(side="left", padx=(0, 6))
        self._btn_pause.pack(side="left")

        self._status_var = tk.StringVar(value="En attente")
        ttk.Label(bar, textvariable=self._status_var, foreground="gray").pack(
            side="right", padx=6)

        ttk.Button(bar, text="Tester clipboard", command=self._test_clipboard).pack(
            side="right", padx=6)
        ttk.Button(bar, text="Sauvegarder config", command=self._save_config).pack(
            side="right", padx=6)

    # ------------------------------------------------------------------
    # Position capture
    # ------------------------------------------------------------------

    def _capture_position(self, slot_key: str):
        """Countdown then capture real Windows cursor position via PowerShell."""
        import subprocess

        label = next(l for k, l in CURRENCY_SLOTS if k == slot_key)
        win = tk.Toplevel(self)
        win.title("Capture")
        win.geometry("300x80")
        win.resizable(False, False)
        win.attributes("-topmost", True)

        msg_var = tk.StringVar(value=f"Placer la souris sur : {label}")
        ttk.Label(win, textvariable=msg_var, wraplength=280).pack(pady=8)
        countdown_var = tk.StringVar(value="Capture dans 3s…")
        ttk.Label(win, textvariable=countdown_var, font=("Segoe UI", 11, "bold")).pack()

        def _win_cursor_pos():
            """Read the actual Windows cursor position (works across all monitors)."""
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

        def do_countdown(n):
            if n > 0:
                countdown_var.set(f"Capture dans {n}s…")
                win.after(1000, do_countdown, n - 1)
            else:
                x, y = _win_cursor_pos()
                self._pos_vars[slot_key][0].set(x)
                self._pos_vars[slot_key][1].set(y)
                msg_var.set(f"Capturé : X={x}  Y={y}")
                countdown_var.set("✓")
                win.after(800, win.destroy)

        do_countdown(3)

    def _add_item_position(self):
        """Countdown then capture a new item position and add it to the list."""
        import subprocess
        idx = len(self._item_positions) + 1
        win = tk.Toplevel(self)
        win.title("Capture item")
        win.geometry("300x80")
        win.resizable(False, False)
        win.attributes("-topmost", True)

        msg_var = tk.StringVar(value=f"Placer la souris sur l'item {idx}")
        ttk.Label(win, textvariable=msg_var, wraplength=280).pack(pady=8)
        countdown_var = tk.StringVar(value="Capture dans 3s…")
        ttk.Label(win, textvariable=countdown_var, font=("Segoe UI", 11, "bold")).pack()

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

        def do_countdown(n):
            if n > 0:
                countdown_var.set(f"Capture dans {n}s…")
                win.after(1000, do_countdown, n - 1)
            else:
                x, y = _win_cursor_pos()
                self._item_positions.append((x, y))
                self._item_pos_listbox.insert("end", f"Item {idx}: ({x}, {y})")
                msg_var.set(f"Capturé : X={x}  Y={y}")
                countdown_var.set("✓")
                win.after(800, win.destroy)

        do_countdown(3)

    def _remove_item_position(self):
        """Remove the selected item position from the list."""
        sel = self._item_pos_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self._item_pos_listbox.delete(idx)
        self._item_positions.pop(idx)
        # Renumber labels
        self._item_pos_listbox.delete(0, "end")
        for i, (x, y) in enumerate(self._item_positions):
            self._item_pos_listbox.insert("end", f"Item {i+1}: ({x}, {y})")

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    def _start(self):
        if not self._validate():
            return
        self._save_config()

        cfg = self._build_config()
        self._session = CraftSession(
            config=cfg,
            log_callback=self._append_log,
            status_callback=lambda s: self._status_var.set(s),
        )
        self._session.start()
        self._btn_start.configure(state="disabled")
        self._btn_stop.configure(state="normal")
        self._btn_pause.configure(state="normal", text="⏸  Pause")
        self._notebook.select(self._tab_log)
        self._window_was_unfocused = False
        self._poll_session()
        self._poll_window_focus()

    def _stop(self):
        if self._session:
            self._session.stop()
        self._btn_start.configure(state="normal")
        self._btn_pause.configure(state="disabled", text="⏸  Pause")

    def _toggle_pause(self):
        if not self._session:
            return
        if self._session.is_paused():
            self._session.resume()
            self._btn_pause.configure(text="⏸  Pause")
            self._status_var.set("Running")
        else:
            self._session.pause()
            self._btn_pause.configure(text="▶  Reprendre [F7]")
            self._status_var.set("En pause")

    def _poll_window_focus(self):
        """Stop session when window regains focus after user switched to POE."""
        if not (self._session and self._session.is_running()):
            return
        has_focus = self.focus_displayof() is not None
        if not has_focus:
            self._window_was_unfocused = True   # user switched to POE
        elif self._window_was_unfocused:
            self._stop()                         # user Alt+Tabbed back → stop
            return
        self.after(250, self._poll_window_focus)

    def _poll_session(self):
        if self._session and self._session.is_running():
            self.after(500, self._poll_session)
        else:
            self._btn_start.configure(state="normal")
            self._btn_pause.configure(state="disabled", text="⏸  Pause")

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # CSV helpers
    # ------------------------------------------------------------------

    def _load_csv(self):
        path = filedialog.askopenfilename(
            title="Charger un CSV de combinaisons",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        self._load_csv_from_path(path)

    def _load_csv_from_path(self, path: str):
        try:
            self._csv_rows = []
            self._csv_listbox.delete(0, "end")
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    notables = [
                        row.get("Notable1", "").strip(),
                        row.get("Notable2", "").strip(),
                        row.get("Notable3", "").strip(),
                    ]
                    notables = [n for n in notables if n]
                    if not notables:
                        continue
                    passives = row.get("Passives", "").strip()
                    avg = row.get("AvgChaos", "").strip()
                    label = " + ".join(notables)
                    if passives:
                        label += f"  [{passives}]"
                    if avg:
                        label += f"  ~{avg}c"
                    self._csv_rows.append(notables)
                    self._csv_listbox.insert("end", label)
            self._csv_path_var.set(os.path.basename(path))
            self._csv_full_path = path
            self._notables_warning.grid()
            self._notables_text.configure(state="disabled", background="#2a2a2a")
        except Exception as e:
            messagebox.showerror("Erreur CSV", str(e))

    def _clear_csv(self):
        self._csv_rows = []
        self._csv_listbox.delete(0, "end")
        self._csv_path_var.set("")
        self._notables_warning.grid_remove()
        self._notables_text.configure(state="normal", background="white")

    def _on_csv_select(self, event):
        sel = self._csv_listbox.curselection()
        if not sel:
            return
        notables = self._csv_rows[sel[0]]
        self._notables_text.delete("1.0", "end")
        self._notables_text.insert("1.0", "\n".join(notables))

    def _validate(self) -> bool:
        notables = self._get_notables()
        if not self._csv_rows and not notables:
            messagebox.showerror("Erreur", "Ajoute au moins un Notable requis.")
            return False
        if not self._item_positions:
            messagebox.showerror("Erreur", "Ajoute au moins une position d'item.")
            return False
        for slot_key, slot_label in CURRENCY_SLOTS:
            x, y = self._pos_vars[slot_key][0].get(), self._pos_vars[slot_key][1].get()
            if x == 0 and y == 0:
                ok = messagebox.askyesno(
                    "Position manquante",
                    f"La position « {slot_label} » est (0, 0).\nContinuer quand même ?")
                if not ok:
                    return False
        return True

    def _build_config(self) -> dict:
        positions = {k: (self._pos_vars[k][0].get(), self._pos_vars[k][1].get())
                     for k, _ in CURRENCY_SLOTS}
        manual_notables = self._get_notables()
        # Flat list of all notables across all combos (for alteration check)
        if self._csv_rows:
            all_notables = list({n for combo in self._csv_rows for n in combo})
            combinations = self._csv_rows
        else:
            all_notables = manual_notables
            combinations = [manual_notables] if manual_notables else []
        return {
            "positions": positions,
            "item_positions": self._item_positions,
            "required_notables": all_notables,
            "required_combinations": combinations,
            "delay_min": self._delay_min.get(),
            "delay_max": self._delay_max.get(),
            "max_iterations": self._max_iter.get(),
        }

    def _get_notables(self) -> list:
        raw = self._notables_text.get("1.0", "end").strip()
        return [l.strip() for l in raw.splitlines() if l.strip()]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_config(self):
        data = {
            "positions": {k: [self._pos_vars[k][0].get(), self._pos_vars[k][1].get()]
                          for k, _ in CURRENCY_SLOTS},
            "item_positions": [(x, y) for x, y in self._item_positions],
            "notables": self._get_notables(),
            "csv_path": self._csv_full_path,
            "delay_min": self._delay_min.get(),
            "delay_max": self._delay_max.get(),
            "max_iterations": self._max_iter.get(),
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
                self._item_positions = [tuple(pos) for pos in data["item_positions"]]
                self._item_pos_listbox.delete(0, "end")
                for i, (x, y) in enumerate(self._item_positions):
                    self._item_pos_listbox.insert("end", f"Item {i+1}: ({x}, {y})")
            csv_path = data.get("csv_path", "")
            if csv_path and os.path.exists(csv_path):
                self._load_csv_from_path(csv_path)
            if "notables" in data:
                self._notables_text.insert("1.0", "\n".join(data["notables"]))
            self._delay_min.set(data.get("delay_min", 0.15))
            self._delay_max.set(data.get("delay_max", 0.45))
            self._max_iter.set(data.get("max_iterations", 5000))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Log helpers
    # ------------------------------------------------------------------

    def _append_log(self, msg: str):
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
        """Read current Windows clipboard and display it in the log (for debugging)."""
        import subprocess
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

        # Try to parse as POE item
        from src.item_parser import parse_item_text
        item = parse_item_text(text)
        if item:
            self._append_log(f"→ Item détecté : {item.rarity} | {item.name}")
            self._append_log(f"  Mods : {item.all_mods}")
        else:
            self._append_log("→ Non reconnu comme item POE (hover l'item dans le jeu puis Ctrl+C manuellement, ensuite cliquer Tester clipboard)")

    # ------------------------------------------------------------------
    # Hotkeys  (F5 / F6)
    # ------------------------------------------------------------------

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
            # pynput not available — hotkeys disabled, buttons still work
            pass


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    app = AutoCraftApp()
    app.mainloop()
