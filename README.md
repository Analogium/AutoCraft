# AutoCraft — Spécification

## Contexte

Outil de craft automatisé pour **Path of Exile 1**, dédié au **cluster jewel crafting**.

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
     [L'item a-t-il 1 seul affix ?]                                │
     │                                                             │
     ├── OUI → [Orb of Augmentation]                               │
     │                                                             |
     ▼                                                             |
[Vérification : est-ce que l'un des passifs/stats visés est là ?]  │
     │                                                             │
     ├── NON ──────────────────────────────────────────────────────┘
     │
     ▼ OUI
[Regal Orb]  (Magic → Rare)
     │
     ▼
[Exalted Orb]  (ajoute un mod au Rare)
     │
     ▼
[Vérification finale : l'item a-t-il le combo de stats/passifs voulu ?]
     │
     ├── OUI → ✅ STOP — Item terminé
     │
     └── NON → [Orb of Scouring]  (Rare → Normal)
                     │
                     └──────────────────── retour au début
```

---

## Conditions d'arrêt (par étape)

### Étape Alteration (condition intermédiaire)
L'outil roll avec des Alterations tant que l'item **ne contient pas** les passifs/stats ciblés.

- L'utilisateur définit une liste de **Notables requis par nom exact** (ex: `Rote Reinforcement`, `Herculean Form`)
- Condition : `TOUS les Notables requis sont présents` → passer à l'étape suivante

### Étape finale (condition de succès)
Après Exalted, les mêmes Notables requis que pour l'étape Alteration sont vérifiés sur l'item final.

- Si tous les Notables requis sont présents → **STOP**
- Sinon → **Scouring** et recommencer

---

## Lecture de l'item

Méthode : **Clipboard POE**
- Déplacer la souris sur l'item
- Simuler `Ctrl+C` (copie les stats dans le presse-papiers)
- Parser le texte pour extraire rareté, passifs, nombre d'affixes

---

## Positions à configurer

L'utilisateur doit indiquer (via capture de position dans l'UI) :

| Slot            | Description                            |
|-----------------|----------------------------------------|
| Item            | Position de l'item dans l'inventaire   |
| Transmutation   | Position de l'Orb of Transmutation     |
| Alteration      | Position de l'Orb of Alteration        |
| Augmentation    | Position de l'Orb of Augmentation      |
| Regal           | Position du Regal Orb                  |
| Exalted         | Position de l'Exalted Orb              |
| Scouring        | Position de l'Orb of Scouring          |

---

## Interface utilisateur (GUI)

### Onglet "Configuration"
- Capture des positions (bouton → compte à rebours 3s → capture)
- Définition des mods requis pour l'étape Alteration
- Définition des mods requis pour la validation finale
- Délai min/max entre actions (ex: 0.15s – 0.45s)
- Nombre max d'itérations (sécurité)

### Onglet "Log"
- Affichage en temps réel des actions effectuées
- Compteur : Alterations utilisées / Scourings / Tentatives totales

### Contrôles
- `F5` : Démarrer le craft
- `F6` : Arrêter immédiatement
- Bouton Start / Stop dans l'UI

---

## Sécurité et comportement humain

- Délais **aléatoires** entre chaque action (intervalle configurable)
- Petits mouvements de souris aléatoires autour des positions cibles
- Arrêt automatique si le presse-papiers ne contient pas un item POE valide
- Arrêt si le nombre max d'itérations est atteint

---

## Stack technique

- **Python 3.8+**
- `pyautogui` — contrôle souris/clavier
- `pyperclip` — lecture du presse-papiers
- `pynput` — écoute des hotkeys globaux (F5/F6)
- `tkinter` — interface graphique (natif Python)
- Plateforme cible : **Windows** (là où POE tourne)

---

## Fichiers du projet

```
AutoCraft/
├── main.py              # Point d'entrée, GUI tkinter
├── requirements.txt     # Dépendances
├── SPEC.md              # Ce fichier
└── src/
    ├── __init__.py
    ├── item_parser.py   # Parse le texte clipboard POE
    ├── conditions.py    # Vérifie les conditions sur un item
    └── crafter.py       # Boucle de craft principale
```



## Clusters

1 affixe(magique):

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
Place into an allocated Medium or Large Jewel Socket on the Passive Skill Tree. Added passives do not interact with jewel radiuses. Right click to remove from the Socket.


2 affixes(magique):

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
Place into an allocated Medium or Large Jewel Socket on the Passive Skill Tree. Added passives do not interact with jewel radiuses. Right click to remove from the Socket.

3 affixes(rare):

Item Class: Jewels
Rarity: Rare
Brood Shard
Medium Cluster Jewel
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
1 Added Passive Skill is Brush with Death
--------
Place into an allocated Medium or Large Jewel Socket on the Passive Skill Tree. Added passives do not interact with jewel radiuses. Right click to remove from the Socket.

4 affixes(rare):

Item Class: Jewels
Rarity: Rare
Brood Shard
Medium Cluster Jewel
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
Added Small Passive Skills also grant: 5% increased Mana Regeneration Rate
Added Small Passive Skills also grant: +4 to Maximum Energy Shield
1 Added Passive Skill is Brush with Death
--------
Place into an allocated Medium or Large Jewel Socket on the Passive Skill Tree. Added passives do not interact with jewel radiuses. Right click to remove from the Socket.
