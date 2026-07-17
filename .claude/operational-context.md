# Contexte opérationnel — transcripts de réunions (vérité terrain)

> Intégré le 2026-07-12 depuis 2 transcripts : `TPDL_Agents_Pilot` (16.06.2026, Betty & Nathalie)
> et `Claude x TPDL commercial agents` (25.06.2026).
> ⚠️ Ces réunions sont ANTÉRIEURES à nos décisions du 09/07 (modèles Sonnet 5/Opus 4.8, Serper←SerpAPI,
> Kaspr←Apollo, budget révisé). Là où un transcript contredit une décision plus récente, la
> DÉCISION du 09/07 PRIME — voir « Conflits » en bas.

## MISE À JOUR 2026-07-16 — réunion pilote (Betty & Nathalie)
> Source : `Downloads/TPDL_agent_pilot-20260716_125029-Meeting_Recording.docx`. Note Obsidian
> détaillée : vault TPDL → `Agents IA & Pipeline TPDL/Réunion — 16 juillet — Pilote agents…`. Plus récente que
> les transcripts de juin ci-dessous → PRIME en cas de conflit.
- **⚠️ CHANGEMENT DE SCOPE MOTEUR (Nathalie).** On abandonne la base FERMÉE de 500 (diagnostic/
  dermato/dental + CRM) : « les 500 sont irrelevant ». Nouveau périmètre = **veille de marché
  large** : critère principal **life science & pharmaceutical**, sous-catégories dental/derm/
  diagnostics, CRM en option seulement. Base de départ = **top 35 + du NOUVEAU crawlé sur le net**.
  But = développer le business, pas recycler l'existant. → impacte l'ICP de Hugo (voir CLAUDE.md,
  « ÉTAT CIBLE » + question ouverte scope). À FORMALISER dans un doc de segmentation (tâche Betty,
  Nathalie relit) avant de toucher au prompt Hugo / `scoring_config.yaml`.
