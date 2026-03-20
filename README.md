# AutoCraft — POE1 Cluster Jewel Crafter

Outil de craft automatisé pour **Path of Exile 1**, dédié au **cluster jewel crafting**.
Tourne sous **WSL2** et contrôle Windows via un bridge PowerShell (user32.dll).

---

## Workflow de craft

```
[Item Normal]
     │
     ▼
[Orb of Transmutation]  ← si l'item n'est pas déjà Magique
     │
     ▼
[Orb of Alteration]  ──────────────────────────────────────────────┐
     │                                                             │
     ▼                                                             │
[L'item a-t-il 1 seul affix ?]                                     │
     │                                                             │
     ├── OUI + seul affix = préfixe non-notable → continuer Alts  │
     │                                                             │
     ├── OUI autre cas → [Orb of Augmentation]                     │
     │                                                             │
     ▼                                                             │
[Vérification : au moins un Notable cible est présent ?]           │
     │                                                             │
     ├── NON ──────────────────────────────────────────────────────┘
     │
     ▼ OUI
[Regal Orb]  (Magic → Rare)
     │
     ▼
[Exalted Orb]  ← seulement si < 2 préfixes (sinon inutile)
     │
     ▼
[Vérification finale : l'item correspond à une combo complète du CSV ?]
     │
     ├── OUI → ✅ STOP — Item terminé → passer à l'item suivant
     │
     └── NON → [Orb of Scouring]  (Rare → Normal)
                     │
                     └──────────────────── retour au début
```

---

## Logique Augmentation

Les notables sont **toujours des préfixes** sur les cluster jewels.

- 1 seul affix ET c'est un **préfixe non-notable** → on re-altère (un Augment ajouterait un suffixe inutile)
- Tous les autres cas avec 1 seul affix → on augmente

## Logique Exalted

Après le Regal :
- Si l'item a déjà **2+ préfixes** → skip l'Exalt (un exalt n'ajouterait qu'un suffixe, jamais un notable)
- Sinon → Exalted Orb

---

## Système CSV de combinaisons

Chaque ligne du CSV = **une combinaison valide et complète** (pas un mix).

| Colonne   | Description                        |
|-----------|------------------------------------|
| Notable1  | Premier notable de la combo        |
| Notable2  | Deuxième notable (optionnel)       |
| Notable3  | Troisième notable (optionnel)      |
| Passives  | Nombre de passifs (info affichage) |
| AvgChaos  | Valeur moyenne en chaos (info)     |

- La **boucle d'Alteration** s'arrête dès qu'un notable de n'importe quelle combo est trouvé
- Le **check final** valide qu'UNE combo entière est présente (pas un mix de combos)
- Sans CSV : saisie manuelle des notables dans l'UI

---

## Multi-item

Plusieurs items peuvent être configurés (liste de positions).
Le craft passe automatiquement à l'item suivant une fois le précédent terminé.

---

## Lecture de l'item

Méthode : **Clipboard POE via Ctrl+Alt+C**
- Déplacer la souris sur l'item dans l'inventaire
- Simuler `Ctrl+Alt+C` (copie les stats avec infos préfixe/suffixe)
- Parser le texte pour extraire rareté, passifs, préfixes, suffixes

Sentinel anti-stale : avant chaque lecture, le clipboard est vidé avec `AUTOCRAFT_CLEAR`.
Poll jusqu'à obtenir un texte différent contenant `--------`.

---

## Positions à configurer

| Slot          | Description                                  |
|---------------|----------------------------------------------|
| Transmutation | Stack d'Orb of Transmutation                 |
| Alteration    | Stack d'Orb of Alteration                    |
| Augmentation  | Stack d'Orb of Augmentation                  |
| Regal         | Stack de Regal Orb                           |
| Exalted       | Stack d'Exalted Orb                          |
| Scouring      | Stack d'Orb of Scouring                      |
| Items         | Liste de positions (un item par slot)        |

Capture via bouton dans l'UI → compte à rebours 3s → position souris Windows capturée.

---

## Interface utilisateur (GUI)

### Onglet "Craft" → "Double Passifs Cluster Craft"
- Capture des positions currencies et items
- Import CSV de combinaisons
- Saisie manuelle des notables (si pas de CSV)
- Délai min/max entre actions (défaut : 0.15s – 0.45s)
- Nombre max d'itérations par item (défaut : 5000)

### Onglet "Log"
- Affichage en temps réel des actions
- Stats : Transmutations / Alterations / Augmentations / Regals / Exalts / Scourings / Cycles
- Copier tout / Vider

### Contrôles (barre du bas)
- `F5` / bouton **Démarrer** : lance le craft avec countdown 5s
- `F6` / bouton **Arrêter** : arrêt immédiat
- `F7` / bouton **Pause** : suspend/reprend la session
- **Alt+Tab** vers AutoCraft pendant une session → arrêt automatique

