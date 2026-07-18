# Runbook de mise en production — TPDL Lead Intelligence

> Chargé à la demande. Écrit le 2026-07-15, quand le code était **complet et gated** : tout tourne
> en dry-run (0 coût) ; il ne manque que les clés externes et quelques décisions. Ce fichier est le
> chemin CLÉ-EN-MAIN pour passer en réel, ordonné par dépendance. Chaque étape dit : quelle clé,
> ce qu'elle débloque, la commande exacte, comment vérifier, le garde-fou coût.
>
> Règle d'or (constitution) : **rien ne dépense sans `--live` + une clé**. Un run sans clé ne
> fabrique jamais de donnée — il s'arrête proprement (money gate `require_live()`).

## Pré-requis (une fois)
```bash
cp .env.example .env         # puis remplir les clés au fur et à mesure (voir étapes)
make run                     # lance le dashboard sur http://localhost:8000 (PORT=8080 pour changer)
python -m pytest -q          # doit afficher 123 passed
```
`.env` n'est JAMAIS commité (couvert par `.gitignore`). `.env.example` liste tous les noms de variables.

---

## Étape 1 — Clé Anthropic (débloque le chat + le scoring live) 🔑 PRIORITÉ 1
- **Variable** : `ANTHROPIC_API_KEY=sk-ant-...` dans `.env`.
- **Débloque** : (a) le chat live des 9 agents dans le dashboard ; (b) l'extraction (Sonnet 5) +
  l'interprétation/scoring (Opus 4.8) du moteur.
- **Vérifier le chat** : `make run` → ouvrir http://localhost:8000 → parler à un agent (ex. Hugo
  `/company Organon`). Sans clé, l'agent l'explique au lieu de planter.
