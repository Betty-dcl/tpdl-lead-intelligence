# CLAUDE.md — Mémoire persistante — TPDL Lead Intelligence

> Chargé automatiquement au début de CHAQUE session (à la racine du repo).
> Source de vérité du projet. Le détail long vit dans les fichiers importés en bas.

## RÈGLE DE MÉMOIRE (lis ça en premier)
- Tu LIS ce fichier automatiquement à chaque session. Tu ne le RÉÉCRIS PAS tout seul.
- Après toute décision structurante (modèle, seuil, outil, convention), PROPOSE de mettre à
  jour ce fichier + `.claude/state.md`, dans le même commit que le changement de code. Ne laisse
  jamais le code et la mémoire diverger.
- Contradiction entre ce fichier et le code réel → signale-la, ne devine pas.
- Mémoire canonique = CE repo (racine + `.claude/`). L'ancienne copie dans
  `Downloads/tpdl-memory/` est SUPERSEDÉE et peut être supprimée.

## ⚠️ DEUX SYSTÈMES À NE PAS CONFONDRE
1. **Ce repo = le DASHBOARD / cockpit + agents de chat.** App FastAPI. Les agents (Hugo, Maya,
   Inès, Julie, Iris, Marc, Oliver + manager) LISENT une base d'entreprises déjà scorée (table
   `companies`) et la restituent / analysent en chat. Ils NE produisent PAS le scoring.
2. **Le MOTEUR pipeline Neotek** (recherche → extraction → scoring → CSV). **Code NON accessible**
   (propriété Neotek). On ne possède que les CSV de sortie (run du 25/05 : 492 entreprises, 35
   éligibles). Pour « alimenter le process », il faudra soit obtenir l'accès, soit RECONSTRUIRE
   ce moteur ici — c'est le chantier du Step 3.

## ÉTAT ACTUEL (ce qui tourne vraiment, aujourd'hui)
- Dashboard FastAPI ; agents de chat sur **Opus 4.8** (un seul modèle, variable `ANTHROPIC_MODEL`).
- Données : issues du run Neotek du 25/05 (à rafraîchir — mais dépend du moteur inaccessible).
- Outils câblés dans le code : **SerpAPI**, **Apollo** (partiels/stubs). Clés Exa/Perplexity/Apify vides.
- Outreach/CRM réel (terrain, hors repo) : **PipeDrive** (CRM), **Surf** (LinkedIn→PipeDrive),
  Sales Navigator, **MailChimp** (newsletters). Envoi des messages MANUEL par un SDR en Inde.
  Détail dans `.claude/operational-context.md`.
- PAS de pipeline d'extraction/scoring dans ce repo.
- PAS encore de dépôt git initialisé.

## ÉTAT CIBLE (où on va)
- Pipeline reconstruit, séparation à 2 modèles : **extraction = Sonnet 5**, **interprétation /
  scoring = Opus 4.8**.
- Outils : **Serper** (← SerpAPI), **Kaspr** (← Apollo), Firecrawl, Perplexity, Bouncer, Lemlist.
- Campagne Lunch : 48 entreprises CH + 19 ES.

## ROADMAP MACRO (4 steps — on avance petit à petit)
1. **Abonnements / API** : décider quoi payer (Anthropic, Firecrawl, Perplexity, Serper, Kaspr,
   Bouncer, Lemlist). Priorité juste après la base.
2. **Former chaque agent** : prompt détaillé + contenu de résultat attendu, agent par agent.
3. **Améliorer le workflow** : reconstruire / brancher le moteur pipeline, connecter les outils.
4. **Essayer** : run de bout en bout, mesurer, itérer.
> Priorité IMMÉDIATE avant tout ça : établir la BASE + la MÉMOIRE propre (ce fichier).
> Le détail granulaire vit dans `.claude/roadmap.md`.

