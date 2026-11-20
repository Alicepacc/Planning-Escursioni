#!/usr/bin/env bash
# Pubblica la demo di Cordata su GitHub Pages (branch gh-pages, autorizzato dall'utente il
# 16/11/2026). Il branch contiene solo il sito costruito, senza cronologia: ogni pubblicazione
# lo sostituisce, così il repository non cresce a ogni aggiornamento dei dati.
#
# Prerequisiti: dati e tile generati dalla pipeline (services/ingest, `build all`).
# Uso: scripts/deploy-gh-pages.sh
# Indirizzo: https://alicepacc.github.io/Planning-Escursioni/
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
WEB="$ROOT/apps/web"
BASE_PATH=/Planning-Escursioni
# servizio delle uscite di gruppo (services/outings, pubblicato su Cloudflare il 20/11/2026):
# indirizzo pubblico, non un segreto. Con USCITE_API= vuoto la demo lo dà per non attivo.
USCITE_API=${USCITE_API-https://cordata-uscite.cordata.workers.dev}

if [ ! -f "$WEB/static/data/sentieri/index.json" ] || [ ! -f "$WEB/static/tiles/pilota.pmtiles" ]; then
	echo "Mancano dati o tile in apps/web/static: esegui prima la pipeline di services/ingest." >&2
	exit 1
fi

(cd "$WEB" && BASE_PATH=$BASE_PATH VITE_USCITE_API=$USCITE_API pnpm run build)

WORK=$(mktemp -d)
trap 'git -C "$ROOT" worktree remove --force "$WORK" 2>/dev/null || true; git -C "$ROOT" branch -D gh-pages-pubblicazione 2>/dev/null || true' EXIT
git -C "$ROOT" worktree add --detach "$WORK" >/dev/null
cd "$WORK"
git checkout -q --orphan gh-pages-pubblicazione
git rm -rf -q . >/dev/null
cp -a "$WEB/build/." .
touch .nojekyll # senza, GitHub Pages (Jekyll) ignora la cartella _app
git add -A
git commit -q -m "Demo Cordata: build del $(date -u +%Y-%m-%d)"
git push -q -f origin HEAD:gh-pages
echo "Pubblicato su gh-pages: https://alicepacc.github.io$BASE_PATH/"
