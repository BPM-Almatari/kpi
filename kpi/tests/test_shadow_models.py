# coding: utf-8

import json
import datetime
from django.test import TestCase
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import FileField
from mock import MagicMock
from kpi.deployment_backends.kc_reader.shadow_models import ReadOnlyModelError
from kpi.deployment_backends.kc_reader.shadow_models import _models


class ShadowModelsTest(TestCase):
    fixtures = ['test_data']
    MEDIA_URL = 'http://localhost:8000' + settings.MEDIA_URL

    def _mockFile(self, filename, size=200):
        media_file = MagicMock(spec=FileField, name='FileMock', absolutespec=True)
        media_file.name = filename
        media_file.url = self.MEDIA_URL.rstrip('/') + filename
        media_file.size = size
        return media_file

    def setUp(self):
        self.now = datetime.datetime.now()
        self.filename = '/path/to/test/image.jpg'
        self.short_filename = self.filename.split('/')[-1]
        self.media_file = self._mockFile(self.filename)

        self.user = User.objects.get(username='someuser')
        self.questions = json.dumps({'children': [{
            'type': 'text',
            'name': 'Test_Question',
            'label': 'Test Question'
        }, {
            'type': 'photo',
            'name': 'Test_Image_Question',
            'label': 'Test Image Question'
        }]})
        self.xform = _models.XForm(
            pk=1,
            id_string='xform_id_string',
            title='Test XForm',
            user=self.user,
            json=self.questions
        )

        self.instance = _models.Instance(
            pk=1,
            uuid='instance_uuid',
            status='test_status',
            xform=self.xform,
            json={'Test_Question':'Test Answer', 'Test_Image_Question': self.short_filename},
            date_created=self.now,
            date_modified=self.now
        )

        self.attachment = _models.Attachment(
            pk=1,
            instance=self.instance,
            media_file=self.media_file,
            mimetype='image/jpeg'
        )

    def test_xform_is_read_only(self):
        with self.assertRaises(ReadOnlyModelError):
            self.xform.save()

    def test_instance_is_read_only(self):
        with self.assertRaises(ReadOnlyModelError):
            self.instance.save()

    def test_attachment_is_read_only(self):
        with self.assertRaises(ReadOnlyModelError):
            self.attachment.save()


    def test_xform_questions_property(self):
        question_json = json.loads(self.questions).get('children', [])
        questions = self.xform.questions
        self.assertIsNotNone(questions)
        self.assertEqual(len(questions), len(question_json))
        for (index, expected) in enumerate(question_json):
            actual=questions[index]
            self.assertEqual(actual['number'], index+1)
            for field in expected:
                self.assertEqual(actual[field], expected[field])


    def test_instance_submission_property(self):
        submission = self.instance.submission
        self.assertEqual(submission['xform_id'], self.xform.id_string)
        self.assertEqual(submission['instance_uuid'], self.instance.uuid)
        self.assertEqual(submission['username'], self.user.username)
        self.assertEqual(submission['status'], self.instance.status)
        self.assertEqual(submission['date_created'], self.instance.date_created)
        self.assertEqual(submission['date_modified'], self.instance.date_modified)


    def test_attachment_properties(self):
        self.assertEqual(self.attachment.filename, self.short_filename)
        self.assertEqual(self.attachment.can_view_submission, True)


    def test_attachment_with_valid_question(self):
        question_name = self.attachment.question_name
        self.assertIsNotNone(question_name)
        self.assertEqual(self.instance.json[question_name], self.short_filename)

        question = self.attachment.question
        self.assertIsNotNone(question)
        self.assertEqual(question['name'], question_name)

        question_index = self.attachment.question_index
        self.assertEqual(question_index, question['number'])


    def test_attachment_with_invalid_question(self):
        self.xform.json = json.dumps({})

        self.assertIsNotNone(self.attachment.question_name)
        self.assertIsNone(self.attachment.question)
        self.assertEqual(self.attachment.question_index, self.attachment.pk)


    def test_attachment_question_does_not_exist(self):
        self.instance.json = {}

        self.assertIsNone(self.attachment.question_name)
        self.assertIsNone(self.attachment.question)
        self.assertEqual(self.attachment.question_index, self.attachment.pk)