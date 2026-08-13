# AI Consulting Firm — Brief Claude Code

> **Tu es Claude Code.** Ce fichier est ton brief maître. Tu lis ce fichier en entier AVANT d'écrire la moindre ligne de code. Tu suis les phases dans l'ordre. Tu ne sautes pas d'étape. Tu demandes validation à l'utilisateur à la fin de chaque phase avant de passer à la suivante.

---

## 0. CONTEXTE & OBJECTIF

L'utilisateur dirige une **boîte de consulting** et veut construire une plateforme web interne ("AI Consulting Firm") qui simule une **équipe d'employés IA** dédiée à deux missions :

1. **Market Intelligence & Sales Intel** — détecter des entreprises cibles, scorer leur ICP-fit, identifier des signaux d'opportunité (hiring, leadership change, levée, deal PE/M&A), interpréter ce que la boîte de consulting peut leur apporter.
2. **Médiatisation & Communication** — produire du contenu de marque (posts LinkedIn, études de cas, slides) selon une ligne édito cohérente, prêt à être validé puis publié.

La plateforme doit ressembler à un **bureau virtuel** où chaque "employé IA" a un prénom, un avatar et une spécialité. Un **Manager IA** sert de point d'entrée conversationnel : l'utilisateur lui décrit ce qu'il veut, le Manager identifie le bon agent et route la demande. L'utilisateur peut aussi parler à chaque agent individuellement et consulter son historique.

**Version 1 = locale, gratuite, sans intégrations externes payantes.** Les agents sont des "shells" prompt-ready : leur logique métier est définie (prompt système, capacités, format de sortie) mais les appels à des APIs externes (LinkedIn scraping, news APIs, etc.) sont **mockés**. L'utilisateur veut d'abord valider l'expérience utilisateur et le squelette technique. Les intégrations payantes viendront en V2.

---

## 1. STACK TECHNIQUE IMPOSÉE

**Non négociable :**

- **Backend** : Python 3.11+ avec **FastAPI** (REST + WebSocket)
- **Frontend** : HTML/CSS/JS vanilla + **Tailwind CSS** (CDN) + **Alpine.js** (CDN) pour l'interactivité légère. Pas de framework lourd type React.
- **Base de données** : **SQLite** (fichier `data/app.db`). Schémas via SQLAlchemy 2.0.
- **LLM** : **Anthropic Claude** via le SDK officiel `anthropic`. Modèle par défaut : `claude-sonnet-4-5` (configurable via env).
- **Avatars** : utiliser **DiceBear API** (gratuit, pas de clé) — `https://api.dicebear.com/9.x/personas/svg?seed={name}`
- **Charts dashboard** : **Chart.js** (CDN)
- **Aucun framework JS lourd**, aucune build step. Le frontend doit tourner en ouvrant un HTML servi par FastAPI.

**Pourquoi ces choix :** stack légère, zéro friction setup, parfaitement maîtrisable par un non-dev, déployable sur un Raspberry Pi ou Railway gratuit.

---

## 2. ARCHITECTURE FICHIERS À CRÉER

```
ai-consulting-firm/
│
├── .env.example                  # Template variables d'env
├── .gitignore
├── README.md                     # Setup utilisateur
├── requirements.txt              # Dépendances Python
├── INSTRUCTIONS.md               # Ce fichier (déjà créé)
├── AGENTS.md                     # Fiches des 5 agents + Manager (déjà créé)
│
├── app/
│   ├── __init__.py
│   ├── main.py                   # FastAPI entry point
│   ├── config.py                 # Settings (Pydantic Settings)
│   ├── database.py               # SQLAlchemy engine + session
│   ├── models.py                 # ORM models
│   ├── schemas.py                # Pydantic schemas (API I/O)
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py               # Classe Agent générique
│   │   ├── manager.py            # Le Manager (routeur)
│   │   ├── sarah.py              # Market Intelligence Lead
│   │   ├── lea.py                # ICP Analyst & Interpreter
│   │   ├── marcus.py             # LinkedIn Content Strategist
│   │   ├── tom.py                # Outreach Copywriter
│   │   └── nina.py               # Case Studies & PPT Designer
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── pages.py              # Servir les 3 pages HTML
│   │   ├── chat.py               # POST /api/chat/{agent_id}
│   │   ├── agents.py             # GET /api/agents, GET /api/agents/{id}/history
│   │   ├── intel.py              # GET /api/intel/* (page 3 data)
│   │   └── marketing.py          # GET /api/marketing/* (page 2 data)
│   │
│   └── mocks/
│       ├── __init__.py
│       ├── companies.py          # Fake DB de boîtes cibles
│       ├── signals.py            # Fake signaux marché
│       └── linkedin_drafts.py    # Fake posts LinkedIn générés
│
├── data/
│   └── .gitkeep                  # SQLite DB sera créée ici au runtime
│
├── static/
│   ├── css/
│   │   └── custom.css            # Overrides Tailwind
│   └── js/
│       ├── office.js             # Page 1 — bureau virtuel
│       ├── marketing.js          # Page 2 — dashboard marketing
│       └── intel.js              # Page 3 — dashboard market intel
│
└── templates/
    ├── base.html                 # Layout commun (nav, footer)
    ├── office.html               # Page 1 — les 6 personas + chat manager
    ├── marketing.html            # Page 2 — dashboard marketing
    ├── intel.html                # Page 3 — dashboard market intel
    └── agent_profile.html        # Modal/page profil d'un agent
```