- **Signal fort explicitement visé : earnings calls (Q2/trimestriels)** où une société pose
  l'investissement/stratégie digitale comme priorité stratégique du board/exécutif → soutien board
  → coordination PMO ↔ execs commerciaux ↔ IT = cœur de cible TPDL. (Recoupe `digital_initiative`,
  mais l'angle « priorité board via earnings call » est à encoder côté Hugo.)
- **Coût & cadence CONFIRMÉS terrain** : run ≈ **40–60 €** ; Batch API (−50 %, 24 h) adopté ;
  **~1 run/mois** au début (vérif aval énorme, doublons, peu de signaux neufs/semaine). Nathalie :
  faire le run même à 100 € — sinon « on travaille dans le vide ». Qualité > quantité (top 35, dont
  <10 réellement utilisés sur le pilote de mai).
- **Apollo + PipeDrive : à connecter**, mais **PipeDrive en staging** (vérifier + catégoriser les
  contacts avant import ; ne pas déverser 500 contacts). Apollo = « boîte noire » pour Nathalie ;
  périmètre à trancher (arrêt aux résultats vs jusqu'aux contacts). Neotek ≈ 60 sociétés = 10-15 %
  du CRM → levier sales à retravailler.
- **MailChimp : plafond 1 500 mails/mois** (plan actuel), < 1 000 contacts. **Bouncer = usage RÉEL**
  (Nathalie filtre déjà le risque de bounce avant envoi newsletter).
- **Contenu LinkedIn** : **Yasmine** produit le contenu (objectif 15 pièces ≈ 2,5 mois) → carrousels
  réutilisables. Pas de graphic designer.
- **ACCÈS (critique)** : comptes & API existent mais Betty n'a PAS l'accès direct à tout. **Andrés**
  détient la feuille de tous les codes/accès (+ rajoute les crédits pendant les vacances de Nathalie).
  **Alfredo** a le code du « Pharma Data Lab Systems App » + une boîte mail « anonyme » à rattacher
  chez Betty (même Nathalie ne l'a pas). Betty a échoué à se connecter à Perplexity (code redemandé).
  → distinction clé : **clé API dans `.env` ≠ accès compte/login de Betty**.
- **Sophia** peut re-runner le VRAI Neotek (« un clic », ~500 €) → option de comparaison phase 2.
  Question : rerun ≈ mêmes résultats ? Si variation ≤ 2-3 % → rapport tous les 6 mois suffit.
- **Langue** : notes/transcripts **en français OK** ; le **CODE reste en anglais** (universel).
- **Nouvelles personnes** : Sophia (opère le Neotek d'origine), Pierre (envoi newsletter à ses
  contacts), Yasmine (contenu), Alfredo (codes systèmes/IT), + Fernando & Patricio (à ranger au fil).

## PROCESS RÉEL DE PROSPECTION (aujourd'hui, surtout manuel)
- Sourcing ICP : Sales Navigator + Apollo. Manuel = trop lent (92 contacts en 2 semaines).
- LinkedIn : demandes de connexion manuelles, plafond ~200/semaine, ~30 % acceptées.
- Envoi des messages : **MANUEL, par un SDR en Inde**, pour éviter les blocages LinkedIn.
  Validation humaine cruciale (surtout CEO). Automatisation = plus tard.

## CRM & OUTILS (nouveau — absent de la mémoire jusqu'ici)
- **PipeDrive** = le CRM (contacts, campagnes, segmentation).
- **Surf** = automatise le transfert des contacts LinkedIn → PipeDrive.
- **MailChimp** = envoi des newsletters (segment 3).
- **Sales Navigator** = sourcing.
- Plateformes à comparer/évaluer : **Lucia**, **Gaspers**.

## SEGMENTATION CRM (3 segments)
- Segment 1 : excellente relation, potentiel commercial rapide.
- Segment 2 : suivi, opportunités moyen terme.
- Segment 3 : newsletters.
> Propriétaire à confirmer : Inès (CRM/contacts) vs Maya (analyse).

## PREMIUM 5 / VIP (confirme et détaille la mémoire)
- 5 contacts VIP/semaine, ciblés par Andrés, messages hyper-personnalisés (1 à 1h15 chacun).
  = l'approche LA PLUS performante.
- Campagnes Lunch/Coffee : contacts Espagne & Suisse (où Andrés se déplace), messages adaptés
  à la langue (espagnol). = l'approche humaine la plus engageante.

## LEÇON OUTREACH (clé pour Julie + playbook)
- Le cold outreach direct est INEFFICACE (« LinkedIn sales fatigue »).
- Ce qui marche : message simple, humain, personnalisé. Exemple type (voix Andrés) :
  « Thanks for connecting. Always interesting to meet people from [industry/company].
    Wishing you well with everything at [Company Name]. Best A. »
- Objectif = thought leadership : créer des connexions, visibilité organique (likes/commentaires),
  PAS de vente directe.

## MARKETING / CONTENU
- Iris : recherche tendances/articles/posts → conclusions.
- Marc : contenu brut à partir des données d'Iris + inputs TPDL.
- Oliver : adapte le contenu par format (posts LinkedIn, carrousels, études de cas, web, newsletters),
  priorise l'info selon le format.
- Alex : manager marketing.
- Principe « begin with the end in mind » ; connecter contenu ↔ audience CRM + hot topics + UVP TPDL.
- Pondération newsletter : **70 % audience CRM existante / 10 % tendances LinkedIn / 20 % forces &
  études de cas TPDL** (alimentées par les decks clients).

## RÔLES AGENTS — cartographie confirmée (25.06, la plus récente)
- Hugo : détection (moteur Neotek + **Firecrawl** pour formulaires/PDF/bases de recherche).
- Maya : analyse & scoring (top 50/100).
- Inès : recherche de contacts (Apollo, Sales Nav, Surf → PipeDrive) ; débat sur le rôle « Radar » (géo/national).
- Julie : rédaction des messages (segmentation secteur / entreprise / personne / spécificités TPDL).
- Iris / Marc / Oliver / Alex : marketing (voir ci-dessus).
> Le transcript du 16.06 attribuait les contacts à Maya → SUPERSEDÉ par le 25.06 (Maya = analyse,
> Inès = contacts). On garde le 25.06.

## IDÉE : AGENT DE VÉRIFICATION (9e agent potentiel)
- Agent dédié à la vérification des données à chaque étape. Vérif humaine au début, automatisation
  plus tard. → à trancher : l'ajoute-t-on au roster ?

## PLATEFORME / CRÉDITS / FACTURATION
- Workplace TPDL créé. Commencer petit (10-20 €) pour comprendre la conso pendant les tests.
- Souci de facturation Anthropic → passer sur carte d'entreprise TPDL.
- Possibilité d'augmenter/transférer l'abonnement pour doubler les crédits.

## CALENDRIER (du 25.06)
- Crash test initial : mi-juillet.
- Semaine du 20 juillet : analyse des 1ers résultats.
- Amélioration continue jusqu'en août ; points réguliers le mardi après-midi.

## CONFLITS avec nos décisions du 09/07 (la décision récente PRIME)
- Modèles : transcripts parlent de Haiku/Sonnet (et « passer à Opus »). → SUPERSEDÉ : extraction
  **Sonnet 5** / interprétation **Opus 4.8**.
- Budget : « 10-15 €/mois » (transcript) → INVALIDÉ (extraction Sonnet 5 ≫ Haiku).
- Outils : Apollo → cible **Kaspr** ; SerpAPI/DuckDuckGo → cible **Serper**. Apollo/Surf/PipeDrive/
  MailChimp restent la réalité ACTUELLE côté outreach/CRM.
- « Guillaume » (16.06) = ancien nom du rédacteur = aujourd'hui **Julie**.
