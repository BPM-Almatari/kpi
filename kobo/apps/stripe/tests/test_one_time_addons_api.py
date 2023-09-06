from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from djstripe.models import Customer, PaymentIntent, Charge, Price, Product
from model_bakery import baker
from rest_framework import status

from kobo.apps.organizations.models import Organization
from kpi.tests.kpi_test_case import BaseTestCase


class OneTimeAddOnAPITestCase(BaseTestCase):
    fixtures = ['test_data']

    def setUp(self):
        self.someuser = User.objects.get(username='someuser')
        self.client.force_login(self.someuser)
        self.url = reverse('addons-list')
        self.price_id = 'price_305dfs432ltnjw'

    def _insert_data(self):
        self.organization = baker.make(Organization)
        self.organization.add_user(self.someuser, is_admin=True)
        self.customer = baker.make(Customer, subscriber=self.organization)

    def _create_product(self, metadata):
        self.product = baker.make(
            Product,
            active=True,
            metadata=metadata,
        )
        self.price = baker.make(Price, active=True, product=self.product, type='one_time')
        self.product.save()

    def _create_payment(self, status='succeeded', refunded=False):
        self.payment_intent = baker.make(
            PaymentIntent,
            customer=self.customer,
            status=status,
            payment_method_types=["card"],
            livemode=False,
            amount=2000,
            amount_capturable=2000,
            amount_received=2000,
        )
        self.charge = baker.prepare(
            Charge,
            customer=self.customer,
            refunded=refunded,
            created=timezone.now(),
            payment_intent=self.payment_intent,
            paid=True,
            status='succeeded',
            livemode=False,
            amount_refunded=0 if refunded else 2000,
            amount=2000,
            metadata={
                'price_id': self.price.id,
                'organization_id': self.organization.id,
                **self.product.metadata,
            }
        )
        self.charge.save()

    def test_no_addons(self):
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['results'] == []

    def test_get_endpoint(self):
        self._insert_data()
        self._create_product({'product_type': 'addon', 'submissions_limit': 2000})
        self._create_payment()
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1

    def test_anonymous_user(self):
        self._insert_data()
        self._create_product({'product_type': 'addon', 'submissions_limit': 2000})
        self._create_payment()
        self.client.logout()
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_not_own_addon(self):
        self._insert_data()
        self._create_product({'product_type': 'addon', 'submissions_limit': 2000})
        self._create_payment()
        self.client.force_login(User.objects.get(username='anotheruser'))
        response_get_list = self.client.get(self.url)
        assert response_get_list.status_code == status.HTTP_200_OK
        assert response_get_list.data['results'] == []
