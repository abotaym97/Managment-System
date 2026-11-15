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
const copyToken = document.querySelector('[data-copy-token]');
if (copyToken) {
  copyToken.addEventListener('click', async () => {
    const input = document.getElementById('new-token');
    const status = document.querySelector('[data-copy-status]');
    try {
      await navigator.clipboard.writeText(input.value);
      status.textContent = copyToken.dataset.copied;
    } catch {
      input.focus();
      input.select();
      status.textContent = copyToken.dataset.copyFailed;
    }
  });
}