## LA CONSTITUTION (les agents la suivent sans dévier)
1. **Séparation à deux modèles STRICTE** :
   - Extraction (**Sonnet 5**) : sort des phrases verbatim, n'interprète JAMAIS.
   - Interprétation (**Opus 4.8**) : juge, mais ne voit JAMAIS le texte source brut — uniquement
     les blocs d'évidence déjà isolés.
   - Ces deux étapes ne fusionnent jamais. L'anti-hallucination est STRUCTURELLE, pas seulement
     dans le prompt.
   - ⚠️ Sonnet 5 étant un modèle fort, son prompt d'extraction doit VERROUILLER le verbatim (zéro
     éditorialisation) encore plus fermement qu'avec l'ancien Haiku.
2. Ne scorer que des signaux prouvés ET datés. Sinon → `signals_not_evidenced`.
3. Formule déterministe : `score = signal_strength(0-6) + recency(0-2) + corroboration(0-2)`.
4. `assessed_score` = moyenne sur les signaux TROUVÉS seulement (pas sur les 6 types).
5. `outreach_eligible = assessed_score >= 8`.
6. Intelligence Summary = EXACTEMENT 3 phrases (situation / statut signaux / timing TPDL).
7. Chaque affirmation doit être traçable à une phrase source précise.

## LES 7 RÈGLES DURES ANTI-HALLUCINATION (prompt interprétation Opus 4.8)
1. Raisonner uniquement depuis le bloc d'évidence fourni.
2. Ne jamais inventer dates, noms, événements.
3. Ne pas combiner deux évidences pour en fabriquer une troisième.
4. Catégorie non prouvée → `signals_not_evidenced`.
5. Toute affirmation traçable à une phrase source.
6. Compléter la chaîne EVENT → PRESSURE → GAP → TPDL SERVICE AREA, sinon `relevance = null`.
7. `signal_strength` est le SEUL input de scoring. Pas de bonus discrétionnaire.

## LE SCORING (détail — design Neotek de référence)
- recency : ≤90j = 2 ; ≤6 mois = 1 ; sans date = 0.
- corroboration : 2+ sources = 2 ; 1 URL vérifiée = 1 ; Perplexity seul sans URL = 0.
- signal_strength (0-6) fixé par l'interprétation = pertinence commerciale UNIQUEMENT.
- Tout est ajustable dans `scoring_config.yaml` (poids NON codés en dur). Seuil outreach : 8.

## LES 6 SIGNAUX SCORÉS → DOMAINES DE SERVICE TPDL (design Neotek)
- leadership_change → Operating model / Commercial effectiveness
- hiring → Commercial effectiveness / Digital execution & activation
- ma_expansion → Operating model alignment / CRM & data strategy
- pe_event → Operating model alignment
- digital_initiative → Digital execution & activation / Customer journey optimisation
- org_restructuring → Operating model alignment / CRM & data strategy
EXCLUS (ne sont PAS des signaux) : certifs réglementaires, lancements produits non liés,
descriptions génériques, affirmations sans date.

## LES 8 SOURCES DE RECHERCHE (Step 2 — design cible)
Exa Q1 (news), Exa Q2 (leadership/hiring), Exa Q3 (M&A/expansion),
Perplexity Sonar (PE/M&A presse financière, SANS URL → corroboration 0),
Serper Google News (← remplace SerpAPI), Serper Google Jobs (← remplace SerpAPI),
Registres UE (conditionnel), IR page fetch (conditionnel).

## LE PIPELINE (6 steps — design Neotek, moteur à reconstruire)
0 Load → 1 Tech scan (Wappalyzer/Apify) → 2 Research (8 sources) →
3 Extract (Sonnet 5) → 4 Score (Opus 4.8) → 5 Fetch/batch poll (Batch API) → 6 Output CSV.
Sortie finale : `scored_results.csv` (38 colonnes). NON implémenté dans ce repo.

## ÉTAT DE RÉFÉRENCE DES DONNÉES (run du 25/05 — figé, moteur inaccessible)
492 entreprises scorées, 35 outreach-eligible (≥8).
Top : Organon 9.5, Hologic 9.5, Eurobio Scientific 9.0, UCB 9.0.
Maya `/recurring` reste AVEUGLE tant qu'il n'y a qu'un seul run (2e run bloqué par l'accès moteur).

