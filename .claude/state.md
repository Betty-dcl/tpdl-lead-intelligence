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
- [x] Repo Git initialisé (local). Reste : remote partagé avec Andrés + `main` protégée.
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
- Date : 2026-07-17
- Fait : **analyse + rangement de la réunion pilote du 16/07** (Betty & Nathalie). Transcript Word
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