- **Vérifier le moteur (dry-run d'abord, 0 coût)** :
  ```bash
  python -m pipeline.runner --fixture pipeline/fixtures/probe_diagnostics.json
  ```
- **Coût** : Sonnet 5 = 2 $/10 $ le MTok (tarif de lancement jusqu'au 31/08/2026), Opus 4.8 =
  5 $/25 $. Batch API = -50 %.

## Étape 2 — Au moins une source de recherche (débloque un run LIVE réel) 🔑 PRIORITÉ 1
- **Variables** (une suffit pour démarrer ; les autres enrichissent) :
  - `SERPER_API_KEY=` — Google News + Jobs (**préféré** ; free 2500/mois). Si absent, le moteur
    bascule automatiquement sur `SERPAPI_KEY=` (SerpAPI) sans changement de code.
  - `EXA_API_KEY=` — recherche neuronale (Q1 news / Q2 leadership / Q3 M&A).
  - `PERPLEXITY_API_KEY=` — presse financière (PE/M&A ; renvoie sans URL → corroboration 0).
  - `FIRECRAWL_API_KEY=` — fetch pages IR (conditionnel).
  - `EU_REGISTRY_ENABLED=true` — registres UE via le SERP déjà payé (source GRATUITE, opt-in).
- **Toujours pré-voler le coût AVANT de dépenser** :
  ```bash
  python -m pipeline.runner --top 5 --estimate      # n'appelle rien, imprime le coût + quota SerpAPI
  ```
- **Premier run LIVE, petit et plafonné** :
  ```bash
  python -m pipeline.runner --top 5 --live --max-usd 1
  ```
  `--max-usd` = coupe-circuit dur : le run s'arrête AVANT de dépasser le plafond. `--batch` ajoute
  -50 % (scoring en Batch API, jusqu'à 24 h). `--resume` reprend un run interrompu.
- **Réinjecter le résultat dans le dashboard** :
  ```bash
  python import_csv.py data/csv/engine_run.csv        # crée un RunSnapshot = run #2
  ```

## Étape 3 — `/recurring` de Maya s'active (mécanique, aucune action de code)
- L'historique contient **déjà** le run 25/05 (run #1, amorcé par `backfill_snapshots.py`).
- Dès que l'Étape 2 produit et importe un **2e** run, `/recurring` passe d'« aveugle » à actif.
- **Vérifier** : dans le chat, demander à Maya `/recurring` → elle compare les signaux entre runs.
  Page historique : http://localhost:8000/credits (route data `/runs`).

## Étape 4 — Contacts (Inès) 🔑
- **Variables** : `KASPR_API_KEY=` (**préféré**, meilleure couverture CH/ES) OU `APOLLO_API_KEY=`.
  Inès choisit Kaspr si sa clé est là, sinon Apollo. Aucune des deux → elle décrit la cible sans
  jamais inventer de contact.
- **Débloque** : `/contacts <société>` (décideurs + LinkedIn + segmentation 5 axes, dédupliqué).
- **Vérifier email avant tout envoi** : `BOUNCER_API_KEY=` → seuls les emails `deliverable`
  doivent partir. Toute erreur de vérif = `unknown` (fail-closed, jamais « safe to send »).

## Étape 5 — Séquences (Julie → Lemlist) 🔑 ⚠️ SORTANT
- **Variable** : `LEMLIST_API_KEY=`.
- **⚠️ Action sortante** : `add_lead_to_campaign` enrôle une vraie personne dans une vraie séquence.
  Ce n'est **jamais** automatique : un humain enrôle le lead APRÈS validation du message ET
  seulement si Bouncer l'a marqué `deliverable`. Les Premium 5 restent gérés par Andrés en direct.

## Étape 6 — Git partagé + `main` protégée (Andrés)
- Aujourd'hui : repo local, branche `feat/neotek-engine` mergée dans `main` (local).
- À faire : créer le remote partagé (`git remote add origin ...`), pousser, protéger `main`
  (PR obligatoires). NE PAS committer `.env`.

---

## ⛔ GATE RGPD — avant le 1er envoi (UE/CH), non négociable
Cibles UE/Suisse → vérifier la base légale (intérêt légitime B2B), le mécanisme d'opt-out, et la
minimisation des données AVANT le premier message. À trancher avec Andrés. Voir CLAUDE.md § RGPD.

## Ordre recommandé (le plus court chemin vers un signal de valeur)
1. Anthropic → 2. Serper (ou SerpAPI) → `--estimate` → `--top 5 --live --max-usd 1` →
   `import_csv.py` → `/recurring` actif. **C'est le premier jalon bout-en-bout.**
2. Ensuite : Kaspr/Apollo + Bouncer (contacts vérifiés) → Julie (messages) → Lemlist (humain).
3. En parallèle : remote git + gate RGPD.

## Garde-fous déjà en place (rien à installer)
- Money gate : dry-run par défaut, `--live` obligatoire, clé obligatoire.
- `--estimate` : coût + quota SerpAPI avant de dépenser.
- `--max-usd` : coupe-circuit budget dur.
- Garde-fou quota SerpAPI : refuse de démarrer un run qui finirait à moitié (sauf `--force`).
- Vera (QA) + file de revue humaine `/review` (http://localhost:8000/review).
- Connecteurs contacts/email/séquences : fail-closed, ne fabriquent jamais de donnée.
```

---

# Le RITUEL DU RUN MENSUEL (checklist reproductible — ajouté 2026-07-18)

> Cadence actée : ~1 run/mois. Chaque euro est décidé AVANT d'être dépensé.
> Coûts de référence : découverte <0,50 $ · scoring ~0,055 $/société (~0,03 $ en batch)
> · run 67 sociétés ≈ 4-5 $ · run ~500 ≈ 40-60 €. SerpAPI Free = 250 recherches/mois
> (2/société, découverte ≈ 8) ; la recherche déjà en CACHE (<7 j) ne consomme rien.

## AVANT (0 coût)
1. **Vera `/audit`** (sans argument) dans le chat → l'univers est-il propre ?
   Doublons/localisations à régler AVANT (sinon l'outreach hérite des défauts).
2. **Quota** : ouvrir la page Usage (localhost:8000/credits) → SerpAPI restant,
   crédits Firecrawl, tally Anthropic.
3. **Devis** : `python -m pipeline.runner --lunch --estimate` (ou `--top N`) —
   affiche coût modèle + besoins SerpAPI, ne dépense rien.
4. **Accord budget** (Andrés/Nathalie si >10 €). Pas d'accord = pas de run.

## LE RUN (dépense explicite, plafonnée)
5. **Découverte** (~0,50 $) : `python -m pipeline.runner --discover --live`
   → `data/csv/discovery_candidates.csv` (nouveaux candidats par thème).
6. **Sélection** : lunch/top + candidats selon le quota restant
   (candidats × 2 ≤ SerpAPI restant ; prioriser earnings_call > digital > pe).
7. **Soumission batch (−50 %, Mac libre ensuite)** :
   `python -m pipeline.runner --names "<A;B;C>" --live --batch --submit --max-usd 12`
   (+ `--rescan-tech` ~1×/trimestre pour rafraîchir les tech stacks Apify).
   ⚠️ La phase locale (recherche+extraction) prend ~1-2 h : Mac ouvert, branché
   (`caffeinate -i` aide). Ensuite → state JSON sauvé, **Mac éteignable**.
   🛑 STOP D'URGENCE à tout moment : `pkill -f pipeline.runner` — tant que le
   state `.pending.json` n'existe pas, AUCUN batch n'a été soumis (0 $ scoring).
8. **Récupération (≤24 h après)** :
   `python -m pipeline.runner --fetch data/csv/<out>.csv.pending.json`
   (répéter jusqu'à « ended » ; écrit le CSV final).

## APRÈS (0 coût)
9. **Import** : `python import_csv.py data/csv/<out>.csv` → DB + snapshot run.
10. **Vera `/audit`** → 0 nouvelle issue attendue (sentinelles, formats, doublons).
11. **Maya** : `/trends` (le run frais vs le stock — digital/hiring montent ?) ·
    `/recurring` (RISERS/FADERS + NEW THIS RUN = les nouveaux candidats) ·
    `/top` (fraîcheur par ligne).
12. **File humaine** : page /review → traiter les review-flags (motifs porteurs
    uniquement depuis le fix « resting on speculation »).
13. **Mémoire** : consigner le run dans `.claude/state.md` (coût réel, éligibles,
    findings) + commit.
