"""
AutoCraft — POE1 Cluster Jewel Crafter
Entry point pywebview
"""

import webview
import json
import os
import threading
import time
import csv
import subprocess
import re

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
        return {"x": int(x), "y": int(y)}
    except Exception:
        return {"x": 0, "y": 0}


class Api:
    def __init__(self):
        self._session  = None
        self._logs     = []
        self._log_lock = threading.Lock()
        self._window   = None

    def set_window(self, w):
        self._window = w

    # ── Données ───────────────────────────────────────────────────────────

    def get_cluster_mods(self):
        if os.path.exists(CLUSTER_MODS_FILE):
            try:
                with open(CLUSTER_MODS_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                # Normalise le texte des enchants (supprime espaces avant %)
                for size, block in data.items():
                    enchants = block.get("enchants", []) if isinstance(block, dict) else block
                    for e in enchants:
                        e["enchant_text"] = [
                            re.sub(r'(\d+)\s+%', r'\1%', t)
                            for t in e.get("enchant_text", [])
                        ]
                return data
            except Exception:
                pass
        return {}

    def get_config(self):
        if not os.path.exists(CONFIG_FILE):
            return {}
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            return {}

    def save_config(self, config):
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        return True

    # ── CSV ───────────────────────────────────────────────────────────────

    def pick_csv_file(self):
        if not self._window:
            return None
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("CSV files (*.csv)", "All files (*.*)",)
        )
        return result[0] if result else None

    def load_csv(self, path):
        rows = []
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    notables = [row.get(c, "").strip()
                                for c in ("Notable1", "Notable2", "Notable3")]
                    notables = [n for n in notables if n]
                    if not notables:
                        continue
                    rows.append({
                        "notables":  notables,
                        "passives":  row.get("Passives", "").strip(),
                        "avg_chaos": row.get("AvgChaos", "").strip(),
                    })
        except Exception as e:
            return {"error": str(e)}
        return {"rows": rows, "filename": os.path.basename(path)}

    # ── Capture position ──────────────────────────────────────────────────

    def capture_position(self):
        """Attend 3 secondes, puis retourne la position Windows du curseur."""
        time.sleep(3)
        return _win_cursor_pos()

    # ── Session ───────────────────────────────────────────────────────────

    def start_session(self, config):
        if self._session and self._session.is_running():
            return False

        # Convertit positions {x,y} → tuples pour CraftSession
        converted = dict(config)
        converted["positions"] = {
            k: (v["x"], v["y"]) for k, v in config["positions"].items()
        }
        converted["item_positions"] = [
            (p["x"], p["y"]) for p in config["item_positions"]
        ]

        def log_cb(msg):
            with self._log_lock:
                self._logs.append(msg)

        self._session = CraftSession(
            config=converted,
            log_callback=log_cb,
            status_callback=lambda s: None,
        )
        self._session.start()
        return True

    def stop_session(self):
        if self._session:
            self._session.stop()
        return True

    def pause_session(self):
        if self._session:
            self._session.pause()
        return True

    def resume_session(self):
        if self._session:
            self._session.resume()
        return True

    def get_status(self):
        if not self._session:
            return "idle"
        if self._session.is_paused():
            return "paused"
        if self._session.is_running():
            return "running"
        return "idle"

    def get_logs(self):
        with self._log_lock:
            logs = self._logs.copy()
            self._logs.clear()
        return logs

    # ── Clipboard ─────────────────────────────────────────────────────────

    def test_clipboard(self):
        lines = []
        text  = ""
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=2
            )
            text = result.stdout.strip()
        except Exception:
            pass

        lines.append("=== Test clipboard ===")
        lines.append(text if text else "(clipboard vide ou illisible)")

        from src.item_parser import parse_item_text
        item = parse_item_text(text)
        if item:
            lines.append(f"→ Item détecté : {item.rarity} | {item.name}")
            lines.append(f"  Mods : {item.all_mods}")
        else:
            lines.append("→ Non reconnu comme item POE")

        with self._log_lock:
            self._logs.extend(lines)
        return True


if __name__ == "__main__":
    api     = Api()
    ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "index.html")
    window  = webview.create_window(
        "AutoCraft — POE1 Cluster Jewel",
        ui_path,          # pywebview 3.x accepte un chemin local directement
        js_api=api,
        width=960,
        height=720,
        min_size=(800, 560),
    )
    api.set_window(window)
    webview.start()
