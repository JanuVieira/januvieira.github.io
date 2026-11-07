# Patentes para Bioinovadores

Site de uma página do curso **Patentes para Bioinovadores** (CGDI/INPI), de 3 a 19 de novembro de 2026.

HTML, CSS e JavaScript puros. Todo o site usa Schibsted Grotesk e IBM Plex Mono (Google Fonts).

Sirva o projeto por HTTP para que carregamento, cache e comportamento dos scripts sejam reproduzidos corretamente:

```sh
python3 -m http.server 5501
```

Depois, acesse `http://localhost:5501`. O Live Server do VS Code também pode ser usado. Evite abrir o projeto por `file://`.

## Estrutura

```
index.html                    Página única, com as seções em ordem
assets/
  css/main.css                Fonte editável dos estilos em camadas
  css/main.compat.css         CSS compilado e servido aos navegadores
  js/main.js                  Menu do celular, carrossel do cronograma, confirmação de inscrição, cards de objetivos e cursor seguidor
  js/dna.js                   Animação 3D da hélice de DNA no hero (canvas)
  img/logo.svg                Favicon: logo do INPI em branco sobre quadrado azul (visível em abas claras e escuras)
  img/favicon-32.png          Favicon em PNG para navegadores sem suporte a SVG (Safari)
  img/apple-touch-icon.png    Ícone da tela inicial do iPhone/iPad (180×180, sem cantos arredondados)
  img/og-image.png            Prévia de compartilhamento (WhatsApp, LinkedIn etc.), 1200×630
  img/icons/                  Ícones do conteúdo programático (traço, 32×32)
  img/palestrantes/           Fotos dos palestrantes (quadradas)
  img/empresas/               Logos das empresas convidadas (fundo branco, recortados)
```

Seções do `index.html`: hero, 01 Conteúdo programático, 02 Objetivos (geral, público-alvo e específicos em cartões), 03 Cronograma, 04 Palestrantes e 05 Dúvidas.

## Paleta

Definida no topo de `assets/css/main.css`:

| Cor | Uso |
| --- | --- |
| Cobalto `#1c40ce` | Cor dominante: hero, cronograma, títulos em destaque, ícones |
| Lima `#d3f76e` | Único destaque: painel de datas, dia selecionado, "Próximo encontro", chips de instituição |
| Azul-marinho `#10131e` | Texto e rodapé |
| Papel `#f4f5ef` e branco | Fundos das seções claras, alternados |
| Vermelho `#ff3b30` | Só o ponto de "ao vivo" |

## Como editar

### Cores, fontes e espaçamentos

As variáveis ficam no topo de `assets/css/main.css` (`@layer tokens`). Os componentes usam a mesma escala em todo o site.

Faixas responsivas:

| Consulta | Uso principal |
| --- | --- |
| até `360px` | Ajustes para celulares muito estreitos |
| até `374px` | Card compacto dos palestrantes (foto de 76px), para os temas caberem em duas linhas |
| até `430px` | Controles e tipografia em celulares estreitos |
| até `480px` | Composição compacta e fallback de compatibilidade |
| até `599px` / `600–767px` | Variações do hero e conteúdo em celulares |
| até `767px` | Composição mobile geral |
| `768–1023px` | Tablets |
| a partir de `1024px` | Desktop |
| até `1023px` e altura até `500px` | Celulares e tablets em paisagem |
| até `599px`, altura até `500px` e paisagem | Paisagem muito estreita |

Os breakpoints usam `min-width`/`max-width` para compatibilidade com WebViews e versões anteriores do Safari. O navegador carrega `main.compat.css`, que já contém toda a composição com seletores planos e sem dependência de CSS nesting ou cascade layers.

Depois de alterar `assets/css/main.css`, regenere o arquivo usado pelo site:

```sh
sh scripts/build-css.sh
```

Não edite `main.compat.css` diretamente: ele é um artefato gerado. O fallback no fim de `main.css` existe apenas para inspeção direta do arquivo-fonte e é excluído da compilação para não duplicar regras.
O build também aplica permissão `644`, atualiza o hash curto dos recursos críticos em `index.html` e gera `version.json`. A página consulta esse manifesto sem cache e recarrega uma vez quando detecta uma publicação mais recente no GitHub Pages.

