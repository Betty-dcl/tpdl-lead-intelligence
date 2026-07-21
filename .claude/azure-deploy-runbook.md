# Déploiement Azure — TPDL Lead Intelligence (app web partagée, multi‑utilisateurs)

> But : passer du `localhost:8000` (Mac de Betty) à une **vraie app web** sur une URL HTTPS,
> solide pour plusieurs personnes en même temps, avec **mot de passe d'équipe** (pas de rôles).
> Hébergement : **Azure App Service (conteneur Docker)** + **Azure Database for PostgreSQL**.
> Les commandes se lancent avec le compte Azure de TPDL (Betty / Alfredo qui a les codes).

## Pourquoi cette architecture
- **Conteneur Docker** (`Dockerfile` à la racine) : build reproductible, pas de surprise de build Azure.
- **1 worker uvicorn** (voir note dans le `Dockerfile`) : l'app a un scheduler APScheduler + un état
  WebSocket en mémoire ; plusieurs workers dupliqueraient les jobs et fragmenteraient le temps réel.
  Un worker async sert largement toute l'équipe pour cette charge (490 sociétés, ~5‑15 personnes).
- **PostgreSQL** au lieu de SQLite : SQLite sur le disque réseau d'App Service se corrompt en écriture
  concurrente. Postgres = le choix « solide multi‑utilisateurs ». L'app est **déjà prête** : elle lit
  `DATABASE_URL` et la couche DB gère les deux dialectes (`app/database.py`). Rien à recoder.

## Variables d'environnement (App Settings Azure)
| Variable | Valeur | Note |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://USER:PASS@HOST:5432/tpdl?sslmode=require` | Postgres Azure |
| `TPDL_AUTH_GATE` | `on` | active le login équipe |
| `TPDL_TEAM_PASSWORD` | *(un vrai mot de passe)* | 🔴 pas « TPDL » |
| `TPDL_SESSION_SECRET` | *(64 hex aléatoires)* | `python -c "import secrets;print(secrets.token_hex(32))"` — fige les sessions |
| `WEBSITES_PORT` | `8000` | dit à Azure sur quel port le conteneur écoute |
| `ANTHROPIC_API_KEY` | *(clé)* | chat des agents |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | modèle chat |
| *(autres clés)* | SERPER/EXA/PERPLEXITY/FIRECRAWL/APIFY… | seulement si on lance des runs depuis l'app |

> 🔴 Ne jamais committer ces valeurs. Elles se saisissent dans Azure (Portal → Configuration, ou `az`).

## Étapes (Azure CLI)

```bash
# 0. Pré‑requis : az login ; choisir l'abonnement TPDL
az login
az account set --subscription "<TPDL subscription>"

RG=tpdl-intel-rg
LOC=westeurope
PLAN=tpdl-intel-plan
APP=tpdl-intel                     # → https://tpdl-intel.azurewebsites.net
PG=tpdl-intel-db
ACR=tpdlintelacr                   # registre d'images (nom global unique, minuscules)

# 1. Groupe de ressources
az group create -n $RG -l $LOC

# 2. PostgreSQL Flexible Server (burstable, le moins cher ; ~12‑20 €/mois)
az postgres flexible-server create -g $RG -n $PG -l $LOC \
  --tier Burstable --sku-name Standard_B1ms --storage-size 32 \
  --admin-user tpdladmin --admin-password '<MOT_DE_PASSE_DB>' \
  --version 16 --public-access 0.0.0.0   # autorise les services Azure ; restreindre ensuite
az postgres flexible-server db create -g $RG -s $PG -d tpdl

# 3. Registre + build de l'image (build côté Azure, pas besoin de Docker local)
az acr create -g $RG -n $ACR --sku Basic --admin-enabled true
az acr build -r $ACR -t tpdl-intel:latest .

# 4. Plan Linux + Web App conteneur
az appservice plan create -g $RG -n $PLAN --is-linux --sku B1
az webapp create -g $RG -p $PLAN -n $APP \
  --deployment-container-image-name $ACR.azurecr.io/tpdl-intel:latest

# 5. Variables d'environnement (voir tableau ci‑dessus)
az webapp config appsettings set -g $RG -n $APP --settings \
  DATABASE_URL="postgresql+psycopg://tpdladmin:<MOT_DE_PASSE_DB>@$PG.postgres.database.azure.com:5432/tpdl?sslmode=require" \
  TPDL_AUTH_GATE=on \
  TPDL_TEAM_PASSWORD='<MOT_DE_PASSE_EQUIPE>' \
  TPDL_SESSION_SECRET='<64_HEX>' \
  WEBSITES_PORT=8000 \
  ANTHROPIC_API_KEY='<clé>' ANTHROPIC_MODEL=claude-opus-4-8

az webapp restart -g $RG -n $APP
```

Au premier démarrage, `init_db()` crée le schéma vide dans Postgres. Il reste à **charger les données**.

## Amorçage des données (une seule fois, vers Postgres)
Depuis le Mac (ou une Cloud Shell), en pointant `DATABASE_URL` vers le Postgres Azure :

```bash
export DATABASE_URL="postgresql+psycopg://tpdladmin:<PASS>@<PG>.postgres.database.azure.com:5432/tpdl?sslmode=require"
python seed.py                                   # prompts système des 9 agents + users
python import_csv.py data/csv/<dernier_run>.csv  # les sociétés scorées → table companies
python backfill_snapshots.py                     # amorce l'historique des runs (idempotent)
```

> Les utilisateurs de connexion (Marie, Pierre, Sophie, Léa, Tomás) sont semés par `seed.py`.
> Chacun choisit son nom et tape le `TPDL_TEAM_PASSWORD`. Mêmes droits pour tous (décision : pas de rôles).

## Mise à jour de l'app (à chaque nouvelle version)
```bash
az acr build -r $ACR -t tpdl-intel:latest .
az webapp restart -g $RG -n $APP
```

## Vérifs post‑déploiement
- `https://tpdl-intel.azurewebsites.net/healthz` → 200
- La page de login demande le mot de passe équipe (gate ON).
- `/intel` charge le cockpit + les filtres (localisation, comparaison de runs, Top‑N).
- 2 personnes connectées en même temps : claim/commentaire de l'une visible par l'autre (Postgres partagé).

## Durcissement (après le premier essai)
- Restreindre l'accès réseau Postgres (retirer `0.0.0.0`, garder « Allow Azure services »).
- HTTPS only : `az webapp update -g $RG -n $APP --https-only true`.
- Plus tard : login **Microsoft SSO** (Azure AD) à la place du mot de passe partagé — l'app est chez
  Microsoft (SharePoint/Teams), donc c'est le prolongement naturel. À faire quand le mot de passe
  d'équipe montrera ses limites.
```
