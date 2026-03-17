"""
Parse POE1 item clipboard text into a structured object.
In POE, hovering an item and pressing Ctrl+C copies its stats to clipboard.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ParsedItem:
    rarity: str = "Normal"          # Normal / Magic / Rare / Unique
    name: str = ""
    base_type: str = ""
    item_class: str = ""
    item_level: int = 0
    num_sockets: int = 0
    num_links: int = 0
    sockets_str: str = ""
    implicits: List[str] = field(default_factory=list)
    explicits: List[str] = field(default_factory=list)
    crafted_mods: List[str] = field(default_factory=list)
    prefix_mods: List[str] = field(default_factory=list)   # subset of explicits tagged as prefix
    suffix_mods: List[str] = field(default_factory=list)   # subset of explicits tagged as suffix
    is_corrupted: bool = False

    @property
    def all_mods(self) -> List[str]:
        return self.implicits + self.explicits + self.crafted_mods

    @property
    def num_affixes(self) -> int:
        """Number of explicit + crafted affixes (not implicits)."""
        return len(self.explicits) + len(self.crafted_mods)

    @property
    def num_prefixes(self) -> int:
        return len(self.prefix_mods)

    @property
    def num_suffixes(self) -> int:
        return len(self.suffix_mods)

    def has_notable(self, name: str) -> bool:
        """
        Check if the item has the given notable.
        Handles all known cluster jewel formats:
          - "Rote Reinforcement"                         (exact)
          - "1 Added Passive Skill is Rote Reinforcement"
          - "2 Added Passive Skills are Rote Reinforcement"
          - "Added Passive Skill is Rote Reinforcement"
        """
        import re
        name_stripped = name.strip()
        name_lower    = name_stripped.lower()

        for mod in self.all_mods:
            mod_lower = mod.strip().lower()

            # 1. Exact match
            if mod_lower == name_lower:
                return True

            # 2. "...is/are {name}" at end of line
            if mod_lower.endswith(f" is {name_lower}") or \
               mod_lower.endswith(f" are {name_lower}"):
                return True

            # 3. Whole-word substring (covers any other wrapping format)
            if re.search(r'\b' + re.escape(name_lower) + r'\b', mod_lower):
                return True

        return False


def parse_item_text(text: str) -> Optional[ParsedItem]:
    """
    Parse POE item clipboard text.
    Returns None if the text doesn't look like a POE item.
    """
    if not text or "--------" not in text:
        return None

    item = ParsedItem()
    sections = [s.strip() for s in text.strip().split("--------")]
    sections = [s for s in sections if s]

    if not sections:
        return None

    # --- Header section (first block) ---
    header_lines = [l.strip() for l in sections[0].split("\n") if l.strip()]
    name_lines = []
    for line in header_lines:
        if line.startswith("Item Class:"):
            item.item_class = line.split(":", 1)[1].strip()
        elif line.startswith("Rarity:"):
            item.rarity = line.split(":", 1)[1].strip()
        else:
            name_lines.append(line)

    if len(name_lines) >= 1:
        item.name = name_lines[0]
    if len(name_lines) >= 2:
        item.base_type = name_lines[1]
    else:
        item.base_type = item.name

    # --- Find key fields across all sections ---
    for section in sections[1:]:
        for line in [l.strip() for l in section.split("\n") if l.strip()]:
            if line.startswith("Item Level:"):
                m = re.search(r"(\d+)", line)
                if m:
                    item.item_level = int(m.group(1))
            elif line.startswith("Sockets:"):
                socket_str = line.split(":", 1)[1].strip()
                item.sockets_str = socket_str
                item.num_sockets = len(re.findall(r"[RGBWA]", socket_str))
                groups = socket_str.split(" ")
                item.num_links = max((len(g.split("-")) for g in groups), default=0)
            elif line == "Corrupted":
                item.is_corrupted = True

    # --- Extract mod sections (everything after Item Level) ---
    item_level_idx = -1
    for i, section in enumerate(sections):
        if "Item Level:" in section:
            item_level_idx = i
            break

    if item_level_idx < 0:
        return item

    mod_sections = []
    for section in sections[item_level_idx + 1:]:
        lines = [l.strip() for l in section.split("\n") if l.strip()]
        if not lines:
            continue
        # Skip metadata sections
        if _is_meta_section(lines):
            continue
        # Skip single-word special lines
        if lines in (["Corrupted"], ["Unidentified"], ["Mirrored"]):
            continue
        # Skip flavor/description text (item socket instructions, etc.)
        if _is_flavor_section(lines):
            continue
        mod_sections.append(lines)

    # Cluster jewels have no sockets, so the first mod section is implicits,
    # the rest are explicits (with optional crafted marker).
    if len(mod_sections) == 1:
        _classify_mods(mod_sections[0], item, as_implicits=False)
    elif len(mod_sections) >= 2:
        _classify_mods(mod_sections[0], item, as_implicits=True)
        for sec in mod_sections[1:]:
            _classify_mods(sec, item, as_implicits=False)

    return item


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FLAVOR_PREFIXES = (
    "Place into",
    "Right click",
    "Shift click",
    "Double click",
    "Can be used",
    "This item",
    "Travel to",
)


def _is_flavor_section(lines: List[str]) -> bool:
    """Return True if this section is item description/tooltip text, not mods."""
    return any(
        any(l.startswith(p) for p in _FLAVOR_PREFIXES)
        for l in lines
    )


_META_PREFIXES = (
    "Quality:", "Energy Shield:", "Armour:", "Evasion:", "Chaos Inoculation",
    "Requirements:", "Level:", "Str:", "Dex:", "Int:",
    "Sockets:", "Item Level:", "Stack Size:", "Item Class:",
    "Map Tier:", "Item Quantity:", "Item Rarity:", "Monster Pack Size:",
    "Physical Damage:", "Elemental Damage:", "Critical Strike Chance:",
    "Attacks per Second:", "Weapon Range:", "Radius:",
    "Adds ", "Experience:",
)


def _is_meta_section(lines: List[str]) -> bool:
    if not lines:
        return True
    return all(
        any(l.startswith(prefix) for prefix in _META_PREFIXES)
        for l in lines
    )


def _classify_mods(lines: List[str], item: ParsedItem, as_implicits: bool):
    skip = {"Corrupted", "Unidentified", "Mirrored"}
    next_is_prefix = False
    next_is_suffix = False
    for line in lines:
        # Filter parenthesized explanation lines from Ctrl+Alt+C format: (All Added Passive Skills...)
        if line.startswith("("):
            continue
        if line in skip or line.startswith("Note:"):
            continue
        # Detect Ctrl+Alt+C affix type headers: { Prefix Modifier "..." } / { Suffix Modifier "..." }
        if line.startswith("{ Prefix"):
            next_is_prefix = True
            next_is_suffix = False
            continue
        if line.startswith("{ Suffix"):
            next_is_suffix = True
            next_is_prefix = False
            continue
        if "(crafted)" in line:
            item.crafted_mods.append(line.replace(" (crafted)", "").strip())
        elif as_implicits:
            item.implicits.append(line)
        else:
            item.explicits.append(line)
            if next_is_prefix:
                item.prefix_mods.append(line)
            elif next_is_suffix:
                item.suffix_mods.append(line)
        next_is_prefix = False
        next_is_suffix = False
