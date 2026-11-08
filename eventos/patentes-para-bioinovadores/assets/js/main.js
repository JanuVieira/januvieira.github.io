/**
 * Patentes para Bioinovadores — interações da página.
 * Sem dependências. Sem JavaScript, todo o conteúdo continua acessível.
 */

const rootStyle = getComputedStyle(document.documentElement);
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');

const listenMediaChange = (query, listener) => {
  if (typeof query.addEventListener === 'function') query.addEventListener('change', listener);
  else query.addListener(listener);
};

const readDuration = (name, fallback) => {
  const value = rootStyle.getPropertyValue(name).trim();
  if (!value) return fallback;
  if (value.endsWith('ms')) return Number.parseFloat(value);
  if (value.endsWith('s')) return Number.parseFloat(value) * 1000;
  return fallback;
};

const motion = {
  standard: rootStyle.getPropertyValue('--ease-standard').trim() ||
    'cubic-bezier(0.32, 0.72, 0, 1)',
  out: rootStyle.getPropertyValue('--ease-out').trim() ||
    'cubic-bezier(0.22, 1, 0.36, 1)',
  exit: rootStyle.getPropertyValue('--ease-exit').trim() ||
    'cubic-bezier(0.4, 0, 1, 1)',
  press: readDuration('--dur-press', 120),
  reveal: readDuration('--dur-reveal', 280),
  disclose: readDuration('--dur-disclose', 420),
};

const runningAnimations = new Set();

const runAnimation = (element, keyframes, options, settle) => {
  if (reducedMotion.matches || typeof element.animate !== 'function') {
    settle?.();
    return null;
  }
  const animation = element.animate(keyframes, options);
  runningAnimations.add(animation);
  animation.finished.then(settle, settle).finally(() => runningAnimations.delete(animation));
  return animation;
};

// A troca da preferência deve encerrar também movimentos iniciados via JS.
listenMediaChange(reducedMotion, () => {
  if (!reducedMotion.matches) return;
  runningAnimations.forEach((animation) => animation.finish());
});

/**
 * Expande ou recolhe um <details> animando o seu conteúdo real.
 * O clique do summary também cobre Enter e Espaço, como no elemento nativo.
 */
function animateDisclosure(details, { content, enabled = () => true, onOpen, onClose } = {}) {
  const summary = details.querySelector(':scope > summary');
  if (!summary || !content) return;

  const setOpen = (open) => {
    details.open = open;
    if (open) onOpen?.();
    else onClose?.();
  };

  summary.addEventListener('click', (event) => {
    if (!enabled()) return;
    event.preventDefault();
    if (details.dataset.animating) return;

    const opening = !details.open;
    if (reducedMotion.matches || typeof content.animate !== 'function') {
      setOpen(opening);
      return;
    }

    details.dataset.animating = 'true';
    if (opening) setOpen(true);

    const style = getComputedStyle(content);
    const fullHeight = content.offsetHeight;
    const paddingTop = style.paddingTop;
    const paddingBottom = style.paddingBottom;
    content.style.overflow = 'hidden';

    const clear = () => {
      content.style.removeProperty('height');
      content.style.removeProperty('padding-top');
      content.style.removeProperty('padding-bottom');
      content.style.removeProperty('opacity');
      content.style.removeProperty('overflow');
      delete details.dataset.animating;
    };

    if (opening) {
      runAnimation(
        content,
        [
          { height: '0px', paddingTop: '0px', paddingBottom: '0px', opacity: 0 },
          { height: `${fullHeight}px`, paddingTop, paddingBottom, opacity: 1 },
        ],
        { duration: motion.disclose, easing: motion.standard },
        clear,
      );
      return;
    }

    onClose?.();
    runAnimation(
      content,
      [
        { height: `${fullHeight}px`, paddingTop, paddingBottom, opacity: 1 },
        { height: '0px', paddingTop: '0px', paddingBottom: '0px', opacity: 0 },
      ],
      { duration: motion.disclose * 0.75, easing: motion.exit },
      () => {
        details.open = false;
        clear();
      },
    );
  });
}

