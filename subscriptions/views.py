from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Hotel, License


def subscription_overview():
    today = timezone.localdate()
    licenses = License.objects.filter(activated=True, starts_on__lte=today).select_related(
        'installation__hotel').order_by('installation_id', '-starts_on', '-pk')
    current = {}
    for license in licenses:
        current.setdefault(license.installation_id, license)
    by_hotel, notices = {}, []
    totals = dict(active=0, warning=0, grace=0, expired=0)
    for license in current.values():
        remaining = (license.ends_on - today).days
        state = ('expired' if remaining < -license.grace_days else 'grace' if remaining < 0
                 else 'warning' if remaining <= license.warning_days else 'active')
        totals[state] += 1
        by_hotel.setdefault(license.installation.hotel_id, []).append((license, state))
        if state in ('warning', 'grace'):
            notices.append(license)
    return by_hotel, sorted(notices, key=lambda item: item.ends_on), totals


@staff_member_required(login_url="login")
def dashboard(request):
    _, notices, totals = subscription_overview()
    return render(request, 'subscriptions/dashboard.html', {
        'total': Hotel.objects.count(), 'totals': totals, 'notices': notices,
        'distribution': totals.items(), 'distribution_max': max(totals.values()),
    })


@staff_member_required(login_url="login")
def hotel_directory(request):
    from django.db.models import Q
    query = request.GET.get('q', '').strip()[:200]
    status = request.GET.get('status', '')
    hotels = list(Hotel.objects.order_by('name', 'pk'))
    by_hotel, notices, totals = subscription_overview()
    matches = Hotel.objects.filter(Q(name__icontains=query) | Q(contact__icontains=query) | Q(email__icontains=query))
    matching_ids = set(matches.values_list('pk', flat=True))
    rows = []
    for hotel in hotels:
        items = by_hotel.get(hotel.pk, [])
        license, state = min(items, key=lambda item: item[0].ends_on) if items else (None, 'none')
        if hotel.pk in matching_ids and (not status or status == state):
            rows.append({'hotel':hotel,'license':license,'state':state})
    return render(request, 'subscriptions/hotels.html', {'rows':rows, 'query':query, 'status':status,
        'notices':sorted(notices,key=lambda item:item.ends_on), 'total':len(hotels), 'totals':totals,
        'statuses':('active','warning','grace','expired','none')})



@staff_member_required(login_url="login")
def detail(request, pk):
    hotel = get_object_or_404(Hotel.objects.prefetch_related('installations__licenses'), pk=pk)
    if request.method == 'POST':
        from django.core.exceptions import PermissionDenied
        if not request.user.is_superuser:
            raise PermissionDenied
        selected = get_object_or_404(hotel.installations, pk=int(value) if (value := request.POST.get('installation', '')).isascii() and value.isdecimal() and len(value) <= 18 else 0)
        if request.POST.get("action") == "sync":
            hotel.installations.filter(pk=selected.pk).update(sync_requested_at=timezone.now())
            return redirect("hotel-detail", pk=hotel.pk)
        return redirect("installation-token", pk=selected.pk)
    response = render(request, 'subscriptions/detail.html', {'hotel': hotel})
    response['Cache-Control'] = 'private, no-store'
    return response



from django.forms import modelform_factory
from django.shortcuts import redirect
from django.http import Http404
from .models import Installation

EDITOR = {
    'hotel': (Hotel, ['name','contact','email'], 'الفندق'),
    'installation': (Installation, ['hotel','identifier','active_branches','website','deployment_branch'], 'بيئة التشغيل'),
    'license': (License, ['installation','serial','plan','starts_on','ends_on','branch_limit','warning_days','grace_days','activated'], 'الترخيص'),
}
LABELS = dict(name='اسم الفندق',contact='مسؤول التواصل',email='البريد الإلكتروني',hotel='الفندق',identifier='معرّف النظام',active_branches='الفروع النشطة',website='رابط النظام',deployment_branch='برانش النشر',installation='بيئة التشغيل',serial='الرقم التسلسلي',plan='الباقة',starts_on='تاريخ البداية',ends_on='تاريخ الانتهاء',branch_limit='حد الفروع',warning_days='أيام التنبيه',grace_days='أيام السماحية',activated='مفعّل')

