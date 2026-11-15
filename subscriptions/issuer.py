import base64
import json
import os
from calendar import monthrange
from datetime import datetime, timedelta, timezone as utc
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django import forms
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.core import signing
from django.db import IntegrityError, transaction
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from cryptography.exceptions import UnsupportedAlgorithm

from .models import Installation, License


PLANS = {'trial': ('Trial', 'تجريبي'), 'monthly': ('Monthly', 'شهري'),
         'annual': ('Annual', 'سنوي'), 'custom': ('Custom', 'مخصص')}


class IssueForm(forms.Form):
    installation = forms.ModelChoiceField(queryset=Installation.objects.select_related('hotel').order_by('hotel__name', 'pk'))
    customer = forms.CharField(max_length=160, required=False)
    plan = forms.ChoiceField()
    starts_on = forms.DateField(input_formats=['%Y-%m-%d'], widget=forms.DateInput(attrs={'type':'date'}, format='%Y-%m-%d'))
    duration = forms.IntegerField(min_value=1, max_value=1200, required=False, initial=1)
    unit = forms.ChoiceField(required=False, initial='months')
    branch_limit = forms.IntegerField(min_value=1, max_value=10000, initial=1)
    warning_days = forms.IntegerField(min_value=0, max_value=365, initial=14)
    grace_days = forms.IntegerField(min_value=0, max_value=365, initial=7)

    def __init__(self, *args, arabic=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.arabic = arabic
        self.fields['plan'].choices = [(key, titles[arabic]) for key, titles in PLANS.items()]
        self.fields['unit'].choices = [('months', 'أشهر' if arabic else 'Months'), ('years', 'سنوات' if arabic else 'Years')]
        self.fields['installation'].label_from_instance = lambda item: f'{item.hotel.name} · {item.identifier}'
        labels = ('بيئة التشغيل','اسم الفندق','الباقة','تاريخ البداية','المدة','الوحدة','حد الفروع','أيام التنبيه','أيام السماحية')
        for field, label in zip(self.fields.values(), labels):
            if arabic:
                field.label = label

    def clean(self):
        data = super().clean()
        installation = data.get('installation')
        if installation and not data.get('customer'):
            customer = installation.hotel.name.strip()
            if not 1 <= len(customer) <= 160:
                self.add_error('customer', 'أدخل اسمًا من ١ إلى ١٦٠ حرفًا.' if self.arabic else 'Enter a name of 1 to 160 characters.')
            data['customer'] = customer
        plan, start = data.get('plan'), data.get('starts_on')
        if not plan or not start:
            return data
        count = data.get('duration')
        if plan == 'monthly':
            months = 1
        elif plan == 'annual':
            months = 12
        else:
            if not count:
                self.add_error('duration', 'حدد المدة.' if self.arabic else 'Enter a duration.')
                return data
            months = count * (12 if plan == 'custom' and data.get('unit') == 'years' else 1)
        try:
            if not 1 <= months <= 1200:
                raise ValueError
            year, month = divmod(start.year * 12 + start.month - 1 + months, 12)
            data['ends_on'] = start.replace(year=year, month=month+1,
                day=min(start.day, monthrange(year, month+1)[1])) - timedelta(days=1)
        except (ValueError, OverflowError):
            self.add_error('duration', 'اختر مدة ضمن النطاق.' if self.arabic else 'Choose a duration within range.')
        return data


def encode(value):
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def issue(data, serial):
    pem = os.environ['OMDA_ISSUER_PRIVATE_KEY'].replace(chr(92) + 'n', chr(10)).encode()
    password = os.environ['OMDA_ISSUER_KEY_PASSWORD'].encode()
    if not password:
        raise ValueError('Signing password is required.')
    key = serialization.load_pem_private_key(pem, password)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError('Expected an Ed25519 key.')
    item = data['installation']
    plan = PLANS[data['plan']][0]
    fields = {name:data[name] for name in ('branch_limit', 'warning_days', 'grace_days', 'starts_on', 'ends_on')}
    payload = json.dumps({'version':2, 'serial':str(serial), 'installation':str(item.identifier),
                          'customer':data['customer'], 'plan':plan, 'issued_at':datetime.now(utc.utc).isoformat(),
                          **fields}, default=lambda value:value.isoformat(), ensure_ascii=False, separators=(',', ':')).encode()
    token = f'OMDA2.{encode(payload)}.{encode(key.sign(payload))}'
    with transaction.atomic():
        License.objects.create(installation=item, serial=serial, plan=plan, activated=False, **fields)
    return token


@staff_member_required(login_url='login')
@never_cache
@require_http_methods(['GET', 'POST'])
def issue_license(request):
    if not request.user.is_superuser or not request.user.has_perm('subscriptions.add_license'):
        raise PermissionDenied
    arabic = request.LANGUAGE_CODE == 'ar'
    configured = bool(os.getenv('OMDA_ISSUER_PRIVATE_KEY') and os.getenv('OMDA_ISSUER_KEY_PASSWORD'))
    form = IssueForm(request.POST if request.method == 'POST' else None, arabic=arabic,
                     initial={'plan':'monthly','starts_on':timezone.localdate(),
                              'installation':request.GET.get('installation')})
    token = None
    salt = 'omda-license-issuance'
    submission = signing.dumps([request.user.pk, str(uuid4())], salt=salt)
    if request.method == 'POST' and form.is_valid():
        try:
            owner, serial = signing.loads(request.POST.get('submission', ''), salt=salt, max_age=3600)
            if owner != request.user.pk:
                raise signing.BadSignature
        except signing.BadSignature:
            form.add_error(None, 'انتهت صلاحية النموذج. راجع البيانات وحاول مجددًا.' if arabic else 'The form expired. Review the details and try again.')
        else:
            submission = request.POST['submission']
            try:
                token = issue(form.cleaned_data, serial)
            except IntegrityError:
                if not License.objects.filter(serial=serial).exists():
                    raise
                form.add_error(None, 'صدر هذا المفتاح سابقًا. افتح نموذجًا جديدًا لإصدار مفتاح آخر.' if arabic else 'This key was already issued. Open a new form to issue another key.')
            except (KeyError, ValueError, TypeError, UnsupportedAlgorithm):
                form.add_error(None, 'تحقق من إعدادات مفتاح التوقيع بالخادم.' if arabic else 'Check the signing key settings on the server.')
    return render(request, 'subscriptions/issue-license.html', {
        'form': form, 'issued_token': token, 'submission': submission,
        'issuer_configured': configured, 'today': timezone.localdate().isoformat(),
    })
