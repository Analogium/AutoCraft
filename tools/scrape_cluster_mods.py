"""
Scraper poedb.tw — Cluster Jewel Modifiers
Extrait les enchants + notables disponibles pour Large/Medium/Small Cluster Jewels.

Usage :
    python3 tools/scrape_cluster_mods.py

Sortie : data/cluster_mods.json
"""

import json
import os
import re
import time
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://poedb.tw"

CLUSTER_PAGES = {
    "Large":  "/us/Large_Cluster_Jewel",
    "Medium": "/us/Medium_Cluster_Jewel",
    "Small":  "/us/Small_Cluster_Jewel",
}

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cluster_mods.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AutoCraft-scraper/1.0)"
}


def fetch_page(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def get_enchant_text(td):
    """Extrait les lignes de texte de l'enchant depuis les spans explicitMod."""
    lines = []
    for span in td.find_all("span", class_="explicitMod", recursive=True):
        # Ignore les sous-spans item_description (texte entre parenthèses)
        if "item_description" in span.get("class", []):
            continue
        # Récupère le texte sans les enfants item_description
        for desc in span.find_all("span", class_="item_description"):
            desc.decompose()
        text = span.get_text(separator=" ").strip()
        if text:
            lines.append(text)
    return lines


def get_notable_tags(td_passive):
    """Extrait les tags (Physical, Attack, etc.) depuis les badges."""
    return [
        badge.get_text(strip=True)
        for badge in td_passive.find_all("span", class_="badge")
        if "craftingphysical" in " ".join(badge.get("class", []))
        or badge.get("data-tag")
    ]


def parse_enchant_section(soup, size):
    """Parse la section EnchantmentModifiers et retourne la liste des enchants avec leurs notables."""
    section = soup.find(id="EnchantmentModifiers")
    if not section:
        print(f"  [!] Section EnchantmentModifiers introuvable pour {size}")
        return []

    enchants = []

    # On cible uniquement la table principale (pas les tables imbriquées des notables)
    main_table = section.find("table", class_="filters")
    if not main_table:
        print(f"  [!] Table principale introuvable pour {size}")
        return []
    main_tbody = main_table.find("tbody")
    if not main_tbody:
        return []

    # Chaque ligne = un enchant (recursive=False → pas les tr des tables imbriquées)
    for row in main_tbody.find_all("tr", recursive=False):
        td = row.find("td")
        if not td:
            continue

        # URL de l'enchant
        link = td.find("a", href=True)
        if not link:
            continue
        enchant_url = BASE_URL + link["href"] if link["href"].startswith("/") else link["href"]
        enchant_slug = link["href"].rstrip("/").split("/")[-1]

        # Texte de l'enchant (cloner le td avant de décomposer les collapse divs)
        td_clone = BeautifulSoup(str(td), "html.parser").find("td")
        # Supprimer le div collapse pour ne garder que le lien principal
        for div in td_clone.find_all("div", class_="collapse"):
            div.decompose()
        for btn in td_clone.find_all("button"):
            btn.decompose()
        enchant_lines = get_enchant_text(td_clone)

        # Notables : table dans le div collapse
        notables = []
        collapse_div = td.find("div", class_="collapse")
        if collapse_div:
            for notable_row in collapse_div.select("table tbody tr"):
                cells = notable_row.find_all("td")
                if len(cells) < 4:
                    continue

                td_passive, td_weight, td_level, td_type = cells[:4]

                # Nom du notable
                passive_link = td_passive.find("a", class_="PassiveSkills")
                if not passive_link:
                    continue
                name = passive_link.get_text(strip=True)

                # Tags (Physical, Attack, etc.)
                tags = [
                    badge.get("data-tag", badge.get_text(strip=True))
                    for badge in td_passive.find_all("span", attrs={"data-tag": True})
                ]

                try:
                    weight = int(td_weight.get_text(strip=True))
                except ValueError:
                    weight = 0

                try:
                    level = int(td_level.get_text(strip=True))
                except ValueError:
                    level = 0

                mod_type = td_type.get_text(strip=True)  # Prefix / Suffix

                notables.append({
                    "name":   name,
                    "weight": weight,
                    "level":  level,
                    "type":   mod_type,
                    "tags":   tags,
                })

        enchants.append({
            "enchant_slug":  enchant_slug,
            "enchant_url":   enchant_url,
            "enchant_text":  enchant_lines,
            "notables":      notables,
        })

    return enchants


SPAWN_KEY = {
    "Large":  "expansion_jewel_large",
    "Medium": "expansion_jewel_medium",
    "Small":  "expansion_jewel_small",
}


def parse_explicit_mods(soup, size):
    """Extrait tous les mods explicites craftables (prefix/suffix) depuis le JSON ModsView."""
    spawn_key = SPAWN_KEY[size]
    prefixes, suffixes = [], []

    for script in soup.find_all("script"):
        text = script.string or ""
        if "ModsView" not in text or "baseitem" not in text:
            continue
        m = re.search(r"new ModsView\((\{.*?\})\s*\)", text, re.DOTALL)
        if not m:
            continue
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue

        for mod in data.get("normal", []):
            spawn = mod.get("spawn_no", [])
            if spawn_key not in spawn and "default" not in spawn:
                continue
            raw = mod.get("str", "")
            text_clean = re.sub(r"<[^>]+>", "", raw).strip()
            if not text_clean:
                continue
            entry = {
                "name":   mod.get("Name", ""),
                "text":   text_clean,
                "level":  int(mod.get("Level", 0) or 0),
                "weight": int(mod.get("DropChance", 0) or 0),
            }
            gtype = str(mod.get("ModGenerationTypeID", "1"))
            if gtype == "1":
                prefixes.append(entry)
            else:
                suffixes.append(entry)
        break  # un seul script ModsView par page

    return prefixes, suffixes


def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    result = {}

    for size, path in CLUSTER_PAGES.items():
        url = BASE_URL + path
        print(f"Fetch {size} Cluster Jewel… ({url})")
        try:
            soup = fetch_page(url)
            enchants = parse_enchant_section(soup, size)
            prefixes, suffixes = parse_explicit_mods(soup, size)
            result[size] = {
                "enchants":  enchants,
                "prefixes":  prefixes,
                "suffixes":  suffixes,
            }
            print(f"  → {len(enchants)} enchants, {len(prefixes)} prefixes, {len(suffixes)} suffixes")
        except Exception as exc:
            print(f"  [ERREUR] {exc}")
            result[size] = {"enchants": [], "prefixes": [], "suffixes": []}

        time.sleep(1)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Sauvegardé : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
