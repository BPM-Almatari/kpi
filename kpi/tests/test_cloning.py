'''
Created on Jun 15, 2015

@author: esmail
'''


import unittest

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from rest_framework import status

from .kpi_test_case import KpiTestCase

ASSET_CLONE_FIELDS = {'name', 'content', 'asset_type'}
COLLECTION_CLONE_FIELDS = {'name'}

class TestCloning(KpiTestCase):

    def setUp(self):
        self.someuser= User.objects.get(username='someuser')
        self.someuser_password= 'someuser'
        self.another_user= User.objects.get(username='anotheruser')
        self.another_user_password= 'anotheruser'

    def _clone_asset(self, original_asset, **kwargs):
        expected_status_code= kwargs.pop('expected_status_code', status.HTTP_201_CREATED)

        response = self.client.post(
            reverse('asset-clone', kwargs={'uid': original_asset.uid}),
            kwargs
        )
        self.assertEqual(response.status_code, expected_status_code)

        if expected_status_code != status.HTTP_201_CREATED:
            return
        else:
            cloned_asset= self.url_to_obj(response.data['url'])
            for field in ASSET_CLONE_FIELDS:
                self.assertEqual(cloned_asset.__dict__[field],
                                 original_asset.__dict__[field])
            original_asset_tags= set(original_asset.tag_string.split(','))
            cloned_asset_tags= set(cloned_asset.tag_string.split(','))
            self.assertSetEqual(cloned_asset_tags, original_asset_tags)

            return cloned_asset

    def test_clone_asset(self):
        self.login(self.someuser.username, self.someuser_password)
        original_asset= self.create_asset(
            'cloning_asset', tag_string='tag1,tag2')
        self._clone_asset(original_asset)

    def test_clone_asset_into_collection(self):
        self.login(self.someuser.username, self.someuser_password)
        original_asset= self.create_asset('cloning_asset')
        parent_collection= self.create_collection('parent_collection')
        parent_url= reverse(
            'collection-detail', kwargs={'uid': parent_collection.uid})
        cloned_asset= self._clone_asset(
            original_asset, parent=parent_url)
        self.assertEqual(cloned_asset.parent, parent_collection)

    def test_cannot_clone_unshared_asset(self):
        self.login(self.someuser.username, self.someuser_password)
        original_asset= self.create_asset('cloning_asset')
        self.login(self.another_user.username, self.another_user_password)
        self._clone_asset(original_asset, expected_status_code=status.HTTP_404_NOT_FOUND)

    def test_clone_shared_asset(self):
        self.login(self.someuser.username, self.someuser_password)
        original_asset= self.create_asset('cloning_asset')
        self.add_perm(original_asset, self.another_user, 'view')
        self.login(self.another_user.username, self.another_user_password)
        self._clone_asset(original_asset)

# TODO
#     def test_clone_collection(self):
#         raise NotImplementedError
#         self.login(self.someuser.username, self.someuser_password)
#         original_collection= self.create_collection(
#             'cloning_collection', tag_string='tag1,tag2')
#         response = self.client.post(reverse('collection-list'),
#                                     {'clone_from': original_collection.uid})
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED)
#         cloned_collection= self.url_to_obj(response.data['url'])
#         for field in COLLECTION_CLONE_FIELDS:
#             self.assertEqual(cloned_collection.__dict__[field],
#                              original_collection.__dict__[field])
#         original_collection_tags= set(
#             original_collection.tag_string.split(','))
#         cloned_collection_tags= set(cloned_collection.tag_string.split(','))
#         self.assertSetEqual(cloned_collection_tags, original_collection_tags)
#
#     def test_clone_collection_into_collection(self):
#         raise NotImplementedError
#
#     def test_clone_shared_collection(self):
#         raise NotImplementedError
#
#     def test_cannot_clone_unshared_collection(self):
#         raise NotImplementedError

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
