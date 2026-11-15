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
