#!/bin/sh
# Gera assets/css/main.compat.css a partir de assets/css/main.css, atualiza as
# versões (?v=) no index.html e escreve version.json.
#
# Reproduzível: as dependências têm versões fixas no package.json e no
# package-lock.json (instaladas com npm ci), e os navegadores-alvo ficam no
# campo "browserslist" do package.json.
# Atômico: tudo é gerado em arquivos temporários; os originais só são
# substituídos no fim, depois que todas as etapas passaram.
set -eu

cd "$(dirname "$0")/.."

if [ ! -x node_modules/.bin/postcss ]; then
  npm ci --no-audit --no-fund --loglevel=error
fi

css_tmp="$(mktemp "${TMPDIR:-/tmp}/evento-main-compat.XXXXXX")"
normalized_index_tmp="$(mktemp "${TMPDIR:-/tmp}/evento-index-normalized.XXXXXX")"
hashes_tmp="$(mktemp "${TMPDIR:-/tmp}/evento-hashes.XXXXXX")"
index_tmp="$(mktemp "${TMPDIR:-/tmp}/evento-index.XXXXXX")"
version_tmp="$(mktemp "${TMPDIR:-/tmp}/evento-version.XXXXXX")"
cleanup() {
  rm -f "$css_tmp" "$normalized_index_tmp" "$hashes_tmp" "$index_tmp" "$version_tmp"
}
trap cleanup EXIT INT TERM

# 1. CSS compilado (lê o arquivo direto, sem pipe: um erro sempre interrompe).
node_modules/.bin/postcss assets/css/main.css --use postcss-preset-env --no-map --output "$css_tmp"
if [ ! -s "$css_tmp" ]; then
  echo "build-css: o CSS compilado saiu vazio" >&2
  exit 1
fi

# Recursos com ?v= no index.html: CSS, scripts e imagens (inclusive as fotos e
# os logos em subpastas de img/).
versioned='(assets/(css/main\.compat\.css|js/head\.js|js/main\.js|js/dna\.js|img/[a-z0-9/-]+\.(svg|png|webp))\?v=)'

# 2. Versão: hash de todos os arquivos de assets/ (com o CSS novo no lugar do
# atual) e do index.html com as versões neutralizadas. Idempotente: dois
# builds seguidos dão a mesma versão. Arquivos .DS_Store não entram.
sed -E \
  -e 's/data-site-version="[^"]+"/data-site-version="SITE_VERSION"/' \
  -e 's#'"$versioned"'[^"]+#\1SITE_VERSION#g' \
  index.html > "$normalized_index_tmp"

find assets -type f ! -name '.DS_Store' -print | LC_ALL=C sort | while IFS= read -r asset_file; do
  if [ "$asset_file" = "assets/css/main.compat.css" ]; then
    shasum -a 256 "$css_tmp"
  else
    shasum -a 256 "$asset_file"
  fi | cut -d ' ' -f1
done > "$hashes_tmp"
shasum -a 256 "$normalized_index_tmp" | cut -d ' ' -f1 >> "$hashes_tmp"
site_hash="$(shasum -a 256 "$hashes_tmp" | cut -c1-10)"

# 3. index.html e version.json com a versão nova.
sed -E \
  -e "s/data-site-version=\"[^\"]+\"/data-site-version=\"${site_hash}\"/" \
  -e 's#'"$versioned"'[^"]+#\1'"${site_hash}"'#g' \
  index.html > "$index_tmp"
printf '{"version":"%s"}\n' "$site_hash" > "$version_tmp"

# 4. Só agora substitui os arquivos, todos de uma vez.
chmod 644 "$css_tmp" "$index_tmp" "$version_tmp"
mv "$css_tmp" assets/css/main.compat.css
mv "$index_tmp" index.html
mv "$version_tmp" version.json
trap - EXIT INT TERM
cleanup
