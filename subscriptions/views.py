from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Hotel, License


@staff_member_required
def dashboard(request):
    query = request.GET.get('q', '').strip()[:200]
    hotels = Hotel.objects.filter(name__icontains=query).order_by('name', 'pk')
    today = timezone.localdate()
    notices = []
    licenses = License.objects.filter(activated=True, starts_on__lte=today).select_related(
        'installation__hotel').order_by('installation_id', '-starts_on', '-pk')
    seen = set()
    for license in licenses:
        if license.installation_id in seen:
            continue
        seen.add(license.installation_id)
        if today <= license.ends_on + timedelta(days=license.grace_days):
            if license.ends_on <= today + timedelta(days=license.warning_days):
                notices.append(license)
    return render(request, 'subscriptions/dashboard.html', {'hotels': hotels, 'query': query, 'notices': notices})


@staff_member_required
def detail(request, pk):
    hotel = get_object_or_404(Hotel.objects.prefetch_related('installations__licenses'), pk=pk)
    return render(request, 'subscriptions/detail.html', {'hotel': hotel})

