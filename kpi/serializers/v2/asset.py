# coding: utf-8
from __future__ import annotations

import json
import re
from datetime import timedelta
from distutils import util

from constance import config
from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import QuerySet
from django.db.models.signals import pre_delete
from django.utils.timezone import now
from django.utils.translation import gettext as t, ngettext as nt
from django_celery_beat.models import (
    ClockedSchedule,
    PeriodicTask,
    PeriodicTasks,
)
from django_request_cache import cache_for_request
from rest_framework import serializers, exceptions
from rest_framework.fields import empty
from rest_framework.relations import HyperlinkedIdentityField
from rest_framework.reverse import reverse
from rest_framework.utils.serializer_helpers import ReturnList

from kobo.apps.project_trash.models.project_trash import (
    ProjectTrash,
    ProjectTrashStatus,
)
from kobo.apps.reports.constants import FUZZY_VERSION_PATTERN
from kobo.apps.reports.report_data import build_formpack
from kpi.constants import (
    ASSET_STATUS_DISCOVERABLE,
    ASSET_STATUS_PRIVATE,
    ASSET_STATUS_PUBLIC,
    ASSET_STATUS_SHARED,
    ASSET_TYPES,
    ASSET_TYPE_COLLECTION,
    PERM_CHANGE_ASSET,
    PERM_CHANGE_METADATA_ASSET,
    PERM_MANAGE_ASSET,
    PERM_DISCOVER_ASSET,
    PERM_PARTIAL_SUBMISSIONS,
    PERM_VIEW_ASSET,
    PERM_VIEW_SUBMISSIONS,
)
from kpi.deployment_backends.kc_access.shadow_models import (
    KobocatUser,
    KobocatXForm,
)
from kpi.deployment_backends.kc_access.utils import kc_transaction_atomic
from kpi.fields import (
    PaginatedApiField,
    RelativePrefixHyperlinkedRelatedField,
    WritableJSONField,
)
from kpi.models import (
    Asset,
    AssetVersion,
    AssetExportSettings,
    ObjectPermission,
)
from kpi.models.asset import UserAssetSubscription
from kpi.utils.jsonbfield_helper import ReplaceValues
from kpi.utils.object_permission import (
    get_cached_code_names,
    get_database_user,
    get_user_permission_assignments,
    get_user_permission_assignments_queryset,
)
from kpi.utils.project_views import (
    get_project_view_user_permissions_for_asset,
    user_has_project_view_asset_perm,
    view_has_perm,
)
from .asset_version import AssetVersionListSerializer
from .asset_permission_assignment import AssetPermissionAssignmentSerializer
from .asset_export_settings import AssetExportSettingsSerializer


