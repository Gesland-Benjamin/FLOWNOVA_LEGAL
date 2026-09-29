const menuButton = document.querySelector('.doc-menu-toggle');
const documentMenu = document.getElementById('document-navigation');
if (menuButton && documentMenu) {
  function closeDocumentMenu() {
    documentMenu.classList.remove('open');
    menuButton.setAttribute('aria-expanded', 'false');
    menuButton.setAttribute('aria-label', 'Ouvrir le menu');
  }
  menuButton.addEventListener('click', () => {
    const open = menuButton.getAttribute('aria-expanded') !== 'true';
    documentMenu.classList.toggle('open', open);
    menuButton.setAttribute('aria-expanded', String(open));
    menuButton.setAttribute('aria-label', open ? 'Fermer le menu' : 'Ouvrir le menu');
  });
  documentMenu.querySelectorAll('a').forEach(link => link.addEventListener('click', closeDocumentMenu));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && menuButton.getAttribute('aria-expanded') === 'true') {
      closeDocumentMenu();
      menuButton.focus();
    }
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.nav')) closeDocumentMenu();
  });
}
