#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# share.sh — met l'app en ligne sur un LIEN PUBLIC gratuit (Cloudflare tunnel).
#
#   ./share.sh
#
# Donne une URL https://….trycloudflare.com à partager avec l'équipe.
# Chacun se connecte : choisit son prénom + mot de passe d'équipe (TPDL).
#
# ⚠️  Le lien marche TANT QUE cette fenêtre reste ouverte et que ton Mac est
#     allumé. Ferme la fenêtre (Ctrl+C) = le lien s'éteint. À chaque relance,
#     l'URL trycloudflare change (lien gratuit, non permanent).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

# Charger le .env dans l'environnement (gate d'auth + clés) — auth.py lit os.environ.
set -a; [ -f .env ] && . ./.env; set +a
PORT="${PORT:-8000}"

# venv
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true

APP_PID=""
cleanup() { [ -n "$APP_PID" ] && kill "$APP_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

if lsof -ti:"$PORT" >/dev/null 2>&1; then
  echo "▶ App déjà lancée sur le port $PORT."
else
  echo "▶ Démarrage de l'app sur le port $PORT…"
  python -m uvicorn app.main:app --port "$PORT" --log-level warning &
  APP_PID=$!
  for _ in $(seq 1 40); do
    lsof -ti:"$PORT" >/dev/null 2>&1 && break
    sleep 0.5
  done
fi

echo
echo "▶ Ouverture du lien public (Cloudflare)…"
echo "   → Partage l'URL https://….trycloudflare.com affichée ci-dessous."
echo "   → Connexion : prénom + mot de passe  TPDL"
echo "   → Garde cette fenêtre ouverte tant que l'équipe l'utilise."
echo
cloudflared tunnel --url "http://localhost:$PORT"
