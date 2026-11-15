'use strict';

const toggle = document.querySelector('[data-password-toggle]');
if (toggle) {
  const password = document.getElementById(toggle.getAttribute('aria-controls'));
  if (password) {
    toggle.hidden = false;
    toggle.addEventListener('click', () => {
      const visible = password.type === 'password';
      password.type = visible ? 'text' : 'password';
      toggle.setAttribute('aria-pressed', String(visible));
      toggle.textContent = visible ? toggle.dataset.hide : toggle.dataset.show;
    });
  }
}

const signIn = document.querySelector('[data-sign-in]');
if (signIn) {
  const submit = signIn.querySelector('[type="submit"]');
  const restore = () => {
    submit.disabled = false;
    submit.textContent = submit.dataset.ready;
    signIn.removeAttribute('aria-busy');
  };
  submit.dataset.ready = submit.textContent;
  signIn.addEventListener('submit', () => {
    submit.disabled = true;
    submit.textContent = submit.dataset.busy;
    signIn.setAttribute('aria-busy', 'true');
  });
  window.addEventListener('pageshow', restore);
}

for (const form of document.querySelectorAll('form')) {
  form.addEventListener('submit', event => {
    const message = event.submitter?.dataset.confirm;
    if (message && !window.confirm(message)) event.preventDefault();
  });
}

const editor = document.querySelector('[data-editor]');
if (editor) {
  const serialize = () => JSON.stringify([...new FormData(editor)]);
  const initial = serialize();
  let saving = false;
  const warn = event => {
    if (!saving && serialize() !== initial) {
      event.preventDefault();
      event.returnValue = '';
    }
  };
  const watch = () => window.addEventListener('beforeunload', warn);
  editor.addEventListener('input', watch);
  editor.addEventListener('change', watch);
  editor.addEventListener('submit', () => { saving = true; });
  window.addEventListener('pageshow', () => { saving = false; });
  editor.querySelector('[aria-invalid="true"]')?.focus();
}

const profile = document.querySelector('.profile');
if (profile) {
  profile.addEventListener('keydown', event => {
    if (event.key === 'Escape' && profile.open) {
      profile.open = false;
      profile.querySelector('summary').focus();
    }
  });
  document.addEventListener('click', event => {
    if (profile.open && !profile.contains(event.target)) profile.open = false;
  });
}

const tokenDialog = document.querySelector('[data-token-dialog]');
if (tokenDialog?.showModal) {
  tokenDialog.removeAttribute('open');
  tokenDialog.showModal();
  tokenDialog.addEventListener('cancel', event => {
    event.preventDefault();
    tokenDialog.querySelector('.actions a')?.click();
  });
}
document.addEventListener('click', async event => {
  const button = event.target.closest('[data-copy-token]');
  if (!button) return;
  const scope = button.closest('[data-issue-result]') || document;
  const input = scope.querySelector('#new-token');
  const status = scope.querySelector('[data-copy-status]');
  try {
    await navigator.clipboard.writeText(input.value);
    status.textContent = button.dataset.copied;
  } catch {
    input.focus();
    input.select();
    status.textContent = button.dataset.copyFailed;
  }
});

function prepareIssuer(form) {
  if (!form?.matches('[data-issuer]')) return;
  const {installation, plan, duration, unit, starts_on: start} = form.elements;
  const today = form.querySelector('[data-issuer-today]');
  const expiry = form.querySelector('[data-issuer-end]');
  const identifier = form.querySelector('[data-issuer-id]');
  const update = () => {
    identifier.parentElement.hidden = !installation.value;
    identifier.value = installation.value ? installation.selectedOptions[0].text.split(' · ').pop() : '';
    const fixed = plan.value === 'monthly' || plan.value === 'annual';
    duration.disabled = fixed;
    unit.disabled = plan.value !== 'custom';
    if (unit.disabled) unit.value = plan.value === 'annual' ? 'years' : 'months';
    if (fixed) duration.value = 1;
    const months = Number(duration.value) * (unit.value === 'years' ? 12 : 1);
    expiry.value = '—';
    if (!start.value || !Number.isInteger(months) || months < 1 || months > 1200) return;
    const end = new Date(start.value + 'T00:00:00Z');
    const day = end.getUTCDate();
    end.setUTCDate(1);
    end.setUTCMonth(end.getUTCMonth() + months + 1, 0);
    end.setUTCDate(Math.min(day, end.getUTCDate()) - 1);
    if (end.getUTCFullYear() <= 9999) expiry.value = end.toISOString().slice(0, 10);
  };
  today.hidden = false;
  today.addEventListener('click', () => {
    start.value = form.dataset.today;
    start.dispatchEvent(new Event('change', {bubbles: true}));
  });
  form.addEventListener('input', update);
  form.addEventListener('change', update);
  update();
}

prepareIssuer(document.querySelector('[data-issuer]'));

