# Process Neotek — référence détaillée

Chargé à la demande via l'import dans CLAUDE.md. Détail complet du pipeline.
> ⚠️ Ce moteur (6 steps) est le DESIGN Neotek. Son code n'est PAS accessible (voir CLAUDE.md,
> « Deux systèmes »). Ce fichier sert de spéc pour la reconstruction (Step 3), pas de doc d'un
> code existant dans ce repo.

## POURQUOI LA SÉPARATION EXTRACTION/INTERPRÉTATION EST NON-NÉGOCIABLE
- Extraction (**Sonnet 5**, Step 3) touche le texte source brut mais ne juge pas : elle isole des
  phrases verbatim.
- Interprétation (**Opus 4.8**, Step 4) juge mais ne touche jamais le brut : elle ne voit que des
  phrases déjà isolées.
- Conséquence : l'interprète ne PEUT PAS inventer un fait, car il n'a pas accès à la matière où
  inventer. L'anti-hallucination est structurelle, pas seulement dans le prompt.
- ⚠️ Sonnet 5 est un modèle capable, donc plus tenté d'éditorialiser pendant l'extraction que
  l'ancien Haiku. Son prompt doit imposer strictement : phrases verbatim uniquement, aucune
  reformulation, aucun jugement, aucune synthèse. À valider par QA (voir Step 2 de la roadmap).
- Bénéfices annexes : (1) re-scorer = relancer Step 4 seul, sans re-rechercher ;
  (2) auditer les blocs d'évidence avant de faire confiance à l'interprétation ;
  (3) coût : l'extraction (étape la plus lourde en tokens) coûte plus cher qu'avec Haiku — à
  surveiller et arbitrer (Batch API -50 %, effort/reasoning calibrés).

## STEP 2 — LES 8 SOURCES EN DÉTAIL
- Exa Q1 : news générales, neural search (trouve du sémantiquement proche, pas du mot-clé).
- Exa Q2 : leadership / hiring.
- Exa Q3 : M&A / expansion.
- Perplexity Sonar : presse financière (Reuters/FT/Bloomberg). Ne renvoie PAS d'URL →
  tout signal Perplexity-seul reçoit corroboration = 0. Corrobore mais n'ancre pas.
- Serper Google News (remplace SerpAPI) : presse régionale/trade européenne.
- Serper Google Jobs (remplace SerpAPI) : offres d'emploi = proxy direct de signal hiring.
- Registres UE (conditionnel) : ownership, changements de dirigeants (sociétés privées).
- IR page fetch (conditionnel) : communiqués, communications investisseurs.

## LA FORMULE DE SCORING (rappel opérationnel)
score = signal_strength + recency + corroboration   (0-10)
- signal_strength (0-6) : SEUL jugement de l'interprète.
    0 = aucune pertinence ; 1-2 = faible/indirect ; 3 = pertinence claire, cas standard ;
    4 = forte, alignement direct domaine TPDL ; 5 = très forte, point d'entrée + gap identifié ;
    6 = exceptionnel, urgence haute + gap documenté.
- recency (0-2) : ≤90j=2 ; ≤6mois=1 ; sans date=0.
- corroboration (0-2) : 2+ sources=2 ; 1 URL vérifiée=1 ; Perplexity sans URL=0.
- assessed_score = moyenne sur signaux TROUVÉS seulement.
- coverage = combien des 6 types de signaux ont une évidence (dimension distincte du score).

## LES CHAÎNES DE RAISONNEMENT (à compléter avant signal_strength > 3)
- Leadership change → nouveau dirigeant audite les capacités héritées sous 90j →
  gap type : maturité CRM, activation data, cohérence go-to-market → TPDL : CRM & data strategy
  OU Digital execution & activation.
- M&A / acquisition → systèmes dupliqués, process incohérents → TPDL : Operating model
  alignment OU Customer journey optimisation.
- PE / nouvel investissement → mandat PE = amélioration perf commerciale sous 12-18 mois →
  TPDL : Commercial effectiveness OU CRM & data strategy.
- Hiring (rôles commercial/digital) → capacité en construction = transformation en cours →
  TPDL : Digital execution & activation.
- Org restructuring → modèle opérationnel en revue → TPDL : Operating model alignment OU
  Commercial effectiveness.
- Tech stack gap (pas de CRM détecté) → pas de gestion client systématique à ce niveau de CA
  → TPDL : CRM & data strategy OU Digital execution & activation.

## INTELLIGENCE SUMMARY — GABARIT (exactement 3 phrases)
1. Situation actuelle : ce que fait l'entreprise maintenant, y compris événements NON scorés
   (jalons réglementaires, lancements). Si filiale, noter le parent.
2. Statut signaux : trouvés / absents, ce que l'absence suggère. Pour une filiale, noter que
   les signaux peuvent être au niveau du parent.
3. Timing TPDL : reco spécifique — engage now / monitor and revisit / manual verification needed.

## SORTIE — scored_results.csv (38 colonnes, groupes)
Identity (nom, secteur, site, localisation, CA) ; Score (assessed, coverage, outreach eligible) ;
Narrative (intelligence summary) ; Signal counts ; Signal 1/2/3 detail (catégorie, what happened,
why it matters, TPDL relevance, confidence, sources, URLs) ; Context (tech stack, historique) ;
Flags (ICP, review flag + raison, run date).

## REVIEW FLAG : TRUE si
- signal haute confiance mais toutes sources non vérifiables ;
- signal haute confiance sans date approximative ;
- tpdl_rationale identique à 3+ autres entreprises (détection de boilerplate).
Row flaggée = check manuel de 60 s avant d'agir sur le signal flaggé.
