// Keep recovery independent of the application and its Markdown dependencies.
const status = document.querySelector('#loading-status');
const showFailure = message => {
  if (!document.querySelector('.loading')) return;
  document.querySelector('.loader')?.remove();
  document.querySelector('.loading h1').textContent = 'Каталог не загрузился';
  status.textContent = message;
  document.querySelector('#loading-retry').hidden = false;
};
document.querySelector('#loading-retry').onclick = () => location.reload();
const timer = setTimeout(() => showFailure('Загрузка заняла слишком много времени. Обновите страницу; если это не поможет — запустите каталог через ярлык «Навыки».'), 45000);
document.addEventListener('catalog-ready', () => clearTimeout(timer), {once:true});
import('./app.js').catch(() => {
  clearTimeout(timer);
  showFailure('Не удалось загрузить файлы каталога. Запустите каталог через ярлык «Навыки», затем обновите страницу.');
});