---

## 3. SCHÉMA BASE DE DONNÉES

5 tables, gardées simples. Tout est dans `app/models.py`.

### Table `agents`
- `id` (str, PK) — slug : "manager", "sarah", "lea", "marcus", "tom", "nina"
- `name` (str) — prénom affiché
- `role` (str) — titre du poste
- `avatar_seed` (str) — seed DiceBear
- `system_prompt` (text) — prompt système complet (chargé depuis `AGENTS.md` au seed)
- `color` (str) — code couleur hex pour l'UI
- `status` (str) — "online" / "busy" / "offline" (default "online")
- `created_at` (datetime)

### Table `conversations`
- `id` (int, PK, autoincrement)
- `agent_id` (str, FK → agents.id)
- `title` (str) — auto-généré depuis le premier message
- `created_at` (datetime)
- `updated_at` (datetime)

### Table `messages`
- `id` (int, PK, autoincrement)
- `conversation_id` (int, FK → conversations.id)
- `role` (str) — "user" / "assistant" / "system"
- `content` (text)
- `created_at` (datetime)

### Table `tasks`
- `id` (int, PK, autoincrement)
- `agent_id` (str, FK)
- `title` (str)
- `description` (text)
- `status` (str) — "pending" / "in_progress" / "done" / "blocked"
- `output` (text, nullable) — JSON sérialisé du résultat
- `created_at`, `updated_at` (datetime)

### Table `activity_log`
- `id` (int, PK, autoincrement)
- `agent_id` (str, FK)
- `action` (str) — ex: "analysed_company", "drafted_post", "scored_icp"
- `metadata` (text, JSON) — détails de l'action
- `created_at` (datetime)

---

## 4. LES 3 PAGES DU DASHBOARD — SPECS UI

### Page 1 — `/` — "L'Open Space"

**Layout :**
- Header avec nom de la boîte (placeholder "Consulting AI Firm") et nav vers les 3 pages
- **Section haute (40% hauteur écran) — Le Manager** :
  - Avatar grand format du Manager (centre gauche)
  - Bulle de présentation : "Bonjour, je suis votre Manager. Décrivez ce dont vous avez besoin et je vous oriente vers la bonne personne de l'équipe."
  - Zone de chat principale (centre/droite) : input + bouton "Envoyer" + historique des messages
  - Les réponses du Manager incluent éventuellement un bloc "→ Je transfère ça à **Sarah**" cliquable qui ouvre une conv avec l'agent ciblé
- **Section basse (60%) — L'équipe** :
  - Grille de 5 cartes (Sarah, Léa, Marcus, Tom, Nina)
  - Chaque carte : avatar large (rond), prénom, rôle (1 ligne), statut (point vert "online"), dernière activité (1 ligne, ex: "il y a 12 min — a analysé 3 nouvelles boîtes"), bouton "Parler" (ouvre une conv directe en modal/nouvelle page)
  - Hover : légère élévation, ombre, cursor pointer

### Page 2 — `/marketing` — "Dashboard Marketing & Communication"

**Layout :**
- Sidebar gauche : navigation entre sections (LinkedIn / Case Studies / Website / Outreach)
- Zone principale : 4 sections (toggleables via sidebar)
  - **LinkedIn** :
    - Bloc "Posts en attente de validation" — liste de drafts (mocks au début) avec aperçu, agent qui l'a rédigé (Marcus), boutons ✅ Approuver / ✏️ Éditer / ❌ Rejeter
    - Graphique "Engagement par post (30j)" — Chart.js (line chart, données mockées)
    - KPIs : posts publiés / impressions / engagement rate
  - **Case Studies** :
    - Liste des études de cas existantes (mocks)
    - Bouton "+ Nouvelle étude de cas avec Nina" (ouvre conv Nina)
  - **Site Web** :
    - Liste de pages générées/à générer
    - Statut SEO mocké
  - **Outreach** :
    - Pipeline de mails préparés par Tom
    - Templates par segment ICP

