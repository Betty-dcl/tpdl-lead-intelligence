# État courant — journal de bord vivant

> C'est LE fichier qui bouge le plus. Après chaque session, mettre à jour « Dernière session »
> et la checklist des blocages. Claude Code doit PROPOSER de le faire.

> 📘 **Mise en production (moteur/run)** : chemin clé-en-main dans `.claude/go-live-runbook.md`
> (quelle clé débloque quoi, commandes exactes, garde-fous, gate RGPD). Chargé à la demande.
> 🌐 **Déploiement de l'APP web partagée** : `.claude/azure-deploy-runbook.md` (Azure App Service +
> Postgres, conteneur Docker, mot de passe équipe, pas-à-pas `az`). Ajouté le 2026-07-21.

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
- 2026-09-02 (3) — **Chantier 3/4 du recap réunion Nathalie : curation 70/30 Europe/monde livrée
  (lot de lecture hebdomadaire de Nathalie).** **Clarification Betty (ce tour) sur le périmètre
  du 70/30 à travers les 3 phases** : (a) phase de base (les ~620 sociétés scorées) = **70/30
  confirmé littéral** ; (b) phase "personnes" (mouvements exécutifs, futur chantier 4) — le recap
  du 01/09 dit explicitement que le même 70/30 s'applique **aux deux** phases (base scorée ET
  mouvements exécutifs) ⇒ `app/tools/curation.py` est volontairement écrit GÉNÉRIQUE
  (`interleave_by_tier` prend deux listes pré-triées quelconques) pour que le chantier 4 le
  réutilise au lieu de dupliquer la logique de ratio ; (c) phase "top 10-15 méga-caps" (chantier 2,
  déjà livré) = **monde entier, aucun split** — confirmé cohérent avec ce qui a été codé (aucune
  logique géo dans `pipeline/recap.py`).
  **Autres décisions (ce tour)** : aucun plancher de score (tout l'univers in-scope éligible,
  colle à l'exemple réunion "10 boîtes" sans hypothèse supplémentaire) ; affichage = petite carte
  sur la page Sales existante (pas de nouvelle page dans le menu).
  **Fait** : nouveau `app/tools/curation.py` — `DEFAULT_RATIO = (7, 3)`, `interleave_by_tier()`
  (round-robin pondéré déterministe, même entrée → même sortie toujours, ne perd jamais une société :
  quand un côté s'épuise l'autre continue à se vider — reprend la règle du 22/07 "la géo n'exclut
  rien" même à cette couche de présentation) + `weekly_review_batch()` (partitionne par
  `market_tier` déjà exposé par `_serialize_company`, aucun plancher). Volontairement PAS fusionné
  dans `app/tools/shortlist.py` : son propre docstring est un contrat dur ("Maya OWNS it, Inès
  CONSUMES it, they can never disagree") — y mélanger un ratio de curation changerait
  silencieusement ce qu'Inès remet à Marketeering.ai, jamais demandé. Nouvel endpoint
  `GET /api/intel/weekly-review?n=10` (lecture seule, exclut `icp_flag=True`, réutilise
  `_serialize_company`/`_neotek_baseline` déjà en place). Nouvelle carte sur la page Sales
  (`templates/intel.html`, sous le cockpit du run) + état Alpine isolé (`weeklyBatch`/`weeklyN`/
  `weeklyMeta`/`loadWeeklyBatch()` dans `static/js/intel.js`, v=20) — délibérément SANS toucher
  `filteredCompanies`/`topN`/le picker de période existants (ils filtrent l'univers AVANT le
  tri, donc un ré-ordre 70/30 câblé dessus aurait pu être cassé par les propres filtres ad-hoc de
  Nathalie ; carte indépendante = jamais ce risque). +6 tests (`tests/test_curation.py` +
  1 test smoke API). **300 tests verts.** Vérifié : test API réel (curl authentifié, `n=5` → 3
  core / 2 world, données réelles Eurobio Scientific etc.), page `/intel` sert bien le nouveau
  markup, JS validé (`node --check`), 0 erreur dans les logs serveur. ⚠️ Vérif visuelle navigateur
  (capture d'écran) PAS faite cette fois — aucun outil Chromium/Playwright disponible dans
  l'environnement ; vérifié à la place par HTML/JSON/logs bout-en-bout, ce qui couvre le rendu et
  la donnée mais pas l'œil humain sur le layout final. Pas encore commité au moment de l'écriture.
  **RESTE (chantier 4, déjà conçu, à valider avant de coder)** : tracker mouvements exécutifs — le
  plus gros chantier, réutilisera `app/tools/curation.py` pour son propre 70/30, point RGPD à
  trancher avant le live (données de carrière de personnes nommées).
- 2026-09-02 (2) — **Chantier 2/4 du recap réunion Nathalie : veille "top 10-15 méga-caps" livrée
  (mode `--recap`, jamais scoré).** Suite directe du chantier 1 (plafond de revenu, log ci-dessous) :
  les sociétés au-dessus du plafond routent maintenant vers CE mode plutôt que d'être ignorées.
  **Décisions Betty (ce tour)** : (1) nouvelle table DB dédiée `MegaCapRecap` (+ export CSV en
  prime) plutôt qu'un CSV seul — même pattern append-only que `RunSnapshot`, pour pouvoir comparer
  les runs dans le temps plus tard ; (2) **citations verbatim uniquement, aucune synthèse IA** —
  zéro appel Opus, zéro risque d'interprétation, cohérent avec le "juste pour être au courant" de
  Nathalie ; (3) **déclenchement CLI uniquement** (`python -m pipeline.runner --recap --names "..."
  --live`), aucune commande chat, aucune page UI — Hugo reste strictement scopé à la base scorée,
  pas étendu.
  **Fait** : nouveau module `pipeline/recap.py` — mode structurellement séparé du pipeline scoré,
  réutilise Steps 1-3 mais s'arrête AVANT le scoring (jamais d'appel `score.interpret_and_score`) :
  (a) `gather_recap()` — pool de sources plus PETIT que les 9 du pipeline scoré (pas de registre UE,
  pas de job-board, pas de scan social) : `research.serp_news` + `research.exa_search` (réutilisés
  tels quels) + 2 sources NOUVELLES scopées à ce mode seulement (jamais touché `research.gather()`
  du pipeline scoré) : `ir_sources()` (balaie `/investors`, `/investor-relations`, `/en/investors`,
  `/news`, `/press-releases`, `/media/press-releases` avant repli sur la page d'accueil, 1er hit
  gagne) et `financial_statement_query()` (Perplexity Sonar, formulation annual report/10-K/investor
  day/earnings call) ; (b) extraction verbatim-lockée avec son PROPRE prompt/taxonomie
  (`pipeline/prompts/recap_sonnet.md`, 4 catégories `new_product`/`ma_activity`/`tech_platform`/
  `other` — les lancements produits sont explicitement INCLUS ici, contrairement aux 6 catégories du
  pipeline scoré qui les excluent) et son propre QA dupliqué à dessein (`verbatim_qa_recap`, pas un
  partage paramétré avec `extract.verbatim_qa` — pour qu'un item recap ne puisse JAMAIS glisser dans
  `score.interpret_and_score()` par un futur refactor : type distinct `RecapItem` vs `EvidenceItem`,
  erreur de type dure plutôt que bug silencieux) ; (c) `summarize_item()` = résumé déterministe non-IA
  (préfixe `[unconfirmed]` sur une citation hedgée via `extract.has_negation`, jamais un paragraphe
  rédigé par un modèle — décision Betty ci-dessus) ; (d) `write_recap_rows()` (table
  `app/models.py::MegaCapRecap`, une ligne par fait accepté, append-only) + `export_recap_csv()`
  (courtoisie, pas la source de vérité). `pipeline/runner.py` : flag `--recap` (exige `--live` +
  `--names`), `_run_recap()`, tôt dans `main()` juste après la sélection des sociétés — jamais
  d'appel à `_assemble()`/`CompanyResult`. `pipeline/estimate.py` : `estimate_recap_run()` +
  `render_recap()` (coût extraction seule, sans le levier Opus — `--recap --estimate` fonctionne
  sans clé). +14 tests (`tests/test_recap.py`, fail-open/QA/CLI, aucun appel réseau). **294 tests
  verts.** Vérifié : `--recap --names "Pfizer;Sanofi;Merck" --estimate` tourne sans clé
  (~$0,0233/société, "no Opus/scoring") ; `--recap` sans `--live` refuse proprement (money gate).
  Pas encore commité au moment de l'écriture. **RESTE (chantiers 3-4, déjà conçus, à valider avant
  de coder)** : (3) curation 70/30 Europe/monde ; (4) tracker mouvements exécutifs (le plus gros,
  point RGPD à trancher avant le live). La LISTE réelle des 10-15 méga-caps reste à fournir par
  Nathalie (le code est agnostique à la liste — `--names` — donc rien ne bloque côté implémentation).
- 2026-09-02 — **Chantier 1/4 du recap réunion Nathalie (2026-09-01) : plafond de revenu mega-cap
  (~$20 Mds) livré.** Suite du meeting du 01/09 (mémoire auto `project_tpdl_meeting_20260901`) :
  4 chantiers conçus le jour même par des agents de planification dédiés (session interrompue avant
  écriture du plan final), repris et livrés un par un, dans l'ordre convenu avec Betty (plus petit/
  moins risqué → plus gros ; validation à chaque étape). **Ce chantier** : au-dessus d'un certain CA,
  une société ne doit plus être scorée par le moteur classique — elle route vers le futur chantier 2
  (« veille top 10-15 méga-caps », pas construit ici). `app/tools/icp.py` : nouvelle
  `revenue_above_ceiling()` + constante `MEGA_CAP_REASON`, câblées dans `assess_icp()` **après** le
  plancher 100 M€ existant (même garde-fous conservateurs : inconnu/privé/regional → jamais exclu ;
  comparaison de MAGNITUDE seule, pas de conversion €/$ ; précédence : un nom curaté type Danaher
  garde SA raison "tools/instruments conglomerate", jamais écrasée par la raison mega-cap ; les 6
  cibles confirmées restent testées en tout premier, jamais exclues même sous un CA absurde).
  **Décisions Betty (ce tour)** : (1) seuil **configurable dans `scoring_config.yaml`**
  (`icp_ceiling_musd: 20000`, lu par `EngineConfig.load()` comme `outreach_threshold` — contrairement
  au plancher 100 M€ qui reste en dur, non touché) ; (2) **pas de backfill** sur les ~620 sociétés
  déjà en base — `icp_flag_reason` reste `NULL` jusqu'à leur prochain scoring naturel ; (3) la RAISON
  de l'exclusion est désormais **persistée** (`icp_flag_reason`, nouvelle colonne, pas juste le
  booléen `icp_flag`) — décision actée le 01/09, pour que le futur chantier 2 n'ait pas à re-dériver
  "pourquoi" une société est hors-ICP. La raison circule de bout en bout : `assess_icp()` →
  `CompanyResult.icp_flag_reason` (`pipeline/types.py`) → `pipeline/runner.py` (`_assemble()`, un seul
  appel, ne jette plus la moitié du dict) → CSV colonne **"ICP Flag Reason"** ajoutée en **dernière**
  position (`pipeline/export.py`, 38→39 colonnes — gardée en dernier pour ne pas casser
  `test_csv_headers_match_import_contract`, qui compare par égalité stricte au CSV Neotek de mai figé ;
  ce test passe maintenant en comparaison de PRÉFIXE) → `import_csv.py` → `Company.icp_flag_reason`
  (`app/models.py`, migration additive SQLite dans `app/database.py`, même pattern que
  `review_status`/`reviewed_at`/`reviewed_note`) → exposée dans `_serialize_company()`
  (`app/routers/intel.py`) pour que le futur chantier 2 puisse la lire sans nouveau round-trip.
  +9 tests (`test_icp_revenue_ceiling`, `test_revenue_above_ceiling_parsing`,
  `test_mega_cap_ceiling_flows_through_to_csv`). **280 tests verts.** Vérifié en dry-run
  (`python -m pipeline.runner --fixture pipeline/fixtures/probe_diagnostics.json`) : CSV bien à 39
  colonnes, "ICP Flag Reason" en dernière position. Pas encore commité au moment de l'écriture.
  **RESTE (chantiers 2-4, déjà conçus en détail, à valider un par un avant de coder)** : (2) veille
  "top 10-15 méga-caps" — mode séparé qui s'arrête AVANT le scoring (jamais d'appel Opus), nouvelle
  table `MegaCapRecap`, flag CLI `--recap` ; (3) curation 70/30 Europe/monde — nouveau
  `app/tools/curation.py` (interleave pondéré déterministe), nouvel endpoint
  `GET /api/intel/weekly-review`, sans toucher `shortlist.py` (contrat Maya/Inès préservé) ; (4)
  tracker mouvements exécutifs — nouvelle table `ExecutiveMove`, `pipeline/exec_moves.py`, commandes
  `/moves …` portées par Inès (file de revue) + Julie (rédaction, réutilise `andres_linkedin.md`) —
  le plus gros chantier, avec un point RGPD à trancher avant de le passer en live (données de
  carrière de personnes nommées, hors du cadre `Contact` existant).