/** Carrossel de dias: navegação, anúncio acessível e transição FLIP de altura. */
function initDayCarousel() {
  const nav = document.querySelector('.day-nav');
  const days = [...document.querySelectorAll('.day')];
  if (!nav || days.length === 0) return;

  const tabs = [...nav.querySelectorAll('[data-day]')];
  const [prev, next] = nav.querySelectorAll('[data-step]');
  const status = nav.querySelector('.day-nav__status');
  const dayContainer = days[0].parentElement;
  if (tabs.length !== days.length || !prev || !next || !status || !dayContainer) return;

  const cardNavTemplate = document.querySelector('#schedule-card-nav-template');
  if (cardNavTemplate instanceof HTMLTemplateElement) {
    days.forEach((day) => {
      const actions = day.querySelector('.day__actions');
      if (actions) actions.after(cardNavTemplate.content.cloneNode(true));
    });
  }
  const cardNavs = days
    .map((day) => day.querySelector('.schedule-card-nav'))
    .filter(Boolean);
  let current = 0;

  const meetingLabel = (index) =>
    days[index]?.querySelector('.day__label h3')?.textContent.trim() ||
    `Encontro ${index + 1}`;

  const updateState = () => {
    tabs.forEach((tab, index) => tab.setAttribute('aria-pressed', String(index === current)));
    prev.disabled = current === 0;
    next.disabled = current === days.length - 1;
    status.textContent = `${meetingLabel(current)} de ${days.length}`;

    cardNavs.forEach((cardNav) => {
      const [cardPrev, cardNext] = cardNav.querySelectorAll('[data-card-step]');
      const cardStatus = cardNav.querySelector('.schedule-card-nav__status');
      if (!cardPrev || !cardNext || !cardStatus) return;
      cardPrev.disabled = current === 0;
      cardNext.disabled = current === days.length - 1;
      cardPrev.setAttribute(
        'aria-label',
        current === 0 ? 'Não há encontro anterior' : `Ver ${meetingLabel(current - 1)}`,
      );
      cardNext.setAttribute(
        'aria-label',
        current === days.length - 1
          ? 'Não há próximo encontro'
          : `Ver ${meetingLabel(current + 1)}`,
      );
      cardStatus.textContent = `${current + 1} de ${days.length}`;
    });
  };

  const show = (index, animate = true) => {
    if (animate && dayContainer.dataset.animating) return;
    const nextIndex = Math.max(0, Math.min(days.length - 1, index));
    if (nextIndex === current && animate) return;
    const oldHeight = dayContainer.offsetHeight;
    current = nextIndex;
    days.forEach((day, dayIndex) => (day.hidden = dayIndex !== current));
    updateState();

    if (!animate || reducedMotion.matches || typeof dayContainer.animate !== 'function') return;
    const newHeight = dayContainer.offsetHeight;
    dayContainer.dataset.animating = 'true';
    dayContainer.style.height = `${oldHeight}px`;
    dayContainer.style.overflow = 'hidden';
    runAnimation(
      dayContainer,
      [{ height: `${oldHeight}px` }, { height: `${newHeight}px` }],
      { duration: motion.disclose, easing: motion.standard },
      () => {
        dayContainer.style.removeProperty('height');
        dayContainer.style.removeProperty('overflow');
        delete dayContainer.dataset.animating;
      },
    );
  };

  nav.addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (!button || button.disabled) return;
    const index = button.dataset.step
      ? current + Number(button.dataset.step)
      : Number(button.dataset.day);
    show(index);
    if (button.disabled) tabs[current].focus();
  });

  nav.addEventListener('keydown', (event) => {
    const step = { ArrowLeft: -1, ArrowRight: 1 }[event.key];
    if (!step || !event.target.matches('[data-day]')) return;
    event.preventDefault();
    show(current + step);
    tabs[current].focus();
  });

  cardNavs.forEach((cardNav) => {
    cardNav.addEventListener('click', (event) => {
      const button = event.target.closest('[data-card-step]');
      if (!button || button.disabled) return;
      const step = Number(button.dataset.cardStep);
      const previous = current;
      show(current + step);
      if (current === previous) return;

      const activeNav = days[current].querySelector('.schedule-card-nav');
      const preferred = activeNav?.querySelector(`[data-card-step="${step}"]:not(:disabled)`);
      const fallback = activeNav?.querySelector('[data-card-step]:not(:disabled)');
      (preferred || fallback)?.focus({ preventScroll: true });
    });
  });

  const today = todayInBrasilia();
  const upcoming = days.findIndex((day) => day.dataset.date >= today);
  if (upcoming !== -1) {
    const badge = document.createElement('span');
    badge.className = 'day__badge';
    badge.textContent = days[upcoming].dataset.date === today ? 'Hoje' : 'Próximo encontro';
    days[upcoming].querySelector('.day__label h3')?.after(badge);
  }

  nav.hidden = false;
  cardNavs.forEach((cardNav) => (cardNav.hidden = false));
  show(upcoming === -1 ? days.length - 1 : upcoming, false);
  document.documentElement.classList.add('schedule-ready');
}