### Page 3 — `/intel` — "Dashboard Market Intelligence"

**Layout :**
- Header : filtres (Pays / Taille / Secteur / Signal type)
- **3 sections :**
  - **Section 1 — Boîtes détectées (table)** :
    - Colonnes : Nom / Pays / Taille / Secteur / Score ICP (0-100) / Dernier signal / Date / "Brief par Léa" (bouton)
    - Tri par score ICP descendant par défaut
    - Données : 15-20 entrées mockées
  - **Section 2 — Signaux récents (timeline)** :
    - Liste verticale chronologique : "Boîte X a recruté un CTO" / "Boîte Y vient de lever 50M€" / etc.
    - Chaque entrée a une couleur selon type de signal
  - **Section 3 — Évolution des résultats (charts)** :
    - Chart 1 : "Boîtes détectées par semaine" (bar chart)
    - Chart 2 : "Distribution par secteur" (pie chart)
    - Chart 3 : "Score ICP moyen dans le temps" (line chart)

---

## 5. SYSTÈME DE CHAT (cœur fonctionnel)

### Endpoints API

- `GET /api/agents` → liste des 6 agents avec status
- `GET /api/agents/{id}` → profil détaillé + dernières activités
- `GET /api/agents/{id}/conversations` → liste des convs avec cet agent
- `GET /api/conversations/{conv_id}/messages` → messages d'une conv
- `POST /api/chat/{agent_id}` → body `{conversation_id?: int, message: str}` → réponse de l'agent (streamée en SSE si possible, sinon JSON simple en V1)

### Logique d'une réponse d'agent

1. Récupérer ou créer la conversation (par `conversation_id` ou auto-créée).
2. Insérer le message user dans `messages`.
3. Charger le `system_prompt` de l'agent depuis sa fiche.
4. Construire l'historique pour Claude (system + messages).
5. **Cas spécial Manager** : son prompt système contient les fiches synthétiques des 5 autres agents et l'instruction "Si la demande relève clairement d'un agent, termine ta réponse par `[ROUTE_TO: agent_id]`". Le frontend détecte ce tag et affiche un bouton de routage.
6. Appeler `client.messages.create(...)` avec le SDK Anthropic.
7. Stocker la réponse dans `messages`.
8. Logger dans `activity_log` (action = "responded_to_user", metadata = {tokens, model}).
9. Renvoyer la réponse au front.

### Streaming (optionnel V1, mais propre à faire)

Endpoint SSE `POST /api/chat/{agent_id}/stream`. Côté JS, utiliser `EventSource` ou `fetch` avec `ReadableStream`. Si tu galères, fallback sur du JSON synchrone.

---

## 6. CAPACITÉS "MOCK" DES AGENTS

Chaque agent doit avoir au moins **une capacité simulée** qui produit un output structuré, pour qu'on voie le système "vivre" dès la V1 :

- **Sarah** : commande `/scan` dans son chat → renvoie 3 boîtes "détectées" depuis `mocks/companies.py`, les insère dans la DB (table `tasks`) et log l'action.
- **Léa** : commande `/score [company_name]` → renvoie un score ICP + interprétation textuelle (générée par Claude avec son prompt).
- **Marcus** : commande `/draft_post [topic]` → renvoie 2 propositions de post LinkedIn (générées par Claude).
- **Tom** : commande `/email [company_name]` → renvoie un draft de mail outbound personnalisé.
- **Nina** : commande `/case_study [client_name]` → renvoie une structure d'étude de cas (titre, problème, approche, résultat).

Les capacités sont déclenchées par des **slash commands** dans le chat. Le prompt système de chaque agent doit mentionner ces commandes et leur format de sortie.

---

## 7. PHASES D'IMPLÉMENTATION — ORDRE STRICT

**Phase 1 — Squelette tech (objectif : "ça démarre")**
- Setup repo, requirements.txt, .env.example
- `app/main.py` qui sert "Hello World" sur `/`
- `app/database.py` qui crée le SQLite au démarrage
- `app/models.py` avec les 5 tables
- Un script `seed.py` qui peuple la table `agents` à partir de `AGENTS.md`
- **VALIDATION UTILISATEUR** avant phase 2

**Phase 2 — Le Manager fonctionnel**
- `app/agents/base.py` (classe Agent)
- `app/agents/manager.py` avec son system prompt
- Endpoint `POST /api/chat/manager`
- Page 1 minimale : juste le chat avec le Manager qui marche
- **VALIDATION UTILISATEUR**