---

## Sécurité et comportement humain

- Délais **aléatoires** entre chaque action (intervalle configurable)
- Petit **jitter** aléatoire (±3px) sur chaque clic
- Arrêt automatique si le clipboard ne contient pas un item POE valide après 3 tentatives
- Arrêt si le nombre max d'itérations est atteint
- Arrêt réactif : `_stop_event` vérifié dans toutes les boucles bloquantes

---

## Sessions

Chaque session est enregistrée dans `sessions.json` :
```json
{
  "date": "2026-03-20 14:32:00",
  "combinations": [["Notable1", "Notable2"]],
  "currencies": { "Transmutation": 3, "Alteration": 47, "Augmentation": 12, "Regal": 3, "Exalted": 2, "Scouring": 2 },
  "cycles": 2,
  "items_crafted": 1
}
```

---

## Stack technique

- **Python 3.8+**
- `tkinter` — interface graphique (natif Python)
- `pynput` — écoute des hotkeys globaux (F5/F6/F7, scope X11/WSL2)
- `powershell.exe` — bridge Win32 (souris, clavier, clipboard) via subprocess persistant
- Plateforme : **WSL2** (Linux) contrôlant **Windows** (là où POE tourne)

---

## Fichiers du projet

```
AutoCraft/
├── main.py              # Point d'entrée, GUI tkinter
├── config.json          # Config sauvegardée (positions, CSV path, délais)
├── sessions.json        # Rapport cumulatif des sessions
├── requirements.txt     # Dépendances Python
└── src/
    ├── __init__.py
    ├── item_parser.py   # Parse le texte clipboard POE → ParsedItem
    ├── conditions.py    # Vérifie les conditions sur un item
    ├── crafter.py       # Boucle de craft principale (thread)
    └── win_input.py     # Bridge PowerShell → Win32 (souris/clavier/clipboard)
```

---

## Exemples de textes clipboard POE

<details>
<summary>1 affix (Magique) — Ctrl+C</summary>

```
Item Class: Jewels
Rarity: Magic
Harmful Medium Cluster Jewel
--------
Item Level: 83
--------
Adds 4 Passive Skills (enchant)
1 Added Passive Skill is a Jewel Socket (enchant)
Added Small Passive Skills grant: 12% increased Chaos Damage over Time (enchant)
--------
Added Small Passive Skills also grant: 2% increased Damage
--------
Place into an allocated Medium or Large Jewel Socket on the Passive Skill Tree.
```
</details>

<details>
<summary>2 affixes (Magique) — Ctrl+C</summary>

```
Item Class: Jewels
Rarity: Magic
Shining Medium Cluster Jewel of Banishment
--------
Requirements:
Level: 54
--------
Item Level: 83
--------
Adds 4 Passive Skills (enchant)
1 Added Passive Skill is a Jewel Socket (enchant)
Added Small Passive Skills grant: 12% increased Chaos Damage over Time (enchant)
--------
Added Small Passive Skills also grant: +4% to Chaos Resistance
Added Small Passive Skills also grant: +4 to Maximum Energy Shield
--------
Place into an allocated Medium or Large Jewel Socket on the Passive Skill Tree.
```
</details>

<details>
<summary>3 affixes (Rare) — Ctrl+C</summary>

```
Item Class: Jewels
Rarity: Rare
Brood Shard
Medium Cluster Jewel
--------
Item Level: 83
--------
Adds 4 Passive Skills (enchant)
1 Added Passive Skill is a Jewel Socket (enchant)
Added Small Passive Skills grant: 12% increased Chaos Damage over Time (enchant)
--------
Added Small Passive Skills also grant: +4% to Chaos Resistance
Added Small Passive Skills also grant: +4 to Maximum Energy Shield
1 Added Passive Skill is Brush with Death
--------
Place into an allocated Medium or Large Jewel Socket on the Passive Skill Tree.
```
</details>

<details>
<summary>Ctrl+Alt+C (avec infos préfixe/suffixe)</summary>

```
Item Class: Jewels
Rarity: Magic
Hazardous Medium Cluster Jewel of the Wrestler
--------
Requirements:
Level: 54
--------
Item Level: 83
--------
Adds 4 Passive Skills (enchant)
(Added Passive Skills are never considered to be in Radius by other Jewels) (enchant)
1 Added Passive Skill is a Jewel Socket (enchant)
Added Small Passive Skills grant: 12% increased Chaos Damage over Time (enchant)
--------
{ Prefix Modifier "Hazardous" (Tier: 2) — Damage }
Added Small Passive Skills also grant: 3% increased Damage
{ Suffix Modifier "of the Wrestler" (Tier: 2) — Attribute }
Added Small Passive Skills also grant: +4(4-5) to Strength
--------
Place into an allocated Medium or Large Jewel Socket on the Passive Skill Tree.
```
</details>
