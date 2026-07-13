# Roadmap — référence

Chargé à la demande. La roadmap est structurée en 4 macro-steps (décidés le 09/07/2026). On
avance petit à petit. Priorité absolue AVANT les steps : établir la base + la mémoire propre (fait).

> Blocage de fond : le moteur pipeline Neotek est INACCESSIBLE (on n'a que les CSV du 25/05).
> Toute étape « run / rafraîchir les données » est bloquée tant que le moteur n'est pas
> reconstruit (Step 3) ou l'accès obtenu. À trancher tôt avec Andrés.

## STEP 1 — ABONNEMENTS / API (quoi payer)
Objectif : liste claire des services à souscrire, avec coût réel re-vérifié et ordre de priorité.
- Anthropic : clé API réelle dans `.env`. Modèles : Sonnet 5 (extraction) + Opus 4.8 (interprétation
  & chat). Re-chiffrer le budget (extraction plus chère qu'avec Haiku). Batch API -50 %.
- Firecrawl : fetch/scrape de pages (IR, sites). Coût à confirmer.
- Perplexity : Sonar (presse financière PE/M&A). Clé à créer.
- Serper : Google News + Jobs (remplace SerpAPI). Free 2500/mois.
- Kaspr : contacts décideurs (remplace Apollo). Palier API à confirmer.
- Bouncer : vérif email (au 1er envoi).
- Lemlist : séquences multicanal (Lunch Campaign).
- Exa / Apify : recherche neuronale + tech-scan (selon reconstruction moteur).
Succès : tableau des abonnements décidés (payer / attendre), budget mensuel chiffré, clés créées
pour ce qu'on active.

## STEP 2 — FORMER CHAQUE AGENT (prompt + résultat attendu)
Objectif : pour chacun des 8 agents, un prompt système détaillé + une définition précise du
contenu de résultat attendu (format, champs, longueur, ton).
- Encoder la constitution + les 7 règles dures dans les prompts concernés.
- Verrou verbatim pour l'extraction (Sonnet 5) : QA anti-éditorialisation.
- Julie : voix Andrés + playbook + Brand DNA (clients/projects à remplir avec Andrés, 30 min).
- Maya : /top /trends /recurring (message explicite si <2 runs).
- Définir les livrables attendus (ex. Intelligence Summary = 3 phrases exactes ; brief société ;
  message perso citant 1 signal réel + 1 cas Brand DNA).
Succès : prompts versionnés dans `app/agents/`, exemples de sortie validés par Andrés.

## STEP 3 — AMÉLIORER LE WORKFLOW DU PROCESS
Objectif : reconstruire / brancher le moteur pipeline et connecter les outils.
- Décision moteur : reconstruire dans ce repo vs obtenir l'accès Neotek.
- Séparation stricte extraction (Sonnet 5) / interprétation (Opus 4.8) ; Batch API pour le scoring.
- Migrer SerpAPI → Serper, Apollo → Kaspr dans le code + `.env`/`config.py`.
- Brancher Firecrawl (fetch), Bouncer (email), Lemlist (séquences), renderers PDF/PPTX (Oliver).
- Git : initialiser le repo, main protégée, .gitignore .env, partage Andrés.
Succès : un run reproductible produit un `scored_results.csv` daté du jour ; /recurring débloqué.

## STEP 4 — ESSAYER
Objectif : run de bout en bout sur un sous-ensemble, mesurer, itérer.
- Sous-ensemble maîtrisé (score ≥8 des 67 cibles Lunch), pas les 67 d'un coup.
- Chaîne : Hugo → Maya → Inès → Bouncer → Julie → Lemlist. Premium 5 réservés à Andrés.
- Mesurer, réinjecter dans Maya, ajuster `scoring_config.yaml` (documenter + commit).
Succès : campagne test partie, métriques connues, 1re itération de tuning planifiée.

## CRITÈRES « BONS RÉSULTATS » (à caler avec Andrés — propositions)
- Données fraîches : dépend du déblocage moteur ; delta vs run 25/05 documenté.
- Contacts : ≥1 décideur pour ≥70 % des 67 cibles (≈47 comptes).
- Emails : 100 % passés par Bouncer ; envoi limité aux Deliverable.
- Messages : ≥1 message voix Andrés par cible, citant un signal réel + un cas Brand DNA.
- Taux de réponse : cible à fixer selon benchmarks LinkedIn + email B2B.

## BOUCLE D'AMÉLIORATION
1. Vers Maya : nouveau CSV → /recurring, /trends, /top ; qui monte/descend depuis Organon 9.5.
2. Vers `scoring_config.yaml` : si haut score ne convertit pas, re-pondérer strength vs
   recency/corroboration, ou ajuster le seuil (8). Documenter dans CLAUDE.md + commit.
3. Vers prompts : intégrer les accroches gagnantes de l'A/B Lemlist dans Julie + playbook.
