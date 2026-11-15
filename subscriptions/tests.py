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

    def test_dashboard_is_read_only_and_registers_enforce_permissions(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        staff = get_user_model().objects.create_user('directory-staff', is_staff=True)
        self.client.force_login(staff)
        dashboard = self.client.get('/')
        self.assertContains(dashboard, 'Subscription Distribution')
        self.assertNotContains(dashboard, 'Hotel directory')
        self.assertNotContains(dashboard, 'Add hotel')
        self.assertContains(self.client.get('/hotels/'), 'Hotel directory')
        for path in ('/licenses/', '/installations/', '/system/'):
            self.assertEqual(self.client.get(path).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename='view_installation'))
        self.assertContains(self.client.get('/installations/'), 'Installations')
        self.assertEqual(self.client.get('/system/').status_code, 200)
        self.assertEqual(self.client.get('/manage/installation/new/').status_code, 403)

    def test_installation_token_is_one_time_hash_only_and_replacement_revokes_access(self):
        import hashlib
        from django.contrib.auth import get_user_model
        from django.test import Client
        from .token_service import token_revision
        User = get_user_model()
        admin = User.objects.create_superuser('token-admin')
        staff = User.objects.create_user('token-staff', is_staff=True)
        hotel = Hotel.objects.create(name='Token test')
        item = Installation.objects.create(hotel=hotel, identifier=uuid.uuid4())
        path = f'/installations/{item.pk}/token/'
        report = f'/api/installations/{item.identifier}/report/'
        client = Client(enforce_csrf_checks=True)
        client.force_login(staff)
        self.assertEqual(client.get(path).status_code, 403)
        client.force_login(admin)
        self.assertEqual(client.post(path, {'revision': token_revision(item)}).status_code, 403)
        initial = client.get(path)
        revision = token_revision(item)
        csrf = client.cookies['csrftoken'].value
        data = {'revision': revision, 'csrfmiddlewaretoken': csrf}
        result = client.post(path, data)
        self.assertEqual(result.status_code, 200)
        self.assertIn('no-store', result['Cache-Control'])
        token = result.context['new_token']
        item.refresh_from_db()
        self.assertEqual(item.sync_token_hash, hashlib.sha256(token.encode()).hexdigest())
        self.assertNotContains(client.get(path), token)
        self.assertNotContains(client.get('/installations/'), token)
        conflict = client.post(path, data)
        self.assertEqual(conflict.status_code, 409)
        self.assertNotContains(conflict, token, status_code=409)
        self.assertEqual(client.get(report, HTTP_AUTHORIZATION=f'Bearer {token}').status_code, 200)
        data['revision'] = token_revision(item)
        replacement = client.post(path, data).context['new_token']
        self.assertNotEqual(replacement, token)
        self.assertEqual(client.get(report, HTTP_AUTHORIZATION=f'Bearer {token}').status_code, 401)
        self.assertEqual(client.get(report, HTTP_AUTHORIZATION=f'Bearer {replacement}').status_code, 200)

    def test_installations_include_searchable_hotels_without_installation(self):
        from django.contrib.auth import get_user_model
        manager = get_user_model().objects.create_superuser('installations-list-admin')
        self.client.force_login(manager)
        hotel = Hotel.objects.create(name='Hotel without installation')
        linked = Hotel.objects.create(name='Linked hotel')
        installation = Installation.objects.create(hotel=linked, identifier=uuid.uuid4())
        response = self.client.get('/installations/')
        self.assertContains(response, str(installation.identifier))
        self.assertContains(response, f'?hotel={hotel.pk}')
        response = self.client.get('/installations/', {'q':'without installation'})
        self.assertContains(response, 'No installation')
        self.assertNotContains(response, str(installation.identifier))
        form = self.client.get('/manage/installation/new/', {'hotel':hotel.pk}).context['form']
        self.assertEqual(str(form['hotel'].value()), str(hotel.pk))