Não há build automático no GitHub: rode `sh scripts/build-css.sh` antes de cada commit. O GitHub Pages publica os arquivos do repositório como estão, inclusive `main.compat.css`, os hashes em `index.html` e `version.json`.

Escala de espaço: `--space-1` (4px), `--space-2` (8px), `--space-3` (12px), `--space-4` (16px), `--space-5` (20px), `--space-6` (24px), `--space-8` (32px), `--space-10` (40px), `--space-12` (48px), `--space-14` (56px), `--space-16` (64px), `--space-20` (80px) e `--space-24` (96px).

| Tipo | Tamanho | Uso |
| --- | --- | --- |
| `--fs-label` | 12px | Eyebrows, chips e rótulos mono |
| `--fs-small` | 14px | Metadados, notas e tópicos |
| `--fs-ui` | 15px | Botões, links e abas |
| `--fs-body` | 16–17px | Texto corrido |
| `--fs-lead` | 18–22px | Textos de destaque |
| `--fs-h4` | 18–22px | Cards, aulas e nomes |
| `--fs-h3` | 22–32px | Subtítulos e perguntas |
| `--fs-h2` | 34–72px | Títulos de seção |
| `--fs-display` | até 72px | Nome do curso no hero |
- **Links de aula:** cada `.day__actions` tem um único botão, “Assistir aula”, do tamanho do rótulo no tablet e desktop e na largura do card no celular; enquanto não tem endereço, fica desabilitado com o estado “Em breve”. Quando os endereços oficiais chegarem, substitua cada `<button disabled>` por um `<a href="…">`, preservando as classes e o conteúdo, troque “Em breve” pelo destino (ex.: “Via Zoom”, como no Encontro 1) e atualize o `aria-label`. Para links externos, use também `target="_blank"`, `rel="noopener noreferrer"` e informe no `aria-label` que o destino abre em nova aba. O formulário oficial de inscrição já está conectado ao hero, à nota do cronograma e ao FAQ.
- **Confirmação de inscrição:** links de aula com o atributo `data-requires-enrollment` abrem antes o diálogo `.enrollment-dialog`, que pergunta se a pessoa já se inscreveu. Ela escolhe entre duas opções (rádios nativos estilizados como cartões) e o único botão, “Continuar”, só é liberado depois da escolha: com “Sim, já me inscrevi” ele vira “Entrar na aula” (abre o endereço do próprio link); com “Ainda não me inscrevi”, vira “Ir para a inscrição” (abre o formulário e mantém o diálogo aberto, com um aviso para voltar e entrar). Ao entrar, a resposta fica salva no `localStorage` daquele navegador e as próximas aulas abrem direto. No tablet e desktop o diálogo é centralizado; no celular, é um painel inferior com as opções empilhadas; em celulares deitados, as opções ficam lado a lado. Ctrl/Cmd + clique e navegadores sem `<dialog>` abrem a aula diretamente. Para ativar nos próximos encontros, basta adicionar `data-requires-enrollment` ao novo `<a>`.
- **Biografias dos palestrantes:** no celular, “Abrir biografia” expande o conteúdo em linha e mantém somente uma biografia aberta. Em tablets e desktops, o mesmo controle abre um diálogo de leitura que aceita textos extensos sem alterar a grade. Coloque o conteúdo dentro de `.speaker__bio-content`, preferencialmente em dois ou três parágrafos; quando o texto oficial chegar, substitua a mensagem e remova `speaker__bio--pending`.
- **Fotos dos palestrantes:** a área de retrato permanece quadrada (1:1) em desktop, tablet e celular, sem alongamento pela altura do texto. Salve em `assets/img/palestrantes/` com nome em minúsculas e hífens (ex.: `paula-adamis.jpg`), em formato quadrado. Dentro de `.speaker__art`, adicione `<img src="assets/img/palestrantes/nome.jpg" alt="" width="800" height="800" loading="lazy" decoding="async" />`. A foto cobre as iniciais.
- **Grade de palestrantes:** com dez itens, a grade fica 5 × 2 a partir de 1200px; entre 1024 e 1199px, usa quatro colunas e centraliza a última dupla; no tablet, 2 × 5; no celular, uma coluna. O `main.js` aplica `speakers--nine` ou `speakers--ten` conforme a quantidade de cards, e a regra de nove (3 × 3, último card centralizado no tablet) continua disponível. A Dra. Stefania Palma Araujo ainda não tem foto e o card mostra as iniciais. Os cards seguem a ordem do cronograma; quando um palestrante muda de dia, mova o card e atualize a data em `.speaker__meta`.
- **Empresas convidadas:** a aula de uma empresa usa `<li class="lesson lesson--company">` e segue o formato das outras (horário, título e `.lesson__speaker`). A apresentação fica num `<details class="lesson__topics">` com “Conhecer a startup” / “Fechar apresentação”: dentro de `.lesson__about`, o logo (`<img class="lesson__logo">`, de `img/empresas/`) vem primeiro, acima do texto e alinhado a ele, sem moldura, e só aparece quando a pessoa abre. Salve o logo recortado rente ao desenho: a largura (144px no tablet e desktop, 120px no celular) define a altura. O `main.js` anima esse bloco como os tópicos. Exemplo: Inovafhytos Cerrado, no Encontro 4. O horário do Encontro 3 (16h às 17h) continua como “Empresa a confirmar”.
- **Nomes e temas em duas linhas:** em cada card, o `<h3>` e o `.speaker__topic` têm dois `<span>`, um por linha, separados por um espaço (ex.: `<h3><span>Dra. Tatiana</span> <span>Carestiato</span></h3>`). Nos nomes, a 1ª linha leva o título e o prenome (“Dra. Tatiana”); com “Profa. Dra.”, o título fica sozinho na 1ª linha. Os temas são versões curtas dos títulos das aulas; o título completo continua no cronograma. Cada linha deve caber em cerca de 190px (celular de 375px, fonte de 15px): a linha mais longa hoje é “Limites de patenteabilidade”. Abaixo de 360px, uma linha longa pode quebrar de novo. O teste de regressão confere as duas linhas em todas as telas.
- **Espaçamento dos cards:** dois valores definidos em `.speakers` valem em todas as telas: `--speaker-gap` (8px) entre selo, nome e tema, e `--speaker-block` (16px) entre foto, texto e biografia. No tablet e no celular, o espaço vertical é feito por margens, e não por `row-gap`, para que um card sem tema não ganhe uma linha vazia. O botão “Abrir biografia” dá o respiro da base do card, com o mesmo espaço acima e abaixo do rótulo. No tablet, a linha da biografia fica alinhada entre os dois cards da mesma fileira.
- **Conteúdo programático:** são sete eixos. Cada item de `.program__list` traz o número em `data-index` (`01` a `07`); ao incluir um eixo novo, use o próximo número e um ícone de `img/icons/`. Quando o último item fica sozinho na linha (3 colunas no desktop, 2 no tablet), ele ocupa a linha inteira como uma faixa, com o ícone ao lado do título.
- **Compartilhamento:** `og-image.png` é a prévia usada por WhatsApp, LinkedIn e redes sociais. Se as datas ou o título mudarem, gere a imagem de novo; o build versiona os PNGs e o SVG de `img/` junto com o restante.
- **Dias do cronograma:** cada `<article class="day" data-date="AAAA-MM-DD">` é um dia. O carrossel abre automaticamente no próximo dia de aula.
- **Encontros encerrados:** a partir do dia seguinte a cada encontro, o `main.js` troca o botão da aula por “Aula encerrada”, desativado e com um ícone de confirmação, inclusive quando havia link do Zoom. No próprio dia o botão continua ativo. Se as aulas forem gravadas, esse é o lugar para um link “Assistir gravação”.
- **Testes:** `tests/site_regression.py` fixa a data em 02/11/2026, antes do curso, para dar o mesmo resultado em qualquer dia. Os encontros encerrados são testados com datas simuladas.
- **Publicação:** rode o build, faça commit e push na `main`; o GitHub Pages publica em `januvieira.tech/eventos/patentes-para-bioinovadores/` em cerca de um minuto.

## Créditos

- Layout derivado do template *Assembly*, da MRHTML (licença MIT, consulte `LICENSE`).
- Animação da hélice portada do projeto PrivDNA (licença MIT, aviso em `assets/js/dna.js`).
