import random

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings, TestCase
from django.urls import reverse
from rest_framework import status


from kobo.apps.accounts.models import EmailContent


class EmailContentModelTestCase(TestCase):
    """
    These tests are to ensure both the custom activation email and the default
    activation emails work as expected
    """
    def setUp(self) -> None:
        self.signup_url = reverse('account_signup')

    @override_settings(
        CACHES={
            'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}
        }
    )
    def test_custom_activation_email_template(self):
        email_content = EmailContent.objects.create(
            email_name='email_confirmation_signup_message',
            section_name='section_one',
            content='This is some content to test'
        )
        email_subject = EmailContent.objects.create(
            email_name='email_confirmation_signup_message',
            section_name='subject',
            content='This is a test subject line'
        )

        # Using the randomint to make sure that usernames and emails
        # are unique to ensure the tests will pass when run back to back
        # as only one email can be requested per username and email every three
        # minutes
        username = 'user001'
        email = username + '@example.com'
        data = {
            'email': email,
            'password1': username,
            'password2': username,
            'username': username,
        }
        request = self.client.post(self.signup_url, data)
        user = get_user_model().objects.get(email=email)
        assert request.status_code == status.HTTP_302_FOUND
        self.client.login(username=user.username, password=user.password)
        self.client.get(reverse('account_email_verification_sent'))
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == email_subject.content
        assert email_content.content in mail.outbox[0].body

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
    def test_custom_activation_email_template_blank_content(self):
        with self.assertNumQueries(3):
            email_content = EmailContent.objects.create(
                email_name='email_confirmation_signup_message',
                section_name='section_one',
                content=''
            )
            email_content_closing = EmailContent.objects.create(
                email_name='email_confirmation_signup_message',
                section_name='section_two',
                content=''
            )
            email_subject = EmailContent.objects.create(
                email_name='email_confirmation_signup_message',
                section_name='subject',
                content=''
            )
        # Using the randomint to make sure that usernames and emails
        # are unique to ensure the tests will pass when run back to back
        # as only one email can be requested per username and email every three
        # minutes
        username = 'user002'
        email = username + '@example.com'
        data = {
            'email': email,
            'password1': username,
            'password2': username,
            'username': username,
        }
        default = "Thanks for signing up with KoboToolbox!"
        request = self.client.post(self.signup_url, data)
        user = get_user_model().objects.get(email=email)
        assert request.status_code == status.HTTP_302_FOUND
        self.client.login(username=user.username, password=user.password)
        self.client.get(reverse('account_email_verification_sent'))
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == 'Activate your KoboToolbox Account'
        assert email_content.content in mail.outbox[0].body
        assert default not in mail.outbox[0].body

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
    def test_default_activation_email_template(self):
        # Using the randomint to make sure that usernames and emails
        # are unique to ensure the tests will pass when run back to back
        # as only one email can be requested per username and email every three
        # minutes
        username = 'user003'
        email = username + '@example.com'
        data = {
            'email': email,
            'password1': username,
            'password2': username,
            'username': username,
        }
        default_subject = "Activate your KoboToolbox Account"
        default_greeting = "Thanks for signing up with KoboToolbox!"
        default_body = "Confirming your account will give you access to " \
                       "KoboToolbox applications. Please visit the following " \
                       "URL to finish activation of your new account."
        default_closing = "For help getting started, check out the KoboToolbox " \
                          "user documentation: https://support.kobotoolbox.com "
        request = self.client.post(self.signup_url, data)
        user = get_user_model().objects.get(email=email)
        assert request.status_code == status.HTTP_302_FOUND
        self.client.login(username=user.username, password=user.password)
        self.client.get(reverse('account_email_verification_sent'))
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == default_subject
        assert default_greeting in mail.outbox[0].body
        assert default_body in mail.outbox[0].body
        assert default_closing in mail.outbox[0].body
        assert "Best,\nKoboToolbox" in mail.outbox[0].body