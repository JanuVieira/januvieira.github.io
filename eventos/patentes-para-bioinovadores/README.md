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
| até `374px` | Card compacto dos palestrantes (foto de 76px e espaço interno de 12px) |
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

Não edite `main.compat.css` diretamente: ele é um artefato gerado a partir de `main.css`, a única fonte dos estilos.
O build também aplica permissão `644`, atualiza o hash curto dos recursos críticos em `index.html` e gera `version.json`. A página consulta esse manifesto sem cache e recarrega uma vez quando detecta uma publicação mais recente no GitHub Pages.

Não há build automático no GitHub: rode `sh scripts/build-css.sh` antes de cada commit. O GitHub Pages publica os arquivos do repositório como estão, inclusive `main.compat.css`, os hashes em `index.html` e `version.json`.

Escala de espaço: `--space-half` (2px, só entre linhas de um mesmo bloco, como nome e cargo), `--space-1` (4px), `--space-2` (8px), `--space-3` (12px), `--space-4` (16px), `--space-5` (20px), `--space-6` (24px), `--space-8` (32px), `--space-10` (40px), `--space-12` (48px), `--space-14` (56px), `--space-16` (64px), `--space-20` (80px) e `--space-24` (96px). Todo margin, padding e gap usa um token da escala ou um token semântico (`--section-space`, `--head-gap`, `--eyebrow-gap`, `--subhead-gap`, `--block-gap`, `--column-gap`, `--card-pad`, `--gutter`), que muda por faixa de tela. Ajustes de 1–3px sobre um token (`calc(var(--space-3) - 2px)`) existem só para compensar borda de 1px ou a altura da linha em botões, selos e abas; não crie valores soltos em px.

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

Cantos: padrão único de 8px (`--radius-card` e `--radius-tile`) em todo canto arredondado: cards, painel do cronograma, barra de abas, diálogos, abas, botões retangulares e fotos. Quando um elemento arredondado fica dentro de outro mais perto da borda do que o raio de fora, os cantos são concêntricos (r = R − d); com o padrão de 8px e espaços internos de 12px ou mais, nenhum caso chega a isso, e o elemento de dentro nunca é mais arredondado que o de fora. Círculos (`50%`) e selos/botões em pílula (`--pill`) mantêm a forma. O “Inscreva-se” do cabeçalho usa as mesmas medidas do botão “Menu” (altura, espaço interno, borda e fonte).