@staff_member_required(login_url="login")
def editor(request, kind, pk=None):
    from django.forms import DateInput
    from django.core.exceptions import PermissionDenied
    if kind not in EDITOR:
        raise Http404
    model, fields, label = EDITOR[kind]
    action = 'change' if pk else 'add'
    if not request.user.has_perm(f'subscriptions.{action}_{model._meta.model_name}'):
        raise PermissionDenied
    instance = get_object_or_404(model, pk=pk) if pk else None
    widgets = {name: DateInput(attrs={'type':'date'}, format='%Y-%m-%d') for name in fields if name in ('starts_on','ends_on')}
    arabic = request.LANGUAGE_CODE == 'ar'
    english_labels = dict(contact='Contact person', identifier='Installation ID', website='Website',
                          serial='License serial number', activated='Activated')
    labels = LABELS if arabic else {name: english_labels.get(name, name.replace('_', ' ').capitalize()) for name in fields}
    form_class = modelform_factory(model, fields=fields, labels=labels, widgets=widgets)
    initial = {name: request.GET[name] for name in ('hotel','installation') if name in fields and request.GET.get(name,'').isdigit()}
    form = form_class(request.POST if request.method == 'POST' else None, instance=instance, initial=initial)
    if request.method == 'POST' and form.is_valid():
        record = form.save()
        hotel = record if kind == 'hotel' else record.hotel if kind == 'installation' else record.installation.hotel
        return redirect('hotel-detail', pk=hotel.pk)
    entity = {'hotel':'hotel','installation':'installation','license':'license'}[kind]
    title = f'{"تعديل" if pk else "إضافة"} {label}' if arabic else f'{"Edit" if pk else "Add"} {entity}'
    return render(request,'subscriptions/editor.html',{'form':form,'title':title})



@staff_member_required(login_url="login")
def license_register(request):
    from django.db.models import Q
    records = License.objects.select_related('installation__hotel').order_by('-ends_on', '-pk')
    return register(request, records, 'license', Q(serial__icontains=search_term(request)) |
                    Q(plan__icontains=search_term(request)) | Q(installation__hotel__name__icontains=search_term(request)))


def search_term(request):
    return request.GET.get('q', '').strip()[:200]


@staff_member_required(login_url="login")
def installation_register(request):
    from django.core.exceptions import PermissionDenied
    from django.core.paginator import Paginator
    from django.db.models import Q
    if not request.user.has_perm('subscriptions.view_installation'):
        raise PermissionDenied
    term = search_term(request)
    records = Installation.objects.select_related('hotel')
    unconfigured = Hotel.objects.filter(installations__isnull=True)
    if term:
        records = records.filter(Q(identifier__icontains=term) | Q(hotel__name__icontains=term) |
                                 Q(deployment_branch__icontains=term))
        unconfigured = unconfigured.filter(name__icontains=term)
    rows = [{'hotel': item.hotel, 'item': item} for item in records]
    rows.extend({'hotel': hotel, 'item': None} for hotel in unconfigured)
    rows.sort(key=lambda row: (row['hotel'].name.casefold(), row['hotel'].pk, row['item'].pk if row['item'] else 0))
    query = request.GET.copy()
    query.pop('page', None)
    return render(request, 'subscriptions/installations.html', {
        'page': Paginator(rows, 30).get_page(request.GET.get('page')),
        'query': term, 'page_query': query.urlencode(),
    })


def register(request, records, kind, search):
    from django.core.paginator import Paginator
    from django.core.exceptions import PermissionDenied
    if not request.user.has_perm(f'subscriptions.view_{kind}'):
        raise PermissionDenied
    status = request.GET.get('status', '')
    term = search_term(request)
    if term:
        records = records.filter(search)
    if kind == 'license' and status in ('issued', 'activated'):
        records = records.filter(activated=status == 'activated')
    query = request.GET.copy()
    query.pop('page', None)
    return render(request, f'subscriptions/{kind}s.html', {'page':Paginator(records,30).get_page(request.GET.get('page')),
                  'query':term,'status':status,'page_query':query.urlencode()})


@staff_member_required(login_url="login")
def license_detail(request, pk):
    from django.core.exceptions import PermissionDenied
    if not request.user.has_perm('subscriptions.view_license'):
        raise PermissionDenied
    record = get_object_or_404(License.objects.select_related('installation__hotel'), pk=pk)
    return render(request, 'subscriptions/license-detail.html', {'record':record})


@staff_member_required(login_url="login")
def system_administration(request):
    from django.contrib import admin
    from django.core.exceptions import PermissionDenied
    apps = admin.site.get_app_list(request)
    if not apps:
        raise PermissionDenied
    return render(request, 'subscriptions/system.html', {'apps':apps})


def token_result(request, token, installation):
    from django.views.decorators.cache import add_never_cache_headers
    response = render(request, 'subscriptions/installation-token.html',
                      {'item':installation, 'new_token':token})
    add_never_cache_headers(response)
    return response


@staff_member_required(login_url="login")
def installation_token(request, pk):
    from django.core.exceptions import PermissionDenied
    from django.views.decorators.cache import add_never_cache_headers
    from .token_service import rotate_sync_token, token_revision, TokenConflict
    if not request.user.is_superuser or not request.user.has_perm('subscriptions.change_installation'):
        raise PermissionDenied
    item = get_object_or_404(Installation.objects.select_related('hotel'), pk=pk)
    conflict = False
    if request.method == 'POST':
        try:
            token = rotate_sync_token(request.user, item, revision=request.POST.get('revision', ''))
        except TokenConflict:
            conflict = True
        else:
            return token_result(request, token, item)
    response = render(request, 'subscriptions/installation-token.html',
                      {'item':item,'revision':token_revision(item),'conflict':conflict}, status=409 if conflict else 200)
    add_never_cache_headers(response)
    return response
