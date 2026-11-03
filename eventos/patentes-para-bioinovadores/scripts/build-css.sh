#!/bin/sh

set -eu

cd "$(dirname "$0")/.."

output_tmp="$(mktemp "${TMPDIR:-/tmp}/evento-main-compat.XXXXXX")"
normalized_index_tmp="$(mktemp "${TMPDIR:-/tmp}/evento-index-normalized.XXXXXX")"
hashes_tmp="$(mktemp "${TMPDIR:-/tmp}/evento-hashes.XXXXXX")"
index_tmp="$(mktemp "${TMPDIR:-/tmp}/evento-index.XXXXXX")"
version_tmp="$(mktemp "${TMPDIR:-/tmp}/evento-version.XXXXXX")"
cleanup() {
  rm -f "$output_tmp" "$normalized_index_tmp" "$hashes_tmp" "$index_tmp" "$version_tmp"
}
trap cleanup EXIT INT TERM

# O fallback manual serve apenas ao main.css aberto diretamente. No artefato
# compilado ele seria redundante e poderia sobrescrever a composição completa.
sed '/^\/\* compat-fallback:start \*\/$/,$d' assets/css/main.css |
  BROWSERSLIST='Safari >= 13.1, iOS >= 13.4, Chrome >= 80, Firefox >= 78' \
    npx --yes \
      --package postcss-cli@11.0.1 \
      --package postcss-preset-env@10.6.1 \
      postcss --use postcss-preset-env --no-map --output "$output_tmp"

chmod 644 "$output_tmp"
mv "$output_tmp" assets/css/main.compat.css

# Normaliza os valores gerados antes de calcular a versão. Assim o hash inclui
# HTML, CSS, JavaScript e imagens, mas continua idempotente entre dois builds.
sed -E \
  -e 's/data-site-version="[^"]+"/data-site-version="SITE_VERSION"/' \
  -e 's#(assets/(css/main\.compat\.css|js/main\.js|js/dna\.js|img/[a-z0-9-]+\.(svg|png))\?v=)[^"]+#\1SITE_VERSION#g' \
  index.html > "$normalized_index_tmp"

find assets -type f -print | LC_ALL=C sort | while IFS= read -r asset_file; do
  shasum -a 256 "$asset_file" | cut -d ' ' -f1
done > "$hashes_tmp"
shasum -a 256 "$normalized_index_tmp" | cut -d ' ' -f1 >> "$hashes_tmp"
site_hash="$(shasum -a 256 "$hashes_tmp" | cut -c1-10)"

# Atualiza todos os recursos críticos e a versão embutida em uma única passada.
# As expressões são compatíveis com o sed do macOS e não acumulam parâmetros.
sed -E \
  -e "s/data-site-version=\"[^\"]+\"/data-site-version=\"${site_hash}\"/" \
  -e "s#(assets/(css/main\.compat\.css|js/main\.js|js/dna\.js|img/[a-z0-9-]+\.(svg|png))\?v=)[^\"]+#\1${site_hash}#g" \
  index.html > "$index_tmp"
chmod 644 "$index_tmp"
mv "$index_tmp" index.html

printf '{"version":"%s"}\n' "$site_hash" > "$version_tmp"
chmod 644 "$version_tmp"
mv "$version_tmp" version.json
trap - EXIT INT TERM
