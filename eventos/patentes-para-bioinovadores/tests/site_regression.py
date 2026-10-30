#!/usr/bin/env python3
"""Testes de regressão com Chromium/Playwright para site estático."""
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlparse
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
        for width, height in SIZES:
            page = browser.new_page(viewport={"width":width,"height":height}, reduced_motion="reduce")
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
            page.close()

        page = browser.new_page(viewport={"width":390,"height":844}, reduced_motion="reduce")
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
        check(action_statuses.count() == 2, 'ações do encontro exibem dois estados Em breve')
        statuses_below = action_statuses.evaluate_all("""
          els => els.every((el) => {
            const status = el.getBoundingClientRect();
            const label = el.parentElement.getBoundingClientRect();
            return el.textContent.trim() === 'Em breve' && status.top > label.top + 2;
          })
        """)
        check(statuses_below, 'Em breve fica abaixo do rótulo no mobile')

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

        bios = page.locator('.speaker__bio')
        speaker_count = page.locator('.speaker').count()
        visible_bios = bios.locator('summary').evaluate_all("""
          els => els.filter((el) => {
            const rect = el.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
          }).length
        """)
        check(speaker_count == 9 and bios.count() == speaker_count and visible_bios == speaker_count, 'as nove biografias ficam acessíveis no mobile')
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

        manifest = page.evaluate("async () => await (await fetch('version.json', {cache: 'no-store'})).json()")
        embedded_version = page.locator('html').get_attribute('data-site-version')
        check(manifest.get('version') == embedded_version, 'version.json corresponde à versão embutida no HTML')
        page.close()

        desktop = browser.new_page(viewport={"width":1280,"height":900}, reduced_motion="reduce")
        desktop.goto(url, wait_until="domcontentloaded")
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

        nine_grid = desktop.locator('.speakers').evaluate("""
          (list) => {
            const cards = [...list.children];
            const listRect = list.getBoundingClientRect();
            const rects = cards.map((card) => card.getBoundingClientRect());
            const lefts = [...new Set(rects.map((rect) => Math.round(rect.left)))];
            return {
              columns: lefts.length,
              leftGap: Math.abs(Math.min(...rects.map((rect) => rect.left)) - listRect.left),
              rightGap: Math.abs(listRect.right - Math.max(...rects.map((rect) => rect.right))),
            };
          }
        """)
        check(
            nine_grid['columns'] == 3 and
            nine_grid['leftGap'] <= 1 and
            nine_grid['rightGap'] <= 1,
            'grade de nove palestrantes forma três colunas alinhadas ao container no desktop',
            str(nine_grid),
        )
        desktop.close()

        tablet_context = browser.new_context(
            viewport={"width":820,"height":1180},
            is_mobile=True,
            has_touch=True,
            reduced_motion="reduce",
        )
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