/** Menu do celular: painel sobreposto, fora da ordem de foco quando fechado. */
function initSiteMenu() {
  const header = document.querySelector('.site-header');
  const toggle = header?.querySelector('.site-header__toggle');
  const nav = header?.querySelector('.site-nav');
  if (!header || !toggle || !nav) return;
  const compact = matchMedia('(max-width: 767px)');

  const setOpen = (open) => {
    header.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    nav.inert = compact.matches && !open;
    if (compact.matches) nav.setAttribute('aria-hidden', String(!open));
    else nav.removeAttribute('aria-hidden');
  };

  toggle.hidden = false;
  header.classList.add('has-menu');
  setOpen(false);
  toggle.addEventListener('click', () => setOpen(!header.classList.contains('is-open')));
  nav.addEventListener('click', (event) => {
    if (event.target.closest('a')) setOpen(false);
  });
  document.addEventListener('click', (event) => {
    if (!header.contains(event.target)) setOpen(false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || !header.classList.contains('is-open')) return;
    setOpen(false);
    toggle.focus();
  });
  listenMediaChange(compact, () => setOpen(false));

  const onScroll = () => header.classList.toggle('is-scrolled', window.scrollY > 4);
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}

/** Data de hoje (AAAA-MM-DD) em Brasília. Os encontros acontecem no horário de
 *  Brasília, então "hoje", "próximo encontro" e "encerrado" não dependem do
 *  fuso de quem acessa. */
function todayInBrasilia() {
  try {
    return new Intl.DateTimeFormat('sv', { timeZone: 'America/Sao_Paulo' }).format(new Date());
  } catch {
    return new Date().toLocaleDateString('sv');
  }
}

/** "Inscreva-se" no cabeçalho fixo: aparece quando o botão do hero sai da
 *  tela por cima e some quando ele volta. Depois do fim do curso, o CSS
 *  esconde o botão (data-when="open"). */
function initHeaderCta() {
  const header = document.querySelector('.site-header');
  const cta = document.querySelector('[data-header-cta]');
  const heroCta = document.querySelector('.hero__actions .pill');
  if (!header || !cta || !heroCta) return;
  if (document.documentElement.classList.contains('course-ended')) return;

  // Uma pequena zona neutra impede que oscilações de 1px do scroll/resize
  // façam o botão entrar e sair repetidamente na borda do cabeçalho.
  const hysteresis = 8;
  let visible = header.classList.contains('has-cta');
  let frame = 0;

  const setVisible = (next) => {
    if (next === visible) return;
    visible = next;
    header.classList.toggle('has-cta', visible);
    cta.inert = !visible;
    if (visible) {
      cta.removeAttribute('aria-hidden');
      cta.removeAttribute('tabindex');
    } else {
      cta.setAttribute('aria-hidden', 'true');
      cta.tabIndex = -1;
    }
  };

  // O botão participa do layout desde a inicialização. No desktop, o CSS
  // expande o espaço de forma suave; no celular, o espaço já fica reservado.
  // Assim nenhum item do cabeçalho muda de posição em um único quadro.
  cta.inert = true;
  cta.setAttribute('aria-hidden', 'true');
  cta.tabIndex = -1;
  header.classList.add('is-cta-ready');
  cta.hidden = false;

  const update = () => {
    frame = 0;
    const headerBottom = header.getBoundingClientRect().bottom;
    const heroBottom = heroCta.getBoundingClientRect().bottom;
    const distance = heroBottom - headerBottom;

    if (!visible && distance <= -hysteresis) setVisible(true);
    else if (visible && distance >= hysteresis) setVisible(false);
  };

  const schedule = () => {
    if (frame) return;
    frame = requestAnimationFrame(update);
  };

  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule, { passive: true });
  if ('ResizeObserver' in window) {
    const resizeObserver = new ResizeObserver(schedule);
    resizeObserver.observe(header);
    resizeObserver.observe(heroCta);
  }
  document.fonts?.ready.then(schedule);
  schedule();
}

