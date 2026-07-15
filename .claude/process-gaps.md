# Liste maîtresse — toutes les failles, trous et risques du process

> Audit adversarial du 2026-07-14 (le plus exigeant). Tout ce qui manque, tout ce qui
> peut casser, tout ce qui reste à décider. Sévérité : 🔴 bloquant · 🟠 câblage · 🟡 contenu
> vide · ⚪ risque/qualité · ⚖️ légal · 💰 coût · 🔧 prod/sécu.

## A. Fondation de données
1. 🔴 Données **figées au 25/05** (7 semaines) — un « nouveau CEO » peut être une vieille nouvelle. Agir sur un signal périmé = outreach gênant.
2. 🟠 **Un seul run** → pas de tendance, pas de `/recurring`, pas de delta de fraîcheur.
3. 🟡 **361/492 secteurs = « Unknown »** → segmentation sectorielle aveugle sur ~73 %.
4. ⚪ **212/492 hors-cible (ICP-flag)** → seulement ~280 réellement dans le périmètre.
5. ⚪ Seulement **35 éligibles** → set actionnable minuscule, et probablement déjà contactés / périmés.
6. 🔴 **Aucune dédup contre PipeDrive** → risque de contacter à froid des relations existantes.
7. ⚪ On a le CSV Neotek mais **pas les blocs d'évidence** (`evidence_blocks.json`) → impossible d'auditer d'où vient chaque score ; les review flags ne sont pas re-vérifiés.