class AssetBulkActionsSerializer(serializers.Serializer):
    payload = WritableJSONField()

    def __init__(self, instance=None, data=empty, **kwargs):
        # Check `method` parameter first to support actions from Django Admin
        request = kwargs.get('context').get('request')
        method = kwargs.pop('method', request.method)
        self.__is_delete = method == 'DELETE'

        super().__init__(instance=instance, data=data, **kwargs)

    def create(self, validated_data):
        request = self.context['request']
        undo = validated_data['payload']['undo']

        if asset_uids := validated_data['payload'].get('asset_uids'):
            kc_filter_params = {'kpi_asset_uid__in': asset_uids}
            filter_params = {'uid__in': asset_uids}
        else:
            kc_filter_params = {'user': KobocatUser.get_kc_user(request.user)}
            filter_params = {'owner': request.user}

        kc_update_params = {'downloadable': undo}
        update_params = {
            '_deployment_data': ReplaceValues(
                '_deployment_data',
                updates={'active': undo},
            ),
            'date_modified': now(),
        }

        if self.__is_delete:
            kc_update_params['pending_delete'] = not undo
            update_params['pending_delete'] = not undo

        with transaction.atomic():
            with kc_transaction_atomic():
                # Deployment back end should be per asset. But, because we need
                # to do a bulk action, we assume that all `Asset` objects use the
                # same back end to avoid looping on each object to update their
                # back end.
                queryset = Asset.all_objects.filter(**filter_params)
                updated = queryset.update(
                    **update_params
                )
                kc_updated = KobocatXForm.objects.filter(
                    **kc_filter_params
                ).update(**kc_update_params)
                assert updated == kc_updated
                validated_data['project_counts'] = updated

                self._toggle_trash(queryset, undo)

        return validated_data

    def validate_payload(self, payload: dict) -> dict:
        try:
            asset_uids = payload['asset_uids']
        except KeyError:
            self._validate_confirm(payload)
            asset_uids = []

        self._validate_undo(payload)
        self._has_perms(asset_uids)

        return payload

    def to_representation(self, instance):
        undo = instance['payload']['undo']
        if self.__is_delete:
            if undo:
                message = nt(
                    f'%(count)d project has been undeleted',
                    f'%(count)d projects have been undeleted',
                    instance['project_counts'],
                ) % {'count': instance['project_counts']}
            else:
                message = nt(
                    '%(count)d project has been deleted',
                    '%(count)d projects have been deleted',
                    instance['project_counts'],
                ) % {'count': instance['project_counts']}
        else:
            if undo:
                message = nt(
                    '%(count)d project has been unarchived',
                    '%(count)d projects have been unarchived',
                    instance['project_counts'],
                ) % {'count': instance['project_counts']}
            else:
                message = nt(
                    '%(count)d project has been archived',
                    '%(count)d projects have been archived',
                    instance['project_counts'],
                ) % {'count': instance['project_counts']}

        return {'detail': message}

    def _create_tasks(self, assets: list[dict]):
        request = self.context['request']
        clocked_time = now() + timedelta(days=config.PROJECT_TRASH_GRACE_PERIOD)
        clocked = ClockedSchedule.objects.create(clocked_time=clocked_time)

        try:
            project_trash_objects = ProjectTrash.objects.bulk_create(
                [
                    ProjectTrash(
                        asset_id=asset['pk'],
                        user=request.user,
                        # save name and uid for reference when asset is gone
                        # and to avoid fetching assets again when creating periodic-task
                        metadata={'name': asset['name'], 'uid': asset['uid']},
                    )
                    for asset in assets
                ]
            )

            periodic_tasks = PeriodicTask.objects.bulk_create(
                [
                    PeriodicTask(
                        clocked=clocked,
                        name=f"Delete project {pto.metadata['name']} ({pto.metadata['uid']})",
                        task='kobo.apps.project_trash.tasks.empty_trash',
                        args=json.dumps([pto.id]),
                        one_off=True,
                    )
                    for pto in project_trash_objects
                ],
            )

        except IntegrityError:
            # We do not want to ignore conflicts. If so, something went wrong.
            # Probably direct API calls no coming from the front end.
            raise serializers.ValidationError(
                {'detail': t('One or many projects have been deleted already!')}
            )

        # Update relationships
        updated_project_trash_objects = []
        for idx, pto in enumerate(project_trash_objects):
            periodic_task = periodic_tasks[idx]
            assert periodic_task.args == json.dumps([pto.pk])
            pto.periodic_task = periodic_tasks[idx]
            updated_project_trash_objects.append(pto)

        ProjectTrash.objects.bulk_update(
            updated_project_trash_objects, fields=['periodic_task_id']
        )

    def _delete_tasks(self, assets: list[dict]):
        # Delete project trash and periodic task
        queryset = ProjectTrash.objects.filter(
            status=ProjectTrashStatus.PENDING,
            asset_id__in=[a['pk'] for a in assets]
        )
        periodic_task_ids = list(
            queryset.values_list('periodic_task_id', flat=True)
        )
        del_pto_results = queryset.delete()
        del_pto_count = del_pto_results[1].get('project_trash.ProjectTrash') or 0

        if del_pto_count != len(assets):
            raise serializers.ValidationError(
                {'detail': t('One or many projects have been deleted already!')}
            )

        # Disconnect `PeriodicTasks` (plural) signal, until `PeriodicTask` (singular)
        # delete query finishes to avoid unnecessary DB queries.
        # see https://django-celery-beat.readthedocs.io/en/stable/reference/django-celery-beat.models.html#django_celery_beat.models.PeriodicTasks
        pre_delete.disconnect(PeriodicTasks.changed, sender=PeriodicTask)
        del_ptasks_results = (
            PeriodicTask.objects.only('pk')
            .filter(pk__in=periodic_task_ids)
            .delete()
        )
        pre_delete.connect(PeriodicTasks.changed, sender=PeriodicTask)

        del_ptasks_count = del_ptasks_results[1].get('django_celery_beat.PeriodicTask') or 0
        assert del_ptasks_count == del_pto_count

        PeriodicTasks.update_changed()

    def _has_perms(self, asset_uids: list[str]):

        request = self.context['request']

        if request.user.is_anonymous:
            raise exceptions.PermissionDenied()

        if not asset_uids or request.user.is_superuser:
            return

        if request.method == 'PATCH':
            code_names = get_cached_code_names(Asset)
            perm_dict = code_names[PERM_MANAGE_ASSET]
            objects_count = ObjectPermission.objects.filter(
                user=request.user,
                permission_id=perm_dict['id'],
                asset__uid__in=asset_uids,
                deny=False
            ).count()
        else:
            objects_count = Asset.objects.filter(
                owner=request.user,
                uid__in=asset_uids,
            ).count()

        if objects_count != len(asset_uids):
            raise exceptions.PermissionDenied()

    def _toggle_trash(self, queryset: QuerySet, undo: bool):
        if not self.__is_delete:
            return

        assets = queryset.values('pk', 'uid', 'name')

        if undo:
            self._delete_tasks(assets)
        else:
            self._create_tasks(assets)

    def _validate_confirm(self, payload: dict):

        if not payload.get('confirm'):
            raise serializers.ValidationError(t('Confirmation is required'))

    def _validate_undo(self, payload: dict):
        request = self.context['request']
        undo = payload.get('undo', 'False')
        if not isinstance(undo, bool):
            try:
                undo = bool(util.strtobool(undo))
            except ValueError:
                payload['undo'] = False
                return

        if (
            undo
            and self.__is_delete
            and not request.user.is_superuser
        ):
            raise exceptions.PermissionDenied()

        payload['undo'] = undo


