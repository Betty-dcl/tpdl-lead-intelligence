# Agents — kit de formation détaillé

Chargé à la demande. Pour chaque agent : (a) prompt système, (b) mémoire/playbook à remplir,
(c) part du process + outils.
> Rappel : les agents de chat de CE repo tournent sur **Opus 4.8** et LISENT une base déjà scorée.
> Le moteur d'extraction/scoring (Sonnet 5 / Opus 4.8) est à reconstruire (moteur Neotek inaccessible).
> Le Step 2 de la roadmap = écrire ces prompts détaillés + définir le contenu de résultat attendu.

## HUGO — Deep Research / détection (le moteur)
(a) Prompt : encoder le pipeline 6-étapes, la séparation extraction (Sonnet 5) / interprétation
    (Opus 4.8), les 8 sources, les 6 signaux + exclusions, la formule de scoring, les 7 règles
    dures. Interdire l'interprétation en Step 3 et l'accès au brut en Step 4.
(b) Mémoire : `app/config.py` (modèle), `scoring_config.yaml`, requêtes types Q1/Q2/Q3.
(c) Possède Steps 0-6 (cible). Aujourd'hui : LIT seulement la table `companies`. Outils cible :
    Exa (3 sources), Perplexity, Serper (← SerpAPI), Apify (bonus). C'est lui qui RE-RUN le moteur
    (bloqué : moteur Neotek inaccessible ; données du 25/05 figées).

## MAYA — Analyse loop / re-scoring
(a) Prompt : définir /top (meilleurs scores), /trends (évolution), /recurring (signaux
    récurrents). Inscrire que /recurring exige ≥2 runs et renvoie un message explicite sinon.
(b) Mémoire : historique horodaté des runs, les scored_results.csv successifs.
(c) Re-scoring + comparaison inter-runs. Débloquée dès le 2e run (bloqué par l'accès moteur).
    Alimente le tuning de `scoring_config.yaml`.

## INÈS — Contacts & radars / enrichissement
(a) Prompt : deux rôles — (1) enrichissement décideurs (mobile, email pro/perso depuis
    LinkedIn) ; (2) vérification email (amont de Bouncer). Prioriser les 67 cibles Lunch.
(b) Mémoire : radars Lunch Campaign (48 CH + 19 ES), fonctions cibles (commercial/data/digital).
(c) Outils : Kaspr (remplace le stub Apollo — meilleure couverture CH/ES), puis Bouncer.

## JULIE — Rédaction des messages
(a) Prompt : ancrer la voix d'Andrés + le Playbook LinkedIn v2.1. Chaque message s'appuie sur
    l'Intelligence Summary (3 phrases) du lead ET un cas client/projet concret du Brand DNA.
(b) Mémoire : `app/agents/playbooks/andres_linkedin.md` + Brand DNA clients/projects (À REMPLIR,
    sinon messages génériques).
(c) Génère les messages perso, alimente les séquences Lemlist (email + LinkedIn).

## IRIS — Recherche & scoring de sujets marketing
(a) Prompt : recherche de sujets pharma/medtech/dental + scoring pertinence/actualité.
(b) Mémoire : thèmes sectoriels, angles éditoriaux TPDL.
(c) Migrer de DuckDuckGo (qualité basse) vers Serper — gain immédiat, coût ~0.

## MARC — Architecte de contenu
(a) Prompt : transformer un sujet scoré (Iris) en structure éditoriale (angle, plan, messages).
(b) Mémoire : templates + Brand DNA (clients/projets = preuve sociale).
(c) Architecture éditoriale ; alimente Oliver.

## OLIVER — Producteur de formats
(a) Prompt : produire A4 / carousel / PPT / web au branding TPDL (#094752 / #34D591).
(b) Mémoire : chartes, gabarits.
(c) Renderers PDF/PPTX À CONNECTER. En attendant, sorties web/aperçu seulement.

## ANDRÉS / PREMIUM 5 (handoff humain)
Fondateur (Andres Burdett), voix des messages. Premium 5 = 5 comptes prioritaires gérés en
personne. Dans le plan : (1) fournir le Brand DNA (30 min) ; (2) valider les messages ;
(3) prendre la main sur les Premium 5 de la Lunch Campaign.