- **Cabeçalho:** fica fixo no topo ao rolar em todas as telas (no tablet e no desktop, com o fundo da página em toda a largura e uma linha quando a página já rolou). O menu do desktop mostra Conteúdo, Cronograma, Palestrantes e Dúvidas; Objetivos aparece só no menu do celular (`site-nav__extra`). O “Inscreva-se” do cabeçalho (`[data-header-cta]`) aparece quando o botão do hero sai da tela por cima (IntersectionObserver no `main.js`); no celular, ele ocupa o lugar do nome do curso, ao lado de “Menu”. As âncoras do menu param abaixo do cabeçalho (`scroll-padding-top`).
- **O curso em resumo:** faixa `.facts` logo abaixo do hero, com os fatos que decidem a inscrição (gratuito, certificado com 75% de presença, aulas gravadas, 30 horas-aula), no padrão de Horário/Dias do painel lima. Quatro colunas no desktop e duas no tablet e no celular. Tudo ali precisa estar confirmado no FAQ.
- **Curso encerrado:** o `<html>` traz `data-course-end="2026-11-19"`. A partir do dia seguinte (mesma regra de “Aula encerrada”), um script no `<head>`, antes da pintura, aplica `.course-ended`, e o CSS troca os elementos `data-when="open"` pelos `data-when="ended"`: o selo do hero vira “Curso encerrado”, o “Inscreva-se” some do hero, do cabeçalho e do FAQ, e o hero e o aviso do cronograma explicam gravações e certificado. Sem JavaScript, vale o estado aberto. Se a data do último encontro mudar, atualize o atributo.
- **Links de aula:** cada `.day__actions` tem um único botão, “Assistir aula”, do tamanho do rótulo no tablet e desktop e na largura do card no celular; enquanto não tem endereço, fica desabilitado com o estado “Link em breve”. Quando os endereços oficiais chegarem, substitua cada `<button disabled>` por um `<a href="…">`, preservando as classes e o conteúdo, troque “Link em breve” pelo destino (ex.: “Via Zoom”, como no Encontro 1) e atualize o `aria-label`. Para links externos, use também `target="_blank"`, `rel="noopener noreferrer"` e informe no `aria-label` que o destino abre em nova aba. O formulário oficial de inscrição já está conectado ao hero, ao aviso do cronograma e ao FAQ. O aviso (`.schedule-note`) fecha o card do dia: fica separado por uma linha, com ícone de atenção na cor lima e a primeira frase em negrito. Os tópicos de cada aula abrem com “Abrir tópicos”, sem número.
- **Confirmação de inscrição:** links de aula com o atributo `data-requires-enrollment` abrem antes o diálogo `.enrollment-dialog`, que pergunta se a pessoa já se inscreveu. Ela escolhe entre duas opções (rádios nativos estilizados como cartões) e o único botão, “Continuar”, só é liberado depois da escolha: com “Sim, já me inscrevi” ele vira “Entrar na aula” (abre o endereço do próprio link); com “Ainda não me inscrevi”, vira “Ir para a inscrição” (abre o formulário e mantém o diálogo aberto, com um aviso para voltar e entrar). Ao entrar, a resposta fica salva no `localStorage` daquele navegador e as próximas aulas abrem direto. No tablet e desktop o diálogo é centralizado; no celular, é um painel inferior com as opções empilhadas; em celulares deitados, as opções ficam lado a lado. Ctrl/Cmd + clique e navegadores sem `<dialog>` abrem a aula diretamente. Para ativar nos próximos encontros, basta adicionar `data-requires-enrollment` ao novo `<a>`.
- **Biografias dos palestrantes:** no celular, “Abrir biografia” expande o conteúdo em linha e mantém somente uma biografia aberta. Em tablets e desktops, o mesmo controle abre um diálogo de leitura que aceita textos extensos sem alterar a grade. Coloque o conteúdo dentro de `.speaker__bio-content`, preferencialmente em dois ou três parágrafos; quando o texto oficial chegar, substitua a mensagem e remova `speaker__bio--pending`.
- **Fotos dos palestrantes:** a área de retrato permanece quadrada (1:1) em desktop, tablet e celular, sem alongamento pela altura do texto. Salve em `assets/img/palestrantes/` com nome em minúsculas e hífens (ex.: `paula-adamis-de-barros.webp`), em 800 × 800 px e WebP com qualidade 78 (`cwebp -q 78 -m 6`): fica entre 25 e 50 KB sem perda visível. Dentro de `.speaker__art`, adicione `<img src="assets/img/palestrantes/nome.webp" alt="" width="800" height="800" loading="lazy" decoding="async" />`. O nome do card usa a classe `.speaker__name` (h3 na lista principal, h4 no grupo das startups); o estilo vem da classe, não da tag. A foto cobre as iniciais.
- **Grade de palestrantes:** dois grupos. Em cima, quem conduz as aulas (nove cards, `speakers--nine`): 3 × 3 em todo o desktop; no tablet, duas colunas e o 9º card centralizado; no celular, uma coluna. Embaixo, `.speakers__guests` reúne o cabeçalho do grupo (`.speakers__group-head`: título “Startups / convidadas.” no padrão dos títulos de seção, com a segunda linha na cor de destaque, e uma frase de apoio com as datas) e a lista `speakers--guests`, com quem apresenta as empresas. No desktop, esse bloco é uma quarta linha nas mesmas três colunas: o cabeçalho na primeira e os dois cards nas outras duas, com a largura dos cards de cima (as duas grades usam o mesmo `--col-gap`); no tablet e no celular, o título fica acima dos cards. O `main.js` aplica `speakers--nine` quando a lista principal tem nove cards; com outra quantidade, vale a grade padrão de quatro colunas e é preciso criar a composição no CSS. A Dra. Stefania Palma Araujo ainda não tem foto e o card mostra as iniciais. Dentro de cada grupo, os cards seguem a ordem do cronograma; quando um palestrante muda de dia, mova o card e atualize a data em `.speaker__meta`.
- **Empresas convidadas:** a aula de uma empresa usa `<li class="lesson lesson--company">` e segue o formato das outras (horário, título e `.lesson__speaker`). A apresentação fica num `<details class="lesson__topics">` com “Conhecer a startup” / “Fechar apresentação”: dentro de `.lesson__about`, o logo (`<img class="lesson__logo">`, de `img/empresas/`) vem primeiro, acima do texto e alinhado a ele, e só aparece quando a pessoa abre. O padrão vale para todas as empresas: logo sem moldura, na cor da marca, sobre o fundo da página, recortado rente ao desenho; a largura (144px no tablet e desktop, 120px no celular) define a altura. Prefira o SVG oficial. Se a empresa só tiver a versão branca (feita para fundo escuro), troque o branco pela cor da marca: o logo da NAtiva é o `logo.svg` do site deles com `fill="white"` trocado por `#223513`, o verde do próprio site. O `main.js` anima esse bloco como os tópicos. Exemplos: NAtiva (Dra. Renata Mendes), no Encontro 3, e Inovafhytos Cerrado (Profa. Dra. Jaqueline Cibene), no Encontro 4. Quem apresenta a empresa também tem card em Palestrantes, no grupo “Startups convidadas”, com o selo da empresa e o tema “Apresentação da startup”.
- **Nomes e temas dos cards:** texto corrido, sem quebra forçada: cada um quebra linha naturalmente conforme a largura do card (no desktop, em geral, cabe em uma linha). Os temas são versões curtas dos títulos das aulas; o título completo continua no cronograma. O teste de regressão confere que nome e tema cabem no card sem vazar e que o nome não passa de duas linhas.
- **Espaçamento dos cards:** dois valores definidos em `.speakers` valem em todas as telas: `--speaker-gap` (8px) entre selo, nome e tema, e `--speaker-block` (16px) entre foto, texto e biografia. No tablet e no celular, o espaço vertical é feito por margens, e não por `row-gap`, para que um card sem tema não ganhe uma linha vazia. O botão “Abrir biografia” dá o respiro da base do card, com o mesmo espaço acima e abaixo do rótulo. No tablet, a linha da biografia fica alinhada entre os dois cards da mesma fileira.
- **Selo do card:** um selo só por palestrante, com a instituição (INPI, UERJ, UFT, MAPA…). Quem vem por uma empresa convidada mostra a empresa: a Dra. Renata Mendes aparece com “NAtiva” e a Profa. Dra. Jaqueline Cibene, com “Inovafhytos”. Um nome curto cabe junto da data em todas as larguras; dois selos no mesmo card não cabem numa linha só em várias larguras (abaixo de 360px, em 375px e entre 768 e 799px).
- **Conteúdo programático:** são seis eixos, os mesmos do convite, para fechar 3 × 2 no desktop e 2 × 3 no tablet. “Proteção de cultivares” não é um eixo à parte: aparece no cronograma (Encontro 6) e no card da Dra. Stefania. Cada item de `.program__list` traz o número em `data-index` (`01` a `06`); ao incluir um eixo novo, use o próximo número e um ícone de `img/icons/`. Quando o último item fica sozinho na linha (3 colunas no desktop, 2 no tablet), ele ocupa a linha inteira como uma faixa, com o ícone ao lado do título.
- **Compartilhamento:** `og-image.png` é a prévia usada por WhatsApp, LinkedIn e redes sociais. Se as datas ou o título mudarem, gere a imagem de novo; o build versiona os PNGs e o SVG de `img/` junto com o restante. O `<head>` também traz os dados do curso para buscadores (`application/ld+json`, schema.org `EducationEvent`: nome, datas, horário, gratuito, online, inscrição); atualize junto se algo mudar.
- **Dias do cronograma:** cada `<article class="day" data-date="AAAA-MM-DD">` é um dia. Os horários das aulas ficam em `<time datetime="AAAA-MM-DDTHH:MM-03:00">`, com o fuso de Brasília. O título do dia (“Encontro N”) usa `--fs-h3` e o das aulas, `--fs-h4`, um nível abaixo. O carrossel abre automaticamente no próximo dia de aula.
- **Encontros encerrados:** a partir do dia seguinte a cada encontro, o `main.js` troca o botão da aula por “Aula encerrada (Gravação por e-mail)”, desativado e com um ícone de confirmação, inclusive quando havia link do Zoom; o estado segue o padrão de “Assistir aula (Via Zoom)”, porque as gravações chegam por e-mail aos inscritos. No próprio dia o botão continua ativo.
- **Textos (UX writing):** segunda pessoa (“você”), frases curtas e verbo de ação nos botões e links (“Inscreva-se”, “Ver cronograma”, “Abrir tópicos”). Informação de decisão primeiro: gratuito, online e ao vivo, datas e horário de Brasília. Estados dizem o que falta (“Link em breve”) e o que acontece depois (“Aula encerrada (Gravação por e-mail)”). Termos fixos: “encontro” para o dia, “aula” para o que acontece nele, “inscrição” para o formulário. Bios e conteúdo do cronograma seguem o texto oficial.
- **Dúvidas:** nove perguntas, na ordem de quem vai se inscrever: inscrição, gratuidade, público, datas, acesso, gravações, carga horária, certificado e contato (curso.bioinovadores@inpi.gov.br). Só entram respostas confirmadas pela organização. A pergunta usa `--fs-h4` e a resposta, `--fs-body`.
- **Testes:** `tests/site_regression.py` fixa a data em 02/11/2026, antes do curso, para dar o mesmo resultado em qualquer dia. Os encontros encerrados são testados com datas simuladas.
- **Publicação:** rode o build, faça commit e push na `main`; o GitHub Pages publica em `januvieira.tech/eventos/patentes-para-bioinovadores/` em cerca de um minuto.

## Créditos

- Layout derivado do template *Assembly*, da MRHTML (licença MIT, consulte `LICENSE`).
- Animação da hélice portada do projeto PrivDNA (licença MIT, aviso em `assets/js/dna.js`).