/** Garante a volta ao início mesmo quando #topo já está na URL. */
function initBackToTop() {
  const control = document.querySelector('[data-back-to-top]');
  if (!control) return;

  control.addEventListener('click', (event) => {
    event.preventDefault();
    window.scrollTo({
      top: 0,
      behavior: reducedMotion.matches ? 'auto' : 'smooth',
    });
    history.replaceState(null, '', `${location.pathname}${location.search}#topo`);
  });
}

/** Mantém um cartão em destaque no desktop e usa acordeão no celular. */
function initGoalCards() {
  const list = document.querySelector('.goal-cards');
  if (!list) return;
  const cards = [...list.querySelectorAll('.goal-card')];
  const compact = matchMedia('(max-width: 767px)');
  if (cards.length === 0) return;

  const openCard = (card) => {
    cards.forEach((item) => item.classList.toggle('is-open', item === card));
  };
  const measure = () => cards.forEach((card) => {
    const more = card.querySelector('.goal-card__more');
    if (more) card.style.setProperty('--more-h', `${more.scrollHeight}px`);
  });
  let measureFrame = 0;
  window.addEventListener('resize', () => {
    cancelAnimationFrame(measureFrame);
    measureFrame = requestAnimationFrame(measure);
  });
  document.fonts?.ready.then(measure);
  measure();

  let hoverTimer = 0;
  const openSoon = (card, delay) => {
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => openCard(card), delay);
  };

  const syncComposition = () => cards.forEach((card, index) => {
    const details = card.querySelector('.goal-card__details');
    details.open = compact.matches ? index === 0 : true;
    card.classList.toggle('is-expanded', details.open && compact.matches);
  });

  cards.forEach((card) => {
    const details = card.querySelector('.goal-card__details');
    const summary = details.querySelector(':scope > summary');
    const more = details.querySelector('.goal-card__more');

    card.addEventListener('pointerenter', (event) => {
      if (event.pointerType === 'mouse') openSoon(card, 90);
    });
    card.addEventListener('focusin', () => {
      clearTimeout(hoverTimer);
      openCard(card);
    });
    summary.addEventListener('click', (event) => {
      if (!compact.matches) event.preventDefault();
    });
    animateDisclosure(details, {
      content: more,
      enabled: () => compact.matches,
      onOpen: () => card.classList.add('is-expanded'),
      onClose: () => card.classList.remove('is-expanded'),
    });
  });

  list.addEventListener('pointerleave', (event) => {
    if (event.pointerType === 'mouse') openSoon(cards[0], 150);
  });
  list.addEventListener('focusout', (event) => {
    if (!list.contains(event.relatedTarget) && !list.matches(':hover')) openCard(cards[0]);
  });
  listenMediaChange(compact, syncComposition);
  syncComposition();
  document.documentElement.classList.add('goals-ready');
}

/** Aplica o mesmo acordeão ao FAQ e aos tópicos do cronograma. */
function initDisclosures() {
  document.querySelectorAll('.faq__item').forEach((details) => {
    animateDisclosure(details, { content: details.querySelector(':scope > p') });
  });
  // Tópicos usam <ul>; a apresentação de empresa convidada, .lesson__about.
  document.querySelectorAll('.lesson__topics').forEach((details) => {
    animateDisclosure(details, { content: details.querySelector(':scope > ul, :scope > .lesson__about') });
  });
}

