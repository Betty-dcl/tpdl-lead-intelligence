# État courant — journal de bord vivant

> C'est LE fichier qui bouge le plus. Après chaque session, mettre à jour « Dernière session »
> et la checklist des blocages. Claude Code doit PROPOSER de le faire.

> 📘 **Mise en production** : chemin clé-en-main ordonné dans `.claude/go-live-runbook.md`
> (quelle clé débloque quoi, commandes exactes, garde-fous, gate RGPD). Chargé à la demande.

## Où on en est
- Phase : **Step 3 (workflow) largement FAIT en code** — le moteur Neotek est reconstruit dans
  `pipeline/` (dry-run 0 coût + `--live` gated, 112 tests verts). Step 2 (formation) terminé côté
  prompts (9 agents avec Vera). ⚠️ Les clés recherche + Anthropic sont DANS `.env` (2026-07-16) ⇒
  un run LIVE est techniquement possible (voir log) ; aucun lancé sans accord (coût). Vides :
  Serper, Apollo, Kaspr, Bouncer, Lemlist.
- Base + mémoire : posées et rapatriées dans le repo.
- Dernier run Neotek : 25/05 (492 entreprises, 35 éligibles) — FIGÉ. Amorcé comme run #1 dans
  `RunSnapshot` ; `/recurring` s'active au 2e import réel.

## Décisions prises (log — ajouter en haut, avec la date)
- 2026-07-20 — **Refonte UI « traçabilité du run » + page Découvertes + audit pré-démo (demande Betty).**
  Objectif : présenter la plateforme demain, tout traçable/clair/pro, 0 lien cassé. Fait :
  (1) **Backend intel** : `_neotek_baseline` + enrichissement `_serialize_company` (neotek_score/delta/
  reappeared) + `corroboration` re-dérivée par signal (2+ URLs→2, 1→1, 0→0) ; nouveaux endpoints
  `/api/intel/run` (cockpit : bandes act_now/monitor/weak/none, mouvement vs Neotek, net_new_scored,
  discovered_candidates), `/companies/{n}/trajectory` (courbe mai→juillet), `/export.csv` (42 cols +
  delta), `/candidates` (lit `discovery_candidates.csv`, 122 nouvelles, flag not-scored).
  (2) **Sales (`/intel`)** : cockpit du run (67 sociétés, 7 ≥8, top Cantabria 8.5, 45↑/18↓/4=), colonne
  **Δ Neotek** + bordure gauche couleur « réapparue » (vert↑/rouge↓/gris=), noms cliquables, CSV Excel,
  ligne « 0 nouvelles → 122 candidates ».
  (3) **Fiche société** (nouveau `/intel/company?c=`) : formule du score expliquée, courbe d'évolution
  (Chart.js, caveat cross-engine), signaux avec confiance + corroboration + **liens news cliquables**,
  bandeau « seen before » + delta, export CSV.
  (4) **Contacts** : bandeau run + deltas + « act now » + fiches cliquables.
  (5) **Runs** : carte « Since the Neotek May run » (67 réapparues, top riser/fader) — le delta cross-engine
  que Betty voulait (avant : Neotek exclu).
  (6) **Page Candidates (nouvelle, dans le menu)** : les 122 découvertes vendredi, étiquetées **FOUND ≠
  SCORED** (0 scorée), filtrables par thème, liens sources. Répond à « comment voir du neuf ».
  (7) **Audit pré-démo** : 0 lien cassé (22 pages + routes dynamiques toutes 200), 0 erreur console,
  scoring prouvé RÉEL (63/67 diffèrent de mai, sources 2026). Polish : login (mot de passe exposé +
  « Demo borrador » retirés), marketing (« mock/V1/V2 » → « illustrative »), Home/Sales (« Top 50/weekly »
  → « shortlist/monthly »), Today (« veille » → « market scan », Monday→monthly), fiche agent + 404
  re-charte + « Open Space »→« Home », Review (explication claire du garde-fou Vera), Usage (jargon `.env`/
  dry-run adouci). +5 tests. Suite : **205 verts**.
  RESTE (décisions Betty) : fusionner les 2 générateurs Marketing (Auto Pipeline vs Carousel Studio) ;
  Performance & Data laissés hors menu (internes) ; rebrand cosmétique #094752→#0A0A0A + Funnel Sans
  (migration à part, non faite).
