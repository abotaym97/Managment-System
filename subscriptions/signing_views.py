from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django import forms
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from .issuer import encode
from .models import Installation
from .signing_keys import get_signing_key, legacy_configured, load_key, save_signing_key, storage_configured, stored_path


class SigningSetupForm(forms.Form):
    pem = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'accept': '.pem'}))
    password = forms.CharField(required=False, max_length=1024, strip=False, widget=forms.PasswordInput)

    def __init__(self, *args, arabic=False, scoped=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['pem'].label = 'ملف التوقيع المشفّر' if arabic else 'Encrypted signing file'
        self.fields['password'].label = 'كلمة مرور الملف' if arabic else 'File password'
        if scoped:
            self.fields['confirm'] = forms.BooleanField(label=(
                'أؤكد أن الفندق سيستخدم المفتاح العام المقابل لهذا المفتاح.'
                if arabic else 'I confirm the hotel will use the corresponding public key.'
            ))


@staff_member_required(login_url='login')
@never_cache
@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters('password')
def signing_setup(request, pk=None):
    if not request.user.is_superuser:
        raise PermissionDenied
    installation = get_object_or_404(Installation.objects.select_related('hotel'), pk=pk) if pk else None
    arabic = request.LANGUAGE_CODE == 'ar'
    path = stored_path(installation)
    assigned = bool(path and path.exists())
    configured = storage_configured()
    can_assign = configured and not assigned and (installation is not None or not legacy_configured())
    form = SigningSetupForm(request.POST or None, request.FILES or None, arabic=arabic, scoped=bool(installation))
    error = None
    saved = False
    failures = (ValueError, TypeError, KeyError, OSError, UnsupportedAlgorithm)
    if request.method == 'POST' and not can_assign:
        error = ('لا يمكن حفظ مفتاح في هذا النطاق.' if arabic else 'A key cannot be saved for this scope.')
    if request.method == 'POST' and can_assign:
        action = request.POST.get('action')
        if action not in ('generate', 'import'):
            error = 'اختر إجراءً صالحًا.' if arabic else 'Choose a valid action.'
        elif form.is_valid():
            pem = form.cleaned_data.get('pem')
            password = form.cleaned_data.get('password')
            if action == 'import' and (not pem or not password or pem.size > 16384):
                error = ('اختر ملف توقيع مشفّرًا صالحًا وأدخل كلمة مروره.'
                         if arabic else 'Choose an encrypted signing file and enter its password.')
            else:
                try:
                    key = load_key(pem.read(), password.encode()) if action == 'import' else Ed25519PrivateKey.generate()
                    save_signing_key(key, installation)
                    saved = assigned = True
                    can_assign = False
                except FileExistsError:
                    error = ('حُفظ مفتاح لهذا النطاق مسبقًا. أعد فتح النافذة.'
                             if arabic else 'A key already exists for this scope. Reopen this dialog.')
                except (*failures, ImproperlyConfigured):
                    error = ('تعذر حفظ المفتاح. تحقق من الملف وكلمة المرور أو إعداد التخزين.'
                             if arabic else 'Could not save the key. Check the file, password, or signing storage.')
    try:
        key = get_signing_key(installation)
    except failures:
        key = None
        error = ('تعذر تحميل مفتاح التوقيع. راجع إعداد التخزين.'
                 if arabic else 'Could not load the signing key. Check the signing storage.')
    public = encode(key.public_key().public_bytes_raw()) if key else ''
    return render(request, 'subscriptions/signing-setup.html', {
        'installation': installation, 'public_key': public, 'form': form, 'error': error,
        'saved': saved, 'can_assign': can_assign, 'assigned': assigned, 'configured': configured,
    })
