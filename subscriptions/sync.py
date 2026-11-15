import hashlib
import json
import secrets
from uuid import UUID

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Installation


@csrf_exempt
@require_http_methods(["GET", "POST"])
def report(request, identifier):
    authorization = request.headers.get('Authorization', '')
    if not authorization.startswith('Bearer '):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    token = authorization.removeprefix('Bearer ')
    try:
        installation = Installation.objects.get(identifier=identifier)
    except Installation.DoesNotExist:
        installation = None
    digest = hashlib.sha256(token.encode()).hexdigest()
    if not installation or not installation.sync_token_hash or not secrets.compare_digest(digest, installation.sync_token_hash):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    if request.method == "GET":
        return JsonResponse({"requested": installation.sync_requested_at is not None}, headers={"Cache-Control": "no-store"})
    try:
        if len(request.body) > 4096:
            raise ValueError
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {'active_branches','branch_limit','serial','status','version'}:
            raise ValueError
        for field in ('active_branches','branch_limit'):
            number = data[field]
            if field == 'branch_limit' and number is None:
                continue
            if type(number) is not int or not 0 <= number <= 100000:
                raise ValueError
        if data['serial'] is not None:
            data['serial'] = str(UUID(data['serial']))
        if data['status'] not in ('active','warning','grace','expired','pending','unlicensed') or not isinstance(data['version'], str) or len(data['version']) > 80:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({'error': 'Invalid report'}, status=400)
    updated = Installation.objects.filter(pk=installation.pk, sync_token_hash=digest).update(
        active_branches=data['active_branches'], sync_snapshot=data, last_sync_at=timezone.now(), sync_requested_at=None)
    return JsonResponse({'accepted': bool(updated)}, status=200 if updated else 401)