class AssetSerializer(serializers.HyperlinkedModelSerializer):

    owner = RelativePrefixHyperlinkedRelatedField(
        view_name='user-detail', lookup_field='username', read_only=True)
    owner__username = serializers.ReadOnlyField(source='owner.username')
    url = HyperlinkedIdentityField(
        lookup_field='uid', view_name='asset-detail')
    asset_type = serializers.ChoiceField(choices=ASSET_TYPES)
    settings = WritableJSONField(required=False, allow_blank=True)
    content = WritableJSONField(required=False)
    report_styles = WritableJSONField(required=False)
    report_custom = WritableJSONField(required=False)
    map_styles = WritableJSONField(required=False)
    map_custom = WritableJSONField(required=False)
    advanced_features = WritableJSONField(required=False)
    advanced_submission_schema = serializers.SerializerMethodField()
    analysis_form_json = serializers.SerializerMethodField()
    xls_link = serializers.SerializerMethodField()
    summary = serializers.ReadOnlyField()
    koboform_link = serializers.SerializerMethodField()
    xform_link = serializers.SerializerMethodField()
    version_count = serializers.SerializerMethodField()
    downloads = serializers.SerializerMethodField()
    embeds = serializers.SerializerMethodField()
    parent = RelativePrefixHyperlinkedRelatedField(
        lookup_field='uid',
        queryset=Asset.objects.filter(asset_type=ASSET_TYPE_COLLECTION),
        view_name='asset-detail',
        required=False,
        allow_null=True
    )
    assignable_permissions = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    effective_permissions = serializers.SerializerMethodField()
    exports = serializers.SerializerMethodField()
    export_settings = serializers.SerializerMethodField()
    tag_string = serializers.CharField(required=False, allow_blank=True)
    version_id = serializers.CharField(read_only=True)
    version__content_hash = serializers.CharField(read_only=True)
    has_deployment = serializers.ReadOnlyField()
    deployed_version_id = serializers.SerializerMethodField()
    deployed_versions = PaginatedApiField(
        serializer_class=AssetVersionListSerializer,
        # Higher-than-normal limit since the client doesn't yet know how to
        # request more than the first page
        default_limit=100
    )
    deployment__identifier = serializers.SerializerMethodField()
    deployment__active = serializers.SerializerMethodField()
    deployment__links = serializers.SerializerMethodField()
    deployment__data_download_links = serializers.SerializerMethodField()
    deployment__submission_count = serializers.SerializerMethodField()
    data = serializers.SerializerMethodField()

    # Only add link instead of hooks list to avoid multiple access to DB.
    hooks_link = serializers.SerializerMethodField()

    children = serializers.SerializerMethodField()
    subscribers_count = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    access_types = serializers.SerializerMethodField()
    data_sharing = WritableJSONField(required=False)
    paired_data = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        lookup_field = 'uid'
        fields = ('url',
                  'owner',
                  'owner__username',
                  'parent',
                  'settings',
                  'asset_type',
                  'date_created',
                  'summary',
                  'date_modified',
                  'version_id',
                  'version__content_hash',
                  'version_count',
                  'has_deployment',
                  'deployed_version_id',
                  'deployed_versions',
                  'deployment__identifier',
                  'deployment__links',
                  'deployment__active',
                  'deployment__data_download_links',
                  'deployment__submission_count',
                  'report_styles',
                  'report_custom',
                  'advanced_features',
                  'advanced_submission_schema',
                  'analysis_form_json',
                  'map_styles',
                  'map_custom',
                  'content',
                  'downloads',
                  'embeds',
                  'koboform_link',
                  'xform_link',
                  'hooks_link',
                  'tag_string',
                  'uid',
                  'kind',
                  'xls_link',
                  'name',
                  'assignable_permissions',
                  'permissions',
                  'effective_permissions',
                  'exports',
                  'export_settings',
                  'settings',
                  'data',
                  'children',
                  'subscribers_count',
                  'status',
                  'access_types',
                  'data_sharing',
                  'paired_data',
                  )
        extra_kwargs = {
            'parent': {
                'lookup_field': 'uid',
            },
            'uid': {
                'read_only': True,
            },
        }

    def update(self, asset, validated_data):
        request = self.context['request']
        user = request.user
        if (
            not asset.has_perm(user, PERM_CHANGE_ASSET)
            and user_has_project_view_asset_perm(asset, user, PERM_CHANGE_METADATA_ASSET)
        ):
            _validated_data = {}
            if settings := validated_data.get('settings'):
                _validated_data['settings'] = settings
            if name := validated_data.get('name'):
                _validated_data['name'] = name
            return super().update(asset, _validated_data)

        asset_content = asset.content
        _req_data = request.data
        _has_translations = 'translations' in _req_data
        _has_content = 'content' in _req_data
        if _has_translations and not _has_content:
            translations_list = json.loads(_req_data['translations'])
            try:
                asset.update_translation_list(translations_list)
            except ValueError as err:
                raise serializers.ValidationError({
                    'translations': str(err)
                })
            validated_data['content'] = asset_content
        return super().update(asset, validated_data)

    def get_fields(self, *args, **kwargs):
        fields = super().get_fields(*args, **kwargs)
        # Honor requests to exclude fields
        # TODO: Actually exclude fields from tha database query! DRF grabs
        # all columns, even ones that are never named in `fields`
        excludes = self.context['request'].GET.get('exclude', '')
        for exclude in excludes.split(','):
            exclude = exclude.strip()
            if exclude in fields:
                fields.pop(exclude)
        return fields

    def get_advanced_submission_schema(self, obj):
        req = self.context.get('request')
        url = req.build_absolute_uri(f'/advanced_submission_post/{obj.uid}')
        return obj.get_advanced_submission_schema(url=url)

    def get_analysis_form_json(self, obj):
        return obj.analysis_form_json()

    def get_effective_permissions(self, obj: Asset) -> list[dict[str, str]]:
        """
        Return a list of combined asset and project view permissions that the
        requesting user has for the asset.
        """
        user = get_database_user(self.context['request'].user)
        project_view_perms = get_project_view_user_permissions_for_asset(
            obj, user
        )
        asset_perms = obj.get_perms(user)
        return [
            {'codename': perm} for perm in set(project_view_perms + asset_perms)
        ]

    def get_version_count(self, obj):
        try:
            return len(obj.prefetched_latest_versions)
        except AttributeError:
            return obj.asset_versions.count()

    def get_xls_link(self, obj):
        return reverse('asset-xls',
                       args=(obj.uid,),
                       request=self.context.get('request', None))

    def get_xform_link(self, obj):
        return reverse('asset-xform',
                       args=(obj.uid,),
                       request=self.context.get('request', None))

    def get_hooks_link(self, obj):
        return reverse('hook-list',
                       args=(obj.uid,),
                       request=self.context.get('request', None))

    def get_embeds(self, obj):
        request = self.context.get('request', None)

        def _reverse_lookup_format(fmt):
            url = reverse('asset-%s' % fmt,
                          args=(obj.uid,),
                          request=request)
            return {'format': fmt,
                    'url': url, }

        return [
            _reverse_lookup_format('xls'),
            _reverse_lookup_format('xform'),
        ]

    def get_downloads(self, obj):
        def _reverse_lookup_format(fmt):
            request = self.context.get('request', None)
            obj_url = reverse('asset-detail',
                              args=(obj.uid,),
                              request=request)
            # The trailing slash must be removed prior to appending the format
            # extension
            url = '%s.%s' % (obj_url.rstrip('/'), fmt)

            return {'format': fmt,
                    'url': url, }
        return [
            _reverse_lookup_format('xls'),
            _reverse_lookup_format('xml'),
        ]

    def get_koboform_link(self, obj):
        return reverse('asset-koboform',
                       args=(obj.uid,),
                       request=self.context.get('request', None))

    def get_data(self, obj):
        kwargs = {'parent_lookup_asset': obj.uid}
        format = self.context.get('format')
        if format:
            kwargs['format'] = format

        return reverse('submission-list',
                       kwargs=kwargs,
                       request=self.context.get('request', None))

    def get_deployed_version_id(self, obj):
        if not obj.has_deployment:
            return
        if isinstance(obj.deployment.version_id, int):
            asset_versions_uids_only = obj.asset_versions.only('uid')
            # this can be removed once the 'replace_deployment_ids'
            # migration has been run
            v_id = obj.deployment.version_id
            try:
                return asset_versions_uids_only.get(
                    _reversion_version_id=v_id
                ).uid
            except AssetVersion.DoesNotExist:
                deployed_version = asset_versions_uids_only.filter(
                    deployed=True
                ).first()
                if deployed_version:
                    return deployed_version.uid
                else:
                    return None
        else:
            return obj.deployment.version_id

    def get_deployment__identifier(self, obj):
        if obj.has_deployment:
            return obj.deployment.identifier

    def get_deployment__active(self, obj):
        return obj.has_deployment and obj.deployment.active

    def get_deployment__links(self, obj):
        if obj.has_deployment and obj.deployment.active:
            return obj.deployment.get_enketo_survey_links()
        else:
            return {}

    def get_deployment__data_download_links(self, obj):
        if obj.has_deployment:
            return obj.deployment.get_data_download_links()
        else:
            return {}

    def get_deployment__submission_count(self, obj):
        if not obj.has_deployment:
            return 0

        try:
            request = self.context['request']
            user = request.user
            if obj.owner_id == user.id:
                return obj.deployment.submission_count

            # `has_perm` benefits from internal calls which use
            # `django_cache_request`. It won't hit DB multiple times
            if obj.has_perm(user, PERM_VIEW_SUBMISSIONS):
                return obj.deployment.submission_count

            if obj.has_perm(user, PERM_PARTIAL_SUBMISSIONS):
                return obj.deployment.calculated_submission_count(user=user)
        except KeyError:
            pass

        return 0

    def get_assignable_permissions(self, asset):
        return [
            {
                'url': reverse('permission-detail',
                               kwargs={'codename': codename},
                               request=self.context.get('request')),
                'label': asset.get_label_for_permission(codename),
            }
            for codename in asset.ASSIGNABLE_PERMISSIONS_BY_TYPE[asset.asset_type]]

    def get_children(self, asset):
        """
        Handles the detail endpoint but also takes advantage of the
        `AssetViewSet.get_serializer_context()` "cache" for the list endpoint,
        if it is present
        """
        if asset.asset_type != ASSET_TYPE_COLLECTION:
            return {'count': 0}

        try:
            children_count_per_asset = self.context['children_count_per_asset']
        except KeyError:
            children_count = asset.children.count()
        else:
            children_count = children_count_per_asset.get(asset.pk, 0)

        return {'count': children_count}

    def get_subscribers_count(self, asset):
        if asset.asset_type != ASSET_TYPE_COLLECTION:
            return 0
        # ToDo Optimize this. What about caching it inside `summary`
        return UserAssetSubscription.objects.filter(asset_id=asset.pk).count()

    def get_status(self, asset):

        # `order_by` lets us check `AnonymousUser`'s permissions first.
        # No need to read all permissions if `AnonymousUser`'s permissions
        # are found.
        # We assume that `settings.ANONYMOUS_USER_ID` equals -1.
        perm_assignments = asset.permissions. \
            values('user_id', 'permission__codename'). \
            exclude(user_id=asset.owner_id). \
            order_by('user_id', 'permission__codename')

        return self._get_status(perm_assignments)

    def get_paired_data(self, asset):
        request = self.context.get('request')
        return reverse('paired-data-list', args=(asset.uid,), request=request)

    def get_permissions(self, obj):
        context = self.context
        request = self.context.get('request')

        queryset = get_user_permission_assignments_queryset(obj, request.user)
        # Need to pass `asset` and `asset_uid` to context of
        # AssetPermissionAssignmentSerializer serializer to avoid extra queries
        # to DB within the serializer to retrieve the asset object.
        context['asset'] = obj
        context['asset_uid'] = obj.uid

        return AssetPermissionAssignmentSerializer(queryset.all(),
                                                   many=True, read_only=True,
                                                   context=context).data

    def get_exports(self, obj: Asset) -> str:
        return reverse(
            'asset-export-list',
            args=(obj.uid,),
            request=self.context.get('request', None),
        )

    def get_export_settings(self, obj: Asset) -> ReturnList:
        return AssetExportSettingsSerializer(
            AssetExportSettings.objects.filter(asset=obj),
            many=True,
            read_only=True,
            context=self.context,
        ).data

    def get_access_types(self, obj):
        """
        Handles the detail endpoint but also takes advantage of the
        `AssetViewSet.get_serializer_context()` "cache" for the list endpoint,
        if it is present
        """
        # Avoid extra queries if obj is not a collection
        if obj.asset_type != ASSET_TYPE_COLLECTION:
            return None

        # User is the owner
        try:
            request = self.context['request']
        except KeyError:
            return None

        access_types = []
        if request.user == obj.owner:
            access_types.append('owned')

        # User can view the collection.
        try:
            # The list view should provide a cache
            asset_permission_assignments = self.context[
                'object_permissions_per_asset'
            ].get(obj.pk)
        except KeyError:
            asset_permission_assignments = obj.permissions.all()

        # We test at the same time whether the collection is public or not
        for obj_permission in asset_permission_assignments:

            if (
                not obj_permission.deny
                and obj_permission.user_id == settings.ANONYMOUS_USER_ID
                and obj_permission.permission.codename == PERM_DISCOVER_ASSET
            ):
                access_types.append('public')

                if request.user == obj.owner:
                    # Do not go further, `access_type` cannot be `shared`
                    # and `owned`
                    break

            if (
                request.user != obj.owner
                and not obj_permission.deny
                and obj_permission.user == request.user
            ):
                access_types.append('shared')
                # Do not go further, we assume `settings.ANONYMOUS_USER_ID`
                # equals -1. Thus, `public` access type should be discovered at
                # first
                break

        # User has subscribed to this collection
        subscribed = False
        try:
            # The list view should provide a cache
            subscriptions = self.context['user_subscriptions_per_asset'].get(
                obj.pk, []
            )
        except KeyError:
            subscribed = obj.has_subscribed_user(request.user.pk)
        else:
            subscribed = request.user.pk in subscriptions
        if subscribed:
            access_types.append('subscribed')

        # User is big brother.
        if request.user.is_superuser:
            access_types.append('superuser')

        if not access_types:
            raise Exception(
                f'{request.user.username} has unexpected access to {obj.uid}'
            )

        return access_types

    def validate_data_sharing(self, data_sharing: dict) -> dict:
        """
        Validates `data_sharing`. It is really basic.
        Only the type of each property is validated. No data is validated.
        It is consistent with partial permissions and REST services.

        The client bears the responsibility of providing valid data.
        """
        errors = {}
        if not self.instance or not data_sharing:
            return data_sharing

        if 'enabled' not in data_sharing:
            errors['enabled'] = t('The property is required')

        if 'fields' in data_sharing:
            if not isinstance(data_sharing['fields'], list):
                errors['fields'] = t('The property must be an array')
            else:
                asset = self.instance
                fields = data_sharing['fields']
                # We used to get all fields for every version for valid fields,
                # but the UI shows the latest version only, so only its fields
                # can be picked up. It is easier then to compare valid fields with
                # user's choice.
                form_pack, _unused = build_formpack(
                    asset, submission_stream=[], use_all_form_versions=False
                )
                # We do not want to include the version field.
                # See `_infer_version_id()` in `kobo.apps.reports.report_data.build_formpack`
                # for field name alternatives.
                valid_fields = [
                    f.path for f in form_pack.get_fields_for_versions(
                        form_pack.versions.keys()
                    ) if not re.match(FUZZY_VERSION_PATTERN, f.path)
                ]
                unknown_fields = set(fields) - set(valid_fields)
                if unknown_fields and valid_fields:
                    errors['fields'] = t(
                        'Some fields are invalid, '
                        'choices are: `{valid_fields}`'
                    ).format(valid_fields='`,`'.join(valid_fields))

                # Force `fields` to be an empty list to avoid useless parsing when
                # fetching external xml endpoint (i.e.: /api/v2/assets/<asset_uid>/paired-data/<paired_data_uid>/external.xml)
                if sorted(valid_fields) == sorted(fields):
                    data_sharing['fields'] = []
        else:
            data_sharing['fields'] = []

        if errors:
            raise serializers.ValidationError(errors)

        return data_sharing

    def validate_parent(self, parent: Asset) -> Asset:
        user = get_database_user(self.context['request'].user)
        # Validate first if user can update the current parent
        if self.instance and self.instance.parent is not None:
            if not self.instance.parent.has_perm(user, PERM_CHANGE_ASSET):
                raise serializers.ValidationError(
                    t('User cannot update current parent collection'))

        # Target collection is `None`, no need to check permissions
        if parent is None:
            return parent

        # `user` must have write access to target parent before being able to
        # move the asset.
        parent_perms = parent.get_perms(user)
        if PERM_VIEW_ASSET not in parent_perms:
            raise serializers.ValidationError(t('Target collection not found'))

        if PERM_CHANGE_ASSET not in parent_perms:
            raise serializers.ValidationError(
                t('User cannot update target parent collection'))

        return parent

    def validate_settings(self, settings: dict) -> dict:
        if not self.instance or not settings:
            return settings
        return {**self.instance.settings, **settings}

    def _content(self, obj):
        return json.dumps(obj.content)

    def _get_status(self, perm_assignments):
        """
        Returns asset status.

        **Asset's owner's permissions must be excluded from `perm_assignments`**

        Args:
            perm_assignments (list): List of dicts `{<user_id>, <codename}`
                                     ordered by `user_id`
                                     e.g.: [{-1, 'view_asset'},
                                            {2, 'view_asset'}]

        Returns:
            str: Status slug among these:
                 - 'private'
                 - 'public'
                 - 'public-discoverable'
                 - 'shared'

        """
        if not perm_assignments:
            return ASSET_STATUS_PRIVATE

        for perm_assignment in perm_assignments:
            if perm_assignment.get('user_id') == settings.ANONYMOUS_USER_ID:
                if perm_assignment.get('permission__codename') == PERM_DISCOVER_ASSET:
                    return ASSET_STATUS_DISCOVERABLE

                if perm_assignment.get('permission__codename') == PERM_VIEW_ASSET:
                    return ASSET_STATUS_PUBLIC

            return ASSET_STATUS_SHARED

    def _table_url(self, obj):
        request = self.context.get('request', None)
        return reverse('asset-table-view',
                       args=(obj.uid,),
                       request=request)


