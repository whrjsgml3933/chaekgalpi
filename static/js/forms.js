// Keep paid generation requests from being submitted twice from the same form.
document.addEventListener('submit', function (event) {
  const form = event.target;
  if (!form.matches('[data-ai-form], [data-ai-generation]')) return;
  const generates = form.hasAttribute('data-ai-generation') ||
    form.querySelector('[name="generate_author_info"]:checked, [name="generate_cover_image"]:checked');
  if (!generates) return;
  if (form.dataset.busy === 'true') { event.preventDefault(); return; }
  form.dataset.busy = 'true';
  const button = event.submitter || form.querySelector('button[type="submit"]');
  if (!button) return;
  button.dataset.idleLabel = button.textContent;
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  button.replaceChildren();
  const spinner = document.createElement('span');
  spinner.className = 'spinner-border spinner-border-sm me-2';
  spinner.setAttribute('aria-hidden', 'true');
  button.append(spinner, document.createTextNode('AI 생성 중…'));
});
window.addEventListener('pageshow', function () {
  document.querySelectorAll('form[data-busy="true"]').forEach(function (form) {
    delete form.dataset.busy;
    const button = form.querySelector('button[aria-busy="true"]');
    if (button) { button.disabled = false; button.removeAttribute('aria-busy'); button.textContent = button.dataset.idleLabel; }
  });
});