- 2026-08-13 — **9e source de recherche pour Hugo : scan social/vidéo via les CLI d'agent-reach
  (demande Betty « ajoute-lui le skill agent reach pour scraper YouTube/Twitter/LinkedIn/Insta/
  Reddit »).** Clarifié d'abord : `agent-reach` (skill Claude installé chez Betty) n'est pas
  appelable par Hugo (agent de chat qui tourne via l'API Anthropic pure) — mais ses CLI sous-
  jacentes (`opencli`, `yt-dlp`, `mcporter`) SONT de vrais binaires sur PATH, appelables en
  subprocess depuis `pipeline/`, cohérent avec le fait que les runs live tournent déjà depuis le
  Terminal de Betty (pas depuis une session Claude Code). **Testé en direct sur Cantabria Labs**
  avant d'écrire le code : Twitter/Reddit marchent (session Chrome de Betty) ; **LinkedIn jobs**
  (`opencli linkedin search --company`, ne consomme PAS le quota people-search) marche en
  principe mais échoue actuellement chez Betty (« Text not found: Jobs » — mismatch de langue UI,
  pas un bug du code) ; **Instagram** marche via le compte dédié **giraffe.agent** connecté en
  session ; **YouTube** (yt-dlp) trouve du contenu réel pertinent (interview du CEO Susana
  Rodríguez Navarro) mais dégrade en bruit générique pour les petites boîtes sans présence vidéo.
  **Fait** : nouveau `pipeline/social_research.py` (5 fonctions, une par plateforme, fail-open —
  jamais de crash si une plateforme est hors ligne/pas loguée) + câblé dans `research.gather()`
  comme **9e source opt-in** (`cfg.social_scan_enabled`, flag CLI `--social-scan`, env
  `SOCIAL_SCAN_ENABLED`) — désactivé par défaut, car c'est de l'automatisation navigateur (lent,
  soumis aux rate-limits de chaque plateforme), donc dimensionné pour un shortlist/`--lunch`/
  `--names`, jamais l'univers entier (note ajoutée dans `--estimate`). **Bug trouvé et corrigé en
  testant en direct** : le filtre anti-bruit (exiger le nom littéral de la société dans le texte)
  rejetait le VRAI compte Instagram officiel car son handle n'a pas d'espace
  (`cantabrialabs_esp` ne contient pas « cantabria labs ») → nouveau `_account_matches()`
  (normalisé, insensible à la ponctuation) dédié à la résolution de compte, gardé séparé du
  filtre de contenu `_mentions()` (littéral, volontairement strict pour ne pas polluer
  l'extraction). Alimente le MÊME pipeline extraction (Sonnet 5) → scoring (Opus 4.8) — rien
  n'interprète dans ce module, comme toutes les autres sources. Prompt `hugo.md` + docstring
  `hugo.py` mis à jour (9 sources, caveat LinkedIn cassé côté UI, rendement B2B quasi nul attendu
  sur Twitter/Insta/Reddit — c'est normal, pas un bug). +14 tests
  (`tests/test_social_research.py`, CLI moqué). **271 tests verts.** Vérifié en LIVE (pas en
  dry-run) contre Cantabria Labs : les 5 fonctions tournent réellement et renvoient de vrais
  docs. ⚠️ Session bloquée en cours de route par un **disque plein** (89 Mo libres sur 228 Go) —
  nettoyé (40 Go libérés, sessions sandbox `local-agent-mode-sessions`/`vm_bundles` de Claude
  Desktop, vieilles et disposables). Pas encore commité au moment de l'écriture.
- 2026-08-10 (8) — **Démo pipeline MARKETING sur « How it works » (demande Betty « continue à améliorer
  la plateforme »).** Pendant de la démo sales du 03/08 : rend visible le câblage Iris→Marc→Oliver de
  cette session. **Fait** : (1) endpoint `GET /api/marketing/pipeline?theme=` (`app/routers/marketing.py`)
  qui assemble les 3 étapes pour UN thème de campagne, **déterministe, 0 LLM** (réutilise `campaign_themes.py`
  + `oliver.find_marc_content`) : Iris (thème + principe métier prouvé + audience) → Marc (start-from le
  principe, doctrine 7 étapes, mots interdits, marqueur [STAT TO VERIFY]) → Oliver (audience + 5 formats
  dont a4→PDF/ppt→PPTX en fichier + drapeau « contenu Marc prêt »). Picker = les 5 thèmes de Nathalie.
  (2) Section AJOUTÉE dans `how_it_works.html` (« See the marketing engine work a theme ») : sélecteur +
  3 cartes en flux, JS vanilla inline (réutilise les classes CSS de la démo sales, 0 CSS neuf). **Vérifié
  live** (serveur QA :8010, 0 erreur console) : picker 5 thèmes, 3 cartes Iris/Marc/Oliver, réagit au
  changement (omnichannel → principe « Hidden Cost of Fragmentation » + audience Ferrer/ISDIN ; HCP →
  Enterprise Architecture + Medical Affairs). +1 test. **257 verts.** Complète (ne double PAS) la démo sales.
  Pas encore commité au moment de l'écriture.
- 2026-08-10 (7) — **Audit des 3 agents non revus (Hugo, Vera, Alex) + fix des obsolescences de routage
  (demande Betty « vérifie chaque agent »).** Verdict : **Hugo** (moteur : /scan, /company brief intégral +
  fraîcheur, /stats, /candidates, /rerun honnête) et **Vera** (audit d'intégrité déterministe univers +
  par société, file review, stats) = SOLIDES, rien à changer. **Vraies obsolescences trouvées** (en partie
  causées par ma refonte Maya cette session — principe « code/mémoire ne divergent jamais ») : (1) hugo.md
  pointait les questions de récurrence vers `/recurring` de Maya (déprécié) → repointé sur `/summary`
  (mouvement) ; (2) manager.md décrivait le moteur « needs API keys / dry-run only » (FAUX depuis le 16/07 :
  clés dans .env + runs live faits le 17/07) → cadrage corrigé (dry-run gratuit ; live possible mais gated
  coût/intention, CLI, ~1/mois) ; (3) manager.md décrivait Maya « weekly Top 50/100 + recurring » (déprécié)
  → « shortlist / summary+mouvement / trends, cadence mensuelle » ; (4) Inès « via Apollo » → « Kaspr/Apollo ».
  Aucune logique de code touchée (fixes de prompt) + re-seed. **256 tests verts.** BILAN SESSION : les 8
  agents de chat sont tous câblés sur la vraie donnée ET leurs prompts sont cohérents entre eux. Pas encore commité.
- 2026-08-10 (6) — **Maya `/generate` porte enfin sa signature : la TRAJECTOIRE par société (demande
  Betty « continue à améliorer un agent, ou Maya ? »).** Après la refonte des commandes (log (2)), il
  restait un trou spécifique Maya : `/generate <company>` (brief de positionnement, bouton workspace)
  montrait rang / bande / pairs sectoriels / nb signaux mais PAS le mouvement dans le temps — or le
  mouvement EST ce qui distingue Maya de Hugo (Hugo score un point ; Maya lit la direction). **Fait** :
  nouveau `_company_trajectory(db, name)` (déterministe, RunSnapshot, collapse batches → 1 point/run,
  ordre CHRONOLOGIQUE) → ligne « Movement across N runs: 25/05 7.0 → 17/07 8.5 (↑ rising, +1.5) » injectée
  dans le brief `/generate` + consigne « pondère la trajectoire autant que le score absolu ». Fallback
  propre (« first appearance this run » / « no snapshot yet »). +1 test. **256 tests verts.** Vérifié
  DISPATCH réel : Cantabria 7.0→8.5 (+1.5), Ferrer 6.0→8.0 (+2.0), Roche 7.0→8.0 — tous « rising,
  prioritise ». Pas encore commité au moment de l'écriture.
- 2026-08-10 (5) — **Julie câblée sur les vraies données (demande Betty « reprends la mémoire, améliore
  encore un agent »).** Fil rouge de la session = câbler chaque agent sur la donnée réelle, pas du texte
  libre. Julie était déjà bien câblée sur `/draft` (signal + angle secteur + contact d'Inès + langue),
  mais 2 trous SANS dépendance de contenu : (1) `/draft` n'injectait PAS l'**Intelligence Summary** (les
  3 phrases de Hugo) — or la constitution dit que chaque message s'ancre dessus ; (2) `/linkedin` n'était
  PAS société-aware (docstring disait `[company]`, le code traitait tout en texte libre → aucun signal réel
  tiré) alors que LinkedIn = canal PRIORITAIRE (Premium 5, lunch, voix Andrés). **Fait** : (1) `/draft`
  injecte `company.intelligence_summary` comme ancre. (2) nouveau `_resolve_company_in_text()` → `/linkedin
  Cantabria Labs [+ trigger libre]` résout la société (nom entier, sous-chaîne, ou plus longue société
  contenue dans le texte), tire signal + Intelligence Summary + contact primaire d'Inès + `detect_country`
  (règles Espagne→espagnol+in-person / CH→anglais+in-person du playbook), garde le reste comme contexte
  opérateur ; **fallback texte-libre préservé** pour un contact ad-hoc hors univers. Prompt julie.md §7
  re-formé (`/draft` ancre summary, `/linkedin [company | contact+trigger]`) + re-seed. +2 tests. **255
  tests verts.** Vérifié DISPATCH (Cantabria Labs : /draft ancre le summary ; /linkedin résout ES + signal
  départ CEO avril 2026 + « new CEO just appointed » capturé). ⚠️ Vérif = déterministe (drawer chat headless
  intermittent) ; chemin chat→LLM = base.py déjà confirmé live (Inès/Maya). Reste content-bloqué (indépendant
  du câblage) : chiffres clients Andrés + prompt messaging Nathalie + contacts réels (Apollo débranché).
  Pas encore commité au moment de l'écriture.
- 2026-08-10 (4) — **Maillon Marc → Oliver câblé : Oliver formate le VRAI contenu de Marc (suite
  « continue » Betty).** Constat : après avoir câblé Iris→Marc sur la colonne vertébrale (log (3)), il
  restait le copier-coller Marc→Oliver — Oliver re-dérivait le contenu depuis le thème nu. Levier : le
  flux chat persiste DÉJÀ chaque `/content` de Marc comme `Task` (agent_id=marc, title=« Content — <thème> »,
  output=<la pièce>) — donc AUCUNE nouvelle table. **Fait** : `find_marc_content(db, theme)` dans
  `oliver.py` (lecture DB déterministe) retrouve la dernière pièce de Marc qui matche le thème (match par
  thème de campagne via `find_theme`, ou par titre) ; injectée dans l'augmented d'Oliver (« MARC'S CONTENT
  — format THIS, do not rewrite ») avec préservation exacte des marqueurs `[STAT TO VERIFY]` ; métadonnée
  `used_marc_content`. Fallback propre (note « Marc's content would sharpen it ») quand Marc n'a pas encore
  produit sur ce thème. Prompt oliver.md §4 re-formé + re-seed. +1 test (Task Marc réelle → Oliver la
  récupère + préserve les marqueurs ; thème sans contenu → fallback). **253 tests verts.** ⚠️ Vérif =
  test déterministe (le drawer chat headless était intermittent aujourd'hui) ; chemin chat→LLM = même
  base.py déjà confirmé live (Inès/Maya). ⚠️ Le contenu n'est persisté que par le flux CHAT (`respond`),
  PAS par le bouton workspace `/generate` (`generate_one_shot` ne persiste pas). Pas encore commité.
- 2026-08-10 (3) — **Moteur marketing câblé : Iris → Marc → Oliver sur une colonne vertébrale de
  thèmes partagée (demande Betty « continue » ; même trou que Maya→Inès avant câblage).** Constat : la
  chaîne marketing était un RÉCIT, pas un flux — Iris scorait des thèmes dans le vide, Marc/Oliver
  repartaient d'un thème en TEXTE LIBRE, rien de persisté. Levier : les **5 thèmes de campagne de
  Nathalie** (Market Intel July 2026) ne vivaient qu'en prose (iris.md §6b + brand-editorial.md §8).
  **Fait** : (1) nouveau `app/tools/campaign_themes.py` (déterministe, 0 réseau) = les 5 thèmes en
  DONNÉES structurées (titre · audience · **principe métier prouvé** parmi les 10 · angle · reframe
  « business problem not IT » · match_terms) + `find_theme()` (route un thème texte-libre) +
  `render_shortlist()` / `render_brief()`. C'est le `shortlist.py` du marketing (une seule définition
  pour les 3 agents). (2) **Iris** : `/themes` (+ alias `/campaign`) affiche la colonne vertébrale
  déterministe ; `/trends [secteur]` reste la recherche LIVE qui score par-dessus (préférer les angles
  qui mappent la campagne). (3) **Marc** : `/content` + `/angles` injectent le brief campagne quand le
  thème matche (`_campaign_block`) → part du bon principe métier + audience, plus aveugle ; rappel de la
  doctrine 7 étapes. (4) **Oliver** : injecte l'audience cible quand le thème matche. Prompts iris.md
  (§4 + `/campaign`) + marc.md (note grounding) re-formés + re-seed. +10 tests nets (test_campaign_themes.py
  + test_agents_wiring `/themes`→spine). **252 tests verts.** Vérifié DISPATCH déterministe : le brief
  campagne traverse Iris→Marc→Oliver (principe « Hidden Cost of Fragmentation » + audience Ferrer/ISDIN
  sur omnichannel ; audience Med-Affairs sur HCP). ⚠️ Œil-LIVE non fait cette fois (navigateur headless
  dégradé : refs (0,0), screenshots gris = bug d'outil) — mais chemin chat→LLM = même base.py déjà
  confirmé live aujourd'hui (Inès/Maya). Pas encore commité au moment de l'écriture. RESTE (maillon
  suivant proposé) : persister le CONTENU de Marc → Oliver formate le vrai texte (aujourd'hui copier-coller).
- 2026-08-10 (2) — **Maya REFONDUE (demande Betty « elle sert à quoi si Hugo score déjà ? refais-la, la
  plus pro possible »).** Diagnostic honnête re-posé : Hugo score UNE société (un point) ; Maya lit le
  PORTEFEUILLE + dans le TEMPS (priorisation, mouvement, forme du terrain) = 2 métiers. Le vrai problème
  n'était pas Maya mais **2 commandes redondantes** (`/top` doublait la page Sales, `/recurring` la page
  Recurring). **Fait** : (1) nouveau **`/summary`** = flagship analyste (executive read du run : headline
  eligible + top scores avec leur signal + mouvement risers/faders + low-but-rising watch + nouveaux) —
  absorbe la moitié utile de `/recurring` (§4b Nathalie) ; logique de mouvement extraite dans
  `_run_movement(db)` (trajectoire CHRONOLOGIQUE, jamais min→max). (2) **`/top` et `/recurring` dépréciés**
  → renvoient une redirection vers les pages + `/shortlist`/`/summary`, ne dupliquent plus de liste.
  (3) `/shortlist`, `/trends`, `/generate` inchangés. (4) `maya.md` réécrit (rôle net « scoreur vs
  analyste de portefeuille », règle trajectoire chronologique) + re-seed. (5) Sous-titre carte
  `seed.py` « Analyst — Top 50 & Trends » → **« Analyst — Shortlist & Trends »**. (6) 2 textes page Usage
  (credits.html + credits.py) : `/recurring` → `/summary`. Régressions importantes (trajectoire
  chronologique, faders) PRÉSERVÉES, repointées sur `/summary` (deltas de test agrandis pour rester dans
  le cap [:8]). +2 tests nets. **243 tests verts.** Vérifié LIVE (serveur QA :8010) : `/summary` sort un
  vrai executive summary (37 eligible/498, pattern « 2 specialty-pharma ES qui refroidissent ensemble »,
  low-but-rising watch, caveats 611 non re-scannées, what-to-do-next) ; `/top`/`/recurring` redirigent ;
  carte à jour. ⚠️ Leçon : le serveur preview tourne SANS `--reload` → redémarrer pour charger un
  changement de code (1er test `/summary` a échoué là-dessus). Pas encore commité au moment de l'écriture.
- 2026-08-10 (1) — **Inès améliorée sur 2 axes (demande Betty « ameliores la, sois le plus pro possible »),
  Apollo/Kaspr toujours débranché (on améliore le CONTENU + le classifieur, pas la connexion).**
  **Axe 1 — brief scraper exploitable** : nouveau module `app/tools/scraper_brief.py` (déterministe, 0
  réseau) branché dans `/contacts <company>` (Mode A) ET `/contacts shortlist`. Met en CODE ce qui n'était
  que prose : (a) **tie-back §3c** en checklist 3 points (partner-known Andrés/**Pierre** nommé pour l'ES /
  PipeDrive / 1er degré) sur chaque contact ; (b) **sous-lot Medical Affairs réellement séparé** dans la
  sortie ; (c) **config Sales Navigator par société** (recherche par nom · plancher séniorité · géo dérivée
  du pays · keywords) + champs de capture dont `recent join <3 mois`. Résultat : en Mode A, Inès sort un
  livrable prêt pour Marketeering.ai au lieu de « je tirerais plus tard ». **Axe 2 — robustesse du
  classifieur** (`app/tools/segmentation.py`) : bug corrigé — `_norm` SUPPRIMAIT les accents (« Médicos »
  → « m dicos », cassé) → il les **replie** (NFKD) ; titres ES/FR reconnus (« Director Comercial », « Ventas »,
  « Datos y Analítica », « Asuntos Médicos », « Transformación ») qui tombaient en None ; fix métier
  **« Director/Directora General » / « Gerente General » = c_level** (PDG), plus rétrogradés en director ;
  flag **`flags_vp_equivalent`** (Senior Manager sous le plancher mais VP-equivalent en petite boîte → à
  flagger, §3b). +11 tests (test_scraper_brief.py + test_segmentation.py). Vérifié LIVE : `/contacts
  Cantabria Labs` sort le brief complet en voix d'Inès. Pas encore commité au moment de l'écriture.
- 2026-08-03 (4) — **Vue « pipeline démontrable » (choix Betty : rendre la plateforme lisible).** Après le
  constat que les agents sont bons + câblés (Hugo→Maya→Inès→Julie, chaque maillon lit la sortie du précédent
  en code), Betty a choisi une **démo live** plutôt que plus de tuning. **Fait** : (1) endpoint
  `GET /api/intel/pipeline?company=` (`app/routers/intel.py`) qui assemble les 4 étapes pour UNE société,
  **déterministe, 0 appel LLM** (réutilise `_serialize_company`, `shortlist_bands`, `apollo.titles_for_signal`,
  `apply_radars`, `sectors.get_sector_angle`) : Hugo (score/coverage/signaux) → Maya (bande/rang/#N of 498/Δ) →
  Inès (signal→rôles + radar + tie-back + Med-Affairs) → Julie (angle sectoriel + hook tiré du signal réel).
  Picker = bande ACT NOW de Maya (top 30). (2) Section interactive AJOUTÉE dans `templates/how_it_works.html`
  (« See the team work a real company ») : sélecteur + 4 cartes en flux (flèches → entre elles), JS vanilla
  inline, fetch on change. **Vérifié live** (instance QA :8010, 0 erreur console) : Organon (US, rang 1/498,
  pas de lunch) vs Cantabria Labs (ES, rank #10, Δ +1.5, radar ES·🍽lunch·es) → la chaîne s'adapte par société.
  ⚠️ Screenshot du preview headless rend gris (bug d'outil) → vérif faite en DOM/texte (fiable). +1 test,
  **231 verts**. Complète (ne double PAS) la page méthodo moteur du même fichier. Pas encore commité.
- 2026-08-03 (3) — **Maya BRANCHÉE sur Inès (décision Betty « la brancher à Inès + garder »).** Question
  Betty « Maya est-elle vraiment utile ? » → constat honnête : `/top` et `/recurring` **doublent** les pages
  Sales/Recurring ; seule `/trends` (mix de signaux + service areas) + le récit executive summary sont
  uniques ; et la shortlist n'était **pas** câblée sur Inès (partage de DB, pas de tuyau). Choix Betty =
  lui donner un rôle pipeline réel. **Fait** : (1) `app/tools/shortlist.py` NOUVEAU = **définition unique
  de la shortlist** (`shortlist_bands` : ACT NOW in-scope ≥8 / MONITOR 5-7, tri score→couverture→fraîcheur) ;
  (2) `/shortlist` de Maya **refactoré** dessus (même source de vérité) ; (3) Inès : **`/contacts shortlist`**
  = batch hand-off qui prend la bande ACT NOW de Maya et sort le brief scraper par société (rôles pilotés par
  le signal + radar + tie-back + Med-Affairs séparé, plafond 15, jamais de nom inventé). Vérifié live : ACT NOW
  37 sociétés → batch top-15 (Organon 9.5, Hologic 9.5, CNX 9.0…). Prompt ines.md §8 + docstrings + re-seed ;
  +2 tests (`tests/test_maya_ines_wiring.py`) ; **230 tests verts**. Le trou Maya→Inès est comblé. ⚠️ Reste
  ouvert (reco non retenue cette fois) : déprécier `/top`/`/recurring` de Maya (redondants avec l'UI) — à
  reconsidérer plus tard. Batch = Mode A (brief) tant qu'Apollo/Kaspr débranché ; en Mode B il tirerait par société.
- 2026-08-03 (2) — **Inès RE-FORMÉE depuis les documents sources (demande Betty : « relis les
  transcripts + Word qui expliquent comment doit être Inès »).** Apollo reste débranché (câblé, gated,
  clé vide — connexion « plus tard ») ; on améliore le CONTENU du prompt. Sources relues : brief
  `TPDL_ICP_Targeting_Brief_Market Intel campaign July 2026.docx` (Parts 1-4 : companies / role framework /
  Sales Nav config / SDR acknowledge), email Outlook « week 30 Scrapping » (Nathalie→Megha@marketeering.ai =
  handoff réel = liste 6 sociétés + « ICP: review the document »), 2 transcripts 22/07. **4 trous comblés
  dans `app/agents/prompts/ines.md`** (édits chirurgicaux, structure gardée) : (1) **§3c NOUVEAU « tie-back »** —
  demande explicite Nathalie (« tie it back to existing PipeDrive contacts + 1st-degree LinkedIn, reconnect
  subtly ») : vérifier « on connaît déjà ? » (Andrés/**Pierre à Barcelone**, PipeDrive, 1er degré) AVANT de
  traiter en froid = cœur du Segment 1 ; (2) **config Sales Navigator exacte** reproduite (titres/séniorité/
  companies/géo/keywords, brief Part 3) comme livrable scraper v1 « à retravailler avec l'agence/SDR » ;
  (3) capture **recent-join <3 mois** (pilote la règle SDR « pas de félicitations sauf arrivée récente ») ;
  (4) **Mode A sort un brief prêt pour le scraper** (plus « je tirerais plus tard »). + hygiène chiffres
  (490→620, 38→44 éligibles, 48→53 CH) + Segment 1 relié au tie-back. Re-seed OK (DB==fichier), **29 tests
  ines/segmentation/connector/seed verts**. ⚠️ RESTE : (a) l'upgrade ICP Apollo non commité (apollo.py +
  segmentation.py + tests, 24 verts, ajoute Medical Affairs + plancher Director+ à la REQUÊTE) toujours en
  attente de commit ; (b) idée future = commande `/brief` dédiée (le scraper-brief est pour l'instant intégré
  à /contacts Mode A, sans toucher au .py).
- 2026-08-03 — **Passe qualité données (choix Betty « améliorer la plateforme » → axe #4).** Audit Vera
  réel lancé AVANT d'agir → mes notes étaient périmées : **secteurs Unknown 273→5** (pas 273), **0
  doublon**, **0 localisation manquante**, ligne poubelle « …Director | NA » **déjà supprimée**. Dette
  réelle = seulement (a) 5 secteurs Unknown, (b) 16 résumés verbeux, (c) la paire derma.
  **(1) 4 secteurs classifiés** (`scripts/fix_unknown_sectors.py`, réversible, backup
  `data/sector_backup_2026-08-03.json`) via `import_csv.bucket_for` : Slingshot Biosciences +
  SYNLAB → Diagnostics ; Henke Sass Wolf + UNIMED → Medtech. **Shealed GARDÉE Unknown** (obscure,
  score 0, jamais deviner). Unknown 5→1.
  **(2) 16 résumés « hors-format » = FAUX défaut** : lus (Samsung Medison 9.0, Kedrion, Biogen) →
  excellents, 5 phrases car plusieurs événements simultanés, suivent l'intention (situation/signaux/
  timing). **Non touchés** (les rogner détruirait de l'info ; se normalisent au prochain re-score).
  Reste `issue_count=16` = uniquement ces résumés = bruit d'audit assumé, pas une dette.
  **(3) Mediderma/Sesderma FUSIONNÉ en nommant les deux** (décision Betty « fusionne mais nomme qd mm
  les 2 ») : `scripts/merge_mediderma.py` (réversible, backup `data/mediderma_backup_2026-08-03.json`)
  garde la ligne ICP éligible (Mediderma 8.0, ses 3 signaux + historique 6.0→8.0) et la **renomme
  « Mediderma / Sesderma »** ; supprime la ligne Sesderma 7.8 (aucun contact/note sur les 2). Base
  **621→620**, 0 doublon. ⚠️ Tout écrit dans `data/app.db` (gitignoré) = correctif de propreté démo ;
  un futur re-score réécrit ces champs (durable = enrichissement à l'ingestion, `enrich_run.py
  --missing-sector` existe). Aucun code applicatif touché, aucun commit demandé.
- 2026-07-29 (4) — **Frise « inclure les runs du milieu » (Sales + Runs) + textes raccourcis +
  entrée démo Guest retirée (demandes Betty).**
  **(1) Frise à 2 modes** (`/api/intel/compare?...&span=two|full`) : `span=full` replie TOUS les runs
  entre from et to — chaque société suivie de sa **1re→dernière apparition dans la plage** avec sa
  **trajectoire** (ex. Cantabria `7.0→8.5`). Répond au « Neotek→23 Jul = 0 in both » : en full, le 17/07
  du milieu est replié → **67 recurring** (45↑/18↓/4=). Renvoie `span_runs` + `trajectory[]`. Toggle
  **« These two runs / Include runs between »** sur **Sales** (intel.js/intel.html : `period.span`,
  filtre = sociétés à ≥2 points, trajectoire sous le pill Δ, « new » masqué en full) ET **Runs**
  (traceability.html : `cmpSpan`, résumé « recurring », « new » masqué). intel.js → v=19. +1 test.
  **(2) Textes** : hero Home raccourci (plus d'Alex ; « Europe, Middle East and beyond » ; 2 moteurs) ;
  intro Sales réécrite (explique le **Δ** : comparaison au score précédent en base, seuil **≥8**, mais
  le Δ fait ressortir les risers sous 8) ; cockpit : ligne « 135 companies scored… » retirée (répétait
  le « ·135 new » d'à côté).
  **(3) Entrée démo « Guest claimed Cantabria Labs » retirée** (unique ligne `company_assignments`,
  user 6=guest ; backup `data/guest_assignment_backup_2026-07-29.json`, gitignoré). Le user guest reste
  (fallback mode public). Explications données à Betty : « claimed » = fil d'activité d'équipe ;
  « Include ICP-flagged » = réaffiche les hors-cible cachés par défaut. **225 tests verts**, 0 erreur console.
- 2026-07-29 (3) — **Runs unifiés par date + carte Serper + $ estimé par provider + REBRAND charte
  officielle + fix libellé cockpit (demandes Betty).** Suite de la session polish.
  **(1) Page Runs (traceability) re-clée sur la DATE** (au lieu de `import_run_id`) : les batchs d'une
  même date fusionnent en UNE carte (23/07 = « 3 import batches unified », 135 sociétés dédupliquées ;
  17/07 = « single run »). `_date_snapshots(db, day)` (best snapshot/société, score max) partagé ;
  `_runs_ordered`/`_top_company`/`_maya_recap`/`_scores_for`/`_trajectory`/`_neotek_compare` + les CSV
  hugo/maya/combined + export folder filtrent par date. `NEOTEK_REFERENCE_DATE` ajouté. Template : ligne
  « run <id> » → « N import batches unified / single run ».
  **(2) Carte Serper** ajoutée sur Usage (`serper_panel`, free tier 2 500/mois, compteur local + note
  dashboard). **(3) $ estimé** pour les providers sans API d'usage : `_SEARCH_UNIT_USD` (exa/perplexity
  ~$0.005, serper ~$0.001) → « est. spend ~$X all-time (rough, list price) » dans le détail (Exa ~$2,15,
  Perplexity ~$4,17). Les autres (SerpAPI searches, Firecrawl credits, Apify USD, Anthropic $) exposent
  déjà du réel ; « restant » exact = dashboard pour ceux sans API.
  **(4) REBRAND charte officielle Nathalie** (purement visuel, 0 contenu/filtre/catégorie/format touché) :
  teal **#094752 → near-black #0A0A0A** (3 vars CSS + token Tailwind `dark` + `--tpdl-info` + graphes JS
  + company_detail + exports PDF/PPTX DARK_INK + 5 avatars SVG, lift teal `#0d5b68/#0c5a68 → #232323`) ;
  fond **#fafaf8 → #EBEBEB** (token Tailwind `bg` + `--tpdl-bg`) ; police **Space Grotesk/Inter → Funnel
  Sans** (link Google Fonts + `--tpdl-font-*` + Tailwind fontFamily) ; vert #34D591 inchangé. Prompt Oliver
  re-formé (charte appliquée, plus de « teal pending ») + re-seed. custom.css bumpé **v=7**. ✅ **Logo officiel
  intégré** (`static/img/tpdl-logo.svg`, copié de `~/Downloads/TPDL Logo (1).svg` = carré vert #34D591 + « TPDL »
  blanc) : remplace le mini-logo pixel dans base.html (`.tpdl-logo-img`). ⚠️ Si #EBEBEB trop gris → ajustable en 1 ligne.
  **(5) Fix libellé cockpit Sales** ([intel.html]) : le run du 23/07 (135 **toutes neuves, 0 re-score**)
  et la stat base-entière (67 récurrentes, 45↑/18↓/4=) étaient collées → laissait croire que le 23 avait
  bougé. Séparé en 2 blocs étiquetés : « This run … all first-time scores, no within-run movement » +
  « ACROSS ALL RUNS · WHOLE DATABASE (NOT THIS RUN) ». Vérifié live (Home + Sales à la charte, 0 erreur
  console), **224 tests verts**. ⚠️ Index git s'est encore vidé → `git reset` (non destructif) avant commit.
- 2026-07-29 (2) — **Exports téléchargeables riches : fiche société PDF + exports de vue (CSV / PDF liste /
  PDF détails) sur Sales & Recurring (demandes Betty).** Suite de la session polish.
  **(1) Fiche société PDF** (`app/tools/company_pdf.py` + `GET /api/intel/companies/{name}/brief.pdf` +
  bouton sur la page société) : one-pager brandé reprenant la page société — identité, score + formule,
  **courbe d'évolution** (sparkline dessinée), chaque signal (what/why/relevance, confiance, corroboration,
  **liens sources cliquables**), tech stack, historique, delta Neotek. Réutilise TPDLPDF (fpdf2) + helper
  Latin-1. ⚠️ Pièges fpdf2 corrigés : `multi_cell(wrapmode="CHAR", link=…)` **boucle à l'infini** → domaine
  cliquable en `cell` + URL complète en gris `CHAR` sans lien ; curseur laissé à droite après `multi_cell`
  → `new_x=LMARGIN` partout (sinon labels coupés à droite) ; corroboration est un **dict** {points,max} pas
  un int. Décision Betty : CSV par société inutile (1 ligne, déjà dans le run CSV) → **PDF seul**.
  **(2) Exports de vue** (Recurring + Sales) respectant **filtres + tri** (WYSIWYG) : helper JS partagé
  `static/js/view_export.js` (CSV client-side Excel-friendly + `tpdlPostDownload`). Endpoints :
  `POST /export_rich.csv` (CSV **full-depth** filtré aux sociétés affichées, dans l'ordre — 50 colonnes :
  résumé, 3 signaux + sources + corroboration, tech stack, **trajectoire = courbe en données**) ;
  `POST /view.pdf` (**liste** : tableau récap 1 page, `app/tools/view_pdf.py`, paysage) ;
  `POST /view_briefs.pdf` (**détails** : une fiche complète par société, plafonné 60). `export_csv`
  refactoré → helpers `_export_record` + `_csv_response` réutilisés. **3 boutons** par page : ⬇ CSV /
  ⬇ PDF list / ⬇ PDF detail. Vérifié live (Recurring biggest-riser : CSV 50 col + trajectoire + liens,
  PDF list 9 Ko, PDF detail ~17 p pour 8 sociétés) ; Sales (filtre Spain + tri Δ vs May → sous-titre
  capturé). **224 tests verts**, 0 erreur console. ⚠️ `git reset` a été nécessaire (index vidé en cours
  de session, motif `git rm --cached` ; HEAD intact, working tree intact — non destructif). Backups data
  (`data/*_backup_*.json`) ajoutés au .gitignore.
- 2026-07-29 — **CSV téléchargé actualisé + Excel-friendly, enrichissement CA/secteurs, section Home
  retirée, `**` markdown supprimés pour tous les agents (demandes Betty).** Session de polish plateforme.
  **(1) Revenus du run 23/07** : Betty téléchargeait le CSV sans revenus. Ajout `enrich_run.py
  --missing-revenue` (ne re-paie pas les CA déjà remplis) → relance ciblée sur les 66 CA vides ⇒
  **CA 69 → 78/135** (+9 : Sciensus, Berkeley Lights, Industria Chimica Emiliana…). Les 57 restants =
  mid-cap privées / filiales sans CA public (Galapagos, MilliporeSigma…) → jamais inventé.
  **(2) Secteurs Unknown de tout l'univers** (option 2-1 Betty) : ajout `--missing-sector` + `--all-runs`
  → enrichissement des **138 Unknown → 6** (132 remplis, ~0,70 $, fail-open). Répartition propre :
  Pharma 202, Medtech 96, Diagnostics 86, Dental 75, Healthcare/Services 68, Other 47, Dermato 42.
  ⚠️ 1 des 6 restants = **donnée poubelle** « Global Director Digital Strategy and Innovation | NA »
  (titre de poste entré comme société par une passe de découverte) — à supprimer (accord Betty en attente).
  **(3) Export CSV Excel-friendly** ([intel.py] `export_csv`) : le CSV brut s'ouvrait en 1 colonne + accents/
  flèches cassés dans Excel européen. Corrigé : **BOM UTF-8 + ligne `sep=;` + délimiteur point-virgule**
  (colonnes propres quelle que soit la locale) + scores en 1 décimale + texte long nettoyé. Contenu inchangé
  (44 colonnes = tous les critères : identité, ville, geo, secteur, CA, score/flags, résumé, 3 signaux +
  sources + corroboration, tech stack, historique). Tests smoke adaptés (skip ligne `sep=`).
  **(4) `**` markdown retirés pour TOUS les agents** ([base.py]) : le chat affiche le texte brut → les `**`/
  `***` apparaissaient littéralement. Fix à un seul endroit (socle commun) : (a) `PLAIN_TEXT_RULE` ajoutée
  au prompt système de chaque agent (pas de Markdown), (b) `strip_markdown_emphasis()` déterministe en sortie
  de `_call_claude` (retire */**/***, préserve tirets de liste et « 2 * 3 »). Vérifié live : Hugo répond sans
  étoiles même invité à en mettre. +2 tests. ⚠️ Anciens messages déjà stockés gardent leurs étoiles ; seuls
  les nouveaux sont propres.
  **(5) Home** : section « How the team works » (frises Sales+Marketing pipeline) supprimée ([office.html]).
  Suite : **220 tests verts**, 0 erreur console. ⚠️ Enrichissements écrits dans `data/app.db` (gitignoré) —
  un futur re-score réécrirait ces champs. Serveur relancé (auth active). Pas de push GitHub demandé.
- 2026-07-27 (2) — **CSV run nettoyé + enrichissement secteur/CA/site des 135 du 23/07 (accord Betty).**
  Suite retours Betty sur l'export : (a) **1 seule colonne secteur** (fusion Sector/Sector Bucket),
  (b) **« Market Tier » retirée**, (c) **colonnes de comparaison vides supprimées** quand tout le run est
  neuf → remplacées par **« Status » = New company / Re-scored (N scans)** ; elles réapparaissent en
  scope=all. Le **contexte de la boîte** (intelligence summary, signaux + sources + corroboration, tech
  stack, historique) était déjà dans le CSV — confirmé. Commit 148d5b5. Aussi : **page Today supprimée**
  (nav/route/template/js/router `/api/today`, commit c9325e5) ; frise Sales **pilote le run** (dropdown
  « Run » caché quand une comparaison est active, commit 2ee3aaf) ; **page Candidats supprimée** (le « 64 »
  = juste le dernier lot de découverte, source de confusion ; tout est scoré ⇒ page inutile ; garde-fou
  archive reste dans le moteur). **Enrichissement live** (Betty : « oui, sans trop dépenser » → option A) :
  `scripts/enrich_run.py` — **1 appel Perplexity `sonar`/société** (secteur+CA+site en un coup, urllib donc
  tourne en session, fail-open, bucket via `import_csv.bucket_for`, `parse_revenue`, domaine extrait).
  Passé sur les **135 du 23/07** (~0,70 $) → **secteur 133, site 131, CA 69** (les CA vides = mid-cap
  privées, jamais inventé) ; 0 erreur. La table `companies` reflète les vrais secteurs (Pharma 57,
  Diagnostics 26, Medtech 12, Dental 11…). ⚠️ Écrit dans `data/app.db` (gitignoré) ; un futur re-score
  réécrira ces champs. Le script est réutilisable : `python scripts/enrich_run.py [--run …] [--sample N]`.
- 2026-07-27 — **Refonte Sales (frise + double delta), Recurring (matrice), Candidats (honnête) +
  CSV run complet + garde-fou anti-fuite découverte (demandes Betty).** Commits 9311331 + 0812e78
  sur `feat/neotek-engine`, 218 tests verts, 0 erreur console.
  **(1) Sales — « frise » de comparaison de runs** ([templates/intel.html], [static/js/intel.js]) :
  sélecteur From→To façon relevé bancaire (au-dessus du tableau) → le tableau se restreint au run
  « To », résumé live (new/rose/fell/unchanged) + toggle « only new ». **Deux colonnes Δ** : **Δ period**
  (les 2 runs choisis) et **Δ vs May** (base Neotek, TOUJOURS affichée). Pas de frise → Δ period = « — »
  et l'histoire repose sur la colonne May. Réutilise `/api/intel/compare` + `neotek_score/delta` déjà
  sérialisés. Retiré l'ancienne colonne Δ rebaseable + `deltaBase/loadBaseline/compare/renderCharts`.
  **(2) Sales allégé** : import Chart.js inutilisé, 5 cartes KPI redondantes et la timeline de signaux
  du bas supprimées (on arrive direct aux résultats). Phrase « en commun avec la base » clarifiée.
  **(3) Recurring refait en MATRICE** ([templates/recurring.html]) : 1 ligne/société, badge ×N, 1 cellule
  score par date de scan (colorée par bande, « — » si absente) + trajectoire « since first » ; tri
  scans/latest/riser/faller, filtres ×N / in-ICP / recherche. (Endpoint `/api/intel/recurring` inchangé.)
  **(4) Candidats HONNÊTE** ([templates/candidates.html] + `/api/intel/candidates`) : la page ne prétend
  plus que des noms déjà scorés sont « not scored ». Lit l'état réel par nom (**64 découverts · 64 scorés ·
  0 en attente**), badge « ✓ scored → Sales », filtre Waiting/Scored/All, bandeau vert quand 0 en attente.
  Texte périmé « annulé le 18/07 » retiré. Constat clé re-vérifié : **les 135 du 23/07 sont 100 % nouvelles**
  (0 historique) → d'où « new » partout dans les Δ ; les chiffres (+1.5…) n'existent que pour les sociétés
  à historique (les 67 CH+ES). RIEN n'a été perdu : les 122 de vendredi + 13 = 135, toutes scorées.
  **(5) Export CSV run enrichi** (`/api/intel/export.csv`, 53 colonnes) : identité + geo/market_tier, score
  & flags, **évolution inter-runs complète** (times scored, net-new, previous score, Δ vs previous run,
  Δ vs May, trajectoire « May 25 7.0 → Jul 17 8.5 »), summary, chaque signal détaillé + **corroboration
  (0-2)**, tech stack, historique. `?run=AAAA-MM-JJ` cible un run (défaut = dernier). Bouton cockpit renommé
  « Full run detail (CSV) ». Test smoke mis à jour.
  **(6) Garde-fou anti-fuite découverte** (`pipeline/discovery.py`) : `archive_candidates()` écrit un
  journal **append-only** `data/csv/discovery_archive.csv` (dédup par nom normalisé, garde la 1re date vue) —
  appelé dans `discover()` AVANT tout scoring, donc un nom ne peut plus disparaître quand
  discovery_candidates.csv est écrasé. **Backfill fait** : 135 noms (122 vendredi 18/07 + 13 gros run 23/07).
  L'API/UI Candidats exposent « ever discovered 135 / never scored 0 » comme preuve. +1 test (idempotence).
  Fichier gitignoré (comme les autres artefacts discovery). ⚠️ L'archivage AUTO ne s'active qu'au prochain
  `--discover` réel (Terminal).
- 2026-07-23 — **Stratégie SERP inversée : DRAINER SerpAPI d'abord, Serper en BACKUP auto (demande
  Betty).** Betty a un abonnement SerpAPI peu rechargé + une clé Serper (ajoutée dans `.env` le
  23/07, 40 car., chargée OK) qui sera « remplie de tokens ». Consigne : utiliser SerpAPI jusqu'à
  le VIDER, et quand il n'a plus de crédit → **ne pas planter**, arrêter SerpAPI et **basculer sur
  Serper** pour le reste du run ; les deux clés vivent ensemble. ⚠️ Le code faisait l'INVERSE
  (préférait Serper si la clé existait). Corrigé dans `pipeline/research.py` : `SerpApiExhausted`
  + `_check_serpapi_quota` (détecte le body SerpAPI « run out of searches » = HTTP 200 + error) +
  wrappers `serp_news`/`serp_jobs` (`_serp_with_fallback`) = SerpAPI d'abord ; sur épuisement
  (SerpApiExhausted ou HTTP 401/429) → flag **run-scoped** `cfg._serpapi_exhausted` → SerpAPI n'est
  plus rappelé du run, Serper prend le relais ; sur erreur transitoire → fallback Serper pour CETTE
  société seulement (SerpAPI re-tenté à la suivante). Même ordre appliqué à `eu_registry` et à
  `discovery._serp_theme`. `gather()` utilise les wrappers. Message `--estimate` mis à jour (quota
  SerpAPI bas + Serper présent = « OK, fallback auto », plus « INSUFFISANT »). ⚠️ Garde-fou anti-quota
  (`runner.py` ~L368, clé sur le mot « INSUFFICIENT ») préservé : le mot reste UNIQUEMENT dans le cas
  sans-Serper, donc le run n'est bloqué que si SerpAPI est court ET aucun backup Serper. +1 test
  (`test_serpapi_drains_then_serper_backup`). Fonctions validées via python3.14 (assertions PASS).
- 2026-07-23 — **Crédit Anthropic/Perplexity CONFIRMÉ présent (Betty) + lanceur du gros run écrit.**
  ⚠️ **Correction d'intention (Betty)** : PAS de fusion maintenant — **garder vendredi et le gros run
  SÉPARÉS**, voir la **différence** (communes / nouvelles), **merger PLUS TARD**. Script
  `scripts/run_big_launch.sh` (bash 3.2, exécutable) : (1) fige vendredi → `discovery_friday.csv` ;
  (2) `--discover --live` → `discovery_candidates.csv` = le gros run (écrase, séparé de vendredi) ;
  (3) **comparaison SANS fusion** via `scripts/compare_discoveries.py` → `discovery_comparison.csv`
  (colonne Status : common / new / dropped) + résumé écran ; (4) score le **GROS RUN SEUL** (noms via
  `scripts/_names_from_csv.py`, pas d'union) : `--names <gros run> --live --batch --submit
  --enrich-location --enrich-revenue --rescan-tech --max-usd 60 --out engine_run_big.csv` → run/snapshot
  DISTINCT ; (5) affiche `--fetch` (≤24h) + import. Les 2 helpers sont standalone (`_norm` copié de
  discovery._norm, validé identique — tournent par chemin depuis n'importe quel cwd). ⚠️ À LANCER DEPUIS
  LE TERMINAL (SDK bloque en session). Galop GRATUIT = `--top 150 --estimate` (⚠️ `--discover --live`
  coûte ~0,50 $, PAS gratuit). Testé : comparaison 122 vs 5 → 3 common / 2 new / 119 dropped ; noms=122.
  bash -n OK. Ancien helper d'union supprimé. **Vue de comparaison AJOUTÉE dans l'UI** (demande Betty
  « montrer le résultat + la différence de run ») : `/api/intel/candidates` lit `discovery_comparison.csv`
  (join par nom normalisé) → renvoie `comparison{common,new,dropped}` + `vs_friday` par candidat ; page
  Candidates ([templates/candidates.html]) affiche une barre « Big run vs Friday » (X common / Y new /
  Z only-Friday) + filtre All/New/Common + badge par ligne (« new this run » vert / « also on Friday »
  bleu). Vérifié LIVE (.venv, serveur :8000) avec un fichier de comparaison DÉMO (91/31/2) : barre +
  filtre + badges OK, 0 erreur console ; démo supprimée → la page retombe proprement sur les 122 sans
  barre. RESTE (idée future) : le vrai « merge » (dédup du gros run vs vendredi une fois importés).
- 2026-07-23 — **Capture de la VILLE du siège (HQ) demandée par Betty + confirmation filtre Lonza/
  Zühlke.** (1) **Feedback Lonza/Zühlke vérifié** : déjà exclus par `app/tools/icp.py` (Lonza ∈
  `_CDMO_NAMES`, Zühlke ∈ `_CONSULTING_NAMES`) ; les 6 cibles protégées. Les 122 candidats : **42
  flaggés hors-ICP** (CDMO/CRO/tools/distributeurs/conseil), 77 in-scope ; Lonza/Zühlke absents des
  122 (ils sont dans la base historique des 490, où aussi flaggés). Rien à recoder côté exclusion.
  (2) **Ville du HQ = trou identifié, capacité construite** : `location` était du texte libre (souvent
  juste le pays) + le CSV des 122 n'avait AUCUNE colonne localisation. Ajouté, sur le patron
  `enrich_revenue` (déterministe, fail-open, opt-in) : `enrich.parse_hq_location`/`needs_city`/
  `estimate_hq_location` (1 appel Perplexity/société, remplit la ville quand `location` n'a qu'un
  pays ; n'écrase jamais une vraie ville) + flag CLI **`--enrich-location`** (config `enrich_location`)
  câblé dans `runner._assemble`. Découverte : `Candidate.hq` + prompt Sonnet (copie la ville
  **verbatim si le finding la donne**, sinon null) + **colonne « HQ / City »** dans
  discovery_candidates.csv (routeur `/api/intel/candidates` renvoie `hq` ; page Candidates affiche 📍).
  Fichier des 122 réécrit avec la colonne (vide pour l'instant). +1 test (`test_hq_location_enrichment`).
  ⚠️ **Remplissage des villes = étape LIVE** (Perplexity via urllib — marche en session, mais spend
  non lancé sans accord ; le naturel = au prochain run depuis le Terminal avec `--enrich-location`,
  gaté sur la clé Serper de toute façon). ⚠️ pytest non lançable en session (aucun venv trouvé avec
  les deps) — fonctions pures validées via python3.14 direct (toutes assertions PASS) + syntaxe OK.
- 2026-07-22 — **File Review nettoyée (36 → 9) : suppression des faux flags hérités + BLOCAGE SDK
  identifié (demande Betty).** Betty a remarqué des signaux `confidence=high` toujours en review et
  a demandé s'il y avait erreur. Diagnostic : **non, pas une erreur de conception** — les 36 flags
  dataient TOUS du run du 17/07 et **34/36 relevaient de l'ANCIENNE règle « per-quote speculation »**
  (flag dès qu'une citation était hedgée, même noyée dans des sources solides), remplacée le 18/07
  par « resting entirely on hedged quotes » mais **jamais re-passée sur ces données** = dette de
  données. **Option A (re-score exact ~2 $) tentée mais IMPOSSIBLE dans cette session Claude Code** :
  le client `httpx` du SDK `anthropic` **bloque systématiquement** (>120 s, timeout non déclenché),
  y compris machine au repos (load 1,16) — ce n'est NI la RAM, NI les clés, NI le réseau (un appel
  API direct via `urllib` répond en 1,8 s ; `claude-sonnet-5` valide). ⚠️ **LEÇON OPÉRATIONNELLE :
  les runs LIVE du moteur doivent être lancés depuis le TERMINAL macOS, pas depuis cette session**
  (le SDK y bloque). **Option B appliquée (0 $, insensible au SDK — pur SQLite)** : levé le
  `review_flag` des **27 sociétés** au motif 100 % spéculatif (Cantabria, Roche, Ypsomed…) ; **gardé
  les 9 vrais flags** de la règle actuelle (8 « QA verbatim », 1 « no date » = Sandoz). Réversible :
  sauvegarde `data/review_flags_backup_2026-07-22.json` + note d'audit sur chaque société levée.
  ⚠️ B = pansement cosmétique de l'affichage ; le prochain **run batch 24h le régénère/écrase de zéro
  (aucune heuristique)**. Aucun code modifié, aucune migration ; la table `companies` reflète le
  nettoyage.
- 2026-07-22 — **ICP « Market Intel July 2026 » FORMALISÉ + répercuté partout (5 docs analysés).**
  Betty a fourni 5 docs (2 transcripts du 22/07, le brief ICP, les thèmes de contenu, l'email
  scrapping Nathalie→Marketeering.ai). La segmentation moteur passe de « brouillon à valider » à
  **officielle**. Décisions Betty : (1) **découverte large + ICP = filtre de ciblage** ; (2) **encoder
  les exclusions dures** (conseil + CDMO/CRO + plancher 100 M€, privées à CA inconnu gardées).
  **Code** : nouveau `app/tools/icp.py` (`assess_icp`, déterministe, testable) + câblé dans
  `pipeline/runner.py` (chaque run pose `icp_flag`) ; recompute base via sqlite → **17 sociétés
  hors-ICP** (Zühlke/ProductLife conseil ; Lonza/Siegfried/Unither/Avania/Neuland/Quotient/Nuvisan/
  Meribel CDMO/CRO ; BioPorto/NADMED/Medica/Gentian/BEGO/ARENSIA/Qure AI <100M€) → base 490, hors-ICP
  229, in-scope 261. **Prompts** re-formés (à re-seeder) : hugo §2b (couche ICP + 6 cibles + exclusions),
  ines §3b (cadre rôles/séniorité, famille **Medical Affairs** en sous-lot, config Sales Nav,
  Marketeering.ai, PipeDrive) + axe Function `medical_affairs`, julie §3b (message acknowledge + rythme
  SDR), maya §4/§4b (Reality corrigée = 2 runs + executive summary « gros écarts / risers sous 8 »)
  + ICP dans le ranking, iris §6b (5 thèmes + Deyasini). **Mémoire** : CLAUDE.md (ÉTAT CIBLE
  formalisé), operational-context.md (section 22/07), brand-editorial.md (§8 thèmes). **Obsidian** :
  note segmentation à passer en « validée » + note réunion 22/07 (à faire — OneDrive était saturé).
  Personnes neuves : Nathalie **L'Eplattenier** (Zug), Paula **Carretero**, **Deyasini** (contenu),
  **Marketeering.ai** (Megha Dhiman + Priya Arora, scraping/SDR), Priya & Shamli @TPDL, **Sofia P**
  (Neotek réel). Événement Espagne octobre = moteur business (cibles = invités). ⚠️ RESTE : re-seed
  (`python seed.py`) + `pytest` (n'ont pas pu tourner — machine saturée par un scan OneDrive) + notes
  Obsidian + commit. À faire dès que la charge machine retombe.
- 2026-07-22 — **Partage clé-en-main + login « porte d'entrée » + clarté du run (demande Betty).**
  **(1) Lien public gratuit** : `share.sh` (Cloudflare quick-tunnel via `cloudflared`, installé par brew) +
  **`Partager TPDL.command`** (double-clic Finder, copié aussi sur le Bureau) → une fenêtre affiche l'URL
  `…trycloudflare.com`, **la copie dans le presse-papier** (pbcopy). Robuste sous le bash 3.2 de macOS (pas de
  `set -euo pipefail`, PATH Homebrew forcé, python du venv en direct). ⚠️ lien vit tant que la fenêtre est
  ouverte ; URL change à chaque relance (gratuit). Payant/permanent = runbook Azure déjà prêt.
  **(2) Auth = porte d'entrée** : gate activé dans `.env` (`TPDL_AUTH_GATE=on`, `TPDL_TEAM_PASSWORD=TPDL`) ;
  `app/main.py` resserré → **toute** page/API exige le login (Home, Marketing, APIs démo incluses), seule la
  page login + auth + statics sont publiques ; login rendu **standalone** (flag `hide_chrome` sur base.html,
  sans nav/footer). Tests auth-gate mis à jour. NB : une session valide (cookie) = accès direct sans re-login
  (par navigateur) ; les autres voient bien le login.
  **(3) Clarté du run cockpit** : les 4 tuiles de bandes de score somment désormais à 67 (act 7 / monitor 42 /
  weak 15 / **no signal 3**) + ligne « 7+42+15+3 = 67 » ; **review-flagged (36) sorti comme indicateur
  transversal** (pas une 5e bande — recoupe les autres). Corrige la lecture « somme = 100 ».
  **(4) Δ vintage-aware** : une ligne NON re-scorée depuis mai affiche **« — »** (et non un faux « ±0 »).
  Serializer `_serialize_company` ajoute `vintage` (refreshed | neotek_may) ; delta calculé seulement si
  re-scorée après le run Neotek (`NEOTEK_REFERENCE_DATE`). Colonne renommée **« Δ since May »** + infobulle,
  badge de fraîcheur **« refreshed Jul » / « May run »** (fini « stale »). Une re-scorée inchangée = **±0**
  (toujours visible), seule une non-rafraîchie = « — ».
  **(5) Filtre « Run »** (remplace « Fresh only ») : **All runs (490) / Refreshed — Fri 17 Jul (67) / May —
  Neotek (423)** sur `filters.vintage` → un clic pour isoler la diff des 67 de vendredi. Décisions Betty :
  défaut = 490 ; panneau Compare runs gardé visible. Vérifié live (67/423/490), 0 erreur console, 49 smoke verts.
  Commits : b3d71e0, d6687fe, ce05b8c, 572953f, 53ae01a, 4a7858b, 86357e1 (+ ace85f4 partage initial).
- 2026-07-21 — **Filtres Sales enrichis + comparaison de runs + prépa déploiement Azure (demande Betty).**
  UI Sales ([intel.html]/[intel.js]/[intel.py]) : (1) **filtre localisation** (CH/ES/USA/Middle East/
  Europe/APAC/Other) via `geo_region()` déterministe ajouté à `app/tools/radars.py` (bucketing free-text) ;
  (2) **frise comparaison de runs** « comme un relevé bancaire » : sélecteurs From→To, résumé new/rising/
  fading/stable + top riser/fader, **delta recalculé pour la période** ; endpoints génériques `/api/intel/runs`
  + `/api/intel/compare?from_run&to_run` (s'étendent seuls dès un 3e run, rien codé en dur pour 2 runs) ;
  (3) **frise Top-N** (10/20/35/50/200/All) + **colonne de rang `#`**. Fiche société ([company_detail.html]) :
  delta **toujours affiché** (Up/Down/Unchanged/New) + **courbe toujours tracée** (`renderChart` dessine dès
  1 point ; testé 1pt=15 040 px, 2pt=169 450 px — le fix protège les futures sociétés net-new, les 122
  candidats une fois scorés). +5 tests → **210 verts**, 0 erreur console, vérifié en live.
  **Utilisateurs remplacés** (`seed.py`) : Marie/Pierre/Sophie/Léa/Tomás → **Andrés, Paula, Nathalie, Betty**
  (mêmes droits, code équipe **TPDL**, modifiable ensuite) ; `seed_users` purge désormais les users obsolètes
  (nettoie assignments/comments/activity/status/briefs). **Prépa déploiement Azure App Service** (choix Betty,
  vraie app web multi-utilisateurs, pas de rôles) : `Dockerfile` (1 worker gunicorn+uvicorn — scheduler+WS en
  mémoire) + `.dockerignore` + `gunicorn`/`psycopg[binary]` dans requirements + `.claude/azure-deploy-runbook.md`
  (pas-à-pas `az`, Postgres, amorçage, variables d'env). L'app était **déjà Postgres-ready** (`DATABASE_URL` +
  couche DB bi-dialecte). Commande de prod validée en local (gunicorn boote, port en écoute) ; build image non
  testé (Docker absent de la machine). RESTE (action Betty/Alfredo, compte Azure) : lancer le runbook.
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
- [x] Serper configuré (clé ajoutée dans `.env` le 2026-07-23, 40 car., chargée OK ; le moteur préfère Serper, quota SerpAPI n'est plus le blocage du gros run)
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

## 2026-07-24 — Bilan santé + polish dashboard + fusion doublons (demande Betty)
- **Audit d'intégrité** (Vera) : 622 sociétés, 523 scorées, **0 faux zéro** (3 vrais zéros = 2 hôpitaux
  + Z-Systems), 0 incohérence éligibilité, signals sync. Zéros = 99 de mai (ancien univers) + 3 juillet.
- **Bug ville corrigé** : `--enrich-location`/`--enrich-revenue` étaient PERDUS entre `--submit` et
  `--fetch` (fetch recrée une cfg vierge) → 126/135 du batch sans ville. Fix : flags persistés dans le
  pending state + restaurés au fetch (`runner._run_submit`/`_run_fetch`). **Rattrapage fait** via
  `scripts/backfill_hq_city.py` (Perplexity, fail-open, sans re-score) : **219/220 villes remplies**,
  0 société sans localisation (582 avec « Ville, Pays »). 1 inconnue, qq approximations mineures.
- **Cockpit Sales rendu juste** : libellé codé en dur « CH + ES Lunch set » + « re-scored » → dynamique
  via `runComposition()` (« 135 new to Neotek » / « N new + M re-scored »). Bandeau explicatif corrigé.
- **Fusion 3 doublons** (`scripts/merge_duplicates.py`, sauvegarde `data/duplicates_backup_2026-07-24.json`,
  gitignored) : Glenmark Pharmaceuticals ← …Europe ; Julphar (Gulf…) ← Julphar ; Sesderma (Mediderma
  Group) ← Sesderma. Le gardé couvre déjà les dates du doublon → Recurring reste juste (Sesderma 2×).
  625 → 622. ⚠️ **RESTE une paire à trancher (Betty)** : « Mediderma (Sesderma Group) » vs « Sesderma
  (Mediderma Group) » — peut-être 2 marques réelles du même groupe, pas fusionnées.
- Commits : 4615474 (fallback/ville/comparaison/Recurring/libellés), 6c81c4c (fix flags batch + backfill),
  a8d112f (cockpit), 8559367 (fusion). 217 tests verts tout du long.
- ⚠️ RESTE (idées, non urgent) : page « How it works » (méthodo, pour démo) ; 16 résumés hors-format
  (5-6 phrases) à re-scorer ; 273 secteurs « Unknown » (trou CSV source) ; décision Mediderma/Sesderma.

## Run du 2026-07-23 — FAIT (2 batchs récupérés + importés)
- **Gros run (64) + reste-vendredi (71) récupérés & importés** → base **625**, **44 outreach-eligible**,
  ICP-flag 122, review 56, **4 runs** en historique (+ le re-score = 5e). Top nouveaux in-ICP : **CNX
  Therapeutics 9.0**, BCAL Diagnostics 8.5, VIP Dental 8.0, VERAXA Biotech 8.0. Lonza/Zühlke bien
  marqués HORS-ICP (gardent leur 8.0, sortis du ciblage). Comparaison vendredi↔gros run : 51 common /
  13 new / 71 only-Friday.
- **9 faux zéros re-scorés** (`--names … --live`, recherche en cache, run `1bb49f0acb8d`) → tous
  récupérés (EMD Serono 0→7.0 via le retry d'interprétation, Mubadala 7.5, FotoFinder 7.0, WBA 6.7,
  RadNet 6.3, Syngene 6.5, BD Biosciences 6.5, +Galapagos/TMRW). Plus aucun faux zéro des 9.
- **Nouvelle page « Recurring »** (`/recurring`, demande Betty « en commun ») : `templates/recurring.html`
  + endpoint `/api/intel/recurring` (regroupe run_snapshots par **date de run**, pas par batch id → les
  2 batchs du 23 comptent comme un scan). Montre les sociétés vues dans ≥2 scans avec une frise
  May 25 / Jul 17 / Jul 23 (score par scan, chip grisé si absente) + delta 1re→dernière + filtres
  All/3×+/In-ICP. Lien nav ajouté. **67 récurrentes** (toutes 2× May+Jul 17 pour l'instant ; le 3×
  se remplira au prochain re-score de sociétés connues). Vérifié live, 0 erreur.
- **Clarté des libellés Sales (demande Betty)** : `_serialize_company` expose `run_label` (date exacte
  du scan via `_date_label`). Page Sales : badge de ligne = **date précise** (« May 25 / Jul 17 / Jul 23 »,
  fini « refreshed Jul » ambigu) ; en-tête Δ = **« Δ vs May 25 »** (ou « Δ vs <run> » en mode comparaison) ;
  **filtre Run dynamique** (`runOptions`, options + compteurs générés depuis les données : All 625 / Jul 23 135 /
  Jul 17 67 / May 25 423), match par `run_label`. 217 tests verts, 0 erreur console.
- ⚠️ Cosmétique connu non corrigé : le cockpit du run affiche encore « CH + ES Lunch set » pour le run
  du 23 (label codé en dur dans `/api/intel/run`) — c'est en fait découverte + reste-vendredi, pas le lunch.

## Run du 2026-07-23 (soumission — historique)
- **Gros run SOUMIS** (batch `msgbatch_011gXNW…`, 64 sociétés, `engine_run_big.csv.pending.json`).
  Découverte 453 findings/8 thèmes → 64 candidats. **Comparaison vendredi(122) ↔ gros run(64)** :
  **51 common · 13 new · 71 only-Friday** (visible page Candidates). Corrigé en cours de route : le CLI
  charge bien .env (Serper vu par le moteur) mais `serp_quota_check`/`--estimate` lisaient os.environ
  AVANT le chargement → faux « no Serper backup » ; fix = lire via `EngineConfig.load().serper_api_key`
  (test_credits mis à jour : branche avec/sans Serper). Script forcé sur `.venv/bin/python`. 217 tests verts.
- **Petit batch « reste de vendredi »** (`scripts/run_friday_rest.sh` + `scripts/_friday_only_names.py`) :
  score les **71 « seulement vendredi »** (diff friday\big, pas de doublon avec les 51) → `engine_run_friday_rest.csv`,
  run DISTINCT. Demandé par Betty pour valider TOUTE la liste de vendredi. Non encore lancé au moment de l'écriture.
- ⏳ RESTE : `--fetch` des 2 batchs (≤24h) + `import_csv.py` chacun → Sales. Puis fusion vendredi↔gros run (futur).

## Dernière session
- Date : 2026-09-02 (3)
- Fait : **chantier 3/4 du recap réunion Nathalie : curation 70/30 Europe/monde livrée**
  (`app/tools/curation.py` + endpoint `GET /api/intel/weekly-review` + carte sur la page Sales,
  détail complet dans le log 2026-09-02 (3) en haut). Clarifié avec Betty : le 70/30 s'applique à
  la fois à la base scorée ET au futur tracker mouvements exécutifs (chantier 4) — le module est
  écrit générique pour être réutilisé là-bas ; la veille méga-caps (chantier 2) reste monde entier,
  sans split. Aucun plancher de score, carte simple sur Sales (pas de nouvelle page). +6 tests,
  **300 tests verts**. Vérifié API réelle (curl authentifié) + rendu HTML/JS ; pas de vérif
  navigateur visuelle (pas d'outil Chromium disponible).
- Prochaine étape : chantier 4 — tracker mouvements exécutifs (le plus gros ; réutilise
  `app/tools/curation.py` pour son 70/30 ; point RGPD à trancher avant tout run live — données de
  carrière de personnes nommées, hors du cadre `Contact` existant). Déjà conçu en détail (session
  `942839c7…` du 01/09, toujours sur disque).
- Date : 2026-09-02 (2)
- Fait : **chantier 2/4 du recap réunion Nathalie : veille "top 10-15 méga-caps" livrée**
  (`pipeline/recap.py` + flag CLI `--recap`, détail complet dans le log 2026-09-02 (2) en haut).
  Mode séparé qui s'arrête AVANT le scoring (jamais d'appel Opus), nouvelle table `MegaCapRecap`,
  citations verbatim uniquement (pas de synthèse IA), déclenchement CLI seul. +14 tests,
  **294 tests verts**. Vérifié : `--recap --estimate` tourne sans clé, `--recap` sans `--live`
  refuse proprement.
- Prochaine étape : chantier 3 — curation 70/30 Europe/monde, puis chantier 4 — tracker mouvements
  exécutifs (le plus gros, point RGPD à trancher avant le live). Les deux sont déjà conçus en détail
  (session `942839c7…` du 01/09, toujours sur disque).
- Date : 2026-09-02
- Fait : **chantier 1/4 du recap réunion Nathalie du 01/09 : plafond de revenu mega-cap (~$20 Mds)
  livré et testé** (détail complet dans le log 2026-09-02 en haut). `app/tools/icp.py` gagne
  `revenue_above_ceiling()`/`MEGA_CAP_REASON` ; la raison d'exclusion (`icp_flag_reason`) circule
  maintenant de bout en bout jusqu'au CSV (39 colonnes) et à l'API. Seuil configurable dans
  `scoring_config.yaml`, pas de backfill sur la base existante (décisions Betty). +9 tests,
  **280 tests verts**. Vérifié en dry-run. Les 3 chantiers suivants (veille méga-caps, curation
  70/30, tracker mouvements exécutifs) sont déjà conçus en détail (session `942839c7…` du 01/09,
  toujours sur disque) et restent à valider un par un avant de coder, dans cet ordre.
- Date : 2026-08-13 (2)
- Fait : **9e source Hugo — scan social/vidéo via agent-reach (voir log détaillé en haut).**
  `pipeline/social_research.py` (Twitter/Reddit/LinkedIn jobs/Instagram/YouTube, opt-in
  `--social-scan`), câblé dans `research.gather()`, testé en LIVE sur Cantabria Labs, bug de
  matching Instagram trouvé+corrigé en cours de route, hugo.md re-formé + re-seedé. +14 tests,
  **271 verts**. Nettoyage disque (89 Mo→40 Go libres). Pas encore commité.
- Date : 2026-08-13 (1)
- Fait : **maintenance repo + mémoire (demande Betty « mets tout à jour » avant de basculer sur Claude
  terminal).** (1) VÉRIFIÉ : le travail du 08-10 est **bien commité** — Julie (`efe0d0d`), démo marketing
  How-it-works (`07e0565`), fix routage Hugo/Alex (`2c3a244`) sont tous dans l'historique ⇒ la note
  « Julie pas encore commité » ci-dessous était PÉRIMÉE (corrigée). (2) Rangement : 8 vieux fichiers
  racine (AGENTS.md, INSTRUCTIONS.md, 2 xlsx coûts, RECAP_DASHBOARD.md, build_masters_v2.py, build_static.py,
  mockup_office.html) déplacés dans `_archive/` — obsolètes, remplacés par le système `.claude/` + le repo
  courant ; committé (chore). (3) Push `feat/neotek-engine` → origin pour que le terminal / une autre machine
  ait la dernière mémoire. RAPPEL mémoire : `claude` lancé depuis la racine du repo recharge CLAUDE.md +
  les 6 imports `.claude/*.md` automatiquement — la mémoire voyage avec le dossier commité.
- Date : 2026-08-10
- Fait : **grosse session « câbler chaque agent sur la vraie donnée » — 5 agents améliorés + 5 commits (TOUS commités).**
  (1) **Inès** — brief scraper exploitable (tie-back §3c, Med-Affairs séparé, config Sales Nav) +
  classifieur ES/FR durci [commit 71ac97d]. (2) **Maya** REFONDUE — scoreur vs analyste de portefeuille,
  `/summary` flagship, `/top`+`/recurring` dépréciés [3214b7b]. (3) **Moteur marketing câblé** —
  colonne vertébrale campagne partagée `campaign_themes.py`, Iris→Marc [e0d057c] puis Marc→Oliver
  (Oliver formate le vrai contenu de Marc) [dcf2027]. (4) **Julie** câblée sur la vraie donnée — `/draft`
  ancre l'Intelligence Summary, `/linkedin` devient société-aware [commit efe0d0d]. Voir logs (1)-(5) en haut.
  **255 tests verts.** ⚠️ Le drawer chat headless était intermittent aujourd'hui → vérifs surtout
  déterministes ; chemin chat→LLM confirmé live tôt dans la session (Inès `/contacts`, Maya `/summary`).
  ⚠️ Serveur preview sans `--reload` → redémarrer pour charger un changement de code.
  RESTE : les 8 agents de chat sont maintenant tous câblés sur la donnée réelle — la
  suite du travail est du CONTENU (chiffres clients Andrés, prompt messaging Nathalie, contacts Apollo/Kaspr),
  plus du câblage. Idées : passe qualité live quand le navigateur coopère.
- Date : 2026-08-03
- Fait : **passe qualité données** (Betty « comment améliorer la plateforme » → axe #4 choisi). Audit
  Vera réel d'abord (notes périmées : Unknown 273→5, 0 doublon, 0 loc manquante, poubelle déjà nettoyée).
  Actions réversibles à backup : 4 secteurs classifiés (Unknown 5→1, Shealed gardée exprès), fusion
  Mediderma/Sesderma en « Mediderma / Sesderma » (base 621→620). Les 16 résumés « hors-format » =
  faux défaut (excellents, non touchés). Détail : log 2026-08-03 en haut. Aucun code app, aucun commit.
  Scripts : `scripts/fix_unknown_sectors.py`, `scripts/merge_mediderma.py`. RESTE (idées, non urgent) :
  enrichir Shealed au prochain run ; les 16 résumés se normalisent au re-score ; axes plateforme non
  encore faits = hébergement permanent (#2) + boucle terrain export/outcome (#1) + run mensuel (#3).
- Date : 2026-07-27
- Fait : **refonte Sales (frise de comparaison de runs + double colonne Δ), Recurring en matrice,
  Candidats rendus honnêtes, export CSV run complet (53 col.), garde-fou anti-fuite découverte**
  (voir log 2026-07-27 en haut). Commits 9311331 + 0812e78 sur `feat/neotek-engine`, 218 tests verts,
  0 erreur console (vérifié live sur :8000). Points clarifiés à Betty : les 135 du 23/07 sont 100 %
  nouvelles (d'où « new » dans les Δ, pas un bug) ; rien perdu (122 vendredi + 13 = 135, toutes scorées).
  RESTE (idées, non urgent) : (a) pousser sur le remote GitHub ; (b) l'archivage auto de découverte
  s'activera au prochain `--discover` Terminal ; (c) éventuel « merge » vendredi↔gros run une fois voulu.
- Date : 2026-07-22
- Fait (fin de session) : **ICP « Market Intel July 2026 » formalisé + répercuté** (voir log 2026-07-22
  en haut). 5 docs analysés → `app/tools/icp.py` (découverte large + ICP filtre de ciblage ; exclut
  conseil/CDMO/CRO/<100M€, garde les privées à CA inconnu) + câblé runner + recompute base (17 hors-ICP,
  dont Zühlke/Lonza) ; prompts hugo/ines/julie/maya/iris re-formés ; mémoire (CLAUDE.md, operational-
  context.md §22/07, brand-editorial.md §8). ⚠️ RESTE : re-seed + pytest + notes Obsidian + commit
  (machine saturée par un scan OneDrive en fin de session — à finir dès que la charge retombe).
- Fait (début de session) : **partage clé-en-main + login porte d'entrée + clarté du run** (voir log 2026-07-22 en haut).
  `share.sh` + double-clic `Partager TPDL.command` (Cloudflare tunnel gratuit, lien copié auto ; robuste
  bash 3.2) → lien public protégé par mot de passe équipe **TPDL**. Gate resserré : login = porte d'entrée
  (toute page exige la connexion ; page login standalone). Cockpit : 4 bandes → 67 (+ review-flagged 36 sorti
  comme transversal). Δ « vintage-aware » : non re-scorée = **« — »**, colonne **« Δ since May »**, badges
  **refreshed Jul / May run**. Filtre **Run** (All 490 / Refreshed 67 / May 423) = isole les 67 de vendredi.
  Décisions Betty : défaut 490 ; Compare runs gardé. 49 smoke verts, 0 erreur console. RESTE : (a) bouton
  Déconnexion plus visible (demandé) ; (b) déploiement payant Azure/Render quand outil quotidien.
- Fait (session du 2026-07-21) : **filtres Sales (localisation, comparaison de runs, Top-N + rang) + fiche société (delta + courbe
  toujours tracée) + utilisateurs réels + prépa déploiement Azure** (voir log 2026-07-21 en haut). Filtre
  localisation via `geo_region()` ; frise « compare runs » From→To (delta recalculé, s'étend seule dès un 3e
  run) ; Top-N + colonne `#`. Fiche société : delta toujours affiché, courbe tracée dès 1 point. Users →
  **Andrés, Paula, Nathalie, Betty** (code équipe **TPDL**, mêmes droits, purge des anciens). Déploiement :
  `Dockerfile` + `.dockerignore` + `azure-deploy-runbook.md` (Azure App Service + Postgres, mot de passe
  équipe). Commande prod gunicorn validée en local. **210 tests verts**, 0 erreur console. RESTE : Betty/Alfredo
  lancent le runbook Azure avec le compte Azure de TPDL ; (optionnel) tester le build image sur une machine
  avec Docker ; SSO Microsoft plus tard.
- Fait (session du 2026-07-20) : **refonte UI traçabilité du run + page Découvertes + audit pré-démo** (voir log 2026-07-20 en
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
