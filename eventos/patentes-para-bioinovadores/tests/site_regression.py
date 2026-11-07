#!/usr/bin/env python3
"""Testes de regressão com Chromium/Playwright para site estático."""
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlparse
from datetime import datetime
import json
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

def check(ok, title, detail=""):
    results.append({"test": title, "passed": bool(ok), "detail": detail})
    print(("PASS" if ok else "FAIL") + " " + title + (" | " + detail if detail else ""))
    if not ok: issues.append(title)

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
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
                const name = box('h3');
                const topic = box('.speaker__topic');
                const near = (value) => Math.abs(value - 8) <= 1;
                return near(name.top - meta.bottom) && (!topic || near(topic.top - name.bottom));
              })
            """)
            check(speaker_rhythm, f"cards de palestrantes mantêm 8px entre selo, nome e tema em {width}x{height}")
            two_lines = page.locator('.speaker').evaluate_all("""
              cards => cards.map((card) => {
                const lines = (el) => el ? Math.round(el.getBoundingClientRect().height / parseFloat(getComputedStyle(el).lineHeight)) : 2;
                return [card.querySelector('h3'), card.querySelector('.speaker__topic')].map(lines);
              })
            """)
            names_ok = all(name == 2 for name, _ in two_lines)
            # Abaixo de 360px, uma linha longa do tema pode quebrar de novo.
            topics_ok = all(topic == 2 if width >= 360 else topic <= 3 for _, topic in two_lines)
            check(names_ok and topics_ok, f"nomes e temas dos palestrantes ficam em duas linhas em {width}x{height}", str(two_lines))
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
            page.locator('.day-nav__tabs [data-day="3"]').click()
            company_layout = page.locator('#encontro-4').evaluate("""day => {
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
              };
              details.open = false;
              return {...closed, ...opened};
            }""")
            check(all(company_layout.values()), f"logo da Inovafhytos só aparece ao abrir a apresentação, acima do texto, em {width}x{height}", str(company_layout))
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
        check(layout_mobile['audienceBackground'] == 'rgb(255, 255, 255)' and layout_mobile['audienceRadius'] >= 12 and layout_mobile['audienceItemSize'] >= 18,
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
          els => els.map((el) => el.dataset.index).join(',') === '01,02,03,04,05,06,07' &&
            els.every((el) => {
              const content = getComputedStyle(el, '::before').content;
              return content.includes('attr') || content.replace(/"/g, '') === el.dataset.index;
            })
        """)
        check(program_numbers, 'conteúdo programático numerado de 01 a 07 sem contador CSS (evita "00" no Safari)')
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
            "els => els.length > 0 && els.every((el) => el.textContent.trim() === 'Em breve')"
        )
        check(pending_statuses, 'ações pendentes indicam Em breve')
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
        check(speaker_count == 10 and bios.count() == speaker_count and visible_bios == speaker_count, 'as dez biografias ficam acessíveis no mobile')
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
            'encontro-3': [('14:00', '16:00', 'Profa. Dra. Cláudia Auler'), ('16:00', '17:00', 'Empresa a confirmar')],
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
            const name = card.querySelector('h3').textContent.trim();
            const meta = card.querySelector('.speaker__meta span:last-child').textContent.trim();
            return {name, card: meta.replace(/\\/\\d{2}$/, '').match(/\\d{2}/g) || [], schedule: days[name] || []};
          });
        }""")
        dates_match = all(item['card'] == item['schedule'] and item['card'] for item in cards_vs_schedule)
        firsts = [item['card'][0] for item in cards_vs_schedule if item['card']]
        check(dates_match and firsts == sorted(firsts), 'datas dos cards de palestrantes batem com o cronograma e seguem a ordem dos dias', str(cards_vs_schedule))
        company = page.locator('#encontro-4 .lesson--company')
        logo_ok = company.locator('.lesson__logo').evaluate("img => img.complete || img.loading === 'lazy'") and company.locator('.lesson__logo').get_attribute('alt')
        instagram = page.locator('#encontro-4 .lesson__about a[href*="instagram.com/inovafhytos_cerrado"]')
        check(company.count() == 1 and bool(logo_ok) and instagram.count() == 1 and instagram.get_attribute('rel') == 'noopener noreferrer',
              'aula da Inovafhytos mostra logo, apresentação e Instagram')

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
          return {above: Math.round(hero.top - header.bottom), below: Math.round(next.top - hero.bottom), fits: hero.bottom <= innerHeight};
        }""")
        check(hero_space['above'] >= 32 and hero_space['below'] <= 160 and hero_space['fits'],
              'hero tem respiro abaixo do menu e não acumula espaço antes da seção seguinte', str(hero_space))
        fold_issues = []
        for fold_w, fold_h in ((1024, 600), (1280, 720), (1366, 768), (1440, 900)):
            desktop.set_viewport_size({"width": fold_w, "height": fold_h})
            desktop.wait_for_timeout(60)
            bottom = desktop.evaluate("document.querySelector('.hero__actions .pill').getBoundingClientRect().bottom")
            if bottom > fold_h: fold_issues.append((fold_w, fold_h, round(bottom)))
        desktop.set_viewport_size({"width": 1280, "height": 900})
        check(not fold_issues, 'botão Inscreva-se fica visível sem rolar em telas de desktop baixas', str(fold_issues))
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
        ten_grid = desktop.locator('.speakers').evaluate(speaker_grid_js)
        check(
            ten_grid['columns'] == 5 and ten_grid['rows'] == 2 and
            ten_grid['leftGap'] <= 1 and ten_grid['rightGap'] <= 1,
            'grade de dez palestrantes forma duas linhas de cinco alinhadas ao container no desktop',
            str(ten_grid),
        )
        desktop.set_viewport_size({"width": 1100, "height": 900})
        narrow_grid = desktop.locator('.speakers').evaluate(speaker_grid_js)
        check(
            narrow_grid['rows'] == 3 and narrow_grid['lastRowCount'] == 2 and narrow_grid['lastRowCentered'] and
            narrow_grid['leftGap'] <= 1 and narrow_grid['rightGap'] <= 1,
            'entre 1024 e 1199px, a grade usa quatro colunas e centraliza a última dupla',
            str(narrow_grid),
        )
        desktop.close()

        # Limites das faixas responsivas (um pixel antes e depois de cada corte).
        boundary = open_page(viewport={"width": 1024, "height": 900}, reduced_motion="reduce")
        boundary.goto(url, wait_until="load")
        boundary.locator('.day-nav__tabs [data-day="3"]').click()  # Encontro 4, com a aula da Inovafhytos
        boundary_issues = []
        for width in (359, 360, 361, 430, 431, 480, 481, 599, 600, 767, 768, 1023, 1024, 1199, 1200, 2560):
            boundary.set_viewport_size({"width": width, "height": 900})
            boundary.wait_for_timeout(80)
            state = boundary.evaluate("""() => {
              const strong = document.querySelector('.hero__title-strong');
              const range = document.createRange(); range.selectNodeContents(strong);
              const right = Math.max(...[...range.getClientRects()].map((line) => line.right));
              const heading = document.querySelector('.hero__heading').getBoundingClientRect();
              const lines = (el) => Math.round(el.getBoundingClientRect().height / parseFloat(getComputedStyle(el).lineHeight));
              const logo = document.querySelector('#encontro-4 .lesson--company .lesson__about .lesson__logo');
              return {
                // O logo fica dentro da apresentação e não aparece com ela fechada.
                logo: Boolean(logo) && !logo.checkVisibility(),
                overflow: document.documentElement.scrollWidth - innerWidth,
                titleFits: right <= heading.right + 1,
                names: [...document.querySelectorAll('.speaker h3')].every((el) => lines(el) === 2),
                topics: [...document.querySelectorAll('.speaker__topic')].every((el) => lines(el) === 2),
              };
            }""")
            if state['overflow'] > 1 or not state['logo'] or not state['titleFits'] or not state['names'] or (width >= 360 and not state['topics']):
                boundary_issues.append((width, state))
        boundary.close()
        check(not boundary_issues, 'limites dos breakpoints sem overflow, com título do hero na coluna e cards em duas linhas', str(boundary_issues))

        # Encontros de dias anteriores viram "Aula encerrada" (datas simuladas).
        ended_cases = {
            '2026-11-07T12:00:00-03:00': (['encontro-1', 'encontro-2'], 'encontro-3'),  # sábado entre encontros
            '2026-11-05T15:00:00-03:00': (['encontro-1'], 'encontro-2'),  # durante a aula do Encontro 2
        }
        ended_issues = []
        for moment, (expected_ended, current_day) in ended_cases.items():
            when = browser.new_page(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
            when_errors = []
            when.on("pageerror", lambda exc: when_errors.append(str(exc)))
            when.clock.set_fixed_time(datetime.fromisoformat(moment))
            when.goto(url, wait_until="load")
            state = when.evaluate("""() => [...document.querySelectorAll('.day')].map((day) => {
              const btn = day.querySelector('.day__actions .btn');
              return {id: day.id, ended: btn.classList.contains('btn--ended'), disabled: btn.disabled === true,
                      link: btn.tagName === 'A', label: btn.textContent.trim(), aria: btn.getAttribute('aria-label') || ''};
            })""")
            ended = [item['id'] for item in state if item['ended']]
            ok = (
                ended == expected_ended and not when_errors and
                all(item['disabled'] and not item['link'] and item['label'] == 'Aula encerrada' and 'encerrada' in item['aria']
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