/** Círculo que segue o mouse com velocidade independente da taxa da tela. */
function initCursorFollower() {
  const canHover = matchMedia('(hover: hover) and (pointer: fine)').matches;
  if (!canHover || reducedMotion.matches) return () => {};

  const controller = new AbortController();
  const options = { signal: controller.signal };
  const dot = document.createElement('div');
  dot.className = 'cursor-follower';
  dot.setAttribute('aria-hidden', 'true');
  document.body.append(dot);

  const target = { x: -100, y: -100 };
  const pos = { ...target };
  let frame = 0;
  let inactiveTimer = 0;
  let lastTime = 0;

  const tick = (now) => {
    const dt = lastTime ? Math.min((now - lastTime) / (1000 / 60), 4) : 1;
    lastTime = now;
    const k = 1 - (1 - 0.2) ** dt;
    pos.x += (target.x - pos.x) * k;
    pos.y += (target.y - pos.y) * k;
    dot.style.translate = `${pos.x}px ${pos.y}px`;
    const settled = Math.abs(target.x - pos.x) < 0.1 && Math.abs(target.y - pos.y) < 0.1;
    frame = settled ? 0 : requestAnimationFrame(tick);
  };

  window.addEventListener('pointermove', (event) => {
    if (event.pointerType !== 'mouse') return;
    target.x = event.clientX;
    target.y = event.clientY;
    dot.classList.add('is-visible');
    const goalSummary = event.target.closest('.goal-card__details > summary');
    const interactive = event.target.closest('a[href], button:not(:disabled), summary');
    const isInteractive = Boolean(interactive && !(goalSummary && innerWidth >= 768));
    if (isInteractive) {
      clearTimeout(inactiveTimer);
      inactiveTimer = 0;
      dot.classList.add('is-active');
    } else if (!inactiveTimer) {
      inactiveTimer = window.setTimeout(() => {
        dot.classList.remove('is-active');
        inactiveTimer = 0;
      }, motion.press);
    }
    if (!frame) {
      lastTime = 0;
      frame = requestAnimationFrame(tick);
    }
  }, options);
  document.documentElement.addEventListener('pointerleave', () => {
    clearTimeout(inactiveTimer);
    inactiveTimer = 0;
    dot.classList.remove('is-visible', 'is-active');
  }, options);

  return () => {
    controller.abort();
    clearTimeout(inactiveTimer);
    cancelAnimationFrame(frame);
    dot.remove();
  };
}

/**
 * Encontros de dias anteriores: o botão da aula vira "Aula encerrada",
 * desativado, para não levar a uma sala que já fechou nem dizer "Link em breve".
 * Roda antes da confirmação de inscrição, que assim ignora esses links.
 */
function initPastMeetings() {
  const today = todayInBrasilia();
  document.querySelectorAll('.day[data-date]').forEach((day) => {
    if (day.dataset.date >= today) return;
    const action = day.querySelector('.day__actions .btn');
    // Encontros já encerrados no próprio HTML (sem link no código) ficam como estão.
    if (!action || action.classList.contains('btn--ended')) return;
    const title = day.querySelector('.day__label h3')?.textContent.trim() || 'Encontro';
    const ended = document.createElement('button');
    ended.type = 'button';
    ended.className = `${action.className} btn--ended`;
    ended.disabled = true;
    ended.setAttribute('aria-label', `Aula do ${title} encerrada; a gravação chega por e-mail aos inscritos`);
    ended.innerHTML =
      '<span class="btn__icon" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="m3.5 8.5 3 3 6-7" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" /></svg></span>' +
      '<span class="btn__label">Aula encerrada<span class="btn__status">Gravação por e-mail</span></span>';
    action.replaceWith(ended);
  });
}

/** Revela fotos carregadas suavemente, mantendo as iniciais como reserva. */
function initSpeakerImages() {
  document.querySelectorAll('.speaker__art img').forEach((image) => {
    const reveal = () => image.classList.add('is-loaded');
    if (image.complete) reveal();
    else image.addEventListener('load', reveal, { once: true });
  });
  document.documentElement.classList.add('photos-ready');
}

/** Grade 3 × 3 (speakers--nine) quando a lista principal tem nove cards. O
 *  grupo das startups convidadas (.speakers--guests) segue as colunas dela
 *  pelo CSS e fica de fora. */
function initSpeakerGrid() {
  document.querySelectorAll('.speakers:not(.speakers--guests)').forEach((list) => {
    list.classList.toggle('speakers--nine', list.children.length === 9);
  });
}

