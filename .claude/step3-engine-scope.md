# Cadrage — Reconstruction du moteur Neotek (Step 3)

> Rédigé le 2026-07-14. Décision actée : **on reconstruit le moteur dans ce repo**
> (pas d'accès Neotek). Ce document = la carte du chantier AVANT de coder.
> Il est fait pour être lu par Betty **et** validé par Andrés (décisions en §7).
> Statut : brouillon de cadrage, non committé. Source de vérité du design :
> `.claude/neotek-process.md` + `CLAUDE.md`.

---

## 1. Ce qu'on construit (et ce qu'on ne construit pas)

- On construit **le moteur** : recherche → extraction → scoring → CSV daté du jour.
- On NE touche PAS au dashboard/agents de chat (ils tournent déjà, clé Anthropic OK).
- Le moteur **alimentera** le dashboard : chaque run produit un `scored_results.csv`
  qu'`import_csv.py` réingère → nouveau `import_run_id` → Maya `/recurring` se débloque.

## 2. Le principe non négociable (rappel)

Séparation **structurelle** en 2 modèles, jamais fusionnée :
- **Extraction = Sonnet 5** : touche le texte source brut, sort des **phrases verbatim**,
  n'interprète JAMAIS. Prompt qui VERROUILLE le verbatim (zéro éditorialisation).
- **Interprétation/Scoring = Opus 4.8** : juge, mais ne voit **jamais** le brut — uniquement
  les blocs d'évidence déjà isolés. Ne peut donc pas halluciner un fait.
- Formule déterministe : `score = signal_strength(0-6) + recency(0-2) + corroboration(0-2)`.

## 3. État des lieux, étape par étape (design 6 steps vs code réel)

| Step | Rôle | Ce qu'on A déjà (repo) | Ce qu'il faut CONSTRUIRE | Outil / clé |
|------|------|------------------------|--------------------------|-------------|
| **0 Load** | Charger l'univers d'entreprises | ✅ **FAIT** — `import_csv.py` + table `companies` (schéma 38 col. complet) + `Signal` normalisée. 492 lignes prouvées. | Rien (réutilisé tel quel) | — |
| **1 Tech scan** | Détecter la stack (CRM absent = gap) | 🟡 colonne `tech_stack_summary` existe (remplie par l'ancien CSV) | Client Wappalyzer/Apify → remplir la colonne | **Apify** ✅ (clé en .env) |
| **2 Research** | 8 sources → matière brute datée | 🟡 `web_search.py` = DuckDuckGo (sert Marc, PAS le moteur). Apollo = stub (contacts, pas research) | Clients **Exa** (×3 requêtes), **Perplexity Sonar**, **Serper** News+Jobs, fetch IR pages | **Exa** ✅, **Perplexity** ✅, **Serper** (à prendre, cible ≠ SerpAPI), **Firecrawl** ✅ (fetch pages) |
| **3 Extract** | Phrases verbatim + date + URL | ❌ **RIEN** — le cœur anti-hallucination | Module extraction + **prompt Sonnet 5 verrouillé** + QA anti-éditorialisation | **Anthropic (Sonnet 5)** ✅ |
| **4 Score** | signal_strength + formule → score | 🟡 `scoring_config.yaml` (poids recency/corrob/seuil 8) existe. Le déterministe est codable direct. | Module interprétation + **prompt Opus 4.8** (7 règles dures) + application formule | **Anthropic (Opus 4.8)** ✅ |
| **5 Batch** | Scorer en volume à -50 % | ❌ RIEN | Câbler l'**Anthropic Batch API** (poll) | Anthropic ✅ |
| **6 Output** | `scored_results.csv` (38 col.) | 🟡 le **schéma cible existe déjà** (modèle `Company`). `import_csv` fait l'inverse. | Petit exporter DB→CSV (trivial) | — |

## 4. L'insight clé (ça change tout)

> **Les deux bouts du pipeline sont DÉJÀ construits et prouvés.**
> Le Step 0 (chargement) et le format de sortie Step 6 (les 38 colonnes = le modèle
> `Company`) existent — 492 entreprises y sont déjà passées. **Ce qui manque, c'est le
> MILIEU : Steps 1→5**, le moteur qui va de « nom d'entreprise » à « lignes de signaux
> scorés ». On ne part donc PAS de zéro : on remplit un tuyau dont on connaît déjà
> l'entrée et la sortie exactes.

## 5. La 1ʳᵉ tranche verticale — UNE entreprise de bout en bout

Avant tout run en volume, on valide la chaîne sur **1 seule entreprise** (ex. une hors
des 492, pour un vrai test à froid). Objectif : prouver la séparation Sonnet/Opus + le
format, pour ~quelques centimes.

Chaîne minimale : `Serper News (1 requête) → Extract Sonnet 5 → Score Opus 4.8 → 1 ligne CSV`

Critères de succès de la tranche :
1. L'extraction ne sort QUE du verbatim daté + URL (QA : zéro phrase reformulée).
2. L'interprète ne voit PAS le brut (vérifiable dans le payload envoyé à Opus).
3. La ligne produite se réimporte proprement via `import_csv.py`.
4. Le score = strictement la formule (pas de bonus discrétionnaire).

## 6. Séquence de build proposée (petits jalons)

- **M0 — Squelette** : `pipeline/` (nouveau paquet), un `runner.py` qui orchestre 0→6 sur
  1 société, config lue depuis `scoring_config.yaml` + `.env`. Steps 2/3/4 en *stubs*.
- **M1 — Research (Serper d'abord)** : 1 source réelle (Serper News), matière datée + URL.
- **M2 — Extract (Sonnet 5)** : prompt verrouillé + QA verbatim. **Le morceau le plus délicat.**
- **M3 — Score (Opus 4.8)** : 7 règles dures + formule + `scoring_config.yaml`.
- **M4 — Sortie** : exporter DB→CSV 38 col. + réimport (boucle fermée). → **tranche §5 bouclée.**
- **M5 — Élargir les sources** : Exa ×3, Perplexity (corrob 0 sans URL), Serper Jobs, Firecrawl.
- **M6 — Tech scan** : Apify/Wappalyzer → `tech_stack_summary`.
- **M7 — Batch API** : passer le scoring en batch (-50 %) pour le volume.
- **M8 — Run maîtrisé** : sous-ensemble (ex. ≥8 des 67 cibles Lunch), PAS les 492 d'un coup.
  → Maya `/recurring` se débloque (2ᵉ run).

## 7. Décisions à valider avec Andrés (avant / pendant)

1. **Serper** : le prendre (cible du plan, ~25× moins cher que SerpAPI). OK pour souscrire ?
2. **Budget crédits Anthropic** : les 5 $ actuels ne suffisent pas (voir §8). Recharger combien
   sur la carte TPDL, et qui ?
3. **Périmètre du 1ᵉʳ vrai run** : les 67 cibles Lunch ? le top ≥8 ? autre ?
4. **RGPD** : base légale (intérêt légitime B2B, opt-out) avant tout enrichissement/envoi UE/CH.
5. **Agent de vérification (9ᵉ agent ?)** : idée du transcript 25.06 — on l'ajoute au moteur (QA
   automatique des blocs d'évidence) ou vérif humaine au début ?

## 8. Estimation de coût (ORDRE DE GRANDEUR — à affiner)

Par entreprise (avec Batch -50 % sur le scoring) :
- Sonnet 5 extraction : ~6k tok in + 1k out ≈ **~0,02 $**
- Opus 4.8 scoring : ~2,5k in + 0,8k out ≈ **~0,02–0,03 $**
- APIs externes (Serper/Exa/Perplexity/Firecrawl) : variable, **dominent l'incertitude**

→ **Modèles seuls : ~0,04–0,05 $/entreprise.** Pour 492 : **~25–30 $ de modèles**, + coût
des APIs de recherche. **Un run complet ≈ 50–150 $** selon la profondeur de recherche.
**Conclusion : les 5 $ actuels couvrent la tranche §5 (1 société) et quelques dizaines de
tests, PAS un run complet.** Prévoir une recharge avant M8.

## 9. Garde-fous (dans le code, pas que dans le prompt)

- Verrou verbatim Sonnet : test QA qui rejette toute phrase absente du texte source.
- Isolation Opus : le payload de scoring ne contient JAMAIS le texte brut (assert dans le code).
- Review flags automatiques (sources non vérifiables / sans date / boilerplate ≥3 sociétés).
- Poids NON codés en dur : tout dans `scoring_config.yaml` (déjà le cas).
- Idempotence : chaque run = un `import_run_id`, réimport sans doublon (déjà le cas).
