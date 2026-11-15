import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import UUID, uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from .issuer import encode
from .models import Hotel, Installation
from .signing_keys import get_signing_key, stored_path


class SigningSetupTests(TestCase):
    def setUp(self):
        storage = TemporaryDirectory()
        self.addCleanup(storage.cleanup)
        self.enterContext(self.settings(
            OMDA_SIGNING_KEY_DIR=storage.name,
            OMDA_SIGNING_STORAGE_PASSWORD='test-storage-password',
        ))
        self.enterContext(patch.dict(os.environ, OMDA_ISSUER_PRIVATE_KEY='', OMDA_ISSUER_KEY_PASSWORD=''))
        self.admin = get_user_model().objects.create_superuser('issuer')
        self.client.force_login(self.admin)
        self.hotel = Hotel.objects.create(name='Sample Hotel')
        self.installation = Installation.objects.create(hotel=self.hotel, identifier=uuid4())

    def test_generate_default_and_read_effective_values(self):
        url = reverse('signing-setup')
        response = self.client.post(url, {'action': 'generate'})
        public = response.context['public_key']
        self.assertTrue(response.context['saved'])
        self.assertTrue(public)
        self.assertNotContains(response, 'PRIVATE KEY')
        self.assertIn(b'ENCRYPTED PRIVATE KEY', stored_path().read_bytes())
        self.assertEqual(encode(get_signing_key().public_key().public_bytes_raw()), public)
        scoped = self.client.get(reverse('installation-signing', args=[self.installation.pk]))
        self.assertContains(scoped, public)
        self.assertContains(scoped, str(self.installation.identifier))
        self.assertIn('no-store', scoped.headers['Cache-Control'])
        self.assertFalse(self.client.post(url, {'action': 'generate'}).context['saved'])
        self.assertEqual(self.client.get(url).context['public_key'], public)

    def test_import_dedicated_key_and_use_it_for_license(self):
        self.client.post(reverse('signing-setup'), {'action': 'generate'})
        pair = Ed25519PrivateKey.generate()
        old_password = b'test-import-password'
        encrypted = pair.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(old_password),
        )
        expected = encode(pair.public_key().public_bytes_raw())
        url = reverse('installation-signing', args=[self.installation.pk])
        for password, confirm in [('incorrect', True), (old_password.decode(), False)]:
            response = self.client.post(url, {
                'action': 'import', 'pem': SimpleUploadedFile('old.pem', encrypted),
                'password': password, 'confirm': confirm,
            })
            self.assertFalse(response.context['saved'])
            self.assertFalse(stored_path(self.installation).exists())
        imported = self.client.post(url, {
            'action': 'import', 'pem': SimpleUploadedFile('old.pem', encrypted),
            'password': old_password.decode(), 'confirm': True,
        })
        self.assertTrue(imported.context['saved'])
        self.assertEqual(imported.context['public_key'], expected)
        self.assertNotContains(imported, old_password.decode())
        default_public = self.client.get(reverse('signing-setup')).context['public_key']
        self.assertNotEqual(default_public, expected)

        url = reverse('issue-license')
        response = self.client.post(url, {
            'submission': self.client.get(url).context['submission'],
            'installation': self.installation.pk, 'plan': 'monthly',
            'starts_on': '2026-11-15', 'branch_limit': 3, 'warning_days': 14, 'grace_days': 7,
        })
        from base64 import urlsafe_b64decode
        _, payload, signature = response.context['issued_token'].split('.')
        pair.public_key().verify(
            urlsafe_b64decode(signature + '=' * (-len(signature) % 4)),
            urlsafe_b64decode(payload + '=' * (-len(payload) % 4)),
        )

    def test_permission_csrf_and_installation_id(self):
        url = reverse('signing-setup')
        staff = get_user_model().objects.create_user('staff', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'action': 'generate'}).status_code, 403)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.admin)
        self.assertEqual(protected.post(url, {'action': 'generate'}).status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('record-add', args=['installation']))
        self.assertIsInstance(response.context['form'].initial['identifier'], UUID)