class AssetListSerializer(AssetSerializer):

    class Meta(AssetSerializer.Meta):
        # WARNING! If you're changing something here, please update
        # `Asset.optimize_queryset_for_list()`; otherwise, you'll cause an
        # additional database query for each asset in the list.
        fields = ('url',
                  'date_modified',
                  'date_created',
                  'owner',
                  'summary',
                  'owner__username',
                  'parent',
                  'uid',
                  'tag_string',
                  'settings',
                  'kind',
                  'name',
                  'asset_type',
                  'version_id',
                  'has_deployment',
                  'deployed_version_id',
                  'deployment__identifier',
                  'deployment__active',
                  'deployment__submission_count',
                  'permissions',
                  'export_settings',
                  'downloads',
                  'data',
                  'subscribers_count',
                  'status',
                  'access_types',
                  'children',
                  'data_sharing'
                  )

    def get_permissions(self, asset):
        try:
            asset_permission_assignments = self.context[
                'object_permissions_per_asset'].get(asset.pk)
        except KeyError:
            # Maybe overkill, there are no reasons to enter here.
            # in the list context, `object_permissions_per_asset` should
            # be always a property of `self.context`
            return super().get_permissions(asset)

        context = self.context
        request = self.context.get('request')

        # Need to pass `asset` and `asset_uid` to context of
        # AssetPermissionAssignmentSerializer serializer to avoid extra queries
        # to DB within the serializer to retrieve the asset object.
        context['asset'] = asset
        context['asset_uid'] = asset.uid

        user_assignments = get_user_permission_assignments(
            asset, request.user, asset_permission_assignments
        )
        return AssetPermissionAssignmentSerializer(user_assignments,
                                                   many=True, read_only=True,
                                                   context=context).data

    def get_subscribers_count(self, asset):
        if asset.asset_type != ASSET_TYPE_COLLECTION:
            return 0

        try:
            subscriptions_per_asset = self.context['user_subscriptions_per_asset']
            return len(subscriptions_per_asset.get(asset.pk, []))
        except KeyError:
            # Maybe overkill, there are no reasons to enter here.
            # in the list context, `user_subscriptions_per_asset` should be
            # always a property of `self.context`
            return super().get_subscribers_count(asset)

    def get_status(self, asset):

        try:
            asset_perm_assignments = self.context[
                'object_permissions_per_asset'].get(asset.pk)
        except KeyError:
            # Maybe overkill, there are no reasons to enter here.
            # in the list context, `object_permissions_per_asset` should be
            # always a property of `self.context`
            return super().get_status(asset)

        perm_assignments = []

        # Prepare perm_assignments for `_get_status()`
        for perm_assignment in asset_perm_assignments:
            if perm_assignment.user_id != asset.owner_id:
                perm_assignments.append({
                    'user_id': perm_assignment.user_id,
                    'permission__codename': perm_assignment.permission.codename
                })

        perm_assignments.sort(key=lambda pa: pa.get('user_id'))

        return self._get_status(perm_assignments)