/** Bio inline no celular e diálogo de leitura no tablet/desktop. */
function initSpeakerBios() {
  const compact = matchMedia('(max-width: 767px)');
  const bios = [...document.querySelectorAll('.speaker__bio')];
  const dialog = document.querySelector('[data-speaker-bio-dialog]');
  const dialogTitle = dialog?.querySelector('[data-speaker-bio-title]');
  const dialogMeta = dialog?.querySelector('[data-speaker-bio-meta]');
  const dialogContent = dialog?.querySelector('[data-speaker-bio-content]');
  const dialogClose = dialog?.querySelector('[data-speaker-bio-close]');
  let dialogOpener = null;

  const canUseDialog = () => dialog && typeof dialog.showModal === 'function';
  const closeDialog = () => {
    if (dialog?.open) dialog.close();
  };

  dialogClose?.addEventListener('click', closeDialog);
  dialog?.addEventListener('click', (event) => {
    if (event.target === dialog) closeDialog();
  });
  dialog?.addEventListener('close', () => {
    document.body.classList.remove('has-speaker-dialog');
    dialogOpener?.focus();
    dialogOpener = null;
  });

  const openDialog = (details, summary, content) => {
    const speaker = details.closest('.speaker');
    const name = speaker?.querySelector('.speaker__name')?.textContent.trim() || 'Biografia';
    const meta = [...(speaker?.querySelectorAll('.speaker__meta span') || [])]
      .map((item) => item.textContent.trim())
      .filter(Boolean)
      .join(' · ');

    dialogTitle.textContent = name;
    dialogMeta.textContent = meta;
    dialogContent.replaceChildren(
      ...[...content.children].map((item) => item.cloneNode(true)),
    );
    dialogOpener = summary;
    document.body.classList.add('has-speaker-dialog');
    dialog.showModal();
    dialogClose?.focus();
  };

  bios.forEach((details) => {
    const summary = details.querySelector(':scope > summary');
    const content = details.querySelector(':scope > .speaker__bio-content');
    if (!summary || !content) return;
    details.open = false;

    details.addEventListener('toggle', () => {
      if (!compact.matches || !details.open) return;
      bios.forEach((item) => {
        if (item !== details) item.open = false;
      });
    });

    summary.addEventListener('click', (event) => {
      if (compact.matches) {
        bios.forEach((item) => {
          if (item !== details) item.open = false;
        });
        return;
      }
      event.preventDefault();
      if (canUseDialog()) {
        openDialog(details, summary, content);
        return;
      }

      // Fallback para navegadores antigos sem suporte ao elemento <dialog>.
      if (details.dataset.animating) return;
      const opening = !details.open;
      if (reducedMotion.matches || typeof content.animate !== 'function') {
        details.open = opening;
        return;
      }
      details.dataset.animating = 'true';
      if (opening) details.open = true;
      runAnimation(
        content,
        opening
          ? [{ opacity: 0, translate: '0 4px' }, { opacity: 1, translate: '0 0' }]
          : [{ opacity: 1, translate: '0 0' }, { opacity: 0, translate: '0 4px' }],
        {
          duration: opening ? motion.reveal : motion.reveal * 0.75,
          easing: opening ? motion.out : motion.exit,
        },
        () => {
          if (!opening) details.open = false;
          delete details.dataset.animating;
        },
      );
    });
  });

  listenMediaChange(compact, () => {
    closeDialog();
    bios.forEach((details) => (details.open = false));
  });
  document.documentElement.classList.add('bios-ready');
}

