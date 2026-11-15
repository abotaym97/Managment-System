import base64
import json
from datetime import date
from unittest.mock import patch
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.contrib.auth.models import Permission, User
from django.test import Client, TestCase
from django.urls import reverse

from .issuer import IssueForm
from .models import Hotel, Installation, License


class LicenseIssuerTests(TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        pem = self.key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(b'test-only'),
        )
        env = patch.dict('os.environ', {
            'OMDA_ISSUER_PRIVATE_KEY': pem.decode().replace(chr(10), chr(92) + 'n'),
            'OMDA_ISSUER_KEY_PASSWORD': 'test-only',
        })
        env.start()
        self.addCleanup(env.stop)
        self.admin = User.objects.create_superuser(username='issuer')
        self.installation = Installation.objects.create(
            hotel=Hotel.objects.create(name='OMDA Hotel'), identifier=uuid4(),
        )
        self.url = reverse('issue-license')
        self.data = {
            'installation': self.installation.pk, 'plan': 'monthly',
            'starts_on': '2026-11-15', 'branch_limit': 3, 'warning_days': 14, 'grace_days': 7,
        }

    def test_issue_once_and_verify_signature(self):
        self.client.force_login(self.admin)
        self.data['submission'] = self.client.get(self.url).context['submission']
        response = self.client.post(self.url, self.data)
        token = response.context['issued_token']
        prefix, payload, signature = token.split('.')

        def decode(value):
            return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))

        raw = decode(payload)
        self.key.public_key().verify(decode(signature), raw)
        data = json.loads(raw)
        entry = License.objects.get(serial=data['serial'])
        self.assertEqual(prefix, 'OMDA2')
        self.assertEqual(data['installation'], str(self.installation.identifier))
        self.assertEqual(data['customer'], 'OMDA Hotel')
        self.assertEqual(data['branch_limit'], 3)
        self.assertEqual(data['ends_on'], '2026-12-14')
        self.assertEqual(entry.ends_on, date(2026, 12, 14))
        self.assertFalse(entry.activated)
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertNotContains(self.client.get(reverse('licenses')), token)
        self.assertContains(self.client.post(self.url, self.data), 'already issued')
        self.assertEqual(License.objects.count(), 1)

    def test_permission_and_csrf(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        staff = User.objects.create_user(username='staff', is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename='add_license'))
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 403)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.admin)
        self.assertEqual(protected.post(self.url, self.data).status_code, 403)
        self.assertFalse(License.objects.exists())

    def test_subscription_calendar(self):
        cases = (
            ('monthly', '2026-01-31', '', '', date(2026, 2, 27)),
            ('annual', '2028-02-29', '', '', date(2029, 2, 27)),
            ('trial', '2026-03-05', 2, 'months', date(2026, 5, 4)),
            ('custom', '2026-03-05', 2, 'years', date(2028, 3, 4)),
        )
        for plan, start, duration, unit, end in cases:
            with self.subTest(plan=plan):
                form = IssueForm(dict(self.data, plan=plan, starts_on=start, duration=duration, unit=unit))
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data['ends_on'], end)
