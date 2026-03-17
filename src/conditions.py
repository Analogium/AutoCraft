"""
Condition checking for cluster jewel crafting.
All Notable matching is done by exact name (case-insensitive).
"""

from typing import List
from .item_parser import ParsedItem


def all_notables_present(item: ParsedItem, required_notables: List[str]) -> bool:
    """Return True if every notable in the list is found in the item's mods."""
    if not required_notables:
        return False
    return all(item.has_notable(n) for n in required_notables)


def any_notable_present(item: ParsedItem, required_notables: List[str]) -> bool:
    """Return True if at least one notable from the list is found in the item's mods."""
    if not required_notables:
        return False
    return any(item.has_notable(n) for n in required_notables)


def matches_any_combination(item: ParsedItem, combinations: List[List[str]]) -> bool:
    """
    Return True if the item contains ALL notables of at least one combination.
    e.g. combinations = [["Eldritch Inspiration", "Low Tolerance"], ["Brush with Death", "Flow of Life"]]
    """
    return any(
        all(item.has_notable(n) for n in combo)
        for combo in combinations
        if combo
    )


def needs_augmentation(item: ParsedItem) -> bool:
    """
    Return True if the item is Magic and has only 1 affix.
    In that case an Orb of Augmentation should be applied before Regal.
    """
    return item.rarity == "Magic" and item.num_affixes < 2
