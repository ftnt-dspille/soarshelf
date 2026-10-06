(function () {
  var t = null, p = null;
  try { t = localStorage.getItem('soarshelf-theme'); p = localStorage.getItem('soarshelf-palette'); } catch (e) {}
  if (t !== 'light' && t !== 'dark') t = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.dataset.theme = t;
  if (p === 'classic') document.documentElement.dataset.palette = p;
})();