## B. Le moteur (je suis dur avec mon propre code)
8. 🔴 **Jamais tourné en live** → qualité extraction (Sonnet) / interprétation (Opus) **inconnue**.
9. ⚪ Le **verrou verbatim vérifie que la phrase existe, PAS que la catégorie/le sens sont justes** — un modèle peut citer une vraie phrase mais mal la classer, ou ignorer une négation (« ne va PAS nommer »). QA structurelle, pas sémantique.
10. ⚪ `date_in_text` peut attraper **la mauvaise date** d'une phrase (« depuis 2019 … nommé en juin ») → recency faussée.
11. ⚪ Ma **corroboration par domaine** diverge du comptage par source de Neotek → parité non prouvée.
12. ⚪ Le **dry-run donne des scores factices** (mock) → ne prouve que la plomberie, jamais la qualité.
13. 🟠 **Batch API (Step 5) non implémenté** → run en volume à coût ×2 + risque de troncature (Neotek en a eu 13).
14. ⚪ Le **slug de l'actor Apify** (`apify~wappalyzer`) est une supposition → 1er scan live peut faire 404.
15. ⚪ Pas de **garde-fou quota à l'exécution** → un run peut épuiser les 250 SerpAPI en cours de route et ne remplir qu'à moitié.
16. 🟠 **Pas de reprise sur panne** — si un run meurt à 60/125, pas de resume ; risque de re-dépenser.
17. ⚪ Schémas de réponse Exa/Perplexity **supposés** — si l'API change, résultats vides silencieux (une société scorée 0 peut être un **bug de parsing**, pas une absence de signal).
18. 🟠 **Source « registres UE » non implémentée** (Neotek l'utilisait, 32/492).
19. ⚪ **Aucune gestion multilingue** — actus FR/DE/ES ; prompt d'extraction anglocentré → citations non-anglaises mal classées.

## C. Câblage entre agents
20. 🔴 **Apollo est un stub vide** → Inès ne tire **aucun** contact réel. Moitié « contacts→messages » morte.
21. 🟠 **`/recurring` de Maya impossible même à 2 runs** : `import_csv.py` **écrase** les lignes → aucun historique conservé.
22. 🟠 **Julie ne lit pas la table `Contact`** → nom, rôle, langue ES, séniorité, segment CRM d'Inès **perdus** dans l'email.
23. 🟠 **Ciblage signal→rôle seulement dans le prompt d'Inès**, pas dans le code de fetch (liste figée CEO/CTO/CFO).
24. 🟠 **Le moteur est un CLI non relié au dashboard** — boucle run→import→agents **manuelle** (2 commandes).
25. 🟠 **Aucun agent ne peut DÉCLENCHER le moteur** — Hugo « possède » les steps 0-6 sur le papier, sans chemin de code pour lancer un run.

## D. Pipeline marketing
26. 🟠 **Iris tourne sur DuckDuckGo** (qualité basse, lib dépréciée `ddgs`) ; cible Serper non branchée.
27. ⚪ Marc marque `[STAT TO VERIFY]` mais **aucune étape de vérification** n'existe → stats non vérifiées peuvent partir.
28. 🟡 **Newsletter (pondération 70/10/20) notée mais PAS un format supporté** par Oliver.
29. 🔴 **Le marketing n'a aucun accès à l'audience CRM** → les « 70 % audience CRM existante » sont impossibles (pas de données CRM dans l'app).
30. 🟡 **Brand DNA clients/projets vide** → Marc/Oliver sans preuve sociale réelle.

## E. Opérations d'outreach (le monde réel)
31. 🔴 **AUCUNE intégration réelle** : PipeDrive, Surf, MailChimp, Sales Nav, Bouncer, Lemlist, Kaspr, n8n **absents du code**. Le dashboard produit des brouillons ; l'envoi est **manuel (SDR en Inde)**. Copier-coller manuel entre les deux mondes.
32. 🔴 **Aucune boucle de feedback** : réponses/conversions du terrain ne reviennent jamais nourrir le scoring (la « boucle d'amélioration » de la roadmap n'est pas construite).
33. ⚪ **Limites LinkedIn** (~200 connexions/sem, ~30 % acceptées) non modélisées → le process ne peut pas se cadencer.
34. ⚪ **Contradiction stratégique** : les transcripts disent « le cold outreach est mort », mais `/draft` écrit… des emails à froid.

## F. Sécurité / production / ops
35. 🔧 **Mot de passe par défaut « tpdl »** si `TPDL_TEAM_PASSWORD` non défini → faible si déployé.
36. 🔧 **Aucun déploiement** : tourne en local sur le Mac de Betty (`localhost:8000`). Andrés/l'équipe **n'y ont pas accès**.
37. 🔧 **SQLite mono-fichier** → pas de multi-utilisateur concurrent, pas de sauvegarde auto.
38. 🔧 **Secrets dans `.env` sur une seule machine** — pas de gestion de secrets, clés partagées à la main.
39. 🔧 **Git sans remote** → le code n'existe **que sur le disque de Betty**. Point de défaillance unique.
40. 🔧 **Aucun monitoring** — serveur lancé via `nohup` ; s'il crashe, silence.
41. 🔧 **Avatars DiceBear = dépendance externe non épinglée**.

## G. Coût / échelle
42. 💰 **5 $ de crédits Anthropic** → run complet impossible ; même tester le chat les grignote.
43. 💰 **SerpAPI free = 250/mois ≈ 125 sociétés** → run 492 impossible sans payer.
44. 💰 **Pas de coupe-circuit budget** en cours de run (juste l'estimation pré-vol).
45. 💰 **Batch API non branché** → coût modèle ×2.

## H. Qualité / tests / validation
46. ⚪ Tests **unit/dry-run uniquement** — **zéro test d'intégration** contre les vraies API.
47. ⚪ **Aucune étape de QA humaine** sur les évidences extraites avant scoring.
48. ⚪ **Pas d'agent de vérification** (la 9e idée des transcripts) — qualité non contrôlée à chaque étape.
49. ⚪ **Parité vs Neotek non mesurée** (harnais prêt, jamais exécuté en live).

## I. Légal / contractuel
50. ⚖️ **RGPD** : aucune base légale, aucun opt-out, aucune politique de rétention avant d'enrichir/contacter des personnes UE/CH. **Risque réel.**
51. ⚖️ Données Neotek marquées **« Confidential »** → réutilisation/redistribution à cadrer contractuellement.

## J. Process / conceptuel
52. 🔴 **Le trou de fond** : c'est un **cockpit qui lit des scores + rédige**, PAS une machine d'outreach de bout en bout. Les deux moitiés (intelligence ↔ envoi réel) ne sont **pas connectées**.
53. ⚪ **Aucune définition de « réussi »** câblée (objectif de taux de réponse non fixé).
54. ⚪ **Dépendances humaines** : Brand DNA, angles sectoriels, Premium 5, budget, décision moteur — le process ne peut pas être « fini » sans plusieurs inputs d'Andrés.

---

## ✅ Corrigés le 2026-07-15 (2e audit adversarial du code — 0 dépense)
> Audit de tout le code (moteur + app) par 2 passes parallèles, chaque finding vérifié à la main.
> 11 vrais bugs corrigés + 12 tests de régression. Suite : **135 verts**. Tout mergé dans `main`.
- **Moteur `score.py`** : (1) `json.loads` de l'interprétation Opus non gardé → un JSON malformé
  crashait la société ET **jetait tout le batch payant** ; désormais try/except (comme `extract`).
  (2) **double-comptage** : 2 signaux de même catégorie gonflaient `assessed_score` (coverage
  dédupliquait déjà) → dédup. (3) `signal_strength` non-entier (« high »/null) → coercition sûre.
  (4) **corroboration** : tout item sans URL (Exa/Serper au lieu de Perplexity seul) bumpait à 2 →
  restreint à Perplexity.
- **Moteur `research.py`** : `_parse_date` n'acceptait que l'ISO → **toutes les dates SERP
  (MM/DD/YYYY + « 3 days ago ») tombaient à None** = recency 0 silencieuse. Ajouté.
- **Moteur `extract.py`** : (1) le QA verbatim acceptait via `all_text` → une citation mal
  attribuée passait (gonflait la corroboration) ; désormais check sur la source déclarée +
  flag SOURCE MISMATCH. (2) `corpus = {d.source: …}` **écrasait** les docs de même source
  (2 `serper_news` → 1 seul) → concaténation. (3) `has_negation` : « cannot » déclenchait
  « not », « Mayer » déclenchait « may » → frontières de mot.
- **Moteur `runner.py`** : `--max-usd 0` (= ne rien dépenser) **désactivait** le coupe-circuit
  (0.0 falsy) au lieu de bloquer → `is not None`.
- **App `import_csv.py`** : `run_id` dérivé du **hash du contenu** → réimporter le MÊME CSV est
  idempotent (plus de fausse récurrence pour Maya `/recurring`) ; un run différent crée bien un
  2e run. Vérifié en DB temporaire (2 sens).
- **App `maya.py`** : `/top5` (collé) tombait sur le défaut 50 → résout N=5.
- **App `intel.py`** : bandes de score non contiguës (trous 0<x<1, 4.999<x<5, 7.999<x<8) →
  contiguës, plus aucune société perdue du graphe.
- **App `ines.py`** : `/premium add` sur un déjà-Premium recomptait « +1 » à tort + match par
  sous-chaîne prenait le mauvais homonyme → court-circuit + désambiguïsation.
- Docstrings : Julie `/linkedin`, Vera `/qa` documentés ; note « placeholder » de Julie corrigée.
- **Ménage : 3 mocks morts supprimés** (`app/mocks/intel.py`, `marketing_intel.py`, `companies.py`,
  ~1216 lignes) après vérif exhaustive (aucun import statique/dynamique, template, JS, ni test).
- **Trous de test comblés** : coupe-circuit budget séquentiel, échappement CSV, `review_flag`,
  parsing Serper News / Perplexity (« none found » + hit sans URL) / Firecrawl (markdown vide).
- **Derniers items des audits fermés** : docstring `runner` honnête sur la crash-safety (séquentiel
  OK / batch écrit une fois) ; `flag_boilerplate` compte désormais les lignes préservées au
  `--resume` (boilerplate franchissant la frontière de reprise) + test. **Les 2 audits sont
  entièrement traités.** Total suite : **143 verts**.

## ✅ Corrigés le 2026-07-14 (lot gratuit, 0 dépense)
- **#4** QA sémantique : détecteur de négation/spéculation (`extract.has_negation`) → citations
  « reportedly/considering/no longer… » **flaggées pour revue** ; prompt Opus renforcé (cap
  strength ≤2 sur du spéculatif).
- **#5** dates : garde-fous (rejet futur / >5 ans) + on garde la **date plausible la plus récente**.
- **#6/#18 (registres UE) — GRATUIT & fait** : la doc Neotek confirme qu'ils n'avaient AUCUNE
  API de registre payante ; leur source était web-publique. Donc `eu_registry` refaite en
  **gratuit** : recherche sur les **portails publics** (e-Justice/BRIS, OpenCorporates, Companies
  House…) via le SERP engine déjà payé (SerpAPI/Serper), filtrée aux domaines de registre. Opt-in
  (`EU_REGISTRY_ENABLED=1`) pour ne pas manger le quota. (Firecrawl était déjà là.)
- **#8** Batch API : `pipeline/batch.py` (scoring -50 %) + option `--batch`.
- **#10** garde-fou quota : le run **refuse de démarrer** si le quota SerpAPI est insuffisant (`--force` pour outrepasser).
- **#11** reprise sur panne : CSV réécrit après chaque société + option `--resume`.
- **#12** canari anti-bug : log quand une source live renvoie 0 (bug de parsing potentiel).
- **#16** historique de runs : table `run_snapshots` (append-only) → **Maya `/recurring` marche
  vraiment** (compare les scores entre runs, RISING/FADING).
- **#17** Julie lit les contacts d'Inès : `/draft` s'adresse à **la personne** (nom, rôle,
  langue ES, séniorité, segment).
- **#18** ciblage signal→rôle **dans le code** (`apollo.titles_for_signal`) — prêt pour Apollo.
- **#29** `/draft` réorienté : **fini le cold pitch** — note courte, humaine, sans CTA agressif.
- **#35** mot de passe : défaut passé à `TPDL` (à changer avant tout partage — warning au boot).
- **#41** DiceBear : avatar de secours local (`static/img/avatar-fallback.svg`) + handler global
  dans base.html → si DiceBear tombe, pas d'image cassée. **Vérifié en navigateur.**
- **#48 Agent Vera (9e) — FAIT** : agent transversal de QA. `app/agents/vera.py` (+ prompt
  `vera.md`, enregistré, semé, dans le roster = 9 agents). Commandes `/review` (file),
  `/audit [société]` (verdict CLEAR/NEEDS REVIEW), `/stats`. Checks déterministes traçables
  (source absente, haute confiance sans URL, spéculation/négation, boilerplate). Logué dans
  activity_log comme les autres.
- **#20 Apollo — code réel écrit (verrouillé)** : `apollo.fetch_contacts` fait le vrai appel
  `mixed_people/search` (titres pilotés par le signal), dégrade proprement sur erreur. Ne tourne
  qu'avec `APOLLO_API_KEY` dans `.env` → **plug-and-play dès la clé**.
- **#44 Coupe-circuit budget — FAIT** : `--max-usd` stoppe un run avant de dépasser le plafond
  (séquentiel : stop avant la société de trop ; batch : rogne la liste en amont). Live only.
- **#47 Page de revue humaine — FAITE** : `/review` (nav « Review ») — file des sociétés
  flaggées, raison, signaux + « ⚠ no source URL », boutons **Approve/Reject** + note. API
  `GET /api/review` + `POST /api/review/{société}`. Colonnes `review_status/reviewed_at/
  reviewed_note` (migration additive). **Round-trip vérifié en navigateur** (approve → sort de
  la file). 108 tests.
> Tests : **99 verts** (moteur + câblage agents). Reste live-dépendant : #9 (slug Apify à
> confirmer), #2/#3/#8-qualité, #49 (parité) → tout ça se lève au **cran 1**.