## LES 8 AGENTS (rôle / phase / outils)
- Hugo — Détection, moteur Neotek (Steps 0-6). Aujourd'hui : LIT seulement la DB scorée.
  Cible : extraction Sonnet 5. Outils cible : Exa, Perplexity, Serper, Apify.
- Maya — Analyse, re-scoring (`/top` `/trends` `/recurring`). `/recurring` exige ≥2 runs.
- Inès — Contacts + vérif email. Cible : Kaspr (← Apollo), Bouncer.
- Julie — Rédaction voix Andrés. Playbook LinkedIn v2.1 + Brand DNA. Sort vers Lemlist.
- Iris — Recherche/scoring sujets marketing. Outil cible : Serper (← DuckDuckGo).
- Marc — Architecte de contenu. Dépend du Brand DNA.
- Oliver — Producteur de formats (A4/carousel/PPT/web), branding #094752 / #34D591.
  Renderers PDF (fpdf2) + PPTX (python-pptx) CONNECTÉS (endpoints export dans `marketing.py`).
- Andrés — Humain (fondateur). Voix des messages. Premium 5 = 5 comptes gérés en direct.

## FICHIERS CLÉS DU REPO (corrigés)
- `app/config.py` — `anthropic_model` (**Opus 4.8** pour le chat) + Settings. ⚠️ Il n'y a PAS de
  `pipeline/config.py` (n'existe pas dans ce repo).
- `scoring_config.yaml` — poids de scoring (recency/corroboration/seuil 8).
- `app/agents/` — logique/commandes des 8 agents ; `app/agents/base.py` fait l'appel Anthropic.
- `seed.py` — sème les prompts système en DB (`python seed.py`, idempotent/upsert).
  Agents FORMÉS → prompt versionné dans `app/agents/prompts/<agent>.md` (chargé par seed.py).
  Formés : **les 8 agents** — Alex (manager) + Sales (Hugo, Maya, Inès, Julie) + Marketing (Iris,
  Marc, Oliver), chacun dans `app/agents/prompts/<id>.md` (2026-07-12).
  ⚠️ « Former un agent » = écrire son `.md` + re-seeder, PAS éditer `app/agents/*.py`.
- `app/agents/playbooks/andres_linkedin.md` — playbook LinkedIn v2.1.
- `app/tools/` — outils actuels : `apollo.py`, `web_search.py`, `radars.py`, `pdf_export.py`, etc.
- `.env` (JAMAIS commité) / `.env.example` (commité, noms de variables sans valeurs).
- Brand DNA : `history` rempli ; `clients` et `projects` VIDES → À REMPLIR.

## STACK + BUDGET (à re-vérifier avant de payer — RÉVISÉ)
- ⚠️ Le budget « Anthropic ~5-15 $/mois » n'est PLUS valable : l'extraction sur Sonnet 5 (au lieu
  de Haiku, ~20× moins cher) augmente sensiblement le coût. À re-chiffrer au Step 1.
- Sonnet 5 : 2 $/10 $ le MTok (tarif de lancement jusqu'au 31/08/2026), puis 3 $/15 $.
  Opus 4.8 : 5 $/25 $ le MTok. Batch API : remise -50 %.
- Autres : Serper (free 2500/mois), Firecrawl, Kaspr, Bouncer, Lemlist — chiffres à confirmer.
- Orchestration : n8n (mutualiser l'instance Devengo plutôt que payer — à confirmer avec Andrés).

## CONVENTIONS DE TRAVAIL
- Git : PAS encore initialisé. À faire (repo partagé avec Andrés, `main` protégée, `.gitignore` .env).
- Committer : CLAUDE.md, `.claude/*`, `.mcp.json`, `scoring_config.yaml`, prompts d'agents.
  JAMAIS les secrets ni le `.env`.
- Mettre à jour ce fichier + state.md à chaque décision structurante (voir RÈGLE DE MÉMOIRE en haut).
- RGPD : cibles UE/Suisse → vérifier base légale (intérêt légitime B2B, opt-out) avant 1er envoi.

## IMPORTS (détail long, chargé à la demande)
@.claude/neotek-process.md
@.claude/agents.md
@.claude/roadmap.md
@.claude/operational-context.md
@.claude/state.md
