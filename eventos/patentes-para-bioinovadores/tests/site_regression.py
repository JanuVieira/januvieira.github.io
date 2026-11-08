#!/usr/bin/env python3
"""Testes de regressão com Chromium/Playwright para site estático."""
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlparse
from datetime import datetime
import json
import re
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("Instale Playwright: python3 -m pip install playwright && python3 -m playwright install chromium")

ROOT = Path(__file__).resolve().parents[1]
SIZES = [(320,700), (375,812), (390,844), (430,932), (667,375), (768,1024), (1024,768), (1280,800), (1440,900), (1920,1080)]
LONG_BIO = [
    'Engenheira química e doutora em Engenharia de Processos Químicos e Bioquímicos pela UFRJ.',
    'Há 20 anos atua como examinadora de patentes no INPI, nas áreas de fármacos, engenharia química, petroquímica e polímeros.',
    'Atualmente, é tutora de cursos EAD da WIPO e atua na articulação e disseminação da Propriedade Intelectual, aproximando conhecimento, inovação e desenvolvimento, especialmente na região amazônica.',
]
issues = []
results = []

# Os testes simulam datas antes e durante o curso. A página publicada já traz
# os encontros passados como "Aula encerrada" e sem link do Zoom no código;
# aqui o HTML volta ao estado de antes do curso, com um link de teste.
PRECOURSE_ACTIONS = {
    1: """<a class="btn btn--primary" href="https://us02web.zoom.us/j/00000000000?pwd=teste" target="_blank" rel="noopener noreferrer" data-requires-enrollment aria-label="Assistir aula do Encontro 1 no Zoom (abre em nova aba)" aria-describedby="schedule-access-note">
                <span class="btn__icon" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="M4.5 2.8v10.4a.6.6 0 0 0 .9.5l8.3-5.2a.6.6 0 0 0 0-1L5.4 2.3a.6.6 0 0 0-.9.5Z" fill="currentColor" /></svg></span>
                <span class="btn__label">Assistir aula<span class="btn__status">Via Zoom</span></span>
              </a>""",
    2: """<button class="btn btn--primary" type="button" disabled aria-label="Assistir aula do Encontro 2 (link em breve)" aria-describedby="schedule-access-note">
                <span class="btn__icon" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="M4.5 2.8v10.4a.6.6 0 0 0 .9.5l8.3-5.2a.6.6 0 0 0 0-1L5.4 2.3a.6.6 0 0 0-.9.5Z" fill="currentColor" /></svg></span>
                <span class="btn__label">Assistir aula<span class="btn__status">Link em breve</span></span>
              </button>""",
}

def precourse_html(html):
    for number, markup in PRECOURSE_ACTIONS.items():
        pattern = r'(<article class="day" id="encontro-%d".*?<div class="day__actions"[^>]*>).*?(</div>)' % number
        html = re.sub(pattern, lambda m: m.group(1) + '\n              ' + markup + '\n            ' + m.group(2), html, count=1, flags=re.S)
    return html

def use_precourse(target):
    def handle(route):
        response = route.fetch()
        route.fulfill(response=response, body=precourse_html(response.text()))
    target.route(lambda address: urlparse(address).path in ('/', '/index.html'), handle)

def check(ok, title, detail=""):
    results.append({"test": title, "passed": bool(ok), "detail": detail})
    print(("PASS" if ok else "FAIL") + " " + title + (" | " + detail if detail else ""))
    if not ok: issues.append(title)

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

class QuietServer(ThreadingHTTPServer):
    # Uma página de teste que fecha no meio de um download não é erro do site.
    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)): return
        super().handle_error(request, client_address)

server = QuietServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
Thread(target=server.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{server.server_port}/"
try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        # Data fixa antes do curso: os testes não dependem do dia em que rodam
        # (os encontros passados viram "Aula encerrada" e mudariam o resultado).
        COURSE_DATE = datetime.fromisoformat('2026-11-02T10:00:00-03:00')
        def open_page(**options):
            opened = browser.new_page(**options)
            opened.clock.set_fixed_time(COURSE_DATE)
            use_precourse(opened)
            return opened
        for width, height in SIZES:
            page = open_page(viewport={"width":width,"height":height}, reduced_motion="reduce")
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.goto(url, wait_until="domcontentloaded")
            page.locator("main").wait_for()
            layout = page.evaluate("""() => ({doc: document.documentElement.scrollWidth, viewport: innerWidth})""")
            check(layout["doc"] <= layout["viewport"] + 1, f"sem overflow horizontal {width}x{height}", str(layout))
            check(not errors, f"sem exceções JS {width}x{height}", str(errors[:2]))
            portrait_grid = page.locator('.speaker__art').evaluate_all("""
              els => els.every((art) => {
                const r = art.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && Math.abs(r.width - r.height) <= 1;
              })
            """)
            check(portrait_grid, f"áreas de fotografia quadradas em {width}x{height}")
            speaker_rhythm = page.locator('.speaker').evaluate_all("""
              cards => cards.every((card) => {
                const box = (selector) => card.querySelector(selector)?.getBoundingClientRect();
                const meta = box('.speaker__meta');
                const name = box('.speaker__name');
                const topic = box('.speaker__topic');
                const near = (value) => Math.abs(value - 8) <= 1;
                return near(name.top - meta.bottom) && (!topic || near(topic.top - name.bottom));
              })
            """)
            check(speaker_rhythm, f"cards de palestrantes mantêm 8px entre selo, nome e tema em {width}x{height}")
            # Cantos: padrão de 8px. Quando o card é uma caixa branca, a foto nunca
            # é mais arredondada que ele, e, se estiver mais perto da borda que o
            # raio do card, os cantos são concêntricos (r = R - d).
            corners = page.locator('.speaker').evaluate_all("""
              cards => cards.map((card) => {
                const cs = getComputedStyle(card), art = card.querySelector('.speaker__art');
                const R = parseFloat(cs.borderTopLeftRadius), r = parseFloat(getComputedStyle(art).borderTopLeftRadius);
                const d = art.getBoundingClientRect().left - card.getBoundingClientRect().left;
                const boxed = cs.backgroundColor !== 'rgba(0, 0, 0, 0)';
                return {R, r, d: Math.round(d), ok: !boxed || (R === 8 && r <= R && (d >= R || Math.abs(r - (R - d)) <= 1))};
              })
            """)
            check(all(c['ok'] for c in corners), f"cantos do card e da foto do palestrante seguem o padrão de 8px sem conflito em {width}x{height}", str(corners[:2]))
            alignment = page.evaluate("""() => {
              const R = (el) => el.getBoundingClientRect();
              const container = R(document.querySelector('#conteudo-programatico .container'));
              const edges = ['.hero__brand > *', '.hero__icons > *', '.hero__actions .pill']
                .map((s) => document.querySelector(s)).filter((el) => el && R(el).width > 0).map((el) => Math.round(R(el).left));
              const eyebrows = [...document.querySelectorAll('main .section .eyebrow')].map((el) => Math.round(R(el).left - container.left));
              return {hero: edges, eyebrows, titleIndent: parseFloat(getComputedStyle(document.querySelector('.hero__title-strong')).textIndent)};
            }""")
            # Logo, ícones e "Inscreva-se" na mesma borda (a tinta do "P" do título
            # vem para ela pelo recuo óptico); etiquetas das seções na borda do
            # container. (O fecho do "NOV/26" na régua é conferido pela tinta,
            # porque o espaçamento negativo deixa a caixa do texto menor que ela.)
            check(max(alignment['hero']) - min(alignment['hero']) <= 1 and alignment['titleIndent'] < 0 and all(abs(x) <= 1 for x in alignment['eyebrows']),
                  f"alinhamentos do topo e das etiquetas de seção em {width}x{height}", str(alignment))
            facts = page.evaluate("""() => {
              const items = [...document.querySelectorAll('.facts__list > div')];
              const tops = new Set(items.map((el) => Math.round(el.getBoundingClientRect().top)));
              const hero = document.querySelector('.hero').getBoundingClientRect(), list = document.querySelector('.facts').getBoundingClientRect();
              return {count: items.length, columns: items.length / tops.size, afterHero: list.top >= hero.bottom - 1,
                      fits: items.every((el) => el.scrollWidth <= el.clientWidth + 1)};
            }""")
            check(facts['count'] == 4 and facts['afterHero'] and facts['fits'] and facts['columns'] == (4 if width >= 1024 else 2),
                  f"faixa de resumo logo abaixo do hero, com 4 fatos em {4 if width >= 1024 else 2} colunas, em {width}x{height}", str(facts))
            program_rows = page.locator('.program__list > li').evaluate_all("""
              items => Object.values(items.reduce((rows, item) => {
                const top = Math.round(item.getBoundingClientRect().top);
                rows[top] = (rows[top] || 0) + 1;
                return rows;
              }, {}))
            """)
            check(len(set(program_rows)) == 1, f"conteúdo programático sem item sozinho na última linha em {width}x{height}", str(program_rows))
            # Nome e tema quebram linha naturalmente (sem cortes forçados): cabem
            # no card, sem vazar, e o nome nunca passa de duas linhas.
            card_text = page.locator('.speaker').evaluate_all("""
              cards => cards.map((card) => {
                const box = card.getBoundingClientRect();
                const lines = (el) => Math.round(el.getBoundingClientRect().height / parseFloat(getComputedStyle(el).lineHeight));
                const fits = (el) => el.scrollWidth <= el.clientWidth + 1 && el.getBoundingClientRect().right <= box.right + 1;
                const name = card.querySelector('.speaker__name'), topic = card.querySelector('.speaker__topic');
                return {name: lines(name), fits: fits(name) && fits(topic)};
              })
            """)
            check(all(c['fits'] and c['name'] <= 2 for c in card_text), f"nomes e temas dos palestrantes cabem no card, sem quebra forçada, em {width}x{height}", str(card_text))
            footer_balance = page.locator('.speaker').evaluate_all("""
              cards => cards.every((card) => {
                if (getComputedStyle(card).display !== 'grid') return true;
                const summary = card.querySelector('.speaker__bio summary').getBoundingClientRect();
                const label = card.querySelector('.speaker__bio-more').getBoundingClientRect();
                const above = label.top - summary.top;
                const below = card.getBoundingClientRect().bottom - label.bottom;
                return Math.abs(above - below) <= 2;
              })
            """)
            check(footer_balance, f"Abrir biografia tem o mesmo respiro acima e abaixo em {width}x{height}")
            page.context.route('https://us02web.zoom.us/**', lambda route: route.abort())
            enrollment_fit = page.evaluate("""() => {
              const link = document.querySelector('a[data-requires-enrollment]');
              const dialog = document.querySelector('[data-enrollment-dialog]');
              if (!link || !dialog) return {open: false};
              link.click();
              const rect = dialog.getBoundingClientRect();
              const surface = dialog.querySelector('.enrollment-dialog__surface');
              const title = dialog.querySelector('#enrollment-dialog-title');
              const cards = [...dialog.querySelectorAll('.enrollment-option__card')].map((card) => card.getBoundingClientRect());
              const sideBySide = Math.abs(cards[0].top - cards[1].top) <= 1;
              const result = {
                open: dialog.open,
                inside: rect.top >= -1 && rect.left >= -1 && rect.bottom <= innerHeight + 1 && rect.right <= innerWidth + 1,
                noOverflowX: surface.scrollWidth <= surface.clientWidth + 1,
                titleOneLine: title.getBoundingClientRect().height < parseFloat(getComputedStyle(title).lineHeight) * 1.5,
                cardsEqual: !sideBySide || Math.abs(cards[0].height - cards[1].height) <= 1,
              };
              dialog.close();
              return result;
            }""")
            check(enrollment_fit['open'] and enrollment_fit['inside'] and enrollment_fit['noOverflowX'], f"confirmação de inscrição cabe na tela {width}x{height}", str(enrollment_fit))
            check(enrollment_fit['titleOneLine'] and enrollment_fit['cardsEqual'], f"confirmação mantém título em uma linha e cards alinhados em {width}x{height}")
            company_layouts = {}
            for tab, day_id in (('2', 'encontro-3'), ('3', 'encontro-4')):
              page.locator(f'.day-nav__tabs [data-day="{tab}"]').click()
              company_layouts[day_id] = page.locator(f'#{day_id}').evaluate("""day => {
              const lessons = [...day.querySelectorAll('.lesson')];
              const company = day.querySelector('.lesson--company');
              const details = company.querySelector('.lesson__topics');
              const img = company.querySelector('.lesson__logo');
              const box = (root, selector) => root.querySelector(selector).getBoundingClientRect();
              const gap = (root) => box(root, '.lesson__speaker').top - box(root, '.lesson__title').bottom;
              // Fechada, a aula segue o formato das outras e o logo não aparece.
              const closed = {
                hidden: !details.open && !img.checkVisibility(),
                sameGap: Math.abs(gap(company) - gap(lessons[0])) <= 1,
              };
              // Aberta, o logo vem acima do texto da empresa, alinhado a ele.
              details.open = true;
              const lesson = company.getBoundingClientRect();
              const logo = img.getBoundingClientRect();
              const summary = box(company, '.lesson__topics summary');
              const lead = box(company, '.lesson__about-lead');
              const opened = {
                visible: img.checkVisibility() && logo.width > 0,
                aboveText: logo.top >= summary.bottom && logo.bottom <= lead.top,
                alignedWithText: Math.abs(logo.left - lead.left) <= 1,
                inside: logo.left >= lesson.left - 1 && logo.right <= lesson.right + 1,
                // Mesmo padrão nas duas empresas: largura igual e sem moldura.
                width: Math.round(logo.width),
                frameless: getComputedStyle(img).backgroundColor === 'rgba(0, 0, 0, 0)' &&
                  getComputedStyle(img).borderRadius === '0px' && getComputedStyle(img).borderStyle === 'none',
              };
              details.open = false;
              return {...closed, ...opened};
              }""")
            check(all(all(v.values()) for v in company_layouts.values()), f"logos da NAtiva e da Inovafhytos só aparecem ao abrir a apresentação, acima do texto, em {width}x{height}", str(company_layouts))
            check(len({v['width'] for v in company_layouts.values()}) == 1, f"logos da NAtiva e da Inovafhytos seguem o mesmo padrão de tamanho em {width}x{height}", str({k: v['width'] for k, v in company_layouts.items()}))
            page.close()

        page = open_page(viewport={"width":390,"height":844}, reduced_motion="reduce")
        page.goto(url, wait_until="domcontentloaded")
        # Mudanças editoriais mobile, verificadas na página renderizada.
        layout_mobile = page.evaluate("""() => {
          const el = (selector) => document.querySelector(selector);
          const box = (selector) => el(selector).getBoundingClientRect();
          const font = (selector) => parseFloat(getComputedStyle(el(selector)).fontSize);
          const hero = box('.hero__main');
          const primary = box('.hero__actions .pill');
          const secondary = box('.hero__actions .hero__link');
          const audience = el('.audience');
          const footer = el('.site-footer');
          return {
            heroHeight: hero.height,
            titleSize: font('.hero__title-strong'),
            subtitleSize: font('.hero__title-sub'),
            bodySize: font('body'),
            actionsGap: secondary.top - primary.bottom,
            audienceBackground: getComputedStyle(audience).backgroundColor,
            audienceRadius: parseFloat(getComputedStyle(audience).borderTopLeftRadius),
            audienceItemSize: font('.audience li'),
            footerBackground: getComputedStyle(footer).backgroundColor,
            pageBackground: getComputedStyle(document.documentElement).backgroundColor,
            footerPadding: parseFloat(getComputedStyle(footer).paddingBottom),
            viewportFit: el('meta[name=viewport]').content.includes('viewport-fit=cover'),
          };
        }""")
        check(layout_mobile['heroHeight'] >= 500, 'hero azul mobile tem altura ampliada', str(round(layout_mobile['heroHeight'])))
        check(layout_mobile['titleSize'] >= 38 and layout_mobile['subtitleSize'] >= 18 and layout_mobile['bodySize'] >= 17,
              'tipografia mobile ampliada com hierarquia', repr({key: layout_mobile[key] for key in ('titleSize','subtitleSize','bodySize')}))
        check(layout_mobile['actionsGap'] >= 16, 'botoes do hero mobile com separacao reforcada', str(round(layout_mobile['actionsGap'])))
        check(layout_mobile['audienceBackground'] == 'rgb(255, 255, 255)' and layout_mobile['audienceRadius'] == 8 and layout_mobile['audienceItemSize'] >= 18,
              'Para quem e possui composicao mobile independente')
        check(layout_mobile['pageBackground'] == layout_mobile['footerBackground'] and layout_mobile['footerPadding'] >= 24 and layout_mobile['viewportFit'],
              'fundo inferior acompanha rodape e contempla safe area')
        anchors = page.locator("a[href]")
        unnamed = []
        for i in range(anchors.count()):
            link = anchors.nth(i)
            if not link.is_visible(): continue
            name = link.aria_snapshot().strip()
            # aria_snapshot usa o nome computado do acessibility tree, não apenas textContent
            if name.startswith('- link:') or name == '- link':
                unnamed.append(link.get_attribute("href"))
        check(not unnamed, "links visíveis possuem nome acessível", repr(unnamed))
        forms = page.locator('a[href*="forms.cloud.microsoft"]')
        check(forms.count() >= 1 and all(forms.nth(i).inner_text().strip() for i in range(forms.count()) if forms.nth(i).is_visible()) and any(forms.nth(i).is_visible() for i in range(forms.count())), "links de inscrição identificáveis")
        program_numbers = page.locator('.program__list li').evaluate_all("""
          els => els.map((el) => el.dataset.index).join(',') === '01,02,03,04,05,06' &&
            els.every((el) => {
              const content = getComputedStyle(el, '::before').content;
              return content.includes('attr') || content.replace(/"/g, '') === el.dataset.index;
            })
        """)
        check(program_numbers, 'conteúdo programático com os seis eixos do convite, numerados de 01 a 06 sem contador CSS (evita "00" no Safari)')
        nav_toggle = page.locator('.site-header__toggle')
        if nav_toggle.is_visible():
            check(not page.locator('.site-header__brand').is_visible(), 'header mobile mantém somente o botão Menu')
            toggle_style = nav_toggle.evaluate("""
              el => ({
                height: el.getBoundingClientRect().height,
                weight: Number.parseInt(getComputedStyle(el).fontWeight, 10),
              })
            """)
            check(toggle_style['height'] >= 52 and toggle_style['weight'] >= 700, 'botão Menu tem área e peso reforçados')
            nav_toggle.click()
            check(nav_toggle.get_attribute('aria-expanded') == 'true', 'menu móvel abre e atualiza aria-expanded')
            menu_spacing = page.locator('.site-nav a').evaluate_all("""
              els => {
                const rects = els.filter((el) => el.getBoundingClientRect().height > 0)
                  .map((el) => el.getBoundingClientRect());
                return rects.every((rect) => rect.height >= 56) &&
                  rects.slice(1).every((rect, index) => rect.top - rects[index].bottom >= 7.5);
              }
            """)
            check(menu_spacing, 'links do menu móvel têm altura e espaçamento ampliados')
            page.keyboard.press('Escape')
            check(nav_toggle.get_attribute('aria-expanded') == 'false', 'menu móvel fecha com Escape')
        else:
            check(False, 'botão de menu móvel está visível')
        faq = page.locator('details.faq__item')
        if faq.count():
            first = faq.first
            first.locator('summary').click()
            check(first.get_attribute('open') is not None, 'FAQ expande ao clicar')
            faq_questions = page.locator('.faq__item summary > span').all_text_contents()
            check(len(faq_questions) == 9 and {'O curso é gratuito?', 'As aulas ficam gravadas?', 'Ainda tem dúvidas?'} <= set(faq_questions) and
                  page.locator('.faq__item a[href="mailto:curso.bioinovadores@inpi.gov.br"]').count() == 1,
                  'FAQ responde gratuidade, gravações e contato por e-mail', str(faq_questions))
        else:
            check(False, 'existe FAQ interativo')

        action_statuses = page.locator('.day:not([hidden]) .day__actions .btn__status')
        check(action_statuses.count() == 1, 'ação do encontro exibe o estado da aula')
        single_actions = page.locator('.day__actions').evaluate_all("""
          els => els.length === 6 && els.every((el) => el.querySelectorAll('.btn').length === 1) &&
            !document.body.textContent.includes('Baixar materiais')
        """)
        check(single_actions, 'cada encontro mostra só a ação da aula')
        action_width = page.locator('.day:not([hidden]) .day__actions').evaluate("""
          el => Math.abs(el.querySelector('.btn').getBoundingClientRect().width - el.getBoundingClientRect().width) <= 1
        """)
        check(action_width, 'botão da aula ocupa a largura do card no mobile')
        statuses_inline = action_statuses.evaluate_all("""
          els => els.every((el) => {
            const status = el.getBoundingClientRect();
            const label = el.parentElement.getBoundingClientRect();
            return Math.abs(status.top - label.top) <= 1 && label.height < parseFloat(getComputedStyle(el).fontSize) * 2;
          })
        """)
        check(statuses_inline, 'rótulo e estado do botão ficam na mesma linha quando há espaço no mobile')
        pending_statuses = page.locator('.day__actions .btn:disabled .btn__status').evaluate_all(
            "els => els.length > 0 && els.every((el) => el.textContent.trim() === 'Link em breve')"
        )
        check(pending_statuses, 'ações pendentes indicam Link em breve')
        lesson_link = page.locator('#encontro-1 .day__actions a.btn--primary').evaluate_all("""
          els => els.length === 1 && (() => {
            const link = els[0];
            const status = link.querySelector('.btn__status');
            return link.href.startsWith('https://us02web.zoom.us/j/') &&
              link.target === '_blank' && link.relList.contains('noopener') &&
              getComputedStyle(status).color === getComputedStyle(link).color;
          })()
        """)
        check(lesson_link, 'aula do Encontro 1 abre o Zoom em nova aba com estado legível')

        touch_controls = page.locator(
            '.site-header__toggle, .day-nav__tabs button, '
            '.schedule-card-nav button:not(:disabled), .lesson__topics summary, '
            '.speaker__bio summary, [data-back-to-top]'
        )
        safe_touch_targets = touch_controls.evaluate_all("""
          els => els.filter(el => {
            const rect = el.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
          }).every(el => el.getBoundingClientRect().height >= 48)
        """)
        check(safe_touch_targets, 'controles mobile principais têm pelo menos 48px de altura')

        date_spacing = page.locator('.day-nav__tabs button').evaluate_all("""
          els => {
            const rows = new Map();
            els.forEach((el) => {
              const rect = el.getBoundingClientRect();
              const key = Math.round(rect.top);
              if (!rows.has(key)) rows.set(key, []);
              rows.get(key).push(rect);
            });
            return [...rows.values()].every((row) => {
              row.sort((a, b) => a.left - b.left);
              return row.slice(1).every((rect, index) => rect.left - row[index].right >= 11.5);
            });
          }
        """)
        check(date_spacing, 'datas do cronograma têm 12px de separação para toque')

        page.context.route('https://us02web.zoom.us/**', lambda route: route.abort())
        page.context.route('https://forms.cloud.microsoft/**', lambda route: route.abort())
        popups = []
        page.on('popup', lambda popup: popups.append(popup))
        page.locator('.day-nav__tabs [data-day="0"]').click()
        lesson = page.locator('#encontro-1 a[data-requires-enrollment]')
        enrollment = page.locator('[data-enrollment-dialog]')
        proceed = enrollment.locator('[data-enrollment-continue]')
        enrolled_option = enrollment.locator('.enrollment-option', has_text='Sim, já me inscrevi')
        signup_option = enrollment.locator('.enrollment-option', has_text='Ainda não me inscrevi')
        lesson.click()
        page.wait_for_timeout(200)
        check(enrollment.evaluate('el => el.open') and not popups, 'Assistir aula pergunta sobre a inscrição antes de abrir o Zoom')
        sheet = enrollment.evaluate("""el => {
          const rect = el.getBoundingClientRect();
          const radios = [...el.querySelectorAll('input[name="enrollment-status"]')];
          const cards = [...el.querySelectorAll('.enrollment-option__card')].map((card) => card.getBoundingClientRect());
          const proceed = el.querySelector('[data-enrollment-continue]');
          const close = el.querySelector('[data-enrollment-close]');
          return {
            bottom: Math.abs(innerHeight - rect.bottom) <= 1,
            fullWidth: Math.abs(innerWidth - rect.width) <= 1,
            stacked: cards.length === 2 && cards[1].top >= cards[0].bottom,
            targets: [...cards, proceed.getBoundingClientRect(), close.getBoundingClientRect()].every((box) => box.height >= 48),
            focused: document.activeElement === el.querySelector('#enrollment-dialog-title'),
            unselected: radios.length === 2 && radios.every((radio) => !radio.checked),
            waiting: proceed.getAttribute('aria-disabled') === 'true' && !proceed.hasAttribute('href'),
            meta: el.querySelector('[data-enrollment-meta]').textContent,
          };
        }""")
        check(sheet['bottom'] and sheet['fullWidth'] and sheet['stacked'], 'confirmação abre como painel inferior com opções empilhadas no mobile', str(sheet))
        check(sheet['targets'] and sheet['focused'], 'opções e Continuar têm 48px e o título recebe o foco')
        check(sheet['unselected'] and sheet['waiting'] and sheet['meta'] == 'Encontro 1 · 3 de novembro', 'Continuar só é liberado depois da escolha', sheet['meta'])
        signup_option.click()
        signup_state = proceed.evaluate("el => ({href: el.href, label: el.textContent.trim(), target: el.target})")
        with page.expect_popup() as signed:
            proceed.click()
        signed.value.close()
        hint = enrollment.locator('[data-enrollment-hint]').inner_text()
        check(
            'forms.cloud.microsoft' in signup_state['href'] and signup_state['label'].startswith('Ir para a inscrição') and
            signup_state['target'] == '_blank' and enrollment.evaluate('el => el.open') and 'Sim, já me inscrevi' in hint,
            'Ainda não me inscrevi abre o formulário e mantém a confirmação aberta', str(signup_state),
        )
        enrolled_option.click()
        check(proceed.get_attribute('href') == lesson.get_attribute('href') and proceed.inner_text().startswith('Entrar na aula'), 'Sim, já me inscrevi leva ao link da aula')
        page.keyboard.press('Escape')
        check(not enrollment.evaluate('el => el.open') and lesson.evaluate('el => document.activeElement === el'), 'Esc fecha a confirmação e devolve o foco ao botão da aula')
        lesson.click()
        reopened_clean = enrollment.evaluate("""el =>
          [...el.querySelectorAll('input[name="enrollment-status"]')].every((radio) => !radio.checked) &&
          !el.querySelector('[data-enrollment-hint]').textContent
        """)
        check(reopened_clean, 'confirmação reabre sem a escolha anterior')
        enrolled_option.click()
        with page.expect_popup() as entered:
            proceed.click()
        entered.value.close()
        page.wait_for_timeout(100)
        closed_after_enter = not enrollment.evaluate('el => el.open')
        with page.expect_popup() as direct:
            lesson.click()
        direct.value.close()
        check(closed_after_enter and not enrollment.evaluate('el => el.open'), 'depois de confirmar, as próximas aulas abrem direto')

        bios = page.locator('.speaker__bio')
        speaker_count = page.locator('.speaker').count()
        visible_bios = bios.locator('summary').evaluate_all("""
          els => els.filter((el) => {
            const rect = el.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
          }).length
        """)
        check(speaker_count == 11 and bios.count() == speaker_count and visible_bios == speaker_count, 'as onze biografias ficam acessíveis no mobile')
        check(page.locator('.speaker > .speaker__bio').count() == speaker_count and page.locator('.speaker__art .speaker__bio').count() == 0, 'biografias ficam fora da área da foto')
        if bios.count():
            first_bio = bios.first
            check(first_bio.locator('.speaker__bio-more').inner_text().startswith('Abrir biografia'), 'bio usa o rótulo Abrir biografia')
            first_summary = first_bio.locator('summary')
            first_summary.scroll_into_view_if_needed()
            photo_does_not_intercept = first_summary.evaluate("""
              el => {
                const rect = el.getBoundingClientRect();
                const target = document.elementFromPoint(
                  rect.left + rect.width / 2,
                  rect.top + rect.height / 2
                );
                return !!target && el.contains(target);
              }
            """)
            check(photo_does_not_intercept, 'foto não intercepta o toque na biografia')
            first_bio.locator('.speaker__bio-content').evaluate("""
              (el, paragraphs) => {
                el.replaceChildren(...paragraphs.map((text) => {
                  const paragraph = document.createElement('p');
                  paragraph.textContent = text;
                  return paragraph;
                }));
              }
            """, LONG_BIO)
            first_summary.click()
            check(first_bio.get_attribute('open') is not None and first_bio.locator('p').first.is_visible(), 'biografia expande em linha no mobile')
            natural_mobile_bio = first_bio.locator('.speaker__bio-content').evaluate("""
              el => el.querySelectorAll('p').length === 3 && el.scrollHeight <= el.clientHeight + 1
            """)
            check(natural_mobile_bio, 'biografia longa cresce naturalmente no mobile, sem rolagem interna')
            if bios.count() > 1:
                second_bio = bios.nth(1)
                second_bio.locator('summary').click()
                check(first_bio.get_attribute('open') is None and second_bio.get_attribute('open') is not None, 'mobile mantém somente uma biografia aberta')

        back_to_top = page.locator('[data-back-to-top]')
        back_to_top.scroll_into_view_if_needed()
        scroll_before = page.evaluate('scrollY')
        back_to_top.click()
        check(scroll_before > 0 and page.evaluate('scrollY') == 0, 'Voltar ao topo chega ao início da página')

        # Cronograma conforme o convite novo (horário de início, fim e palestrante).
        expected_schedule = {
            'encontro-1': [('14:00', '16:00', 'Dra. Tatiana Carestiato'), ('16:00', '17:00', 'Dra. Tatiana Carestiato')],
            'encontro-2': [('14:00', '15:00', 'Dr. Jeferson Monteiro'), ('15:00', '17:00', 'Profa. Dra. Renata Angeli')],
            'encontro-3': [('14:00', '16:00', 'Profa. Dra. Cláudia Auler'), ('16:00', '17:00', 'Dra. Renata Mendes')],
            'encontro-4': [('14:00', '16:00', 'Dr. Rodrigo Ferraro'), ('16:00', '17:00', 'Profa. Dra. Jaqueline Cibene')],
            'encontro-5': [('14:00', '15:00', 'Dr. Fábio Barros'), ('15:00', '17:00', 'Dra. Paula Adamis de Barros')],
            'encontro-6': [('14:00', '15:00', 'Dra. Stefania Palma Araujo'), ('15:00', '16:50', 'Dra. Cristina D’Urso'), ('16:50', '17:00', 'Dra. Tatiana Carestiato')],
        }
        rendered_schedule = page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('.day')].map((day) => [
          day.id,
          [...day.querySelectorAll('.lesson')].map((lesson) => [
            ...[...lesson.querySelectorAll('.lesson__time time')].map((time) => time.dateTime.slice(11, 16)),
            lesson.querySelector('.lesson__speaker strong').textContent.trim(),
          ]),
        ]))""")
        rendered_schedule = {day: [tuple(row) for row in rows] for day, rows in rendered_schedule.items()}
        check(rendered_schedule == expected_schedule, 'cronograma segue horários e palestrantes do convite', str(rendered_schedule))
        cards_vs_schedule = page.evaluate("""() => {
          const days = {};
          document.querySelectorAll('.day').forEach((day) => {
            const dd = day.dataset.date.slice(8, 10);
            day.querySelectorAll('.lesson__speaker strong').forEach((speaker) => {
              const name = speaker.textContent.trim();
              days[name] = [...new Set([...(days[name] || []), dd])];
            });
          });
          return [...document.querySelectorAll('.speaker')].map((card) => {
            const name = card.querySelector('.speaker__name').textContent.trim();
            const meta = card.querySelector('.speaker__meta > span:last-child').textContent.trim();
            return {name, group: card.closest('.speakers--guests') ? 'guests' : 'main',
                    card: meta.replace(/\\/\\d{2}$/, '').match(/\\d{2}/g) || [], schedule: days[name] || []};
          });
        }""")
        dates_match = all(item['card'] == item['schedule'] and item['card'] for item in cards_vs_schedule)
        # A ordem dos dias vale dentro de cada grupo (aulas e startups convidadas).
        in_order = all(
            [item['card'][0] for item in cards_vs_schedule if item['group'] == group] ==
            sorted(item['card'][0] for item in cards_vs_schedule if item['group'] == group)
            for group in ('main', 'guests')
        )
        guests = [item['name'] for item in cards_vs_schedule if item['group'] == 'guests']
        check(dates_match and in_order and guests == ['Dra. Renata Mendes', 'Profa. Dra. Jaqueline Cibene'],
              'datas dos cards batem com o cronograma, na ordem dos dias dentro de cada grupo, e as startups ficam no grupo de convidadas', str(cards_vs_schedule))
        company = page.locator('#encontro-4 .lesson--company')
        logo_ok = company.locator('.lesson__logo').evaluate("img => img.complete || img.loading === 'lazy'") and company.locator('.lesson__logo').get_attribute('alt')
        instagram = page.locator('#encontro-4 .lesson__about a[href*="instagram.com/inovafhytos_cerrado"]')
        check(company.count() == 1 and bool(logo_ok) and instagram.count() == 1 and instagram.get_attribute('rel') == 'noopener noreferrer',
              'aula da Inovafhytos mostra logo, apresentação e Instagram')
        nativa = page.locator('#encontro-3 .lesson--company')
        nativa_site = page.locator('#encontro-3 .lesson__about a[href="https://nativabiotech.com/"]')
        check(nativa.count() == 1 and nativa.locator('.lesson__logo').get_attribute('alt') == 'Logo da NAtiva' and
              nativa_site.count() == 1 and nativa_site.get_attribute('rel') == 'noopener noreferrer',
              'aula da NAtiva mostra logo, apresentação e site')
        group_head = page.locator('.speakers__group-head')
        check(group_head.locator('h3').inner_text().split() == ['Startups', 'convidadas.'] and group_head.locator('h3 em').count() == 1 and
              '10 e 12 de novembro' in group_head.locator('.speakers__group-lead').inner_text(),
              'grupo das startups tem título no padrão das seções e frase de apoio')
        company_chips = {name: page.locator('.speaker', has_text=name).locator('.speaker__meta > span:first-child').text_content().strip()
                         for name in ('Renata Mendes', 'Jaqueline Cibene')}
        check(company_chips == {'Renata Mendes': 'NAtiva', 'Jaqueline Cibene': 'Inovafhytos'}, 'cards das startups mostram o selo da empresa', str(company_chips))

        manifest = page.evaluate("async () => await (await fetch('version.json', {cache: 'no-store'})).json()")
        embedded_version = page.locator('html').get_attribute('data-site-version')
        check(manifest.get('version') == embedded_version, 'version.json corresponde à versão embutida no HTML')
        page.close()

        desktop = open_page(viewport={"width":1280,"height":900}, reduced_motion="reduce")
        desktop.goto(url, wait_until="domcontentloaded")
        hero_space = desktop.evaluate("""() => {
          const header = document.querySelector('.site-header').getBoundingClientRect();
          const hero = document.querySelector('.hero__grid').getBoundingClientRect();
          const next = document.querySelector('#conteudo-programatico .eyebrow').getBoundingClientRect();
          const facts = document.querySelector('.facts__list').getBoundingClientRect();
          return {above: Math.round(hero.top - header.bottom), toFacts: Math.round(facts.top - hero.bottom),
                  below: Math.round(next.top - facts.bottom), fits: hero.bottom <= innerHeight};
        }""")
        # Entre o hero e a seção 01 fica a faixa de resumo: nem colada, nem com vazio acumulado.
        check(12 <= hero_space['above'] <= 24 and 24 <= hero_space['toFacts'] <= 48 and hero_space['below'] <= 160 and hero_space['fits'],
              'hero tem respiro abaixo do menu, a faixa de resumo vem logo depois e não acumula espaço antes da seção seguinte', str(hero_space))
        fold_issues = []
        for fold_w, fold_h in ((1024, 600), (1280, 720), (1366, 768), (1440, 900)):
            desktop.set_viewport_size({"width": fold_w, "height": fold_h})
            desktop.wait_for_timeout(60)
            bottom = desktop.evaluate("document.querySelector('.hero__actions .pill').getBoundingClientRect().bottom")
            if bottom > fold_h: fold_issues.append((fold_w, fold_h, round(bottom)))
        desktop.set_viewport_size({"width": 1280, "height": 900})
        check(not fold_issues, 'botão Inscreva-se fica visível sem rolar em telas de desktop baixas', str(fold_issues))
        facts_fold_issues = []
        for fold_w, fold_h in ((1280, 800), (1366, 768), (1440, 900)):
            desktop.set_viewport_size({"width": fold_w, "height": fold_h})
            desktop.wait_for_timeout(60)
            bottom = desktop.evaluate("document.querySelector('.facts__list').getBoundingClientRect().bottom")
            if bottom > fold_h: facts_fold_issues.append((fold_w, fold_h, round(bottom)))
        desktop.set_viewport_size({"width": 1280, "height": 900})
        check(not facts_fold_issues, 'faixa de resumo aparece inteira na primeira dobra do desktop', str(facts_fold_issues))
        credit = desktop.locator('.freefingers-credit a').evaluate("""el => {
          const s = getComputedStyle(el);
          return s.textDecorationLine.includes('underline') && s.textDecorationColor !== 'rgba(0, 0, 0, 0)';
        }""")
        check(credit, 'link Janu Vieira fica sublinhado para indicar que é clicável')
        desktop_action = desktop.locator('.day:not([hidden])').evaluate("""day => {
          const button = day.querySelector('.day__actions .btn').getBoundingClientRect();
          const header = day.querySelector('.day__label').getBoundingClientRect();
          const inner = day.getBoundingClientRect().right - parseFloat(getComputedStyle(day).paddingRight);
          const label = day.querySelector('.day__actions .btn__label');
          return {
            sameRow: button.top < header.bottom && button.bottom > header.top,
            rightAligned: Math.abs(button.right - inner) <= 1,
            oneLine: label.getBoundingClientRect().height < parseFloat(getComputedStyle(label).fontSize) * 2,
          };
        }""")
        check(all(desktop_action.values()), 'botão da aula fica na linha do cabeçalho, à direita, com texto em uma linha no desktop', str(desktop_action))
        first_desktop_speaker = desktop.locator('.speaker').first
        desktop_art = first_desktop_speaker.locator('.speaker__art').bounding_box()
        desktop_bio = first_desktop_speaker.locator('.speaker__bio')
        desktop_bio_box = desktop_bio.bounding_box()
        bio_matches_art = (
            desktop_art is not None and desktop_bio_box is not None and
            abs(desktop_art['width'] - desktop_bio_box['width']) <= 1 and
            abs(desktop_art['height'] - desktop_bio_box['height']) <= 1
        )
        check(bio_matches_art, 'painel de biografia permanece limitado à foto no desktop')
        desktop_bio.locator('.speaker__bio-content').evaluate("""
          (el, paragraphs) => {
            el.replaceChildren(...paragraphs.map((text) => {
              const paragraph = document.createElement('p');
              paragraph.textContent = text;
              return paragraph;
            }));
          }
        """, LONG_BIO)
        desktop_summary = desktop_bio.locator('summary')
        desktop_summary.focus()
        desktop_summary.click()
        bio_dialog = desktop.locator('[data-speaker-bio-dialog]')
        check(bio_dialog.get_attribute('open') is not None and bio_dialog.locator('[data-speaker-bio-content] p').count() == 3, 'desktop abre biografia longa em diálogo de leitura')
        dialog_box = bio_dialog.bounding_box()
        check(dialog_box is not None and dialog_box['height'] <= 720 and dialog_box['width'] <= 640, 'diálogo longo respeita os limites da viewport')
        bio_dialog.locator('[data-speaker-bio-close]').click()
        check(bio_dialog.get_attribute('open') is None and desktop.evaluate('(el) => document.activeElement === el', desktop_summary.element_handle()), 'diálogo fecha e devolve o foco ao acionador')

        desktop.context.route('https://us02web.zoom.us/**', lambda route: route.abort())
        desktop.locator('.day-nav__tabs [data-day="0"]').click()
        desktop.locator('#encontro-1 a[data-requires-enrollment]').click()
        desktop_enrollment = desktop.locator('[data-enrollment-dialog]')
        enrollment_box = desktop_enrollment.evaluate("""el => {
          const rect = el.getBoundingClientRect();
          const cards = [...el.querySelectorAll('.enrollment-option__card')].map((card) => card.getBoundingClientRect());
          const proceed = el.querySelector('[data-enrollment-continue]').getBoundingClientRect();
          return {
            open: el.open,
            width: rect.width,
            centered: Math.abs(rect.left + rect.width / 2 - innerWidth / 2) <= 1 &&
              Math.abs(rect.top + rect.height / 2 - innerHeight / 2) <= 1,
            stacked: cards.length === 2 && cards[1].top >= cards[0].bottom,
            fullButton: Math.abs(proceed.width - cards[0].width) <= 1,
          };
        }""")
        check(
            enrollment_box['open'] and enrollment_box['width'] <= 560 and enrollment_box['centered'] and
            enrollment_box['stacked'] and enrollment_box['fullButton'],
            'confirmação de inscrição fica centralizada no desktop, com opções empilhadas', str(enrollment_box),
        )
        desktop.mouse.click(8, 8)
        check(not desktop_enrollment.evaluate('el => el.open'), 'clique fora fecha a confirmação')

        speaker_grid_js = """
          (list) => {
            const cards = [...list.children];
            const listRect = list.getBoundingClientRect();
            const rects = cards.map((card) => card.getBoundingClientRect());
            const lefts = [...new Set(rects.map((rect) => Math.round(rect.left)))];
            const tops = [...new Set(rects.map((rect) => Math.round(rect.top)))];
            const lastRow = rects.filter((rect) => Math.round(rect.top) === Math.max(...tops));
            return {
              columns: lefts.length,
              rows: tops.length,
              leftGap: Math.abs(Math.min(...rects.map((rect) => rect.left)) - listRect.left),
              rightGap: Math.abs(listRect.right - Math.max(...rects.map((rect) => rect.right))),
              lastRowCount: lastRow.length,
              lastRowCentered: Math.abs(
                (Math.min(...lastRow.map((rect) => rect.left)) - listRect.left) -
                (listRect.right - Math.max(...lastRow.map((rect) => rect.right)))
              ) <= 1,
            };
          }
        """
        # Quem conduz as aulas (nove): 3 × 3 em todo o desktop; no tablet, duas
        # colunas e o 9º card centralizado. As startups convidadas vêm abaixo,
        # com cards da mesma largura: no desktop, numa quarta linha com o título
        # na 1ª coluna e os cards na 2ª e na 3ª; no tablet, o título fica acima.
        groups_js = """() => {
          const main = [...document.querySelectorAll('.speakers--nine > .speaker')].map((c) => c.getBoundingClientRect());
          const guests = [...document.querySelectorAll('.speakers--guests > .speaker')].map((c) => c.getBoundingClientRect());
          const label = document.querySelector('.speakers__group').getBoundingClientRect();
          const lefts = [...new Set(main.map((r) => Math.round(r.left)))].sort((a, b) => a - b);
          const near = (a, b) => Math.abs(a - b) <= 1;
          const desktop = innerWidth >= 1024;
          return {
            sameWidth: near(guests[0].width, main[0].width) && near(guests[1].width, main[0].width),
            oneRow: near(guests[0].top, guests[1].top),
            below: Math.min(label.top, guests[0].top) >= Math.max(...main.map((r) => r.bottom)),
            labelLeft: near(label.left, lefts[0]),
            placement: desktop
              ? near(label.top, guests[0].top) && near(guests[0].left, lefts[1]) && near(guests[1].left, lefts[2])
              : label.bottom <= guests[0].top && near(guests[0].left, lefts[0]),
          };
        }"""
        for grid_width, rows, last in ((1024, 3, 3), (1100, 3, 3), (1280, 3, 3), (1440, 3, 3), (1920, 3, 3), (820, 5, 1)):
            desktop.set_viewport_size({"width": grid_width, "height": 900})
            main_grid = desktop.locator('.speakers--nine').evaluate(speaker_grid_js)
            groups = desktop.evaluate(groups_js)
            check(
                main_grid['rows'] == rows and main_grid['lastRowCount'] == last and main_grid['lastRowCentered'] and
                main_grid['leftGap'] <= 1 and main_grid['rightGap'] <= 1,
                f'grade de quem conduz as aulas fica com {rows} linhas e a última centralizada em {grid_width}px',
                str(main_grid),
            )
            where = 'título ao lado dos cards' if grid_width >= 1024 else 'título acima dos cards'
            check(all(groups.values()), f'startups convidadas ficam abaixo, com cards da mesma largura e {where}, em {grid_width}px', str(groups))
        desktop.set_viewport_size({"width": 1280, "height": 900})
        desktop.close()

        # Cabeçalho fixo com "Inscreva-se" ao rolar; "Dúvidas" no menu do desktop.
        for vw, vh in ((1280, 800), (820, 1180), (390, 844)):
            nav_page = open_page(viewport={"width": vw, "height": vh}, reduced_motion="reduce")
            nav_page.goto(url, wait_until="load")
            at_top = nav_page.evaluate("() => !document.querySelector('.site-header').classList.contains('has-cta')")
            faq_link = nav_page.locator('.site-nav a[href="#faq"]')
            faq_visible = faq_link.is_visible() if vw >= 768 else faq_link.count() == 1
            nav_page.evaluate("() => window.scrollTo(0, document.querySelector('#objetivos').offsetTop)")
            nav_page.wait_for_timeout(300)
            scrolled = nav_page.evaluate("""() => {
              const header = document.querySelector('.site-header').getBoundingClientRect();
              const cta = document.querySelector('[data-header-cta]');
              return {ctaVisible: getComputedStyle(cta).visibility === 'visible' && cta.getBoundingClientRect().width > 0, headerTop: Math.round(header.top),
                      ctaInside: cta.getBoundingClientRect().right <= innerWidth + 1};
            }""")
            # Âncora do menu: o título da seção fica abaixo do cabeçalho fixo.
            nav_page.evaluate("() => { document.documentElement.style.scrollBehavior = 'auto'; location.hash = '#palestrantes'; }")
            nav_page.wait_for_timeout(300)
            anchor_ok = nav_page.evaluate("() => document.querySelector('#palestrantes .eyebrow').getBoundingClientRect().top >= document.querySelector('.site-header').getBoundingClientRect().bottom - 1")
            check(at_top and faq_visible and scrolled['ctaVisible'] and scrolled['headerTop'] == 0 and scrolled['ctaInside'] and anchor_ok,
                  f'cabeçalho fixo mostra Inscreva-se só depois do hero, com Dúvidas no menu e âncoras visíveis, em {vw}px', str((at_top, faq_visible, scrolled, anchor_ok)))
            nav_page.close()

        # Robustez: endereço limpo após atualização, CTA recalculado ao mudar de
        # tamanho e diálogo de inscrição que só aceita destinos https.
        robust = open_page(viewport={"width": 1280, "height": 800}, reduced_motion="reduce")
        robust.goto(url + '?site-version=antiga&x=1#faq', wait_until="load")
        # A limpeza acontece depois de confirmar, no version.json, que a página está atualizada.
        try: robust.wait_for_function("() => !location.search.includes('site-version')", timeout=3000)
        except Exception: pass
        clean = robust.evaluate("() => ({search: location.search, hash: location.hash})")
        check(clean == {'search': '?x=1', 'hash': '#faq'}, 'endereço perde ?site-version= depois de carregar e mantém a seção e os outros parâmetros', str(clean))
        robust.evaluate("() => window.scrollTo(0, document.querySelector('#objetivos').offsetTop)")
        robust.wait_for_timeout(250)
        robust.set_viewport_size({"width": 390, "height": 844})
        robust.wait_for_timeout(400)
        robust.evaluate("() => window.scrollTo(0, document.querySelector('#objetivos').offsetTop)")
        robust.wait_for_timeout(400)
        after_resize = robust.evaluate("() => document.querySelector('.site-header').classList.contains('has-cta')")
        robust.evaluate("() => window.scrollTo(0, 0)")
        robust.wait_for_timeout(400)
        at_top_after_resize = robust.evaluate("() => !document.querySelector('.site-header').classList.contains('has-cta')")
        check(after_resize and at_top_after_resize, 'Inscreva-se do cabeçalho continua certo depois de mudar o tamanho da tela', str((after_resize, at_top_after_resize)))
        robust.close()

        # Na fronteira do hero, pequenas oscilações do trackpad não podem
        # alternar o CTA a cada pixel e fazer o cabeçalho piscar.
        stable_header = open_page(viewport={"width":820,"height":900}, reduced_motion="reduce")
        stable_header.goto(url, wait_until="load")
        threshold = stable_header.evaluate("""() => {
          const header = document.querySelector('.site-header');
          const heroCta = document.querySelector('.hero__actions .pill');
          return scrollY + heroCta.getBoundingClientRect().bottom - header.getBoundingClientRect().bottom;
        }""")
        visible_states = []
        for offset in (12, -4, -12, 4, 12):
            stable_header.evaluate("top => scrollTo(0, top)", threshold + offset)
            stable_header.wait_for_timeout(100)
            visible_states.append(stable_header.locator('.site-header').evaluate("header => header.classList.contains('has-cta')"))
        check(visible_states == [True, True, False, False, True],
              'Inscreva-se do cabeçalho usa uma zona estável e não pisca na fronteira do hero', str(visible_states))
        stable_header.close()

        # A entrada do CTA não pode deslocar o menu inteiro em um único frame.
        smooth_header = open_page(viewport={"width":820,"height":900}, reduced_motion="no-preference")
        smooth_header.goto(url, wait_until="load")
        transition_threshold = smooth_header.evaluate("""() => {
          const header = document.querySelector('.site-header');
          const heroCta = document.querySelector('.hero__actions .pill');
          return scrollY + heroCta.getBoundingClientRect().bottom - header.getBoundingClientRect().bottom;
        }""")
        transition_start = smooth_header.evaluate("""() => ({
          navLeft: document.querySelector('.site-nav').getBoundingClientRect().left,
          headerHeight: document.querySelector('.site-header').getBoundingClientRect().height,
          ctaHidden: document.querySelector('[data-header-cta]').hidden,
          ctaWidth: document.querySelector('[data-header-cta]').getBoundingClientRect().width
        })""")
        smooth_header.evaluate("top => scrollTo(0, top)", transition_threshold + 12)
        smooth_header.wait_for_timeout(80)
        transition_middle = smooth_header.evaluate("() => document.querySelector('.site-nav').getBoundingClientRect().left")
        smooth_header.wait_for_timeout(300)
        transition_end = smooth_header.evaluate("""() => ({
          navLeft: document.querySelector('.site-nav').getBoundingClientRect().left,
          headerHeight: document.querySelector('.site-header').getBoundingClientRect().height
        })""")
        smooth_ok = (not transition_start['ctaHidden'] and transition_start['ctaWidth'] <= 1 and
                     transition_start['navLeft'] > transition_middle > transition_end['navLeft'] and
                     abs(transition_start['headerHeight'] - transition_end['headerHeight']) <= 1)
        check(smooth_ok, 'Inscreva-se entra progressivamente sem salto do menu nem mudança de altura',
              str((transition_start, transition_middle, transition_end)))
        smooth_header.close()

        unsafe = open_page(viewport={"width": 1280, "height": 800}, reduced_motion="reduce")
        unsafe.goto(url, wait_until="load")
        unsafe.route('https://us02web.zoom.us/**', lambda route: route.abort())
        unsafe.locator('a[data-requires-enrollment]').first.click()
        unsafe_href = unsafe.evaluate("""() => {
          const enrolled = document.querySelector('[data-enrollment-enrolled]');
          enrolled.dataset.href = 'javascript:alert(1)';
          enrolled.checked = true;
          enrolled.dispatchEvent(new Event('change', {bubbles: true}));
          return document.querySelector('[data-enrollment-continue]').getAttribute('href');
        }""")
        check(unsafe_href is None, 'diálogo de inscrição não aceita destino javascript:', str(unsafe_href))
        unsafe.close()

        # Página publicada (sem a cópia de antes do curso): encontros passados
        # sem link do Zoom no código e política de segurança sem violações.
        published = (ROOT / 'index.html').read_text(encoding='utf-8')
        past_actions = [re.search(r'<article class="day" id="encontro-%d".*?<div class="day__actions"[^>]*>(.*?)</div>' % n, published, re.S).group(1) for n in (1, 2)]
        check('zoom.us' not in published and all('btn--ended' in a and 'href=' not in a for a in past_actions),
              'encontros que já passaram ficam encerrados no HTML, sem link do Zoom no código da página')
        check('<script>' not in published and 'style="' not in published and 'http-equiv="Content-Security-Policy"' in published,
              'HTML sem script nem estilo embutidos, com política de segurança (CSP)')
        csp_violations = []
        for vw, vh, precourse in ((1280, 800, True), (390, 844, True), (1280, 800, False)):
            csp_page = browser.new_page(viewport={"width": vw, "height": vh}, reduced_motion="reduce")
            csp_page.clock.set_fixed_time(COURSE_DATE)
            if precourse: use_precourse(csp_page)
            csp_page.route('https://us02web.zoom.us/**', lambda route: route.abort())
            csp_page.add_init_script("document.addEventListener('securitypolicyviolation', (e) => (window.__csp = window.__csp || []).push(e.violatedDirective + ' ' + e.blockedURI))")
            csp_page.goto(url, wait_until="load")
            csp_page.evaluate("async () => { for (let y = 0; y < document.body.scrollHeight; y += 700) { scrollTo(0, y); await new Promise((r) => setTimeout(r, 40)); } }")
            csp_page.locator('.faq__item summary').first.click()
            csp_page.locator('.speaker summary').first.click()
            csp_page.keyboard.press('Escape')
            if precourse and csp_page.locator('a[data-requires-enrollment]').count():
                csp_page.locator('a[data-requires-enrollment]').first.click()
                csp_page.keyboard.press('Escape')
            ready = csp_page.evaluate("() => ['js', 'schedule-ready', 'main-ready'].every((name) => document.documentElement.classList.contains(name))")
            csp_violations += csp_page.evaluate("() => window.__csp || []") + ([] if ready else ['head.js ou main.js não rodou'])
            csp_page.close()
        check(not csp_violations, 'nenhuma violação da política de segurança ao usar a página', str(csp_violations[:4]))

        # HTML desatualizado (cache ou CDN atrasada) com version.json novo: no
        # máximo uma recarga por versão, sem loop, e a trava fica no endereço.
        stale_context = browser.new_context()
        stale_docs = []
        stale_context.on('request', lambda r: r.resource_type == 'document' and stale_docs.append(r.url))
        stale_context.route('**/version.json**', lambda r: r.fulfill(status=200, content_type='application/json', body='{"version":"versao-nova-teste"}'))
        stale = stale_context.new_page()
        stale.goto(url + '?x=1#cronograma', wait_until='commit')
        stale.wait_for_timeout(4000)
        stale_url = stale.evaluate("() => location.search + location.hash")
        check(len(stale_docs) <= 2 and 'site-version=versao-nova-teste' in stale_url and stale_url.endswith('#cronograma'),
              'HTML antigo com version.json novo recarrega no máximo uma vez, sem loop', str((len(stale_docs), stale_url)))
        stale_context.close()

        # Fuso de quem acessa não muda o dia: 10/11 às 13h de Brasília (aula às 14h)
        # e 19/11 às 23h (em Tóquio já é dia 20) valem como em Brasília.
        tz_issues = []
        for moment, e3_ended, course_ended in (('2026-11-10T13:00:00-03:00', False, False), ('2026-11-19T23:00:00-03:00', True, False), ('2026-11-20T00:30:00-03:00', True, True)):
            for tz in ('America/Sao_Paulo', 'Asia/Tokyo', 'Pacific/Kiritimati', 'Pacific/Pago_Pago'):
                tz_context = browser.new_context(timezone_id=tz)
                use_precourse(tz_context)
                tz_page = tz_context.new_page()
                tz_page.clock.set_fixed_time(datetime.fromisoformat(moment))
                tz_page.goto(url, wait_until="load")
                got = tz_page.evaluate("() => [document.querySelector('#encontro-3 .day__actions .btn').classList.contains('btn--ended'), document.documentElement.classList.contains('course-ended')]")
                if got != [e3_ended, course_ended]: tz_issues.append((moment, tz, got))
                tz_context.close()
        check(not tz_issues, 'encontros e estado do curso seguem o dia de Brasília em qualquer fuso', str(tz_issues))

        # Depois de 19/11, a página entra no estado de curso encerrado.
        for moment, ended_expected in (('2026-11-19T15:00:00-03:00', False), ('2026-11-20T09:00:00-03:00', True)):
            for vw, vh in ((1280, 800), (390, 844)):
                state_page = browser.new_page(viewport={"width": vw, "height": vh}, reduced_motion="reduce")
                use_precourse(state_page)
                state_page.clock.set_fixed_time(datetime.fromisoformat(moment))
                state_page.goto(url, wait_until="load")
                state_page.evaluate("() => window.scrollTo(0, document.querySelector('#objetivos').offsetTop)")
                state_page.wait_for_timeout(300)
                st = state_page.evaluate("""() => {
                  const shown = (el) => !!el && el.getClientRects().length > 0;
                  return {ended: document.documentElement.classList.contains('course-ended'),
                    heroCta: shown(document.querySelector('.hero__actions .pill')), endedText: shown(document.querySelector('.hero__ended')),
                    tag: [...document.querySelectorAll('.hero__tag')].filter(shown).map((el) => el.textContent.trim()),
                    headerCta: shown(document.querySelector('[data-header-cta]')),
                    note: [...document.querySelectorAll('.schedule-note__text')].filter(shown).map((el) => el.textContent.trim().split('.')[0]),
                    faqSignup: shown(document.querySelector('.faq__item[data-when="open"]'))};
                }""")
                if ended_expected:
                    ok = st['ended'] and not st['heroCta'] and st['endedText'] and st['tag'] == ['Curso encerrado'] and not st['headerCta'] \
                        and st['note'] == ['O curso foi encerrado em 19 de novembro'] and not st['faqSignup']
                else:
                    ok = not st['ended'] and st['heroCta'] and not st['endedText'] and st['tag'] == ['Curso gratuito · Online e ao vivo'] \
                        and st['headerCta'] and st['note'] == ['As aulas são exclusivas para inscritos'] and st['faqSignup']
                label = 'mostra o estado de curso encerrado' if ended_expected else 'continua com inscrição aberta'
                check(ok, f'em {moment[:16]} a página {label} em {vw}px', str(st))
                state_page.close()

        # Limites das faixas responsivas (um pixel antes e depois de cada corte).
        boundary = open_page(viewport={"width": 1024, "height": 900}, reduced_motion="reduce")
        boundary.goto(url, wait_until="load")
        boundary.locator('.day-nav__tabs [data-day="3"]').click()  # Encontro 4, com a aula da Inovafhytos
        boundary_issues = []
        for width in (359, 360, 361, 375, 430, 431, 480, 481, 599, 600, 767, 768, 799, 800, 1023, 1024, 1199, 1200, 2560):
            boundary.set_viewport_size({"width": width, "height": 900})
            boundary.wait_for_timeout(80)
            state = boundary.evaluate("""() => {
              const strong = document.querySelector('.hero__title-strong');
              const range = document.createRange(); range.selectNodeContents(strong);
              const right = Math.max(...[...range.getClientRects()].map((line) => line.right));
              const heading = document.querySelector('.hero__heading').getBoundingClientRect();
              const lines = (el) => Math.round(el.getBoundingClientRect().height / parseFloat(getComputedStyle(el).lineHeight));
              const logos = [...document.querySelectorAll('.lesson--company .lesson__about .lesson__logo')];
              return {
                // O logo fica dentro da apresentação e não aparece com ela fechada.
                logo: logos.length === 2 && logos.every((logo) => !logo.checkVisibility()),
                overflow: document.documentElement.scrollWidth - innerWidth,
                titleFits: right <= heading.right + 1,
                names: [...document.querySelectorAll('.speaker__name')].every((el) => lines(el) <= 2 && el.scrollWidth <= el.clientWidth + 1),
                topics: [...document.querySelectorAll('.speaker__topic')].every((el) => el.scrollWidth <= el.clientWidth + 1),
                // Painel lima: "Horário" e "Dias" lado a lado (como no celular),
                // sem vazar; no desktop, base alinhada à dos botões do hero.
                facts: (() => {
                  if (innerWidth >= 600 && innerWidth < 1024) return true;  // tablet: coluna ao lado do calendário
                  const f = document.querySelector('.dates__facts'), items = [...f.children];
                  const side = Math.abs(items[0].getBoundingClientRect().top - items[1].getBoundingClientRect().top) < 2;
                  const fits = [...f.querySelectorAll('dd')].every((dd) => dd.scrollWidth <= dd.clientWidth + 1);
                  const buttons = Math.max(...[...document.querySelectorAll('.hero__actions a')].map((a) => a.getBoundingClientRect().bottom));
                  return side && fits && (innerWidth < 1024 || Math.abs(f.getBoundingClientRect().bottom - buttons) <= 1);
                })(),
                // O painel verde fica contido em todas as faixas: no celular
                // largo há duas colunas; no tablet, calendário e fatos se
                // empilham, com as seis datas e os dois fatos em linhas únicas.
                dates: (() => {
                  const panel = document.querySelector('.dates');
                  const calendar = panel.querySelector('.dates__cal');
                  const facts = panel.querySelector('.dates__facts');
                  const month = panel.querySelector('.dates__month');
                  const p = panel.getBoundingClientRect();
                  const c = calendar.getBoundingClientRect();
                  const f = facts.getBoundingClientRect();
                  const m = month.getBoundingClientRect();
                  const inside = [c, f, m].every((r) =>
                    r.left >= p.left - 1 && r.right <= p.right + 1 &&
                    r.top >= p.top - 1 && r.bottom <= p.bottom + 1
                  );
                  const cellsFit = [...panel.querySelectorAll('.dates__days li')]
                    .every((cell) => cell.scrollWidth <= cell.clientWidth + 1);
                  const factItems = [...facts.children].map((item) => item.getBoundingClientRect());
                  const wideMobileColumns = innerWidth < 600 || innerWidth >= 768 || c.right <= f.left + 1;
                  const tabletStack = innerWidth < 768 || innerWidth >= 1024 || f.top >= c.bottom - 1;
                  const tabletFactsRow = innerWidth < 768 || innerWidth >= 1024 ||
                    Math.abs(factItems[0].top - factItems[1].top) <= 1;
                  const tabletMonth = innerWidth < 768 || innerWidth >= 1024 ||
                    parseFloat(getComputedStyle(month).fontSize) <= 88.1;
                  return inside && cellsFit && wideMobileColumns && tabletStack && tabletFactsRow && tabletMonth;
                })(),
                // Selo e data cabem no card, sem corte, na mesma linha.
                chips: [...document.querySelectorAll('.speaker__meta')].every((meta) => {
                  const box = meta.getBoundingClientRect();
                  const leaves = [...meta.querySelectorAll('span')].filter((el) => !el.children.length);
                  const inside = leaves.every((el) => {
                    const r = el.getBoundingClientRect();
                    return r.left >= box.left - 1 && r.right <= box.right + 1 && el.scrollWidth <= el.clientWidth + 1;
                  });
                  return inside && Math.abs(meta.lastElementChild.getBoundingClientRect().top - leaves[0].getBoundingClientRect().top) <= 1;
                }),
              };
            }""")
            if state['overflow'] > 1 or not state['logo'] or not state['titleFits'] or not state['names'] or not state['topics'] or not state['chips'] or not state['facts'] or not state['dates']:
                boundary_issues.append((width, state))
        boundary.close()
        check(not boundary_issues, 'limites dos breakpoints sem overflow, com hero e painel verde contidos, título na coluna, selo inteiro e Horário/Dias lado a lado', str(boundary_issues))

        # Encontros de dias anteriores viram "Aula encerrada" (datas simuladas).
        ended_cases = {
            '2026-11-07T12:00:00-03:00': (['encontro-1', 'encontro-2'], 'encontro-3'),  # sábado entre encontros
            '2026-11-05T15:00:00-03:00': (['encontro-1'], 'encontro-2'),  # durante a aula do Encontro 2
        }
        ended_issues = []
        for moment, (expected_ended, current_day) in ended_cases.items():
            when = browser.new_page(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
            use_precourse(when)
            when_errors = []
            when.on("pageerror", lambda exc: when_errors.append(str(exc)))
            when.clock.set_fixed_time(datetime.fromisoformat(moment))
            when.goto(url, wait_until="load")
            state = when.evaluate("""() => [...document.querySelectorAll('.day')].map((day) => {
              const btn = day.querySelector('.day__actions .btn');
              return {id: day.id, ended: btn.classList.contains('btn--ended'), disabled: btn.disabled === true,
                      link: btn.tagName === 'A', label: btn.querySelector('.btn__label')?.firstChild?.textContent.trim() || '',
                      status: btn.querySelector('.btn__status')?.textContent.trim() || '', aria: btn.getAttribute('aria-label') || ''};
            })""")
            ended = [item['id'] for item in state if item['ended']]
            ok = (
                ended == expected_ended and not when_errors and
                all(item['disabled'] and not item['link'] and item['label'] == 'Aula encerrada' and item['status'] == 'Gravação por e-mail' and 'encerrada' in item['aria']
                    for item in state if item['ended']) and
                not next(item for item in state if item['id'] == current_day)['ended']
            )
            if not ok: ended_issues.append((moment, ended, when_errors))
            when.close()
        check(not ended_issues, 'encontros de dias anteriores mostram Aula encerrada, desativado, e o do dia continua ativo', str(ended_issues))

        tablet_context = browser.new_context(
            viewport={"width":820,"height":1180},
            is_mobile=True,
            has_touch=True,
            reduced_motion="reduce",
        )
        tablet_context.clock.set_fixed_time(COURSE_DATE)
        use_precourse(tablet_context)
        tablet = tablet_context.new_page()
        tablet.goto(url, wait_until="domcontentloaded")
        tablet_bios = tablet.locator('.speaker__bio')
        visible_tablet_bios = tablet_bios.locator('summary').evaluate_all("""
          els => els.filter((el) => {
            const rect = el.getBoundingClientRect();
            return rect.width > 0 && rect.height >= 48;
          }).length
        """)
        check(tablet_bios.count() == speaker_count and visible_tablet_bios == speaker_count, 'todas as biografias têm área de toque segura no tablet')
        if tablet_bios.count():
            first_tablet_bio = tablet_bios.first
            first_tablet_bio.locator('summary').tap()
            tablet_dialog = tablet.locator('[data-speaker-bio-dialog]')
            check(tablet_dialog.get_attribute('open') is not None and first_tablet_bio.get_attribute('open') is None, 'tablet abre biografia em diálogo sem alterar a grade')
            tablet_dialog.locator('[data-speaker-bio-close]').tap()

        tablet_schedule_controls = tablet.locator('.day-nav__tabs button, .day-nav .round-link')
        safe_tablet_schedule_controls = tablet_schedule_controls.evaluate_all("""
          els => els.filter((el) => {
            const rect = el.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
          }).every((el) => {
            const rect = el.getBoundingClientRect();
            return rect.width >= 48 && rect.height >= 48;
          })
        """)
        check(safe_tablet_schedule_controls, 'controles do cronograma têm pelo menos 48px no tablet')
        tablet_context.close()
        browser.close()
finally:
    server.shutdown()

out = ROOT / '.site-audit' / 'regressao.json'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps({'checks': len(results), 'failed': issues, 'results': results}, indent=2, ensure_ascii=False), encoding='utf-8')
print(f"\n{len(results)-len(issues)}/{len(results)} verificações passaram. Relatório: {out}")
sys.exit(1 if issues else 0)