- 2026-07-18 — **Maya : shortlist par SEUIL/bandes, pas un top-50 figé (décision Betty).** Un « top 50 »
  bourre un petit run de scores 2 (sur ce run il descendrait à ~2). Nouvelle commande **`/shortlist`**
  (le livrable pour Inès) : **ACT NOW = in-scope ≥ 8** (seuil constitution), **MONITOR = 5-7** (les
  risers du mois prochain), <5 parké ; départage couverture puis fraîcheur ; plafond souple 40 qui ne
  mord que si la bande ≥8 explose ; ACT NOW vide = dit honnêtement, jamais rembourré. `/top [N]` reste
  la vue SCAN secondaire (« N meilleurs quoi qu'il arrive »). Vérifié live : 23 ACT NOW + 170 monitor,
  fraîches devant STALE à score égal. maya.md + docstring recadrés, re-seed. +1 test. Suite : **200 verts**.
- 2026-07-18 — **Audit de vérité des 6 agents restants + répétition générale du rituel (commit
  ci-dessus).** (1) Iris, Marc, Julie : PROPRES. Inès (« frozen 492/35 » → lire les chiffres courants ;
  weekly → monthly), Oliver (double vérité charte : renderers = teal legacy #094752 AUJOURD'HUI,
  charte OFFICIELLE Nathalie = à la migration — ne jamais prétendre qu'un fichier sort en charte
  officielle), Vera (connaît son /audit univers + les flags « porteurs » du 18/07) : CORRIGÉS +
  re-seed. Code de dispatch exercé sur données réelles : honnête partout. (2) **Répétition générale
  du rituel mensuel en dry-run (0 €)** : devis OK, run fixture OK (CSV 38 colonnes importable).
  Deux enseignements réels : (a) le garde-fou quota marche — un run lunch complet avec registre UE
  (204 recherches) DÉPASSE le quota SerpAPI restant (102) → la clé SERPER (2 500/mois gratuits)
  devient le prérequis pratique du prochain run complet ; (b) le set --lunch est passé à 68 (le
  remplissage des localisations du nettoyage a fait entrer PeploBio (Spain) dans le périmètre CH+ES).
  Suite : **197 verts**. Le plan d'amélioration à coût zéro est SOLDÉ.
- 2026-07-18 — **Hugo remis au niveau du moteur + registre UE public ACTIVÉ par défaut (commit
  7efa3c2, poussé GitHub).** Constat : hugo.md ne mentionnait NI la découverte, NI le nouveau scope,
  NI les 122 candidats (0 occurrence de « discover ») + une phrase morte « needs API keys ». Fait :
  (1) hugo.md Mode C DISCOVERY (scope veille large tranché par Betty, mécanique --discover, angle
  earnings-call, candidats = décision humaine avant dépense) + table des sources corrigée (registre
  via SERP pas Firecrawl ; SerpAPI actif tant que Serper absent) + re-seed. (2) **`/candidates`** :
  nouvelle commande Hugo — affiche discovery_candidates.csv par thème dans le chat = la porte de
  relecture humaine AVANT de payer le scoring (found ≠ scored ; jamais inventer de détails sur un
  candidat non scoré). (3) **Registre UE public GRATUIT par défaut ON** (demande Betty) : config
  default true, kill-switch EU_REGISTRY_ENABLED=0 + flag --no-eu-registry ; estimateur passé à
  **3 recherches SERP/société** (News+Jobs+registre) pour que le garde-fou quota reste honnête.
  +4 tests. Suite : **197 verts**. RESTE du plan accepté : audit de vérité des 6 agents jamais
  audités (Inès, Julie, Iris, Marc, Oliver, Vera) + répétition générale du rituel mensuel en dry-run.
- 2026-07-18 — **Process durci à coût zéro (commit cfc9b48) : runbook mensuel + tests CLI + hygiène
  Git.** (1) `go-live-runbook.md` : section « RITUEL DU RUN MENSUEL » — checklist reproductible en 13
  étapes (audit Vera → quota → --estimate → accord budget → discover → sélection sous quota → batch
  submit/fetch → import → audit → lectures Maya → file /review → mémoire), coûts de référence, règle
  du cache, et STOP d'urgence (`pkill` avant le .pending.json = 0 $ de scoring). (2) +3 tests CLI :
  main() dry-run bout-en-bout écrit un CSV valide ; --rescan-tech strippe les résumés stockés ;
  --discover sans --live refuse. Suite : **194 verts**. (3) ⚠️ `data/.session_secret` était TRACKÉ
  dans Git → retiré de l'index, fichier régénéré (auto au prochain démarrage), .gitignore couvre
  désormais secret + artefacts de run (engine_run*.csv, discovery_candidates.csv). `main` mergé (ff)
  = à jour avec feat/neotek-engine. RESTE (action Betty, 5 min) : créer le repo GitHub privé + push.
  NB : run #2 ANNULÉ sur demande Betty (dépense stoppée à 1,62 $ du jour, aucun batch soumis) ;
  les 122 candidats découverts restent prêts dans discovery_candidates.csv (non tracké).
- 2026-07-18 — **Plan post-analyse du run lunch EXÉCUTÉ (OK Betty) : flags porteurs + 1re DÉCOUVERTE
  réelle (122 candidats) + run stratégique #2 soumis.** (1) **Fix « spéculation porteuse »**
  (commit 263dee5) : le review-flag spéculation se décide au niveau du SIGNAL scoré — flag seulement
  si TOUTE l'évidence d'un signal est hedgée (« resting entirely on speculative/hedged quotes ») ;
  une citation hedgée parmi des citations propres ne flagge plus (le run lunch flaggait 53 % — 34/36
  pour ce seul motif). +2 tests, 191 verts. (2) **Grifols/Geistlich vérifiés en base** (7.2/6.8, snapshots
  juillet à jour, historique toujours 2 runs). (3) **1re découverte live** : 462 findings/8 thèmes →
  bug de troncature corrigé (commit e363d87 : chunks de 80 + salvage — 13 entrées sauvées d'un chunk
  tronqué) → **122 candidats NOUVEAUX** (`discovery_candidates.csv` ; qualité élevée : DocMorris,
  Recordati, Evotec, Lundbeck, Galapagos… ; 9 earnings-call, 14 PE). (4) **Run #2 SOUMIS** (batch
  `--submit`) : 67 lunch (recherche en cache = 0 quota SERP) + **50 candidats priorisés par thème**
  (earnings-call > digital > PE > restructuring > hiring > leadership ; les 48 ma_expansion attendent
  le quota d'août — SerpAPI restant : 102, sélection = 100 recherches) + `--rescan-tech` (Apify) +
  `--force` (l'estimateur ignore le cache) + `--max-usd 12`. Sortie : `engine_run_strategic.csv` ;
  état pending → `--fetch` quand Anthropic a fini (≤24 h). ⚠️ Reco : créer la clé SERPER (2 500
  recherches/mois gratuites) pour débloquer les 72 candidats restants + les prochains runs larges.
- 2026-07-18 — **Nettoyage données VOLET 1 APPLIQUÉ (OK Betty).** Fusions évidentes : « ADOR
  Diagnostics » (0.0, même site que la ligne Italy) et « NADMED (Finland) » (6.5, doublon de NADMED
  7.0) supprimées — société + signaux + snapshots (l'historique /recurring reste cohérent). Les 15
  localisations manquantes remplies (Eurobio→Les Ulis FR, Trinity→Bray IE, EKF→Cardiff UK, Labor
  Berlin→DE, TBR→Toulouse FR, etc. ; NeoGenomics→Fort Myers USA = hors-Europe à statuer). Table
  signals resynchronisée. **Re-audit Vera : 490 sociétés, 0 sans-localisation, 0 sentinelle, 0
  incohérence — ne restent que les 3 groupes du volet Nathalie** (③ Julphar UAE, ④ Glenmark parent/
  filiale, ⑤ trio Sesderma/Mediderma). Dossier Obsidian passé en statut « volet 1 appliqué ».
  ⚠️ La table `companies` a maintenant divergé des CSV d'export passés (normal — la DB est la vérité).
- 2026-07-18 — **SCOPE TRANCHÉ PAR BETTY (les 6 questions) + étape DÉCOUVERTE construite + signal
  earnings-call encodé (commit 52a10a0).** Décisions Betty (Nathalie peut amender ; doc de segmentation
  Obsidian mis à jour §9) : taille = TOUT (pas de plancher) ; cotées/privées = TOUT ; thèmes = les
  6 signaux existants + angle earnings-call ; dédup = AFFICHER les récurrences avec compteur (« revenu
  2×/3× », = /recurring de Maya), jamais filtrer ; volume = ce que la veille trouve (seuil ≥8 = seul
  filtre). Construit : (1) **`pipeline/discovery.py`** — la capacité manquante « top 35 + du NOUVEAU » :
  8 requêtes thématiques (Exa + SERP news) → 1 appel Sonnet (noms de sociétés SUJET des findings,
  verbatim, JSON strict, consultants/investisseurs/universités exclus) → dédup normalisé vs univers →
  `data/csv/discovery_candidates.csv` (nom/thème/URL source). CLI `--discover` (exige `--live`,
  <0,10 $/passe) ; les candidats se scorent ensuite via `--names`. (2) **Angle earnings-call dans les
  prompts moteur** : extraction (digital_initiative inclut explicitement les déclarations earnings-call/
  rapport annuel « digital = priorité board ») + scoring (bloc BOARD-LEVEL DIGITAL PRIORITY : force 4-5,
  pas 3, traçabilité inchangée). +4 tests. Suite : **189 verts**. Reste avant le 1er run stratégique :
  appliquer le dossier de nettoyage (doublons/localisations, en attente OK Betty/Nathalie) puis
  `--discover --live` → scorer les candidats.
- 2026-07-18 — **Relecture complète des sorties Hugo/Maya → audit d'intégrité PERMANENT (commit
  6b17fb4).** Audit systématique des 492 lignes (2 runs) codifié en garde-fou reproductible :
  (1) `app/tools/integrity.py` — contrôles déterministes 0 coût (doublons de sociétés normalisés,
  résumés hors bande 2-4 phrases, sentinelles, cohérence score↔éligibilité, high-conf sans URL non
  flaggé, localisations manquantes, secteurs Unknown, drift table signals) ; (2) **Vera `/audit` sans
  argument = audit de l'UNIVERS entier** (avec nom = audit société inchangé) ; (3) défense moteur :
  résumé hors 2-4 phrases (avec signaux) → review-flag « summary format breach » à la source.
  **Constat sur données réelles : 34 issues** — 5 groupes de doublons (Sesderma/Mediderma ×3 dont un
  localisé « San Marcos, Ca », Glenmark ×2, Julphar, NADMED, ADOR), 12 résumés hors format (11 de mai
  legacy + 1 de juillet), 17 sans localisation (⇒ pas de locale SERP UE), 138 secteurs « Unknown »
  (trou du CSV source). SAIN : 0 sentinelle, 0 incohérence éligibilité, 0 high-conf non flaggé,
  signals sync OK. Nettoyage des doublons/localisations = tâche DONNÉES (à trancher avec Nathalie,
  idéalement avant le run stratégique). +4 tests. Suite : **185 verts**.
- 2026-07-18 — **Compteur local Exa/Perplexity (commit 07e6393).** Question Betty : « on ne pourra
  jamais savoir combien ? » → Si : le moteur est le seul à connaître le nombre de requêtes qu'il
  envoie, donc il les compte lui-même. `log_search_calls` (fail-open, `activity_log` action
  `engine_search` sous hugo) ; `exa_search` logge le nombre RÉEL de requêtes abouties (finally —
  un run avorté compte ce qui a été dépensé), `perplexity_sonar` 1/appel. Cartes Exa/Perplexity :
  « N requests this month · M all-time (counted by the engine) » au lieu du simple « no usage API ».
  ⚠️ Compte à partir de MAINTENANT (les 201+67 du run lunch d'hier ne sont pas rétro-comptés).
  +2 tests. Suite : **181 verts**.
- 2026-07-18 — **Page Usage : calcul vérifié + tally par modèle + dépense moteur loggée + Apify/
  Firecrawl connectés (commit 9e8012e).** (1) Calcul Anthropic VÉRIFIÉ juste (5 539 in × 5 $ + 453
  out × 25 $ = 0,04 $, tarif liste Opus) mais tout était costé au prix Opus → `usage.py` price désormais
  **par modèle loggé** (Opus 5/25, Sonnet 2/10 lancement). (2) **Le moteur écrit sa dépense dans le
  tally local** : `pipeline/usage_log.py` (fail-open) logge chaque appel Anthropic live (extract/score/
  score_batch) dans `activity_log` sous l'agent `hugo` (tokens réels + modèle) → la page Usage reflétera
  les prochains runs, plus seulement le chat. (3) **Firecrawl CONNECTÉ** : `gather(website=…)` ajoute la
  source conditionnelle `firecrawl_ir` (scrape du site, 1 crédit/société) quand clé+website présents —
  source #8 du design, nourrit l'angle earnings-call. (4) **Apify** : flag CLI `--rescan-tech` (par
  défaut on réutilise le tech-stack de la DB → 0 dépense ; c'est POURQUOI le run lunch n'a fait aucun
  appel Apify — les 492 ont un summary de mai). Constat expliqué à Betty : Exa/Perplexity ONT été
  utilisés au run lunch (201 + 67 appels) mais n'ont pas d'API d'usage publique → cartes « CONFIGURED ».
  +3 tests (pricing par modèle, ligne de log moteur, câblage firecrawl_ir) ; tests fake-client
  neutralisent le logger (sinon lignes fantômes en DB dev à chaque pytest). Suite : **179 verts**.
- 2026-07-17 — **Audit de Hugo (même exercice que Maya) → désinformation du prompt corrigée + fraîcheur
  partout (commit da5f494, DB re-seedée).** Trouvé : (1) **hugo.md désinformait activement** — « a REAL
  data refresh is not possible until keys land » + « dataset frozen, 35 eligible, top Hologic 9.5 » ;
  faux depuis aujourd'hui (clés validées, runs live faits, 38 éligibles, 2 runs). Réécrit : moteur
  OPÉRATIONNEL gated par coût/intention (~1 run/mois), dataset à MILLÉSIMES MÉLANGÉS → fraîcheur
  par société obligatoire dans chaque brief ; la ligne « recurrence impossible (1 seul run) » route
  désormais vers /recurring de Maya (actif). (2) Docstring hugo.py parlait encore de « Haiku extraction
  → Sonnet scoring » (modèles abandonnés le 09/07). (3) `/scan` : fraîcheur par ligne + compte stale ;
  `/company` : ligne « Scored on: » (un brief d'intelligence sans date = faute pro) + « STALE ⇒ verify
  first » ; `/stats` : review-flagged + répartition fraîcheur (67 fresh / 425 stale). (4) `/rerun` :
  live_ready exige Anthropic ET ≥1 clé recherche. +1 test. Suite : **176 verts**. 📌 Observation DONNÉE
  (pas code, pour Vera/futur run) : doublons visibles dans l'univers — « Sesderma », « Sesderma
  (Mediderma Group) », « Mediderma (Sesderma Group) » = 3 lignes du même groupe ; « Glenmark » ×2.
- 2026-07-17 — **Maya : les 3 améliorations restantes de l'audit FAITES (commit ac4b092).**
  (1) `/top` : fraîcheur PAR LIGNE (« scored 2026-05-25 — STALE » vs « (latest run) ») + compte de
  stales — un 9.0 figé de mai ne domine plus silencieusement un 8.5 frais de juillet (constaté :
  7 du top 8 sont stale). (2) `/trends` : segmentation **LATEST RUN vs OLDER STOCK** (join
  signals→import_run_id) — avant, les 790 signaux (618 mai + 172 juillet) étaient présentés comme
  « la semaine » ; lecture réelle du run frais : leadership_change #1 (57) devant ma_expansion (55),
  alors que le stock ancien est dominé par ma_expansion (278) → vraie inflexion visible. Service
  areas calculées sur le run frais only. (3) `/recurring` : section **NEW THIS RUN** (premières
  apparitions, par score) + note honnête « N non-rescannés (absence ≠ signal disparu) » = la question
  nouveaux-vs-répétés de Nathalie. (4) Vocabulaire weekly → per-run/monthly partout. Suite : **175 verts**.
- 2026-07-17 — **Audit de Maya sur le 1er historique réel → bug d'inversion de trajectoire corrigé
  (commit 5b75cf7).** `/recurring` affichait `min→max` comme trajectoire : **toute société en DÉCLIN
  était présentée en HAUSSE** (Reig Jofre 7.5→4.6 affiché « 4.6→7.5 ↑ ») ; en plus, le tri « meilleur
  score récent » + cap 40 faisait sortir les gros déclins de la liste → Maya ne voyait jamais les
  FADERS. Corrigé : trajectoire **chronologique** (1er run → dernier run par `run_date`), sortie en
  **TOP RISERS / TOP FADERS** (delta signé, 20 chacun) + compte des stables. Test de régression
  anti-inversion. Suite : **175 verts**. Améliorations restantes identifiées (non faites, à décider) :
  `/trends` compte TOUS les signaux (618 de mai + 172 de juillet) comme « this week » → segmenter par
  run pour de vraies tendances ; `/top` mélange les millésimes sans le dire (9/10 du top = scores
  figés de mai) → afficher la date de run par ligne ; vue NEW vs DROPPED entre runs (la question
  dédup/nouveaux de Nathalie) ; vocabulaire « weekly » → « per run » (cadence réelle = mensuelle).
- 2026-07-17 — **Durcissement anti-perte-silencieuse (commit 208c916) : 4 défenses structurelles.**
  (1) **Extraction par CHUNKS de 35 docs** (`extract.py`) : sortie bornée par appel → la troncature
  JSON ne PEUT plus arriver, quel que soit le corpus. Tue la flakiness Grifols/Geistlich. Dédup des
  quotes inter-chunks (normalisées). Vérifié live : **Grifols 7.2 (4/6 signaux), Geistlich 6.8 (5/6)** —
  couverture MEILLEURE que l'appel unique (chaque chunk = pleine attention). (2) **Salvage de JSON
  tronqué** (`_salvage_item_dicts`) : une réponse coupée rend tous les items COMPLETS au lieu de 0
  (fail-closed, rien d'inventé). (3) **Retry d'interprétation** (`score.py`) : réponse Opus illisible
  → 1 retry (sentinel `FAILED_SUMMARY` ; évidence vide non retryée). (4) **Canary zéro-évidence**
  (`runner.py`) : ≥30 docs mais 0 item en live → review-flag « extraction anomaly » — un faux zéro ne
  peut plus atteindre le CSV sans marquage. +6 tests → **174 verts**. Dataset final propre :
  fusion upgrade-only + réimport + purge du snapshot intermédiaire → historique = 2 runs nets
  (mai 492 / juillet 67 corrigé), **seuls 3 vrais zéros restent** (Luzerner, USZ, Z-Systems — bas en
  mai aussi), 38 outreach-eligible, deltas /recurring cohérents (Grifols 6.5→7.2, Geistlich 6.0→6.8).
- 2026-07-17 — **10 faux zéros re-scorés avec le fix 16384 → dashboard nettoyé (38 outreach-eligible).**
  Identifié via `/recurring` (mai≥5 → juillet 0) : 10 faux zéros. Re-run `--names …` (cache, ~0,50 $) :
  **8 récupérés** (Cantabria 8.5 + Ferrer 8.0 = nouveaux ≥8 ; Ypsomed 7.7, Faes 7.5, Straumann 7.0,
  Nobel 6.0, Avinent 5.5, Reig Jofre 4.6). **2 restent flaky-0 (Grifols, Geistlich)** = très gros
  corpus qui tronquent parfois MÊME à 16384 → non-déterminisme résiduel du modèle ; un re-run les
  attrape en général. Fusion **upgrade-only** (un 0 flaky n'écrase jamais une valeur) dans
  `engine_run_lunch.csv` + réimport → `companies` : 492, **outreach-eligible 38**, review 35, 5 zéros.
  Le réimport avait ajouté un 3ᵉ snapshot → **NETTOYÉ** : le snapshot juillet-buggé (`c7ff0aab446d`,
  67 lignes) supprimé. Historique propre = **2 runs** : mai #1 (`cb97cf5d50d2`, 492) + juillet-corrigé
  (`d0c561fd8988`, 67). `/recurring` montre des deltas cohérents (Cantabria 7.0→8.5, Ferrer 6.0→8.0,
  Roche 7.0→8.0, Reig Jofre 7.5→4.6).
- 2026-07-17 — **Trou d'extraction diagnostiqué & corrigé (`max_tokens` 16384) + prefill Sonnet 5 KO.**
  Diagnostic des faux zéros du run lunch (Reig Jofre 7.5→0, Grifols 6.5→0 vs mai) : recherche OK
  (~114 docs) mais extraction = 0. Cause : **Sonnet 5 raisonne en prose avant le JSON** (« Now let me
  identify quotes… ») → sur gros corpus (souvent espagnol) le JSON dépasse 8192 tokens → tronqué →
  illisible → 0 évidence. **Fix : `pipeline/extract.py` max_tokens 8192 → 16384** (laisse la place au
  raisonnement + un gros set verbatim). Confirmé live : **Reig Jofre 0→7.0, Grifols 0→7.3/8.0**.
  ⚠️ NE PAS interdire la prose (essayé) : ça FAIT CHUTER le recall (Reig Jofre repassait à 0) — le
  listage de candidats du modèle AIDE l'extraction ; le parseur tolère déjà la prose, seule la
  troncature posait problème. ⚠️ **Le prefill assistant (truc habituel « JSON only ») N'EST PAS
  supporté par `claude-sonnet-5`** (400 « does not support assistant message prefill ») — piste morte,
  d'où le levier max_tokens. Suite : 168 verts. **⚠️ DETTE DONNÉE : la table `companies` garde encore
  des faux zéros** sur les sociétés CH+ES scorées AVANT ce fix (Reig Jofre, Grifols, + prob. Cantabria,
  Faes, Ferrer, Geistlich) → re-runner le set lunch (ou juste ces sociétés) avec le fix + réimporter
  pour un dataset européen propre.
- 2026-07-17 — **Maya `/recurring` ACTIVÉE (2 runs) + re-scoring des 6 faux zéros + import.** (1) Re-scoré
  les 6 faux zéros (`--names …`, recherche en cache, ~0,30 $) → Almirall 7.5, Galderma 5.8, XtalPi 4.8,
  Maddox 5.2, Medinova 6.0, LETI 6.2, **aucune troncature** (fix scoring confirmé). Fusionnés dans
  `engine_run_lunch.csv`. (2) `python import_csv.py engine_run_lunch.csv` → **67 updated** (les 67 CH+ES
  étaient déjà dans les 492 → table reste à 492, 67 re-scorées juillet), run #2 ajouté. Total 492,
  outreach-eligible 36. (3) **`/recurring` actif** : 2 runs distincts (25/05 #1 = 492 ; 17/07 #2 = 67),
  67 sociétés récurrentes avec delta mai→juillet. **⚠️ FINDING (Maya) :** plusieurs sociétés bien scorées
  en mai tombent à 0 en juillet — Reig Jofre 7.5→0, Grifols 6.5→0 (et Cantabria, Faes, Ferrer, Geistlich).
  La **recherche marche** (111-114 docs, comme Roche 115→8.0) → c'est l'**EXTRACTION qui renvoie 0** sur
  ces sociétés (0 troncature loguée) = notre moteur rate des signaux que le Neotek original captait.
  À investiguer (re-run extraction avec dump du brut Sonnet, ~0,05 $). NB : mai = Neotek original,
  juillet = notre reconstruction (moteurs différents) → écart en partie attendu, mais 7.5→0 pue le miss.
- 2026-07-17 — **1er run business `--lunch` (67 sociétés CH+ES) + Solution A batch (submit→fetch) +
  correctif scoring.** (1) **Run `--lunch`** live (~4-5 $, plafond 8 $) : 67 sociétés scorées,
  **5 outreach-eligible ≥8** (Roche, Zühlke, ISDIN, Lonza, Mediderma), 31 review-flagged, 19 à 0.
  CSV : `data/csv/engine_run_lunch.csv`. (2) **Solution A** (`pipeline/batch.py` + `runner.py`) :
  `--submit` (recherche+extraction locale → soumet le batch → sauve l'état JSON → quitte, Mac peut
  s'éteindre) + `--fetch <state>` (récupère quand Anthropic a fini, ≤24 h → écrit le CSV). Découple
  la moitié « attente 24 h » de la machine (les gros runs mensuels n'exigent plus le Mac allumé 24 h).
  submit_blocks/batch_status/collect_results factorisés ; custom_id déterministe ; +5 tests.
  (3) **Correctif scoring** (`score.py` + `batch.py`) : `max_tokens` Opus 4096 → **8192** — 6 faux
  zéros (Almirall, Galderma, XtalPi, Maddox, Medinova, LETI Pharma) venaient d'une **troncature de
  l'interprétation** (« No interpretation produced »), pas d'une absence de signal. Les 13 autres
  zéros = extraction vide réelle (hôpitaux/dental). +log `stop_reason`. Suite : **168 verts**.
  ⚠️ Les 6 faux zéros seront corrects au prochain re-scoring (recherche déjà en cache → ~0,30 $).
- 2026-07-17 — **Géographie du moteur TRANCHÉE : EUROPE, CH + ES d'abord** (décision Betty ; répond à
  la question ouverte de géo #1 du brouillon de segmentation — Nathalie peut affiner les pays ensuite).
  Implémenté côté recherche : `pipeline/research.py` dérive une **locale SERP (`gl`/`hl`) de la
  localisation connue de chaque société** (société suisse → `gl=ch`, espagnole → `gl=es`) via le
  `detect_country` existant (CH/ES seulement pour l'instant ; table `_MARKET_LOCALE` prête pour
  FR/DE/IT/UK/BE/NL/AT/PT). **Aucune recherche supplémentaire** (mêmes 2 appels SERP/société, juste
  localisés → coût inchangé) ; localisation inconnue/non-UE → global (comportement inchangé). Câblé
  dans les 4 fonctions SERP (Serper + SerpAPI) + `gather(location=…)` + `_prepare`. Complète le
  multilingue d'extraction EN/FR/ES/DE. +3 tests. Suite : **164 verts**. ⚠️ L'autre moitié de « baser
  sur l'Europe » = l'**univers d'entreprises** (liste candidate européenne) — dépend de la liste/scope
  (Nathalie) ; `--lunch` (48 CH + 19 ES) est déjà l'univers CH+ES prêt à l'emploi.
- 2026-07-17 — **PREMIER RUN LIVE réel du moteur — clés validées + bug d'extraction trouvé & corrigé.**
  Run de validation `--top 3 --live --max-usd 1` (<0,20 $) : a prouvé que **toutes les clés payantes
  fonctionnent et ont du crédit** (Anthropic Sonnet+Opus, Exa, SerpAPI, Perplexity) et que le pipeline
  tourne de bout en bout (n'écrase PAS `companies`, écrit un CSV). MAIS extraction = 0 évidence sur 3/3
  → « unparseable JSON from model ». **Cause :** ~100 docs bruts/société → sortie Sonnet dépassait
  `max_tokens=4096` → JSON tronqué (le scoring Opus, lui, parsait bien). **Corrigé** (`pipeline/extract.py`,
  commit 1822a46) : max_tokens → 8192, parseur tolérant aux fences ```json``` + log du `stop_reason`.
  **Re-run `--top 1` (Hologic, recherche servie du cache → ~0,05 $) : 24 évidences, score 8,5,
  outreach-eligible** (pe_event Blackstone/TPG + leadership_change, tous deux datés/haute confiance ;
  cession spéculative correctement flaggée). Chaîne recherche→extraction→scoring→CSV **entièrement
  validée en live**. Sorties : `data/csv/engine_run.csv` (top-3, vide) + `engine_run_probe.csv` (top-1, réel).
  Suite : **161 verts**. NB : importer un vrai CSV (`python import_csv.py …`) débloquerait `/recurring` de Maya.
- 2026-07-17 — **Détection de boilerplate renforcée (exact → normalisé + quasi-duplicat).** Le flag
  de review « rationale identique sur 3+ sociétés » (`flag_boilerplate` dans `pipeline/runner.py`)
  reposait sur l'**égalité exacte de chaîne** — or Opus produit rarement deux rationales caractère-
  pour-caractère identiques (dérive d'un mot, d'une casse, d'une virgule) → il ratait précisément le
  boilerplate qu'il vise. Remplacé par comparaison de **jeux de tokens normalisés** (casefold +
  ponctuation retirée) avec seuil de **quasi-duplicat Jaccard ≥ 0.9** (strict : ≤ ~2 mots d'écart sur
  20 → aucun faux positif sur des rationales vraiment distinctes). Englobe l'égalité exacte (tests
  existants toujours verts). +2 tests (quasi-identiques flaggés / distincts non flaggés). `Counter`
  retiré (plus utilisé). Suite : **159 verts**.
- 2026-07-17 — **Requête Jobs multilingue (EN/FR/ES/DE) — input de recherche, indépendant du scope.**
  Suite logique de l'extraction multilingue : `pipeline/research.py` cherchait les signaux de
  recrutement avec des mots anglais only (`hiring OR jobs OR careers`) → une offre FR/ES/DE
  (« emploi/recrutement », « empleo/contratación », « Stellenangebote ») ne remontait jamais.
  Ajout de `_HIRING_TERMS` (verbes de recrutement EN/FR/ES/DE) + `_jobs_query()` (fonction pure,
  testable) utilisée par `serper_jobs`. Les termes métier (`commercial digital CRM`, internationaux)
  restent. ⚠️ **Pas de locale pays (`gl/hl`) codée en dur** : la GÉOGRAPHIE reste une question ouverte
  du scope (Nathalie) — on élargit la LANGUE de la requête, pas le pays. Le réglage de géo des news
  est donc VOLONTAIREMENT reporté après validation du scope. +2 tests. Suite : **157 verts**.
- 2026-07-17 — **Extraction multilingue (EN/FR/ES/DE) — qualité, indépendant du scope.** Constat :
  `pipeline/extract.py` ne comprenait que l'anglais (table des mois `January…December`, marqueurs de
  spéculation anglais-only). Or les cibles sont européennes (CH/ES + veille life science UE) → dates
  FR/ES/DE (« 1er juin 2026 », « 15 de junio de 2026 », « 3. März 2026 », « août 2026 ») non parsées →
  **recency silencieusement 0** ; hedges FR/ES/DE (« envisage », « pourrait », « podría », « erwägt »)
  non flaggés → rumeur scorée comme fait. Corrigé : `_strip_accents` + table de mois multilingue
  (lookup nom complet, PAS `[:3]` — évite la collision juin/juillet), motifs de dates élargis (lettres
  Unicode, ordinaux `1er/2e/3.`, forme espagnole `DD de MOIS de AAAA`, `MOIS de AAAA`), marqueurs de
  négation FR/ES/DE (accent-insensibles ; « no »/« non »/« ne » exclus car trop fréquents). N'affecte
  ni l'ICP ni le scope moteur — pure robustesse d'extraction. +2 tests (`test_date_in_text_multilingual`,
  `test_has_negation_multilingual`). Suite : **155 verts**.
- 2026-07-17 — **Réunion pilote 16/07 (Betty & Nathalie) analysée + rangée.** Transcript Word
  (`Downloads/TPDL_agent_pilot-20260716…docx`) résumé et stocké : (a) note Obsidian détaillée dans le
  vault TPDL → `Agents IA & Pipeline TPDL/Réunion — 16 juillet — Pilote agents…` ; (b) section datée dans
  `operational-context.md` ; (c) CLAUDE.md (convention de langue + flag scope). Faits structurants :
  **(1) changement de scope moteur** — abandon de la base fermée des 500 (« irrelevant ») pour une
  veille large **life science & pharmaceutical** (+ dental/derm/diagnostics), base = **top 35 + du
  nouveau crawlé** ; signal fort = **earnings calls / priorité digitale du board**. À FORMALISER
  dans un doc de segmentation (Betty + Nathalie) AVANT de toucher l'ICP de Hugo / `scoring_config.yaml`
  → non répercuté dans le code cette session. **(2)** run ≈ 40-60 € / Batch API / ~1 run/mois =
  CONFIRMÉS terrain ; faire le run même à 100 € (sinon « on travaille dans le vide »). **(3)** Apollo +
  PipeDrive à connecter, PipeDrive en staging (vérifier/catégoriser avant import). **(4)** MailChimp
  plafond 1 500 mails/mois ; Bouncer = usage réel. **(5)** ACCÈS : clés API dans `.env` ≠ accès
  compte/login de Betty ; Andrés = feuille de codes ; Alfredo = « Systems App » + boîte mail à
  rattacher. **(6)** Sophia peut re-runner le vrai Neotek (~500 €) = option de comparaison.
  **(7)** langue : notes FR / code EN. Aucun code/prompt modifié.
- 2026-07-16 — **Intégration des retours de Nathalie + 4 docs (Brand DNA & éditorial).** Nathalie a
  renvoyé le Word « État du projet » commenté (7 commentaires) + 4 pièces : logo SVG, spec de charte,
  la « Thought Leadership Series », le « Prompt LinkedIn idéologie Andrés », et un report exemple
  (« The Hidden Tax of Ad-Hoc Launches »). Décisions/faits actés :
  (1) **Alex** = manager/routeur PUR, non formé, hors process intelligence & marketing ; existe pour
  donner UNE porte quand on ne sait pas à qui s'adresser ; peut nuancer une demande avant de router
  (ex. affiner ce que Maya doit classer) ; **provisoire, supprimable** s'il s'avère inutile. Encodé
  dans `manager.md`.
  (2) **Cadence = 1 run/mois pour l'instant** (interpréter les résultats est lourd) ; fréquence
  (hebdo ? dédup nouveaux-vs-répétés ?) = question ouverte à revoir. Encodé dans `maya.md`.
  (3) **Charte OFFICIELLE** : Funnel Sans (Regular) · Dark #0A0A0A · Light #EBEBEB · Green #34D591 ·
  logo `TPDL Logo (1).svg`. ⚠️ CONTREDIT le code (teal #094752 dans ~20 fichiers) → migration de
  rebranding à faire à part ; **NON touchée cette session** (consigne : pas de HTML).
  (4) **Ligne éditoriale + lexique + voix Andrés + report exemple** capturés dans le NOUVEAU fichier
  `.claude/brand-editorial.md` (importé par CLAUDE.md). Prompts réalignés : `julie` playbook v2.2
  (règles de voix Andrés), `iris` (principe métier d'abord + lexique), `marc` (doctrine 7 étapes +
  10 principes + lexique + mots interdits). Aussi ajouté dans Obsidian (vault TPDL, dossier « Brand
  DNA & Éditorial »). DB re-seedée pour propager les prompts. **Aucun HTML/CSS/export modifié.**
- 2026-07-16 — ⚠️ **CONSTAT : les clés API sont DANS `.env`** (Anthropic, SerpAPI, Exa, Perplexity,
  Firecrawl, Apify). Contredit toute la mémoire « bloqué sur les clés ». Non testées par un appel
  live (donc validité inconnue), mais présentes ⇒ **un run LIVE du moteur est techniquement
  possible dès maintenant** (dépense réelle). Vides : Serper, Apollo, Kaspr, Bouncer, Lemlist.
  Décision : NE PAS lancer de run live sans accord explicite (coût + écrase la table companies).
- 2026-07-16 — **Moteur déclenchable depuis l'UI (gaps #24/#25/backlog #9).** Nouveau routeur
  `app/routers/engine.py` : `POST /api/engine/run` (dry-run par défaut = smoke test 0 coût de la
  fixture probe, **n'écrit JAMAIS la table companies** ; live gated → 400 sans clé, 501 « lancer
  au CLI » avec clé, pour garder la dépense explicite) + `GET /api/engine/status`. Panneau sur la
  page Usage (bouton « Run smoke test », résultat scoré, chip LIVE READY/DRY-RUN ONLY). Commande
  `/rerun` de Hugo (explicative, ne fabrique jamais un refresh). Vérifié : smoke test UI → Probe
  scoré 5.8, non importé, coût 0. `tests/test_engine_api.py` (3) + test `/rerun`. Suite : 153 verts.
- 2026-07-16 — **Iris/marketing : migration DuckDuckGo → Serper (gap #26).** `app/tools/web_search.py`
  préfère Serper (`google.serper.dev`) quand `SERPER_API_KEY` est set (meilleure qualité), fallback
  DuckDuckGo keyless sinon — même contrat de retour, ne lève jamais. `serper_api_key` ajoutée à
  `app/config.py` ; si Serper erreure, retombe sur DuckDuckGo avant d'abandonner. Prompt+docstring
  Iris réalignés. `tests/test_connectors.py` +3. Suite : 149 verts. Reste : fournir la clé Serper.
- 2026-07-16 — **Avatars pixel-art custom « consulting » + suppression de DiceBear.** Nouveau
  générateur versionné `scripts/gen_avatars.py` → 15 SVG locaux (`static/img/avatars/<seed>.svg`,
  grille 20×20 crispEdges) : tenues consulting (costumes/blazers/cols roulés), accents TPDL
  (#094752/#34D591 — cravates, épingles, micro-casque d'Inès), lunettes fines (Hugo, Vera), signes
  distinctifs par persona (chignon+mèche argent Vera, barbe Marc, queue de cheval Iris…). Les 22
  URL DiceBear des templates remplacées par les fichiers locaux (⚠️ les 2 cas Jinja `{{ seed }}`
  ont dû être repris à la main après le regex) ; handler de fallback de base.html repointé.
  Dépendance externe DiceBear (risque #41) SUPPRIMÉE. Micro-interaction : anneau menthe sur
  l'avatar au survol des tuiles agents. Vérifié en live (home, tuiles, login). 146 verts.
- 2026-07-15 — **Passe accessibilité des 9 pages.** `aria-label` sur les inputs placeholder-seul
  (chat Alex + drawer agent, note review, note intel, filtre OneDrive, sujets/contexte marketing) ;
  `aria-label` sur les 3 `<select>` d'intel (filtre secteur/signal + statut par société, ~280 rendus
  sans nom) ; `alt=""` sur les avatars DiceBear décoratifs (brouillons/légende marketing, activité
  Today, Performance) car le nom d'agent est toujours adjacent. Login déjà OK (`<label for=pw>`).
  Vérifié en live : chaque page = 0 champ sans label / 0 bouton anonyme / 0 image sans alt. 146 verts.
  Puis **contraste WCAG AA** : `ink-3`/`--tpdl-text-faint` #8a8a8a (3.3:1, sous le seuil 4.5) →
  #6f6f6f (4.8:1), hiérarchie préservée. `ink`/`ink-2` OK ; accent-texte utilise `--tpdl-accent-ink`
  #0a3a26 (12:1). Cache custom.css bumpé v=3. Vérifié en live (eyebrow 4.81:1, design intact).
  Puis **focus clavier** : anneau `:focus-visible` `rgba(52,213,145,0.22)` (~1.2:1, à peine visible)
  → anneau 2 couches vert vif + halo teal foncé (~3:1 sur fond clair), cache v=4. Drawer déjà fermé
  par `keydown.escape.window`. Vérifié en live (anneau net sur lien de nav).
- 2026-07-15 — **QA mobile (375px) → overflow horizontal corrigé sur Home + Marketing.** Cause :
  grille `grid-cols-12` avec enfants `col-span-12` → sur mobile les 11 column-gaps de 32px (=352px)
  dépassent la largeur contenu (~311px), quel que soit le nombre de tracks (prouvé : forcer 1 track
  ne suffit pas ; column-gap à 0 oui). Fix (patron d'`intel.html`) : `grid-cols-1 md:grid-cols-12`
  + `gap-y-* md:gap-*`. Vérifié en live : 0px d'overflow. Dark mode = volontairement clair-only
  (non-bug). Aussi : déprécation fpdf2 `ln=` silencée (API new_x/new_y).
- 2026-07-15 — **Endpoints d'export d'Oliver (PDF/PPTX) exercés en direct → 2 bugs de crash 500
  corrigés.** (1) `pdf_export.py` : Helvetica de fpdf2 est Latin-1 only → tout `→`/`€`/`≥`/… dans
  le contenu de Marc faisait un 500 (l'ancienne liste ratait la plupart des symboles, dont `→` du
  CTA). Remplacé par `_latin1_safe()` (map étendue + filet `encode('latin-1','replace')`), appliqué
  au contenu ET à subject/format_label (header/footer). (2) `marketing.py` : les 2 endpoints
  mettaient `subject` dans l'en-tête HTTP `Content-Disposition` (Latin-1 obligatoire) → un sujet
  Unicode levait `UnicodeEncodeError` HORS du try/except → 500 brut. Slug réduit en ASCII. Vérifié
  en live (fichiers %PDF/PPTX valides qui s'ouvrent) + 3 tests d'endpoint. Suite : 146 verts.
  Note : warning déprécation fpdf2 `ln=False` (pré-existant, non bloquant).
- 2026-07-15 — **Revue navigateur des 9 pages du dashboard (aucune erreur console).** Vérifié en
  live que le fix des bandes de score somme à 492 (35+275+67+115). Corrigé 3 copies périmées :
  home « Seven specialists » → « Eight… + Vera » (Vera jamais reflétée dans le hero) ; Usage
  « 8 dashboard agents » → « 9 (Alex + 8) » ; « (via Apollo) » → « (Kaspr/Apollo) » depuis le
  câblage Kaspr. Toutes les pages rendent bien (Sales, Today, Marketing, Contacts, Performance,
  Review, Usage, Data, Home).
- 2026-07-15 — **2e audit adversarial du code → 11 bugs corrigés + 12 tests (135 verts).** Deux
  passes parallèles (moteur + app), chaque finding vérifié à la main. Corrigés : crash JSON qui
  jetait le batch payant, double-comptage de catégories, corroboration sur-créditée, dates SERP
  jamais parsées (recency 0 silencieuse), QA verbatim contournable + collapse de source, négation
  par sous-chaîne, `--max-usd 0` qui désactivait le coupe-circuit, `RunSnapshot` non idempotent
  (fausse récurrence), `/top5` collé, bandes de score à trous, `/premium add` recomptant à tort.
  Détail dans `.claude/process-gaps.md` (§ Corrigés 2026-07-15). NON fait (destructif, à valider) :
  suppression de 3 mocks morts (~1216 lignes).
- 2026-07-15 — **Connecteurs Kaspr / Bouncer / Lemlist câblés (gated, dormants).** Écrits sur le
  patron Apollo (`is_configured()` + exception dédiée, jamais de fabrication, fail-closed).
  `app/tools/kaspr.py` = drop-in d'Apollo (même contrat de retour) ; Inès le PRÉFÈRE quand
  `KASPR_API_KEY` est set (sinon Apollo). `app/tools/bouncer.py` = vérif email, `deliverable`
  seulement si status == deliverable, erreur → `unknown`/False (fail-closed). `app/tools/lemlist.py`
  = séquences ; `add_lead_to_campaign` = action SORTANTE, jamais appelée automatiquement (humain
  après validation + email deliverable). 3 clés ajoutées à `config.py` + `.env.example`. Prompts
  Inès/Julie réalignés. `tests/test_connectors.py` (10). Suite : 123 verts. Reste : fournir les clés.
- 2026-07-15 — **Oliver : 5e format `newsletter` supporté.** Le prompt le décrivait comme « prévu,
  pas encore supporté ». Ajouté à `FORMAT_SPECS` + alias `/newsletter` dans `app/agents/oliver.py`,
  pondération FIXE 70/10/20 (audience CRM / tendances LinkedIn / forces & cas TPDL), destinée à
  MailChimp (Segment 3 d'Inès). Sortie = texte structuré (SUBJECT + preheader + sections + CTA), pas
  de renderer fichier. Prompt `oliver.md` mis à jour + re-seed. Test `test_oliver_newsletter_is_supported`.
  Suite : 113 verts.
- 2026-07-15 — **Mémoire recalée + `/recurring` amorcé + branche prête à merger.** La mémoire
  affirmait encore « pas de pipeline / moteur inaccessible / git non initialisé » : FAUX depuis la
  reconstruction du moteur. CLAUDE.md + state.md remis d'aplomb. `/recurring` était déjà câblé sur
  `RunSnapshot` mais l'historique était vide (les 492 sociétés du 25/05 précèdent la table) → ajout
  de `backfill_snapshots.py` (idempotent) qui amorce le VRAI run 25/05 comme run #1 (pas une
  simulation). Résultat : 1 run en historique, `/recurring` s'active au 2e import.
- 2026-07-14/15 — **Moteur Neotek RECONSTRUIT** (`pipeline/`, branche `feat/neotek-engine`, non
  encore mergée dans `main`). Points clés : money gate `require_live()` (dry-run par défaut =
  0 réseau/0 coût) ; `--estimate` (pré-vol coût + quota SerpAPI) ; `--live`, `--batch` (-50 %),
  `--resume` (crash-safe), `--max-usd` (coupe-circuit budget). 8 sources codées (Serper News/Jobs +
  fallback SerpAPI, Exa Q1/Q2/Q3, Perplexity, registres UE en source web GRATUITE, Firecrawl IR).
  Vera = 9e agent QA + file de revue humaine (`/review`). Dashboard Usage & crédits (`/credits`).
  Apollo réel (gated). Brand DNA peuplé (site public + engagements anonymisés) + angles sectoriels.
  112 tests verts. ⚠️ state.md n'avait PAS été mis à jour pendant ce chantier — dette corrigée le 15.
- 2026-07-12 — **Renderers d'Oliver connectés.** Découverte : le PDF était DÉJÀ branché (fpdf2 +
  `POST /api/marketing/carousel/export-pdf`) — la mémoire « à connecter » était en partie périmée.
  **PPTX ajouté** : `python-pptx` installé (+ requirements), `app/tools/pptx_export.py` (deck 16:9
  brandé #094752/#34D591 ; parse TITLE/SUBTITLE/SLIDE/SECTION/bullets), endpoint
  `POST /api/marketing/deck/export-pptx`. Oliver mis à jour (marqueurs de structure attendus).
  Tests `tests/test_pptx_export.py` → **50 verts**. Vérifié : PDF %PDF valide, PPTX rouvert = bon
  nombre de slides.
- 2026-07-12 — **Passe qualité / audit complet du code** (2 audits parallèles + vérif manuelle de
  chaque trouvaille). 8 vrais bugs corrigés : (1) `base.py` — l'historique tronqué à 30 pouvait
  démarrer sur un tour assistant → 400 Anthropic sur conversations longues ; (2) `DEFAULT_MAX_TOKENS`
  1024→8192 (sorties briefs/articles tronquées) ; (3) `chat.py` — conversation_id invalide → 500
  au lieu de 404 ; (4) `main.py` — faille auth `/api/me` englobait `/api/memory` (fix : match par
  frontière de segment) ; (5) `today.py` — date malformée faisait 500 le dashboard (garde ajoutée) ;
  (6) `ines.py` — dédup contacts sur re-run (`/contacts` idempotent) ; (7) `maya.py` — rang incohérent
  pour une société hors-périmètre (icp_flag) ; (8) `iris.py` — `/themes` s'affichait comme `/trends`.
  Honnêteté prompts : Inès §11 (la segmentation EST persistée) & Julie §2 (adaptation par personne =
  LinkedIn ; email `/draft` = niveau entreprise/secteur). Tests : **47 verts** (+3 régression auth).
  Dispatch des 8 agents exercé : **23/23 OK**. Warning connu non bloquant : `duckduckgo_search`→`ddgs`
  (superseded par la cible Serper).
- 2026-07-12 — **Marketing + Alex FORMÉS → les 8 agents sont formés.** Iris (recherche + scoring de
  thèmes 0-10, DuckDuckGo→Serper cible, jamais de source inventée) ; Marc (contenu depuis thèmes Iris +
  Brand DNA, [STAT TO VERIFY], jamais de client/résultat inventé) ; Oliver (4 formats réels a4/carousel/
  ppt/website + branding #094752/#34D591 ; renderers PDF/PPTX NON connectés = sort du texte/plan, pas de
  fichier ; newsletter 70/10/20 notée mais pas encore un format supporté) ; Alex (routeur `[ROUTE_TO:]`,
  reflète le moteur en lecture seule). Tous versionnés dans `app/agents/prompts/`. `.env.example` aligné
  sur Opus 4.8. Vérifié : DB == fichiers pour les 8, 44 tests OK, app importe.
- 2026-07-12 — **Julie FORMÉE** (4e agent) → **les 4 agents Sales sont formés**. Philosophie outreach
  encodée (cold = mort, humain, porte-pas-pitch, thought leadership) ; 2 canaux (email `/draft` +
  LinkedIn `/linkedin` en voix Andrés via le playbook v2.1, source de vérité non dupliquée) ; message
  adapté aux 5 tags d'Inès (langue/lunch/fonction/séniorité/segment) ; ancrage signal Hugo + preuve
  Brand DNA ; interdiction absolue d'inventer un client/résultat/signal ; segment 3 = nurture, Premium 5
  = Andrés. 7 secteurs — angles désormais peuplés (`app/tools/sectors.py`, positionnement réel
  anonymisé ; il ne manque que les chiffres d'Andrés). Versionnée `app/agents/prompts/julie.md`.
- 2026-07-12 — **Inès FORMÉE** (3e agent, le gros morceau « aller plus loin »). Génération de contacts
  pilotée par le signal Hugo ; **matrice de segmentation 5 axes** (fonction commercial/data/digital ×
  séniorité × géo × langue × **segment CRM 1/2/3**) ; radars Lunch CH/ES + langue ES ; Premium 5 → Andrés.
  Décidé : Apollo pour l'instant (Kaspr en cible), **segments CRM 1/2/3 = Inès**. Interdit d'inventer un
  contact. Versionnée dans `app/agents/prompts/ines.md`, appliquée en DB.
- 2026-07-12 — **Inès part 2 (code) FAITE** : la dette technique est réglée. Ajouté `function` /
  `seniority` / `crm_segment` au modèle `Contact` ; nouveau `app/tools/segmentation.py` (fonctions
  pures, matching par tokens — un bug « cto ⊂ direCTOr » a été attrapé par les tests puis corrigé) ;
  migration additive idempotente SQLite dans `init_db` (pas d'Alembic) ; câblé dans `ines.py` (Mode B
  Apollo) ; `tests/test_segmentation.py` (44 tests OK). La segmentation est maintenant PERSISTÉE.
- 2026-07-12 — **Maya FORMÉE** (2e agent). Frontière dure encodée : « Hugo scores. You rank » —
  jamais de re-scoring, jamais de recherche. 3 jobs : Top 50/100, récurrence (≥2 runs, message
  explicite sinon), tendances. Propage les review flags. Alimente le tuning de scoring_config.yaml
  (propose, n'édite pas). Versionnée dans `app/agents/prompts/maya.md`, appliquée en DB.
- 2026-07-12 — **Hugo FORMÉ** (1er agent). Prompt complet = tout le design Neotek : 2 modes
  (briefing DB / moteur bloqué), 6 steps, 8 sources (+Firecrawl), séparation Sonnet 5/Opus 4.8,
  6 signaux + chaînes de raisonnement, formule + échelle strength 0-6, 7 règles dures, review
  flags, specs de sortie par commande. Versionné dans `app/agents/prompts/hugo.md`, appliqué en DB.
- 2026-07-12 — Structure prompts : chaque agent formé a son fichier `app/agents/prompts/<agent>.md`
  chargé par seed.py ; les non-formés gardent leur squelette inline. Périmètre validé :
  **sources = Hugo (Perplexity incluse) ; scoring = Hugo ; Maya re-classe, ne re-score jamais.**
- 2026-07-12 — Transcripts réunions (16.06 + 25.06) intégrés dans `.claude/operational-context.md`.
  Nouveaux faits terrain : CRM **PipeDrive** + **Surf** (LinkedIn→PipeDrive) + **MailChimp** + Sales Nav ;
  envoi messages MANUEL par un SDR en Inde ; leçon outreach (cold = mort, message humain simple) ;
  pondération newsletter 70/10/20 ; Premium 5 détaillé. Conflits (Haiku/Sonnet, budget 10-15 €, Apollo)
  signalés et SUPERSEDÉS par les décisions du 09/07 — non répercutés.
- 2026-07-09 — Modèles : abandon de Haiku. Extraction = **Sonnet 5**, interprétation/scoring =
  **Opus 4.8**. Le principe anti-hallucination (séparation structurelle) est préservé.
- 2026-07-09 — Chat live : les agents du dashboard tournent sur **Opus 4.8** (`ANTHROPIC_MODEL`).
  Appliqué dans `app/config.py` + `.env`.
- 2026-07-09 — Budget Anthropic « 5-15 $/mois » invalidé (extraction Sonnet 5 ≫ Haiku). À re-chiffrer au Step 1.
- 2026-07-09 — Mémoire canonique déplacée dans le repo (racine `CLAUDE.md` + `.claude/*.md`).
  `Downloads/tpdl-memory/` est superseded (à supprimer).
- 2026-07-09 — Roadmap reformulée en 4 macro-steps (abonnements / former agents / workflow / essayer).
- 2026-07-09 — Confirmé : le moteur pipeline Neotek n'est PAS accessible (on n'a que les CSV).

## Checklist des blocages (cocher quand levé)
- [x] #1 Clé Anthropic dans `.env` (PRÉSENTE au 2026-07-16, validité non testée par un appel live)
- [x] #1b IDs de modèles fixés : Sonnet 5 (extraction) + Opus 4.8 (interprétation/chat)
- [x] #2 Clé Exa (présente dans .env, validité non testée)
- [x] #3 Clé Perplexity (présente dans .env, validité non testée)
- [x] #4 Brand DNA : angles sectoriels peuplés (`app/tools/sectors.py`, positionnement réel
      anonymisé). Reste : les CHIFFRES/résultats clients précis d'Andrés pour durcir les proof points.
- [~] #5 Kaspr : connecteur CODÉ + gated (`app/tools/kaspr.py`, préféré par Inès). Reste : `KASPR_API_KEY`.
- [x] #6 Token Apify (présent dans .env)
- [x] #7 Reconstruction du moteur pipeline (`pipeline/`, dry-run + live gated). **RUN LIVE RÉEL FAIT
      le 2026-07-17** (top-1/top-3, <0,25 $ total) : 6 clés validées, chaîne de bout en bout OK, bug
      d'extraction (max_tokens) trouvé & corrigé. Reste : un run business (Lunch/top-35) après crédit + scope.
- [x] #7c Historique des runs (`RunSnapshot`) + `backfill_snapshots.py` → run 25/05 amorcé (run #1).
      `/recurring` s'active au 2e import. Reste : un 2e CSV réel à importer.
- [x] #7b Modèle `Contact` étendu (function / seniority / crm_segment) + `app/tools/segmentation.py`
      + migration additive SQLite dans `init_db` + tests (44 passent). Reste : Apollo pour peupler.
- [ ] Serper configuré (vide ; SerpAPI présent en fallback, web_search bascule auto)
- [x] Firecrawl configuré (clé présente dans .env)
- [~] Bouncer : connecteur CODÉ + gated (`app/tools/bouncer.py`, fail-closed). Reste : `BOUNCER_API_KEY`.
- [~] Lemlist : connecteur CODÉ + gated (`app/tools/lemlist.py`, sortant/humain). Reste : `LEMLIST_API_KEY`.
- [ ] n8n (mutualisation Devengo demandée à Andrés ?)
- [x] Repo Git : remote GitHub PRIVÉ créé et poussé (2026-07-18) — github.com/Betty-dcl/tpdl-lead-intelligence (main + feat/neotek-engine, auth gh CLI). Reste : inviter Andrés (Settings → Collaborators).
- [x] Renderers PDF/PPTX Oliver connectés (PDF fpdf2 + PPTX python-pptx + endpoints export)

## Calendrier (source transcript 25.06 — à re-confirmer)
- Crash test initial : mi-juillet. Semaine du 20 juillet : analyse des 1ers résultats.
- Amélioration continue jusqu'en août ; points le mardi après-midi.

## Questions ouvertes / à confirmer
- **Scope moteur (16/07)** : brouillon v0.1 RÉDIGÉ (2026-07-17) dans le vault Obsidian → `Agents IA &
  Pipeline TPDL/Segmentation & scope moteur — brouillon v0.1 (à valider Nathalie)`. En attente de
  validation Nathalie (6 questions ouvertes : géo, taille, coté/privé, thèmes de veille, dédup, volume).
  PUIS répercuter dans l'ICP de Hugo + `scoring_config.yaml` + encoder le signal « earnings call /
  priorité board digitale » (angle sur `digital_initiative`). Code NON touché tant que non validé.
- **Accès Betty** : boîte mail « Systems App » (via Alfredo) + login Perplexity ; qui a la feuille de
  codes (Andrés). Débloque le confort d'usage, pas le run (les clés sont dans `.env`).
- **Apollo** : arrêt aux résultats ou jusqu'aux contacts ? **PipeDrive** : ordre/catégories d'import.
- **Sophia** : variabilité d'un rerun Neotek (≤ 2-3 % ⇒ rapport semestriel) — en attente de réponse.
- ~~Agent de vérification (9e agent)~~ → TRANCHÉ (2026-07-14) : OUI = Vera (QA + file de revue).
- ~~Pourquoi Alex si Hugo est le moteur ?~~ → TRANCHÉ (2026-07-16) : manager/routeur pur, provisoire.
- Cadence de capture : **1 run/mois** acté pour l'instant ; passer à plus fréquent (hebdo / top 100)
  + garantir des captures nouvelles (dédup) = à revoir après avoir digéré les 1ers résultats.
- Migration rebranding code (#094752 → #0A0A0A + #EBEBEB + Funnel Sans) : quand ? (spec dans
  `brand-editorial.md`, code non touché).
- Prompt de *messaging* LinkedIn d'Andrés : Nathalie doit encore l'envoyer (à folder dans le playbook).
- Segmentation CRM (Segment 1/2/3) : propriétaire = Inès (contacts) ou Maya (analyse) ?
- Plateformes Lucia / Gaspers : à comparer aux outils actuels ?
- Moteur pipeline : le reconstruire dans ce repo, ou obtenir l'accès Neotek ? (bloque Step 3)
- Prix réels des outils (Firecrawl, Kaspr, Bouncer, Lemlist) avant souscription (Step 1).
- Cible de taux de réponse Lunch Campaign (à fixer avec Andrés).
- Base légale RGPD pour l'enrichissement + envoi (UE/CH) avant le 1er envoi.

## Dernière session
- Date : 2026-07-20
- Fait : **refonte UI traçabilité du run + page Découvertes + audit pré-démo** (voir log 2026-07-20 en
  haut). Sales/Contacts/Runs remis autour du run du 17/07 avec delta vs Neotek + couleur « réapparue » ;
  nouvelle fiche société (`/intel/company`) avec formule du score, courbe d'évolution et liens news
  cliquables ; nouvelle page **Candidates** (122 découvertes vendredi, FOUND ≠ SCORED). Audit : **0 lien
  cassé, 0 erreur console, scoring prouvé réel** (63/67 ≠ mai), **205 tests verts**. Polish démo (login,
  marketing, Home/Today, fiche agent, 404, Review, Usage). Point clarifié pour Betty : le run du 17/07 a
  **re-scoré 67 anciennes CH+ES** (toutes déjà chez Neotek, d'où « tout paraît Neotek ») ; les **122
  nouvelles** sont **découvertes mais NON scorées** (run stratégique annulé le 18/07). Reste : fusion des
  2 générateurs Marketing (décision Betty), rebrand cosmétique #094752→#0A0A0A (non fait).
- Fait (session du 2026-07-17) : **analyse + rangement de la réunion pilote du 16/07** (Betty & Nathalie). Transcript Word
  résumé et stocké aux 3 endroits (Obsidian `Agents IA & Pipeline TPDL/Réunion — 16 juillet…`, `operational-context.md`,
  CLAUDE.md + state.md). Faits neufs : changement de scope moteur (veille large life science, top 35 +
  nouveau, drop des 500 ; signal earnings-call/board), coûts/cadence confirmés (40-60 €, Batch, 1/mois),
  Apollo+PipeDrive (staging), MailChimp 1 500/mois, Bouncer réel, réalité des accès (clés `.env` ≠ login
  Betty ; Andrés = codes, Alfredo = Systems App), Sophia (rerun ~500 €), langue FR notes/EN code.
  ⚠️ Le scope moteur est CAPTURÉ mais PAS répercuté dans le code (à formaliser avec Nathalie d'abord).
  Vérifié `.env` : Anthropic/Exa/Perplexity/SerpAPI/Apify/Firecrawl SET ; Apollo VIDE ; Serper/Kaspr/
  Bouncer/Lemlist absents ⇒ **un run LIVE du moteur est techniquement possible** (validité des clés non
  testée). Aucun run lancé.
- Fait (session précédente 2026-07-16) : (1) **simulation budget des 3 runs** (smoke `--top 5` / Lunch `--lunch` / complet `--top 492`) —
  vérifié en direct les grilles Serper/Exa/Perplexity/Apify : à charger ~40-50 € sur Anthropic (~30) +
  Perplexity (~10) ; Serper/Exa/Apify/Firecrawl couverts par leurs paliers gratuits ; seul gris = Exa
  (0 ou ~10 €). (2) **Intégré les retours de Nathalie + 4 docs** (voir log 2026-07-16) : nouveau
  `.claude/brand-editorial.md` (charte officielle + ligne éditoriale + 10 principes + lexique + voix
  Andrés + report exemple), imports câblés, prompts `manager/maya/julie(playbook v2.2)/iris/marc`
  réalignés, mémoire + Obsidian mis à jour, DB re-seedée. **Aucun HTML/CSS/export touché** (consigne).
- Fait (session précédente 2026-07-15) : (1) recalé la mémoire (CLAUDE.md + state.md + prompts Hugo/Maya/manager) qui affirmait
  encore « pas de pipeline / moteur inaccessible / git non init » ; (2) débloqué `/recurring` via
  `backfill_snapshots.py` (amorce le vrai run 25/05 = run #1) ; (3) mergé `feat/neotek-engine` →
  `main` (local, ff) ; (4) Oliver : 5e format `newsletter` (70/10/20) ; (5) corrigé le docstring
  périmé de `sectors.py` (angles peuplés) ; (6) **connecteurs Kaspr/Bouncer/Lemlist câblés en gated
  dormants** (jamais de fabrication, fail-closed, Kaspr préféré par Inès) + `tests/test_connectors.py`.
  Suite : 123 verts. Tout mergé dans `main`. (7) **2e audit adversarial** → 11 bugs corrigés
  (crash batch, double-comptage, dates SERP, corroboration, QA verbatim, négation, `--max-usd 0`,
  RunSnapshot idempotent, `/top5`, bandes de score, `/premium`) + 12 tests → **135 verts**.
  Runbook de mise en prod ajouté (`.claude/go-live-runbook.md`).
- Prochaine étape : (1) merger `feat/neotek-engine` → `main` (local) ; (2) débloquer l'externe —
  clé Anthropic (→ run LIVE + chat), clés Serper/Exa/Perplexity/Firecrawl (→ recherche réelle),
  Apollo/Kaspr (→ contacts) ; (3) brancher Kaspr/Bouncer/Lemlist ; (4) créer le remote partagé
  avec Andrés + protéger `main`. Un run LIVE réel (même petit, ex. `--top 5 --live --max-usd 1`)
  produit le 2e CSV → `/recurring` s'active.
