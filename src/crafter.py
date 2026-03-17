"""
Main crafting loop for cluster jewel crafting.

Workflow:
  1. Read item via Ctrl+C clipboard
  2. If Normal → apply Transmutation (Normal → Magic)
  3. Roll Alterations until required Notables are found
  4. If Magic with 1 affix → apply Augmentation
  5. Apply Regal (Magic → Rare)
  6. Apply Exalted (add mod to Rare)
  7. Check final conditions → if OK: STOP, else Scouring → repeat from 1
"""

import time
import random
import threading
import json
import os
from datetime import datetime

from .item_parser import parse_item_text, ParsedItem
from .conditions import all_notables_present, any_notable_present, matches_any_combination, needs_augmentation
from .win_input import WinInputBridge

SESSIONS_LOG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sessions.json")


class CraftSession:
    def __init__(self, config: dict, log_callback, status_callback):
        """
        config keys:
            positions: dict of slot -> (x, y)
                "item", "transmutation", "alteration", "augmentation",
                "regal", "exalted", "scouring"
            required_notables: List[str]   flat list for alteration check (any notable)
            required_combinations: List[List[str]]  for final check (must match one full combo)
            delay_min: float  (seconds)
            delay_max: float  (seconds)
            max_iterations: int
        """
        self.config = config
        self.log = log_callback
        self.status = status_callback

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._win = WinInputBridge()

        # Stats
        self.count_transmutations = 0
        self.count_alterations = 0
        self.count_augmentations = 0
        self.count_regals = 0
        self.count_exalteds = 0
        self.count_scourings = 0
        self.count_full_cycles = 0
        self.count_items_crafted = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    def _run(self):
        cfg = self.config
        max_iter = cfg.get("max_iterations", 10000)
        required = cfg.get("required_notables", [])
        combinations = cfg.get("required_combinations", [required] if required else [])
        positions = cfg.get("positions", {})

        self.log("=== Crafting session started ===")

        # Start PowerShell bridge
        self.log("Initialisation du bridge Windows…")
        if not self._win.start():
            self.log("ERROR: Impossible de démarrer le bridge PowerShell.")
            self.log("  → Vérifiez que powershell.exe est accessible depuis WSL2.")
            self.status("Erreur bridge")
            return
        self.log("Bridge OK.")

        self.log("Pour arrêter : Alt+Tab vers AutoCraft")
        self.log("Retournez dans POE maintenant…")
        for i in range(5, 0, -1):
            self.log(f"  Démarrage dans {i}s…")
            time.sleep(1)
        self.status("Running")

        item_positions = cfg.get("item_positions", [])
        if not item_positions:
            self.log("ERROR: Aucune position d'item configurée.")
            return

        total_items = len(item_positions)
        self.log(f"{total_items} item(s) à crafter.")

        iteration = 0
        current_item_idx = 0

        try:
            while current_item_idx < total_items:
                if self._stop_event.is_set():
                    self.log("Arrêt demandé.")
                    break

                item_pos = item_positions[current_item_idx]
                self.log(f"--- Item {current_item_idx + 1}/{total_items} | Cycle #{iteration + 1} ---")

                if iteration >= max_iter:
                    self.log(f"⚠ Max itérations ({max_iter}) atteint pour cet item.")
                    current_item_idx += 1
                    iteration = 0
                    continue

                iteration += 1

                # Step 1: read current item state
                item = self._read_item(item_pos, log_mods=True)
                if item is None:
                    self.log("ERROR: Could not read item from clipboard.")
                    break

                self.log(f"Rareté: {item.rarity} | Affixes: {item.num_affixes}")

                # Step 2: Transmutation if Normal
                if item.rarity == "Normal":
                    self.log("Transmutation…")
                    self._apply_currency(positions["transmutation"], item_pos)
                    self.count_transmutations += 1
                    self._wait()
                    item = self._read_item(item_pos)
                    if item is None:
                        self.log("ERROR: Could not read item after Transmutation.")
                        break

                # Step 3: Alteration loop
                alt_count = 0
                while not self._stop_event.is_set():
                    self._apply_currency(positions["alteration"], item_pos)
                    self.count_alterations += 1
                    alt_count += 1
                    self._wait()
                    item = self._read_item(item_pos)
                    if item is None:
                        self.log("ERROR: Could not read item during Alteration loop.")
                        self._stop_event.set()
                        break

                    # Augmentation decision (magic with 1 affix only):
                    # Only skip augment if the single affix is a prefix that is NOT a notable
                    # (augment would add a suffix which can never be a notable → useless)
                    # All other cases: augment (1 suffix → augment adds prefix that could be notable)
                    if item.rarity == "Magic" and item.num_affixes == 1:
                        has_affix_info = bool(item.prefix_mods or item.suffix_mods)
                        is_non_notable_prefix = (
                            has_affix_info
                            and item.num_prefixes == 1
                            and not any(item.has_notable(n) for n in required)
                        )
                        if not is_non_notable_prefix:
                            self.log("Augmentation (1 seul affix)…")
                            self._apply_currency(positions["augmentation"], item_pos)
                            self.count_augmentations += 1
                            self._wait()
                            item = self._read_item(item_pos)
                            if item is None:
                                self.log("ERROR: Could not read item after Augmentation.")
                                self._stop_event.set()
                                break

                    found   = [n for n in required if item.has_notable(n)]
                    missing = [n for n in required if not item.has_notable(n)]
                    self.log(f"  [alt #{alt_count}] ✓{found}  ✗{missing}")
                    if found:
                        self.log(f"✓ Notable(s) trouvé(s) après {alt_count} Alteration(s): {found}")
                        break

                if self._stop_event.is_set():
                    break

                # Step 5: Regal Orb
                self.log("Regal Orb…")
                self._apply_currency(positions["regal"], item_pos)
                self.count_regals += 1
                self._wait()
                item = self._read_item(item_pos)
                if item is None:
                    self.log("ERROR: Could not read item after Regal.")
                    break

                # Step 6: Exalted Orb — skip if item already has 2 prefixes
                # (exalt would only add a suffix; no more room for a notable prefix)
                has_affix_info = bool(item.prefix_mods or item.suffix_mods)
                if has_affix_info and item.num_prefixes >= 2:
                    self.log(f"Regal a ajouté un préfixe ({item.num_prefixes} préfixes) → Exalt inutile.")
                else:
                    self.log("Exalted Orb…")
                    self._apply_currency(positions["exalted"], item_pos)
                    self.count_exalteds += 1
                    self._wait()
                    item = self._read_item(item_pos)
                    if item is None:
                        self.log("ERROR: Could not read item after Exalted.")
                        break

                # Step 7: Final check

                self.log(f"Mods finaux: {item.all_mods}")

                matched = next(
                    (combo for combo in combinations if all(item.has_notable(n) for n in combo)),
                    None
                )
                if matched:
                    self.log(f"✅ SUCCÈS item {current_item_idx + 1}/{total_items} — Combo: {matched}")
                    self.count_items_crafted += 1
                    self._print_stats()
                    current_item_idx += 1
                    iteration = 0
                    if current_item_idx < total_items:
                        self.log(f"→ Passage à l'item {current_item_idx + 1}/{total_items}…")
                else:
                    self.count_full_cycles += 1
                    self.log("✗ Aucune combo complète. Scouring…")
                    self._apply_currency(positions["scouring"], item_pos)
                    self.count_scourings += 1
                    self._wait()

            if current_item_idx >= total_items:
                self.log(f"🎉 Tous les items craftés ({total_items}/{total_items}) !")
                self.status("Done ✅")

        except Exception as e:
            self.log(f"EXCEPTION: {e}")
        finally:
            self._win.close()
            self.status("Stopped")
            self._print_stats()
            self.log("=== Session terminée ===")

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _wait(self):
        d = random.uniform(
            self.config.get("delay_min", 0.15),
            self.config.get("delay_max", 0.45),
        )
        time.sleep(d)

    def _jitter(self, x: int, y: int, radius: int = 3) -> tuple:
        return (
            x + random.randint(-radius, radius),
            y + random.randint(-radius, radius),
        )

    def _apply_currency(self, currency_pos: tuple, item_pos: tuple):
        """Right-click the currency stack, then left-click the item."""
        cx, cy = self._jitter(*currency_pos)
        ix, iy = self._jitter(*item_pos)
        self._win.right_click(cx, cy)
        time.sleep(random.uniform(0.08, 0.15))
        self._win.left_click(ix, iy)

    def _read_item(self, item_pos: tuple, log_mods: bool = False) -> "ParsedItem | None":
        """
        Send Ctrl+C on the item, then wait until the Windows clipboard content
        CHANGES from what it was before — guarantees we read fresh stats.
        Uses the PowerShell bridge exclusively (no WSL2/X11 clipboard).
        """
        ix, iy = self._jitter(*item_pos)

        for attempt in range(3):
            # 1. Clear clipboard so we can detect a fresh copy
            self._win.clear_clipboard()
            time.sleep(0.08)

            # 2. Move to item and send Ctrl+C
            self._win.ctrl_c(ix, iy)

            # 3. Poll until clipboard has fresh POE item (not the sentinel, has separator)
            text = ""
            deadline = time.time() + 3.0
            while time.time() < deadline:
                time.sleep(0.1)
                text = self._win.read_clipboard()
                if text and text != "AUTOCRAFT_CLEAR" and "--------" in text:
                    break
            else:
                if attempt < 2:
                    self.log(f"  [debug] Clipboard vide, retry {attempt + 1}/3…")
                    time.sleep(0.3)
                    continue
                self.log("  [debug] Clipboard vide après 3 tentatives.")
                return None

            item = parse_item_text(text)
            if item is None:
                preview = text[:100].replace("\n", "↵")
                self.log(f"  [debug] Parse échoué. Clipboard: {preview}")
                return None

            if log_mods:
                self.log(f"  [mods] {item.all_mods}")

            return item

        return None

    def _print_stats(self):
        self.log(
            f"Stats → Trans: {self.count_transmutations} | "
            f"Alt: {self.count_alterations} | "
            f"Aug: {self.count_augmentations} | "
            f"Regal: {self.count_regals} | "
            f"Exalt: {self.count_exalteds} | "
            f"Scour: {self.count_scourings} | "
            f"Cycles: {self.count_full_cycles}"
        )
        self._save_session_report()

    def _save_session_report(self):
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "combinations": self.config.get("required_combinations", []),
            "currencies": {
                "Transmutation": self.count_transmutations,
                "Alteration":    self.count_alterations,
                "Augmentation":  self.count_augmentations,
                "Regal":         self.count_regals,
                "Exalted":       self.count_exalteds,
                "Scouring":      self.count_scourings,
            },
            "cycles": self.count_full_cycles,
            "items_crafted": self.count_items_crafted,
        }
        try:
            sessions = []
            if os.path.exists(SESSIONS_LOG):
                with open(SESSIONS_LOG, "r", encoding="utf-8") as f:
                    sessions = json.load(f)
            sessions.append(entry)
            with open(SESSIONS_LOG, "w", encoding="utf-8") as f:
                json.dump(sessions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log(f"  [warn] Impossible d'écrire sessions.json : {e}")
