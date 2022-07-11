# coding: utf-8
# 😇
import json

import constance
from django.urls import reverse
from django.http import HttpRequest
from markdown import markdown
from django.template import Template, RequestContext
from rest_framework import status

from kobo.apps.hook.constants import SUBMISSION_PLACEHOLDER
from kpi.tests.base_test_case import BaseTestCase


class EnvironmentTests(BaseTestCase):
    fixtures = ['test_data']

    def setUp(self):
        self.url = reverse('environment')
        self.dict_checks = {
            'terms_of_service_url': constance.config.TERMS_OF_SERVICE_URL,
            'privacy_policy_url': constance.config.PRIVACY_POLICY_URL,
            'source_code_url': constance.config.SOURCE_CODE_URL,
            'support_email': constance.config.SUPPORT_EMAIL,
            'support_url': constance.config.SUPPORT_URL,
            'community_url': constance.config.COMMUNITY_URL,
            'frontend_min_retry_time': constance.config.FRONTEND_MIN_RETRY_TIME,
            'frontend_max_retry_time': constance.config.FRONTEND_MAX_RETRY_TIME,
            'project_metadata_fields': lambda x: \
                self.assertEqual(len(x), len(json.loads(constance.config.PROJECT_METADATA_FIELDS))) \
                and self.assertIn({'name': 'organization', 'required': False}, x),
            'user_metadata_fields': lambda x: \
                self.assertEqual(
                    len(x), len(json.loads(constance.config.USER_METADATA_FIELDS))
                ) and self.assertIn({'name': 'sector', 'required': False}, x),
            'sector_choices': lambda x: \
                self.assertGreater(len(x), 10) and self.assertIn(
                    ("Humanitarian - Sanitation, Water & Hygiene",
                     "Humanitarian - Sanitation, Water & Hygiene"),
                    x
                ),
            'operational_purpose_choices': (('', ''),),
            'country_choices': lambda x: \
                self.assertGreater(len(x), 200) and self.assertIn(
                    ('KEN', 'Kenya'), x
                ),
            'all_languages': lambda x: \
                self.assertGreater(len(x), 100) and self.assertIn(
                    ('fa', 'Persian'), x
                ),
            'interface_languages': lambda x: \
                self.assertGreater(len(x), 5) and self.assertIn(
                    ('ar', 'العربيّة'), x
                ),
            'transcription_languages': lambda x: \
                self.assertGreater(len(x), 50) and self.assertIn(
                    'uk-UA', x
                ),
            'translation_languages': lambda x: \
                self.assertGreater(len(x), 50) and self.assertIn(
                    'fa-IR', x
                ),
            'submission_placeholder': SUBMISSION_PLACEHOLDER,
            'mfa_enabled': constance.config.MFA_ENABLED,
            'mfa_localized_help_text': lambda i18n_texts: {
                lang: markdown(text)
                for lang, text in json.loads(
                    constance.config.MFA_LOCALIZED_HELP_TEXT.replace(
                        '##support email##',
                        constance.config.SUPPORT_EMAIL
                    )
                ).items()
            }
        }

    def _check_response_dict(self, response_dict):
        self.assertEqual(len(response_dict), len(self.dict_checks))
        for key, callable_or_value in self.dict_checks.items():
            response_value = response_dict[key]
            try:
                callable_or_value(response_value)
            except TypeError:
                self.assertEqual(response_value, callable_or_value)

    def test_anonymous_succeeds(self):
        response = self.client.get(self.url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self._check_response_dict(response.data)

    def test_authenticated_succeeds(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(self.url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self._check_response_dict(response.data)

    def test_template_context_processor(self):
        """ Not an API test, but hey: nevermind the hobgoblins """
        context = RequestContext(HttpRequest())  # NB: empty request
        template = Template('{{ config.TERMS_OF_SERVICE_URL }}')
        result = template.render(context)
        self.assertEqual(result, constance.config.TERMS_OF_SERVICE_URL)
