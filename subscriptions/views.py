from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Hotel, License


@staff_member_required
def dashboard(request):
    from django.db.models import Q
    today = timezone.localdate()
    query = request.GET.get('q', '').strip()[:200]
    status = request.GET.get('status', '')
    hotels = list(Hotel.objects.order_by('name', 'pk'))
    licenses = License.objects.filter(activated=True, starts_on__lte=today).select_related(
        'installation__hotel').order_by('installation_id', '-starts_on', '-pk')
    current = {}
    for license in licenses:
        current.setdefault(license.installation_id, license)
    by_hotel = {}
    notices = []
    totals = dict(active=0, warning=0, grace=0, expired=0)
    for license in current.values():
        remaining = (license.ends_on - today).days
        state = ('expired' if remaining < -license.grace_days else 'grace' if remaining < 0
                 else 'warning' if remaining <= license.warning_days else 'active')
        totals[state] += 1
        by_hotel.setdefault(license.installation.hotel_id, []).append((license, state))
        if state in ('warning', 'grace'):
            notices.append(license)
    matches = Hotel.objects.filter(Q(name__icontains=query) | Q(contact__icontains=query) | Q(email__icontains=query))
    matching_ids = set(matches.values_list('pk', flat=True))
    rows = []
    for hotel in hotels:
        items = by_hotel.get(hotel.pk, [])
        license, state = min(items, key=lambda item: item[0].ends_on) if items else (None, 'none')
        if hotel.pk in matching_ids and (not status or status == state):
            rows.append({'hotel':hotel,'license':license,'state':state})
    return render(request, 'subscriptions/dashboard.html', {'rows':rows, 'query':query, 'status':status,
        'notices':sorted(notices,key=lambda item:item.ends_on), 'total':len(hotels), 'totals':totals,
        'statuses':('active','warning','grace','expired','none')})



@staff_member_required
def detail(request, pk):
    hotel = get_object_or_404(Hotel.objects.prefetch_related('installations__licenses'), pk=pk)
    token = None
    if request.method == 'POST':
        import hashlib
        import secrets
        from django.core.exceptions import PermissionDenied
        if not request.user.is_superuser:
            raise PermissionDenied
        selected = get_object_or_404(hotel.installations, pk=int(value) if (value := request.POST.get('installation', '')).isascii() and value.isdecimal() and len(value) <= 18 else 0)
        if request.POST.get("action") == "sync":
            hotel.installations.filter(pk=selected.pk).update(sync_requested_at=timezone.now())
            return redirect("hotel-detail", pk=hotel.pk)
        token = secrets.token_urlsafe(32)
        hotel.installations.filter(pk=selected.pk).update(sync_token_hash=hashlib.sha256(token.encode()).hexdigest())
    response = render(request, 'subscriptions/detail.html', {'hotel': hotel, 'token': token})
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

@staff_member_required
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
    form_class = modelform_factory(model, fields=fields, labels=LABELS, widgets=widgets)
    initial = {name: request.GET[name] for name in ('hotel','installation') if name in fields and request.GET.get(name,'').isdigit()}
    form = form_class(request.POST if request.method == 'POST' else None, instance=instance, initial=initial)
    if request.method == 'POST' and form.is_valid():
        record = form.save()
        hotel = record if kind == 'hotel' else record.hotel if kind == 'installation' else record.installation.hotel
        return redirect('hotel-detail', pk=hotel.pk)
    return render(request,'subscriptions/editor.html',{'form':form,'title':f'{"تعديل" if pk else "إضافة"} {label}'})

