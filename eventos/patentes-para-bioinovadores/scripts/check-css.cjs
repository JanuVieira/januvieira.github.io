// Aponta declarações mortas em assets/css/main.css: a mesma propriedade, no
// mesmo seletor e no mesmo contexto (camada, @media, @supports, aninhamento),
// declarada de novo mais adiante, em outro bloco. A última sempre vence, então
// a anterior nunca se aplica. É o sinal de uma correção anulada por outra
// regra centenas de linhas depois. Repetições dentro do mesmo bloco
// (fallbacks) e !important só na anterior não contam.
// Uso: node scripts/check-css.cjs   (sai com erro se encontrar alguma)
const fs = require('fs');
const path = require('path');
const postcss = require('postcss');

const file = path.join(__dirname, '..', 'assets/css/main.css');
const root = postcss.parse(fs.readFileSync(file, 'utf8'), { from: file });
const norm = (value) => value.replace(/\s+/g, ' ').trim();
const context = (node) => {
  const chain = [];
  for (let parent = node.parent; parent && parent.type !== 'root'; parent = parent.parent) {
    chain.unshift(parent.type === 'atrule' ? `@${parent.name} ${norm(parent.params)}` : norm(parent.selector));
  }
  return chain.join(' » ');
};

const groups = new Map();
root.walkDecls((decl) => {
  const key = `${context(decl)} | ${decl.prop.toLowerCase()}`;
  if (!groups.has(key)) groups.set(key, []);
  groups.get(key).push(decl);
});

const dead = [];
for (const [key, decls] of groups) {
  decls.forEach((decl, index) => {
    const winner = decls.slice(index + 1).find((later) => later.parent !== decl.parent);
    if (!winner || (decl.important && !winner.important)) return;
    dead.push(`  linha ${decl.source.start.line} (vence a ${winner.source.start.line}): ${key}`);
  });
}

if (dead.length) {
  console.error(`check-css: ${dead.length} declaração(ões) morta(s) em main.css:\n${dead.join('\n')}`);
  process.exit(1);
}
console.log('check-css: nenhuma declaração morta em main.css');
