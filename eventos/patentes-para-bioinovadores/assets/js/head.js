/* Scripts do <head>, em arquivo próprio para a página poder usar uma
 * política de segurança (CSP) que só aceita scripts do próprio site.
 * Carrega de forma síncrona, antes da pintura. */

/* Consulta um arquivo pequeno sem cache. Se o GitHub Pages já tiver uma
 * publicação nova, recarrega esta página uma única vez usando a versão como
 * parâmetro e preserva a seção que a pessoa estava vendo. */
(() => {
  const currentVersion = document.documentElement.dataset.siteVersion;
  const checkForUpdate = async () => {
    try {
      const manifestUrl = new URL('version.json', document.baseURI);
      manifestUrl.searchParams.set('check', Date.now());
      const response = await fetch(manifestUrl, { cache: 'no-store' });
      if (!response.ok) return;
      const { version } = await response.json();
      if (!version || version === currentVersion) return;

      const nextUrl = new URL(location.href);
      if (nextUrl.searchParams.get('site-version') === version) return;
      nextUrl.searchParams.set('site-version', version);
      location.replace(nextUrl);
    } catch {
      /* O site continua funcionando normalmente quando estiver offline. */
    }
  };

  // Depois da atualização, tira ?site-version= do endereço (mantém a
  // seção e os outros parâmetros), para o link copiado sair limpo.
  try {
    const loadedUrl = new URL(location.href);
    if (loadedUrl.searchParams.has('site-version')) {
      loadedUrl.searchParams.delete('site-version');
      history.replaceState(history.state, '', loadedUrl);
    }
  } catch {
    /* Sem history ou URL, o parâmetro só fica visível no endereço. */
  }

  checkForUpdate();
  addEventListener('pageshow', (event) => {
    if (event.persisted) checkForUpdate();
  });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) checkForUpdate();
  });
  // Com a aba escondida não consulta; ao voltar, o visibilitychange consulta.
  setInterval(() => {
    if (!document.hidden) checkForUpdate();
  }, 5 * 60 * 1000);
})();

/* Esconde os encontros futuros até o main.js montar o seletor. Se o main.js
 * não carregar, o load libera todos os encontros. */
document.documentElement.classList.add('js');
addEventListener('load', () => {
  document.documentElement.classList.add('schedule-ready');
  if (!document.documentElement.classList.contains('main-ready')) {
    document.documentElement.classList.add('main-failed');
  }
});

/* Depois do último encontro (a partir do dia seguinte, como “Aula
 * encerrada”), a página entra no estado “curso encerrado”: o CSS troca os
 * elementos marcados com data-when="open" pelos de data-when="ended". Roda
 * antes da pintura para não piscar. */
(function () {
  var root = document.documentElement;
  var end = root.getAttribute('data-course-end');
  if (end && new Date().toLocaleDateString('sv') > end) root.classList.add('course-ended');
})();
