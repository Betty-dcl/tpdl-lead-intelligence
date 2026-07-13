# État courant — journal de bord vivant

> C'est LE fichier qui bouge le plus. Après chaque session, mettre à jour « Dernière session »
> et la checklist des blocages. Claude Code doit PROPOSER de le faire.

## Où on en est
- Phase : Step 2 (formation) **TERMINÉ côté prompts** — les 8 agents formés (Alex + Sales + Marketing),
  versionnés dans `app/agents/prompts/`. Reste : validation en chat live (bloquée par la clé API).
- Base + mémoire : posées et rapatriées dans le repo.
- Dernier run Neotek : 25/05 (492 entreprises, 35 éligibles) — FIGÉ (moteur Neotek inaccessible).

## Décisions prises (log — ajouter en haut, avec la date)
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
  = Andrés. 7 secteurs réels (placeholders jusqu'au Brand DNA). Versionnée `app/agents/prompts/julie.md`.
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
- [ ] #4 Brand DNA : clients rempli
- [ ] #4 Brand DNA : projects rempli
- [ ] #5 Kaspr connecté (remplace Apollo)
- [ ] #6 Token Apify (bonus)
- [ ] #7 Accès / reconstruction du moteur pipeline (bloque le 2e run et /recurring)
- [x] #7b Modèle `Contact` étendu (function / seniority / crm_segment) + `app/tools/segmentation.py`
      + migration additive SQLite dans `init_db` + tests (44 passent). Reste : Apollo pour peupler.
- [ ] Serper configuré (← SerpAPI + DuckDuckGo)
- [ ] Firecrawl configuré
- [ ] Bouncer (au 1er envoi)
- [ ] Lemlist (séquence Lunch)
- [ ] n8n (mutualisation Devengo demandée à Andrés ?)
- [ ] Repo Git initialisé + partagé avec Andrés
- [x] Renderers PDF/PPTX Oliver connectés (PDF fpdf2 + PPTX python-pptx + endpoints export)

## Calendrier (source transcript 25.06 — à re-confirmer)
- Crash test initial : mi-juillet. Semaine du 20 juillet : analyse des 1ers résultats.
- Amélioration continue jusqu'en août ; points le mardi après-midi.

## Questions ouvertes / à confirmer
- Agent de vérification (9e agent) : l'ajoute-t-on au roster ? (idée du transcript 25.06)
- Segmentation CRM (Segment 1/2/3) : propriétaire = Inès (contacts) ou Maya (analyse) ?
- Plateformes Lucia / Gaspers : à comparer aux outils actuels ?
- Moteur pipeline : le reconstruire dans ce repo, ou obtenir l'accès Neotek ? (bloque Step 3)
- Prix réels des outils (Firecrawl, Kaspr, Bouncer, Lemlist) avant souscription (Step 1).
- Cible de taux de réponse Lunch Campaign (à fixer avec Andrés).
- Base légale RGPD pour l'enrichissement + envoi (UE/CH) avant le 1er envoi.

## Dernière session
- Date : 2026-07-12
- Fait : Step 1 — liste des abonnements Neotek + Firecrawl (2 fichiers Excel : `Neotek_stack_costs.xlsx`,
  `Neotek_free_vs_paid.xlsx`) ; clarifié free tier vs coût réel. Intégré les 2 transcripts terrain
  dans `.claude/operational-context.md` (+ maj CLAUDE.md, state.md). Découverte structurelle :
  les prompts des 8 agents vivent dans `seed.py` (→ DB), pas dans `app/agents/*.py`.
- Prochaine étape : débloquer l'externe (rien d'autre ne peut avancer sans toi/Andrés) —
  (1) clé Anthropic réelle dans `.env` → tester les 4 agents en chat live ; (2) clé Apollo → peupler
  les contacts + segmentation ; (3) Brand DNA (clients/projects) avec Andrés → définir les angles
  sectoriels de Julie ; (4) trancher le moteur Neotek (reconstruire vs accès). Puis : git init + 1er
  commit (base + mémoire + 4 agents Sales), et éventuellement former le marketing.