class AssetUrlListSerializer(AssetSerializer):

    class Meta(AssetSerializer.Meta):
        fields = ('url',)


class AssetMetadataListSerializer(AssetListSerializer):

    languages = serializers.SerializerMethodField()
    owner__name = serializers.SerializerMethodField()
    owner__email = serializers.SerializerMethodField()
    owner__organization = serializers.SerializerMethodField()

    class Meta(AssetSerializer.Meta):
        fields = (
            'url',
            'date_modified',
            'date_created',
            'date_deployed',
            'owner',
            'owner__username',
            'owner__email',
            'owner__name',
            'owner__organization',
            'uid',
            'name',
            'settings',
            'languages',
            'has_deployment',
            'deployment__active',
            'deployment__submission_count',
        )

    def get_deployment__submission_count(self, obj: Asset) -> int:
        if obj.has_deployment and view_has_perm(
            self._get_view(), PERM_VIEW_SUBMISSIONS
        ):
            return obj.deployment.submission_count
        return super().get_deployment__submission_count(obj)

    def get_languages(self, obj: Asset) -> list[str]:
        return obj.summary.get('languages', [])

    def get_owner__email(self, obj: Asset) -> str:
        return obj.owner.email

    def get_owner__name(self, obj: Asset) -> str:
        return self._get_user_detail(obj, 'name')

    def get_owner__organization(self, obj: Asset) -> str:
        return self._get_user_detail(obj, 'organization')

    @staticmethod
    def _get_user_detail(obj, attr: str) -> str:
        owner = obj.owner
        if hasattr(owner, 'extra_details'):
            return owner.extra_details.data.get(attr, '')
        return ''

    def _get_view(self) -> str:
        request = self.context['request']
        return request.parser_context['kwargs']['uid']

    @cache_for_request
    def _user_has_asset_perms(self, obj: Asset, perm: str) -> bool:
        request = self.context.get('request')
        user = get_database_user(request.user)
        if obj.owner == user or obj.has_perm(user, perm):
            return True
        return False
