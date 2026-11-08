#!/bin/sh
# Confere o build: roda duas vezes e compara os arquivos gerados.
# - Falha se o segundo build mudar algo (build não idempotente).
# - Falha se o primeiro build mudar algo (os arquivos gerados estavam
#   desatualizados em relação a main.css, aos scripts ou às imagens); nesse
#   caso eles já ficam regenerados e é só fazer o commit.
set -eu

cd "$(dirname "$0")/.."

snapshot() {
  shasum -a 256 assets/css/main.compat.css index.html version.json
}

before="$(snapshot)"
sh scripts/build-css.sh
first="$(snapshot)"
sh scripts/build-css.sh
second="$(snapshot)"

if [ "$first" != "$second" ]; then
  echo "check-build: o build não é idempotente (dois builds seguidos deram resultados diferentes)" >&2
  exit 1
fi
if [ "$before" != "$first" ]; then
  echo "check-build: os arquivos gerados estavam desatualizados e foram regenerados; faça o commit deles" >&2
  exit 1
fi
echo "check-build: arquivos gerados em dia e build idempotente"
node scripts/check-css.cjs
