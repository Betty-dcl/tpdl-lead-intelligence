# TPDL — AI Consulting Firm Dashboard · Récapitulatif complet

> Plateforme web locale simulant une équipe d'employés IA pour le cabinet **The Pharma Data Lab (TPDL)**.
> Objectif : valider l'UX et le squelette technique avant d'ajouter les vraies intégrations (V2).

---

## 1. Stack technique

| Couche | Choix |
|--------|-------|
| Backend | FastAPI + SQLAlchemy 2.0 |
| Base de données | SQLite (`data/app.db`) |
| Templates | Jinja2 |
| Front | Tailwind (CDN) + Alpine.js (CDN) + Chart.js (CDN) — **pas de build step** |
| IA | Anthropic SDK (modèle configuré : `claude-sonnet-4-5`) |
| Lancement | `make run` ou `uvicorn app.main:app` (port 8000) |

**Contraintes de dev :** pas de framework JS lourd, pas de build, secrets via variables d'environnement uniquement, type hints partout, IDs d'agents via une enum `AgentID`.

**Branding TPDL :** vert foncé `#094752`, accent `#34D591`.

---

## 2. Architecture : un manager + deux pipelines

**Alex (`manager`)** — point d'entrée. Oriente l'utilisateur vers le bon agent.

### 🟦 Pipeline SALES / Outbound Intelligence (4 agents)

| # | Agent | ID | Rôle | Commandes |
|---|-------|-----|------|-----------|
| 1 | **Hugo** | `hugo` | Deep Research & Scoring — recherche multi-sources + notation des entreprises | `/scan [secteur?]`, `/company [nom]`, `/stats` |
| 2 | **Maya** | `maya` | Analyste — Top 50/100 hebdo, entreprises récurrentes + tendances | `/top [N?]`, `/trends`, `/recurring` |
| 3 | **Inès** | `ines` | Contacts (CEO/CTO/CFO via Apollo) + radars de ciblage | `/contacts [entreprise]`, `/radars`, `/premium` |
| 4 | **Julie** | `julie` | Outreach segmenté par secteur, ancré dans l'ADN de marque | `/sectors`, `/segment [secteur]`, `/draft [entreprise]`, `/linkedin [contact + trigger]` |

**Détails clés :**
- **Hugo** = le moteur « TPDL Lead Intelligence Pipeline » (codebase Neotek externe) : 6 étapes, 8 sources (Exa ×3, Perplexity Sonar, SerpAPI News+Jobs, registres EU, IR fetch, Wappalyzer/Apify), split 2 modèles (Haiku extrait / Sonnet score). Formule : signal_strength(0-6) + recency(0-2) + corroboration(0-2). `scoring_config.yaml` ajustable.
- **Inès → radars :** « Lunch Campaign » pour la Suisse (anglais + en personne) et l'Espagne (espagnol + en personne). Sélection « Premium 5 » → handoff vers **Andrés** (= Andres Burdett, **vrai partenaire humain** TPDL, pas un agent).
- **Julie → playbook LinkedIn** v2.1 dans la voix d'Andres Burdett (`app/agents/playbooks/andres_linkedin.md`) : pas de tirets, ≤90 mots, DMs post-acceptation, ancrage « the gap between strategic technology ambition and execution reality », règles de localisation (Espagne→espagnol / Suisse→anglais).

### 🟩 Pipeline MARKETING Intelligence (3 agents)

| # | Agent | ID | Rôle | Commandes |
|---|-------|-----|------|-----------|
| 1 | **Iris** | `iris` | Marketing Research & Trend Scoring (« le Hugo+Maya du marketing ») | `/research [sujet]`, `/trends [secteur?]`, `/themes` |
| 2 | **Marc** | `marc` | Content Architect (« la Julie du marketing ») — écrit la substance | `/angles [thème]`, `/content [thème]` |
| 3 | **Oliver** | `oliver` | Format Producer — met en forme (A4 / carrousel / PPT / website) | `/format [type] [thème]`, `/carousel`, `/article` |

**Détails clés :**
- **Iris** fait de la vraie veille web via DuckDuckGo (sans clé, se dégrade proprement, ne fabrique jamais de source). Score les thèmes 0-10.
- **Marc** ancré dans la voix de marque ; marque tout chiffre non confirmé `[STAT TO VERIFY]`, n'invente jamais de données/clients.
- **Oliver** produit 4 formats (A4 long-form, carrousel LinkedIn 6-8 slides, deck PPT, article web SEO). Les vrais moteurs de rendu (PDF/PPTX/carrousel lead-capture) restent à brancher.