**Phase 3 — Les 5 agents + routage**
- Implémenter les 5 fichiers agents avec leur prompt
- Endpoint `POST /api/chat/{agent_id}` générique
- Détection `[ROUTE_TO: x]` dans réponses Manager, bouton dans UI
- Cartes des agents sur la page 1, chat direct possible
- **VALIDATION UTILISATEUR**

**Phase 4 — Slash commands & activity log**
- Parsing des commands dans `chat.py`
- Insertion dans `tasks` et `activity_log`
- Affichage "dernière activité" sur cartes agents
- Page profil agent (historique + activités)
- **VALIDATION UTILISATEUR**

**Phase 5 — Page 2 Marketing (avec mocks)**
- Template + JS + endpoints
- Données mockées dans `app/mocks/`
- Charts via Chart.js
- **VALIDATION UTILISATEUR**

**Phase 6 — Page 3 Market Intel (avec mocks)**
- Idem phase 5 pour la page Intel
- **VALIDATION UTILISATEUR**

**Phase 7 — Polish**
- Animations subtiles, états de chargement, error handling
- README complet avec setup pas-à-pas
- Script `make setup && make run` (Makefile)

**À chaque phase**, à la fin, tu fais un récap court de ce que tu as livré et tu attends "ok" avant de continuer.

---

## 8. RÈGLES DE CODE NON NÉGOCIABLES

1. **Pas de dépendances inutiles.** Si une lib n'est pas dans `requirements.txt`, justifie-la avant de l'ajouter.
2. **Type hints partout** sur les fonctions publiques.
3. **Pas de magic strings** pour les IDs d'agents — utiliser un Enum dans `config.py`.
4. **Secrets via env uniquement** (clé Anthropic). Jamais en dur. `.env.example` documente toutes les variables.
5. **Logs structurés** (module `logging` standard, format simple `[LEVEL] [agent_id] message`).
6. **Erreurs propres** : si l'API Anthropic plante, l'utilisateur voit un message clair, pas une stack trace.
7. **Pas de framework JS lourd.** HTML servi par Jinja2 + Alpine.js pour la réactivité légère.
8. **Tailwind via CDN** (`https://cdn.tailwindcss.com`) — pas de build PostCSS pour la V1.
9. **CSS responsive** : tout doit marcher sur desktop (priorité) et passable sur mobile.
10. **Commits propres** : un commit par phase, message explicite.

---

## 9. CE QU'IL FAUT DIRE À L'UTILISATEUR AU DÉMARRAGE

Quand tu démarres la session Claude Code dans son terminal, ton **premier message** doit être :

```
J'ai lu INSTRUCTIONS.md et AGENTS.md.

Plan d'implémentation (7 phases, ~6-10h de travail itératif) :
1. Squelette tech (45 min)
2. Manager fonctionnel (1h)
3. Les 5 agents + routage (1h30)
4. Slash commands & activity log (1h)
5. Page Marketing avec mocks (1h30)
6. Page Market Intel avec mocks (1h30)
7. Polish & README (30 min)

Avant de commencer, j'ai besoin que tu confirmes :
- (a) Tu as une clé API Anthropic prête à mettre dans .env ?
- (b) Tu veux que le projet tourne sur quel port (default: 8000) ?
- (c) Tu valides le stack imposé (FastAPI + Tailwind + Alpine + SQLite) ?

Si oui à tout, je lance la Phase 1.
```

**Ne lance pas la Phase 1 sans validation explicite.**

---

## 10. CONTRAINTES DE SCOPE — CE QUE TU NE FAIS PAS EN V1

❌ Pas d'authentification (single-user local)
❌ Pas de vraie intégration LinkedIn / Gmail / etc. — tout est mocké
❌ Pas de déploiement cloud — local seulement
❌ Pas de scheduler/cron en V1 — l'agent agit quand on lui parle
❌ Pas de génération de vrais .pptx en V1 (Nina renvoie une structure texte, la génération PPT viendra plus tard)
❌ Pas de multi-tenant ni de gestion de rôles
❌ Pas de tests unitaires en V1 — focus sur l'expérience utilisateur fonctionnelle

Si l'utilisateur demande l'une de ces features pendant l'implémentation, tu réponds : "Hors scope V1, à noter pour V2. On continue ?"

---

## 11. FIN DE BRIEF

Tu as maintenant tout le contexte. Lis `AGENTS.md` pour le détail des 6 personas, puis applique la séquence d'ouverture définie en section 9.

**Go.**