## 🗂️ BACKLOG « à me redemander » (validé par Betty, à faire plus tard)
1. ✅ **Registres UE** — FAIT en gratuit (voir « Corrigés »). Reste juste à activer avec
   `EU_REGISTRY_ENABLED=1` au moment voulu (faible valeur : 32/492, sociétés privées).
2. **Dédup PipeDrive** (#6 data) : import CSV PipeDrive → Inès marque « déjà dans le CRM ».
3. **Apollo/Kaspr live** (#20) : câbler le vrai fetch quand la clé arrive (+ ciblage signal→rôle déjà prêt).
4. **Confirmer le slug Apify** (#9) : au 1er scan live, mettre le bon identifiant d'actor.
5. **Intégrations terrain** (#31) : exports propres vers PipeDrive/Lemlist/Bouncer, puis n8n.
6. **Boucle de feedback** (#32) : réponses/conversions → Maya + scoring_config.
7. **Contenu à obtenir d'Andrés/Betty** (#25 + #29 — débloque Julie/Marc, ~30-45 min) :
   - **3 à 6 cas clients réels** (même anonymisés) : secteur · le problème · ce que TPDL a fait · **le résultat chiffré**.
   - **2 à 4 projets phares**.
   - **Positionnement par secteur** (pharma / medtech / dental / diagnostics / dermatology / surgery / healthcare) : pourquoi ils devraient écouter + quelle preuve.
   - **3 à 5 exemples de messages gagnants d'Andrés** (le ton/voix qui a VRAIMENT généré des réponses) — pour calibrer `/draft` et Julie.
   - **UVP / propositions de valeur** cœur de TPDL.
   - **KPI de succès** (objectif de taux de réponse, nb de rdv…) + **base légale RGPD** avant envoi.
8. **Déploiement** (#36) : héberger pour qu'Andrés accède (Railway + Postgres/Supabase).
9. **Bouton « Lancer le pipeline » / commande `/rerun` de Hugo** (#19+#20) : déclencher le
   moteur depuis l'UI en tâche de fond + import auto. APRÈS validation du moteur (cran 1).
10. **Remote git** (#39) : Betty crée un dépôt **GitHub privé** → je branche le remote + push
    (je ne peux pas créer de compte). En attendant : bundle de sauvegarde local fait.
11. **Prod / hébergement** (bloc #36-38, #40) : déploiement Railway + Postgres/Supabase (déjà
    préparé) + gestion des secrets + monitoring. Seulement quand ça devient multi-utilisateur /
    accessible à Andrés — pas pour construire en local. (Mon avis : pas utile maintenant.)
12. **Agent Vera (9e, vérification)** (#48) : QA transversale après chaque étape (évidences
    verbatim+datées, contacts non inventés, messages ancrés sur un vrai signal). Trace dans
    `activity_log` + page de revue (#47). Démarre en contrôles auto (déjà en partie codés),
    promu en agent ensuite.
13. **Page de revue humaine** (#47) : file des sociétés review-flaggées à valider avant d'agir.
> Le contenu à obtenir d'Andrés (§7) + les KPI (#53) sont consolidés dans
> `.claude/andres-session.md` (checklist unique, traçable). Betty peut demander
> « donne-moi la liste du backlog » à tout moment.

## Décisions prises (2026-07-14, avec Betty)
- **Dédup PipeDrive (#6 data)** : à faire PLUS TARD. Principe retenu : import CSV PipeDrive →
  Inès marque « déjà dans le CRM » (= Segment 1, jamais approché à froid).
- **Multilingue** : abandonné — **anglais uniquement**.
- **Marketing (Iris/Marc/Oliver, newsletter, audience CRM)** : reporté (équipe marketing plus tard).
- **Apollo** : à connecter (clé à venir). Ciblage signal→rôle à coder au même moment.
- **Sécu/prod** : plus tard, SAUF remote git + mot de passe → à faire tôt.

**Lecture rapide** : 🔴 bloquants = #1, 6, 8, 20, 29, 31, 32, 52. Le cerveau (scoring/prompts)
est prêt ; la chaîne humaine (contacts→message→envoi) et la connexion au terrain sont les
gros manques. À ne PAS lancer en campagne complète. Lançable : le **cran 1 du moteur** (1
société), qui lève les inconnues #8/#12/#49.