**Secteurs à segmenter (contenu à fournir) :** dental, pharma, surgery, …

> Note historique : roster restructuré le 2026-06-17. Anciens agents supprimés : diego, eva, kai, sofia (signal-specialists), marcus, nina. `marcus → marc`, `nina → oliver`.

---

## 3. Données réelles en base (1 seul run, 2026-05-25)

- **492 entreprises** scannées et scorées
- **280** in-scope (après filtre ICP) · **212** ICP-flagged · **35 éligibles à l'outreach** (score ≥ 8)
- **722 signaux** (3 slots par entreprise : what happened / why it matters / TPDL relevance)
- **0 contact** (table prête, vide — bloqué sur Apollo)
- **Radars :** 40 entreprises suisses + 18 espagnoles détectées pour la Lunch Campaign

**Répartition secteurs :** Pharma 91 · Dental 63 · Medtech 60 · Diagnostics 54 · Dermatology 40 · Healthcare 36 · Unknown 138
**Top géo :** Allemagne 26 · Dubaï ~38 · Suisse 12 · France 17 · Espagne 7

**ADN de marque (`brand_memory`) :** `history` rempli (positionnement TPDL réel, ~354 car.) ; `clients` et `projects` encore vides.

---

## 4. Pages du dashboard (nav)

| Page | Route | État |
|------|-------|------|
| **Home** | `/` | ✅ Présentation équipe + diagramme des 2 pipelines + chat Alex |
| **Today** | `/today` | ⚪ Empty-states OK, en attente du 1er run / activité |
| **Sales** | `/intel` | ✅ La plus riche : 492 entreprises, filtres, détail signaux |
| **Marketing** | `/marketing` | 🟡 Bandeau Iris→Marc→Oliver OK ; onglets encore sur ancien modèle Marcus/Nina |
| **Contacts** | `/contacts` | 🟡 Radars live (40 CH + 18 ES) ; 0 contact (Apollo) |
| **Performance** | `/performance` | ⚪ Empty-states OK, en attente d'activité |
| **Data** | `/data` | ⚪ Source OneDrive CSV, `ONEDRIVE_CSV_URL` absente |
| **Agent profile** | `/agent/{id}` | ✅ 8 agents |

**Routers :** agents, auth, briefs, chat, companies, contacts, conversations, intel, marketing, memory_api, onedrive, pages, performance, pipeline, realtime, today, veille

---

## 5. Ce qui marche / ce qui bloque

**✅ Fonctionne :** navigation complète, pages de données (Sales, Contacts), toutes les API renvoient 200, le data-wiring de chaque agent est validé par tests unitaires.

**🔴 Bloqué (dépend de clés/contenu à fournir) :**
1. **Chat live des agents** → `ANTHROPIC_API_KEY` dans `.env` est un placeholder (11 car. ; une vraie clé fait ~100). Sans vraie clé, aucun agent ne répond (401).
2. **Contacts nominatifs** → `APOLLO_API_KEY` vide → Inès ne peut pas remonter les CEO/CTO/CFO.
3. **Tendances/récurrences de Maya** → un seul run de pipeline (il en faut ≥2).
4. **Veille marketing riche** → `EXA_API_KEY` / `PERPLEXITY_API_KEY` / `SERPAPI_KEY` / `APIFY_TOKEN` vides (Iris en mode DuckDuckGo dégradé).
5. **Page Data** → `ONEDRIVE_CSV_URL` absente du `.env`.

**🟡 Dette UI / à fournir :**
- Refondre `templates/marketing.html` (onglets) sur le vrai flow Iris → Marc → Oliver (supprimer/réaffecter la section « Case Studies » de l'ex-Nina).
- Positionnement par secteur pour Julie/Marc (placeholders).
- Enrichir l'ADN de marque (`clients`, `projects`).
- Vrais moteurs de rendu pour Oliver.
- Cosmétique : commentaires Diego/Eva/Kai/Sofia dans `static/js/intel.js:6-9` (non visibles).

---

## 6. Localisation & lancement

- **Dossier :** `/Users/bettydeclety/Documents/TPDL/claude code dashboard/`
- **Lancer :** `make run` (ou `uvicorn app.main:app --port 8000`) → http://localhost:8000
- **Re-seed agents :** `make seed`
- **Reset DB :** `make clean`