/** Pergunta sobre a inscrição antes de abrir a aula e lembra a resposta no navegador. */
function initEnrollmentDialog() {
  const links = [...document.querySelectorAll('a[data-requires-enrollment]')];
  const dialog = document.querySelector('[data-enrollment-dialog]');
  const meta = dialog?.querySelector('[data-enrollment-meta]');
  const title = dialog?.querySelector('[data-enrollment-title]');
  const options = [...(dialog?.querySelectorAll('input[name="enrollment-status"]') || [])];
  const enrolled = dialog?.querySelector('[data-enrollment-enrolled]');
  const proceed = dialog?.querySelector('[data-enrollment-continue]');
  const proceedLabel = proceed?.querySelector('[data-enrollment-continue-label]');
  const hint = dialog?.querySelector('[data-enrollment-hint]');
  const close = dialog?.querySelector('[data-enrollment-close]');
  // Sem suporte ao elemento <dialog>, o link segue direto para a aula.
  if (links.length === 0 || !enrolled || !proceedLabel || typeof dialog.showModal !== 'function') return;

  const compact = matchMedia('(max-width: 767px)');
  const storageKey = 'patentes-bioinovadores:inscricao-confirmada';
  const proceedLabels = { enrolled: 'Entrar na aula', signup: 'Ir para a inscrição' };
  // Só endereços https viram destino do "Continuar" (nunca javascript:, data: etc.).
  const safeHref = (value) => {
    try {
      const url = new URL(value, document.baseURI);
      return url.protocol === 'https:' ? url.href : '';
    } catch {
      return '';
    }
  };
  let opener = null;

  // O armazenamento pode estar bloqueado (navegação privada ou política do navegador).
  const isConfirmed = () => {
    try {
      return localStorage.getItem(storageKey) === 'sim';
    } catch {
      return false;
    }
  };
  const rememberConfirmation = () => {
    try {
      localStorage.setItem(storageKey, 'sim');
    } catch {
      // Sem armazenamento, a pergunta volta a aparecer no próximo clique.
    }
  };
  const closeDialog = () => {
    if (dialog.open) dialog.close();
  };
  const selectedOption = () => options.find((option) => option.checked);

  // "Continuar" só vira link depois que uma opção é escolhida. Sem href,
  // target/rel não são válidos e o estado indisponível vem de role + aria.
  const updateProceed = () => {
    const selected = selectedOption();
    const href = safeHref(selected?.dataset.href || '');
    if (href) {
      proceed.href = href;
      proceed.target = '_blank';
      proceed.rel = 'noopener noreferrer';
      proceed.removeAttribute('role');
      proceed.removeAttribute('aria-disabled');
    } else {
      ['href', 'target', 'rel'].forEach((name) => proceed.removeAttribute(name));
      proceed.setAttribute('role', 'link');
      proceed.setAttribute('aria-disabled', 'true');
    }
    proceedLabel.textContent = proceedLabels[selected?.value] || 'Continuar';
  };

  options.forEach((option) => option.addEventListener('change', updateProceed));
  close?.addEventListener('click', closeDialog);
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) closeDialog();
  });
  dialog.addEventListener('close', () => {
    document.body.classList.remove('has-enrollment-dialog');
    opener?.focus();
    opener = null;
  });

  proceed.addEventListener('click', (event) => {
    const selected = selectedOption();
    if (!selected) {
      event.preventDefault();
      return;
    }
    if (selected === enrolled) {
      rememberConfirmation();
      // Fecha só depois do clique, para que o navegador abra a aula normalmente.
      setTimeout(closeDialog);
      return;
    }
    // A inscrição abre em outra aba; o diálogo fica à espera do retorno.
    if (hint) {
      hint.textContent =
        'O formulário abriu em uma nova aba. Depois de enviar, volte aqui e escolha “Sim, já me inscrevi”.';
    }
  });

  links.forEach((link) => {
    link.addEventListener('click', (event) => {
      // Ctrl/Cmd/Shift + clique mantêm o comportamento nativo do navegador.
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      if (isConfirmed()) return;
      event.preventDefault();

      const day = link.closest('.day');
      if (meta) {
        // "Terça‑feira, 3 de novembro" vira "3 de novembro" para caber numa linha.
        const date = day?.querySelector('.day__label p')?.textContent.split(',').pop().trim();
        meta.textContent = [day?.querySelector('.day__label h3')?.textContent.trim(), date]
          .filter(Boolean)
          .join(' · ');
      }
      enrolled.dataset.href = link.href;
      options.forEach((option) => (option.checked = false));
      if (hint) hint.textContent = '';
      updateProceed();
      opener = link;
      document.body.classList.add('has-enrollment-dialog');
      dialog.showModal();
      // O foco vai ao título: assim nenhuma opção parece pré-selecionada.
      (title || options[0]).focus();
      runAnimation(
        dialog,
        compact.matches
          ? [{ translate: '0 100%' }, { translate: '0 0' }]
          : [{ opacity: 0, translate: '0 12px' }, { opacity: 1, translate: '0 0' }],
        { duration: motion.reveal, easing: motion.out },
      );
    });
  });
}

const initialize = (name, initializer) => {
  try {
    return initializer();
  } catch (error) {
    console.error(`[main] Falha ao iniciar ${name}.`, error);
    return undefined;
  }
};

initialize('menu', initSiteMenu);
initialize('voltar ao topo', initBackToTop);
initialize('inscrição no cabeçalho', initHeaderCta);
initialize('cronograma', initDayCarousel);
initialize('encontros encerrados', initPastMeetings);
initialize('objetivos', initGoalCards);
initialize('acordeões', initDisclosures);
let stopCursor = initialize('cursor', initCursorFollower) || (() => {});
initialize('preferência de movimento', () => listenMediaChange(reducedMotion, () => {
  initialize('cursor após mudança de movimento', () => {
    stopCursor();
    stopCursor = reducedMotion.matches ? () => {} : initCursorFollower();
  });
}));
initialize('imagens dos palestrantes', initSpeakerImages);
initialize('grade de palestrantes', initSpeakerGrid);
initialize('biografias dos palestrantes', initSpeakerBios);
initialize('confirmação de inscrição', initEnrollmentDialog);
document.documentElement.classList.add('main-ready');
