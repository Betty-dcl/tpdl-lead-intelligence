# État courant — journal de bord vivant

> C'est LE fichier qui bouge le plus. Après chaque session, mettre à jour « Dernière session »
> et la checklist des blocages. Claude Code doit PROPOSER de le faire.

> 📘 **Mise en production** : chemin clé-en-main ordonné dans `.claude/go-live-runbook.md`
> (quelle clé débloque quoi, commandes exactes, garde-fous, gate RGPD). Chargé à la demande.

## Où on en est
- Phase : **Step 3 (workflow) largement FAIT en code** — le moteur Neotek est reconstruit dans
  `pipeline/` (dry-run 0 coût + `--live` gated, 112 tests verts). Step 2 (formation) terminé côté
  prompts (9 agents avec Vera). Reste bloqué par l'externe : clés API pour un run LIVE + chat live.
- Base + mémoire : posées et rapatriées dans le repo.
- Dernier run Neotek : 25/05 (492 entreprises, 35 éligibles) — FIGÉ. Amorcé comme run #1 dans
  `RunSnapshot` ; `/recurring` s'active au 2e import réel.

## Décisions prises (log — ajouter en haut, avec la date)
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
- [ ] #1 Clé Anthropic réelle dans `.env` (placeholder actuellement)
- [x] #1b IDs de modèles fixés : Sonnet 5 (extraction) + Opus 4.8 (interprétation/chat)
- [ ] #2 Clé Exa
- [ ] #3 Clé Perplexity
- [x] #4 Brand DNA : angles sectoriels peuplés (`app/tools/sectors.py`, positionnement réel
      anonymisé). Reste : les CHIFFRES/résultats clients précis d'Andrés pour durcir les proof points.
- [~] #5 Kaspr : connecteur CODÉ + gated (`app/tools/kaspr.py`, préféré par Inès). Reste : `KASPR_API_KEY`.
- [ ] #6 Token Apify (bonus)
- [x] #7 Reconstruction du moteur pipeline (`pipeline/`, dry-run + live gated, 112 tests). Reste :
      lancer un run LIVE réel (dépend des clés API), pas le code.
- [x] #7c Historique des runs (`RunSnapshot`) + `backfill_snapshots.py` → run 25/05 amorcé (run #1).
      `/recurring` s'active au 2e import. Reste : un 2e CSV réel à importer.
- [x] #7b Modèle `Contact` étendu (function / seniority / crm_segment) + `app/tools/segmentation.py`
      + migration additive SQLite dans `init_db` + tests (44 passent). Reste : Apollo pour peupler.
- [ ] Serper configuré (← SerpAPI + DuckDuckGo)
- [ ] Firecrawl configuré
- [~] Bouncer : connecteur CODÉ + gated (`app/tools/bouncer.py`, fail-closed). Reste : `BOUNCER_API_KEY`.
- [~] Lemlist : connecteur CODÉ + gated (`app/tools/lemlist.py`, sortant/humain). Reste : `LEMLIST_API_KEY`.
- [ ] n8n (mutualisation Devengo demandée à Andrés ?)
- [x] Repo Git initialisé (local). Reste : remote partagé avec Andrés + `main` protégée.
- [x] Renderers PDF/PPTX Oliver connectés (PDF fpdf2 + PPTX python-pptx + endpoints export)

## Calendrier (source transcript 25.06 — à re-confirmer)
- Crash test initial : mi-juillet. Semaine du 20 juillet : analyse des 1ers résultats.
- Amélioration continue jusqu'en août ; points le mardi après-midi.

## Questions ouvertes / à confirmer
- ~~Agent de vérification (9e agent)~~ → TRANCHÉ (2026-07-14) : OUI = Vera (QA + file de revue).
- Segmentation CRM (Segment 1/2/3) : propriétaire = Inès (contacts) ou Maya (analyse) ?
- Plateformes Lucia / Gaspers : à comparer aux outils actuels ?
- Moteur pipeline : le reconstruire dans ce repo, ou obtenir l'accès Neotek ? (bloque Step 3)
- Prix réels des outils (Firecrawl, Kaspr, Bouncer, Lemlist) avant souscription (Step 1).
- Cible de taux de réponse Lunch Campaign (à fixer avec Andrés).
- Base légale RGPD pour l'enrichissement + envoi (UE/CH) avant le 1er envoi.

## Dernière session
- Date : 2026-07-15
- Fait : (1) recalé la mémoire (CLAUDE.md + state.md + prompts Hugo/Maya/manager) qui affirmait
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
