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