for (const menu of document.querySelectorAll('[data-installation-menu]')) {
  menu.addEventListener('keydown', event => {
    if (event.key === 'Escape' && menu.open) {
      menu.open = false;
      menu.querySelector('summary').focus();
    }
  });
  document.addEventListener('click', event => {
    if (menu.open && !menu.contains(event.target)) menu.open = false;
  });
}

const editorDialog = document.createElement('dialog');
editorDialog.className = 'token-dialog record-dialog';
editorDialog.setAttribute('aria-labelledby', 'record-modal-heading');
let editorSource;
let editorUrl;
let editorDirty = false;
let editorBusy = false;

function modalText(english, arabic) {
  return document.documentElement.lang === 'ar' ? arabic : english;
}

function closeEditor() {
  if (editorBusy || (editorDirty && !window.confirm(modalText('Discard unsaved changes?', 'تجاهل التغييرات غير المحفوظة؟')))) return;
  editorDialog.close();
}

async function loadEditor(options = {}) {
  editorBusy = true;
  editorDialog.setAttribute('aria-busy', 'true');
  const status = editorDialog.querySelector('[data-modal-status]');
  status.textContent = modalText('Loading…', 'جارٍ التحميل…');
  try {
    const response = await fetch(editorUrl, options);
    if (response.redirected) {
      if (new URL(response.url).pathname.includes('/login/') || !options.method) {
        window.location.assign(response.url);
      } else {
        editorDirty = false;
        editorDialog.close();
        window.location.reload();
      }
      return;
    }
    if (!response.ok) throw Error('Form unavailable');
    const page = new DOMParser().parseFromString(await response.text(), 'text/html');
    const result = page.querySelector('[data-issue-result]');
    const form = page.querySelector('[data-editor]');
    const title = page.querySelector('main h1');
    if ((!form && !result) || !title) throw Error('Missing editor');
    form?.querySelector('.actions a')?.remove();
    editorDialog.querySelector('#record-modal-heading').textContent = title.textContent;
    editorDialog.querySelector('[data-modal-content]').replaceChildren(result || form);
    editorDialog.querySelector('[data-full-editor]').hidden = Boolean(result);
    prepareIssuer(form);
    editorDirty = !result && options.method === 'POST';
    result?.querySelector('[data-copy-token]').focus();
    form?.querySelector('[aria-invalid="true"], input:not([type="hidden"]), select')?.focus();
    status.textContent = '';
  } catch {
    status.textContent = modalText('Could not load or save the form. Try again or open the full form.', 'تعذر تحميل النموذج أو حفظه. حاول مجددًا أو افتح النموذج الكامل.');
  } finally {
    editorBusy = false;
    editorDialog.removeAttribute('aria-busy');
    const save = editorDialog.querySelector('button[type="submit"]');
    if (save) save.disabled = false;
  }
}

if (editorDialog.showModal) {
  editorDialog.innerHTML = '<div class="heading"><h2 id="record-modal-heading"></h2><button type="button" data-close-editor></button></div><p data-modal-status role="status"></p><div data-modal-content></div><a data-full-editor></a>';
  editorDialog.querySelector('[data-close-editor]').textContent = modalText('Close', 'إغلاق');
  editorDialog.querySelector('[data-full-editor]').textContent = modalText('Open Full Form', 'افتح النموذج الكامل');
  document.body.append(editorDialog);
  editorDialog.querySelector('[data-close-editor]').addEventListener('click', closeEditor);
  editorDialog.addEventListener('cancel', event => { event.preventDefault(); closeEditor(); });
  editorDialog.addEventListener('close', () => {
    const issued = editorDialog.querySelector('[data-issue-result]');
    editorDialog.querySelector('[data-modal-content]').replaceChildren();
    if (issued) window.location.reload();
    else editorSource?.focus();
  });
  editorDialog.addEventListener('input', () => { editorDirty = true; });
  editorDialog.addEventListener('change', () => { editorDirty = true; });
  editorDialog.addEventListener('submit', event => {
    if (!event.target.matches('[data-editor]')) return;
    event.preventDefault();
    if (editorBusy) return;
    const body = new FormData(event.target);
    if (event.submitter) event.submitter.disabled = true;
    void loadEditor({method:'POST', body});
  });
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href);
    if (url.origin !== location.origin || !/^\/(?:licenses\/issue|manage\/(?:hotel|installation|license)\/(?:new|\d+))\/$/.test(url.pathname)) return;
    if (link.matches('[data-full-editor]') || editorDialog.open) return;
    event.preventDefault();
    editorSource = link.closest('[data-installation-menu]')?.querySelector('summary') || link;
    editorUrl = url.href;
    editorDirty = false;
    editorDialog.querySelector('#record-modal-heading').textContent = link.textContent.trim();
    editorDialog.querySelector('[data-full-editor]').hidden = false;
    editorDialog.querySelector('[data-full-editor]').href = editorUrl;
    editorDialog.querySelector('[data-modal-content]').replaceChildren();
    editorDialog.showModal();
    void loadEditor();
  });
}
