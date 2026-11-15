from django.test import TestCase
from .models import Hotel, Installation
import hashlib
import uuid


class SyncTests(TestCase):
    def test_report_requires_installation_token_and_valid_payload(self):
        hotel = Hotel.objects.create(name='Fixture')
        setup = Installation.objects.create(hotel=hotel, identifier=uuid.uuid4(),
            sync_token_hash=hashlib.sha256(b'fixture-token').hexdigest())
        path = f'/api/installations/{setup.identifier}/report/'
        payload = {'active_branches':2,'branch_limit':3,'serial':str(uuid.uuid4()),'status':'active','version':'test'}
        self.assertEqual(self.client.post(path, payload, content_type='application/json').status_code, 401)
        self.assertEqual(self.client.post(path, {**payload,'guest':'blocked'}, content_type='application/json',
            HTTP_AUTHORIZATION='Bearer fixture-token').status_code, 400)
        self.assertEqual(self.client.post(path, payload, content_type='application/json',
            HTTP_AUTHORIZATION='Bearer fixture-token').status_code, 200)
        setup.refresh_from_db()
        self.assertEqual(setup.active_branches, 2)
        self.assertEqual(setup.sync_snapshot, payload)
        self.assertIsNotNone(setup.last_sync_at)
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.create_superuser(username='sync-admin'))
        self.assertEqual(self.client.post(f'/hotels/{hotel.pk}/', {'action':'sync','installation':setup.pk}).status_code, 302)
        auth = {'HTTP_AUTHORIZATION': 'Bearer fixture-token'}
        self.assertEqual(self.client.get(path, **auth).json(), {'requested': True})
        self.assertEqual(self.client.post(path, payload, content_type='application/json', **auth).status_code, 200)
        self.assertEqual(self.client.get(path, **auth).json(), {'requested': False})


class WorkspaceAuthenticationTests(TestCase):
    def test_access_and_logout_require_the_existing_permissions_and_csrf(self):
        from django.contrib.auth import get_user_model
        from django.test import Client
        staff = get_user_model().objects.create_user('workspace-staff', is_staff=True)
        client = Client(enforce_csrf_checks=True)
        self.assertRedirects(client.get('/hotels/'), '/login/?next=/hotels/')
        client.force_login(staff)
        self.assertEqual(client.get('/licenses/').status_code, 403)
        self.assertEqual(client.get('/manage/hotel/new/').status_code, 403)
        self.assertEqual(client.get('/logout/').status_code, 405)
        self.assertEqual(client.post('/logout/').status_code, 403)
        self.assertEqual(client.get('/').status_code, 200)
        token = client.cookies['csrftoken'].value
        self.assertRedirects(client.post('/logout/', {'csrfmiddlewaretoken': token}), '/login/')
        self.assertRedirects(client.get('/'), '/login/?next=/')
