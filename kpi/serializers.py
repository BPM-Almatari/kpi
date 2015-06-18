import json

from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import get_script_prefix, resolve, Resolver404
from rest_framework import serializers
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.reverse import reverse_lazy, reverse
from taggit.models import Tag
import reversion

from django.utils.six.moves.urllib import parse as urlparse

from .models import Asset
from .models import AssetDeployment
from .models import Collection
from .models import ImportTask
from .models import ObjectPermission
from .models.object_permission import get_anonymous_user


class Paginated(LimitOffsetPagination):

    """ Adds 'root' to the wrapping response object. """
    root = serializers.SerializerMethodField('get_parent_url', read_only=True)

    def get_parent_url(self, obj):
        return reverse_lazy('api-root', request=self.context.get('request'))


class WritableJSONField(serializers.Field):

    """ Serializer for JSONField -- required to make field writable"""

    def to_internal_value(self, data):
        return json.loads(data)

    def to_representation(self, value):
        return value


class TagSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField('_get_tag_url', read_only=True)
    assets = serializers.SerializerMethodField('_get_assets', read_only=True)
    collections = serializers.SerializerMethodField(
        '_get_collections', read_only=True)
    parent = serializers.SerializerMethodField(
        '_get_parent_url', read_only=True)

    class Meta:
        model = Tag
        fields = ('name', 'url', 'assets', 'collections', 'parent')

    def _get_parent_url(self, obj):
        return reverse('tag-list', request=self.context.get('request', None))

    def _get_assets(self, obj):
        request = self.context.get('request', None)
        user = request.user
        # Check if the user is anonymous. The
        # django.contrib.auth.models.AnonymousUser object doesn't work for
        # queries.
        if user.is_anonymous():
            user = get_anonymous_user()
        return [reverse('asset-detail', args=(sa.uid,), request=request)
                for sa in Asset.objects.filter(tags=obj, owner=user).all()]

    def _get_collections(self, obj):
        request = self.context.get('request', None)
        user = request.user
        # Check if the user is anonymous. The
        # django.contrib.auth.models.AnonymousUser object doesn't work for
        # queries.
        if user.is_anonymous():
            user = get_anonymous_user()
        return [reverse('collection-detail', args=(coll.uid,), request=request)
                for coll in Collection.objects.filter(tags=obj, owner=user)
                .all()]

    def _get_tag_url(self, obj):
        request = self.context.get('request', None)
        return reverse('tag-detail', args=(obj.name,), request=request)


class TagListSerializer(TagSerializer):

    class Meta:
        model = Tag
        fields = ('name', 'url', )


class GenericHyperlinkedRelatedField(serializers.HyperlinkedRelatedField):

    def __init__(self, **kwargs):
        # These arguments are required by ancestors but meaningless in our
        # situation. We will override them dynamically.
        kwargs['view_name'] = '*'
        kwargs['queryset'] = ObjectPermission.objects.none()
        return super(GenericHyperlinkedRelatedField, self).__init__(**kwargs)

    def to_representation(self, value):
        self.view_name = '{}-detail'.format(
            ContentType.objects.get_for_model(value).model)
        result = super(GenericHyperlinkedRelatedField, self).to_representation(
            value)
        self.view_name = '*'
        return result

    def to_internal_value(self, data):
        ''' The vast majority of this method has been copied and pasted from
        HyperlinkedRelatedField.to_internal_value(). Modifications exist
        to allow any type of object. '''
        _ = self.context.get('request', None)
        try:
            http_prefix = data.startswith(('http:', 'https:'))
        except AttributeError:
            self.fail('incorrect_type', data_type=type(data).__name__)

        if http_prefix:
            # If needed convert absolute URLs to relative path
            data = urlparse.urlparse(data).path
            prefix = get_script_prefix()
            if data.startswith(prefix):
                data = '/' + data[len(prefix):]

        try:
            match = resolve(data)
        except Resolver404:
            self.fail('no_match')

        ### Begin modifications ###
        # We're a generic relation; we don't discriminate
        '''
        try:
            expected_viewname = request.versioning_scheme.get_versioned_viewname(
                self.view_name, request
            )
        except AttributeError:
            expected_viewname = self.view_name

        if match.view_name != expected_viewname:
            self.fail('incorrect_match')
        '''

        # Dynamically modify the queryset
        self.queryset = match.func.cls.queryset
        ### End modifications ###

        try:
            return self.get_object(match.view_name, match.args, match.kwargs)
        except (ObjectDoesNotExist, TypeError, ValueError):
            self.fail('does_not_exist')


class ObjectPermissionSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        lookup_field='uid',
        view_name='objectpermission-detail'
    )
    user = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        lookup_field='username',
        queryset=User.objects.all(),
    )
    permission = serializers.SlugRelatedField(
        slug_field='codename',
        queryset=Permission.objects.all()
    )
    content_object = GenericHyperlinkedRelatedField(
        lookup_field='uid',
        style={'base_template': 'input.html'}  # Render as a simple text box
    )
    inherited = serializers.ReadOnlyField()

    class Meta:
        model = ObjectPermission
        fields = (
            'uid',
            'kind',
            'url',
            'user',
            'permission',
            'content_object',
            'deny',
            'inherited',
        )

    def create(self, validated_data):
        content_object = validated_data['content_object']
        user = validated_data['user']
        perm = validated_data['permission'].codename
        return content_object.assign_perm(user, perm)


class AssetSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail', lookup_field='username',
                                                read_only=True,)
    owner__username = serializers.ReadOnlyField(source='owner.username')
    url = serializers.HyperlinkedIdentityField(
        lookup_field='uid', view_name='asset-detail')
    asset_type = serializers.ReadOnlyField()
    settings = WritableJSONField(required=False)
    xls_link = serializers.SerializerMethodField()
    summary = serializers.ReadOnlyField()
    koboform_link = serializers.SerializerMethodField()
    xform_link = serializers.SerializerMethodField()
    version_count = serializers.SerializerMethodField('_version_count')
    downloads = serializers.SerializerMethodField()
    embeds = serializers.SerializerMethodField()
    parent = serializers.HyperlinkedRelatedField(lookup_field='uid',
                                                 queryset=Collection.objects.all(),
                                                 view_name='collection-detail',
                                                 required=False)
    permissions = ObjectPermissionSerializer(many=True, read_only=True)
    tag_string = serializers.CharField(required=False)
    # assetdeployment__count comes from annotate() on the view's queryset
    deployment_count = serializers.IntegerField(source='assetdeployment__count', read_only=True)

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
                  'version_count',
                  'downloads',
                  'embeds',
                  'koboform_link',
                  'xform_link',
                  'tag_string',
                  'uid',
                  'kind',
                  'xls_link',
                  'name',
                  'deployment_count',
                  'permissions',)
        extra_kwargs = {
            'parent': {
                'lookup_field': 'uid',
            },
        }

    def get_fields(self, *args, **kwargs):
        fields = super(AssetSerializer, self).get_fields(*args, **kwargs)
        user = self.context['request'].user
        # Check if the user is anonymous. The
        # django.contrib.auth.models.AnonymousUser object doesn't work for
        # queries.
        if user.is_anonymous():
            user = get_anonymous_user()
        fields['parent'].queryset = fields['parent'].queryset.filter(owner=user)
        # Honor requests to exclude fields
        # TODO: Actually exclude fields from tha database query! DRF grabs
        # all columns, even ones that are never named in `fields`
        excludes = self.context['request'].GET.get('exclude', '')
        for exclude in excludes.split(','):
            exclude = exclude.strip()
            if exclude in fields:
                fields.pop(exclude)
        return fields

    def _version_count(self, obj):
        return reversion.get_for_object(obj).count()

    def get_xls_link(self, obj):
        return reverse('asset-xls', args=(obj.uid,), request=self.context.get('request', None))

    def get_xform_link(self, obj):
        return reverse('asset-xform', args=(obj.uid,), request=self.context.get('request', None))

    def get_embeds(self, obj):
        request = self.context.get('request', None)

        def _reverse_lookup_format(fmt):
            url = reverse('asset-%s' % fmt,
                          args=(obj.uid,),
                          request=request)
            return {'format': fmt,
                    'url': url, }
        base_url = reverse('asset-detail',
                           args=(obj.uid,),
                           request=request)
        enkfmt = 'enketopreview'
        return [
            {'format': enkfmt, 'url': '%s?format=%s' % (base_url, enkfmt)},
            _reverse_lookup_format('xls'),
            _reverse_lookup_format('xform'),
        ]

    def get_downloads(self, obj):
        def _reverse_lookup_format(fmt):
            request = self.context.get('request', None)
            url = '%s.%s' % (reverse('asset-detail',
                                     args=(obj.uid,),
                                     request=request), fmt)

            return {'format': fmt,
                    'url': url, }
        return [
            _reverse_lookup_format('xls'),
            _reverse_lookup_format('xml'),
        ]

    def get_koboform_link(self, obj):
        return reverse('asset-koboform', args=(obj.uid,), request=self.context
                       .get('request', None))

    def _content(self, obj):
        return json.dumps(obj.content)

    def _table_url(self, obj):
        request = self.context.get('request', None)
        return reverse('asset-table-view', args=(obj.uid,), request=request)


class AssetDeploymentSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = AssetDeployment
        fields = (
            'user',
            'date_created',
            'asset',
            'uid',
        )
        lookup_field = 'uid'
        extra_kwargs = {
            'user': {
                'lookup_field': 'username',
            },
            'asset': {
                'lookup_field': 'uid',
            }
        }


class ImportTaskSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = ImportTask
        fields = (
            'data',
            'status',
            'uid',
            'date_created',
        )


class AssetListSerializer(AssetSerializer):

    class Meta(AssetSerializer.Meta):
        fields = ('url',
                  'date_modified',
                  'date_created',
                  'owner',
                  'summary',
                  'owner__username',
                  'parent',
                  'uid',
                  'tag_string',
                  'kind',
                  'name',
                  'asset_type',
                  'deployment_count',
                  'permissions',
                  )


class UserSerializer(serializers.HyperlinkedModelSerializer):
    assets = serializers.HyperlinkedRelatedField(many=True,
                                                 view_name='asset-detail',
                                                 read_only=True,
                                                 lookup_field='uid')

    class Meta:
        model = User
        fields = ('url', 'username', 'assets', 'owned_collections')
        lookup_field = 'username'
        extra_kwargs = {
            'owned_collections': {
                'lookup_field': 'uid',
            },
        }


class UserListSerializer(UserSerializer):
    assets_count = serializers.SerializerMethodField('_assets_count')
    collections_count = serializers.SerializerMethodField('_collections_count')

    def _collections_count(self, obj):
        return obj.owned_collections.count()

    def _assets_count(self, obj):
        return obj.assets.count()

    class Meta(UserSerializer.Meta):
        fields = ('url', 'username', 'assets_count', 'collections_count',)


class CollectionChildrenSerializer(serializers.Serializer):

    def to_representation(self, value):
        if isinstance(value, Collection):
            serializer = CollectionListSerializer
        elif isinstance(value, Asset):
            serializer = AssetListSerializer
        else:
            raise Exception('Unexpected child type {}'.format(type(value)))
        return serializer(value, context=self.context).data


class CollectionSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        lookup_field='uid', view_name='collection-detail')
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail',
                                                lookup_field='username',
                                                read_only=True)
    parent = serializers.HyperlinkedRelatedField(lookup_field='uid',
                                                 required=False,
                                                 view_name='collection-detail',
                                                 queryset=Collection.objects.all())
    owner__username = serializers.ReadOnlyField(source='owner.username')
    children = CollectionChildrenSerializer(
        many=True, read_only=True,
        source='get_children_and_assets_iterable'
    )
    permissions = ObjectPermissionSerializer(many=True, read_only=True)
    downloads = serializers.SerializerMethodField()
    tag_string = serializers.CharField(required=False)

    class Meta:
        model = Collection
        fields = ('name',
                  'uid',
                  'kind',
                  'url',
                  'parent',
                  'owner',
                  'owner__username',
                  'downloads',
                  'date_created',
                  'date_modified',
                  'children',
                  'permissions',
                  'tag_string',)
        lookup_field = 'uid'
        extra_kwargs = {
            'assets': {
                'lookup_field': 'uid',
            },
        }

    def _get_tag_names(self, obj):
        return obj.tags.names()

    def get_downloads(self, obj):
        request = self.context.get('request', None)
        obj_url = reverse(
            'collection-detail', args=(obj.uid,), request=request)
        return [
            {'format': 'zip', 'url': '%s?format=zip' % obj_url},
        ]


class CollectionListSerializer(CollectionSerializer):
    children_count = serializers.SerializerMethodField()
    assets_count = serializers.SerializerMethodField()

    def get_children_count(self, obj):
        return obj.children.count()

    def get_assets_count(self, obj):
        return obj.assets.count()

    class Meta(CollectionSerializer.Meta):
        fields = ('name',
                  'uid',
                  'kind',
                  'url',
                  'parent',
                  'owner',
                  'children_count',
                  'assets_count',
                  'owner__username',
                  'date_created',
                  'date_modified',
                  'permissions',
                  'tag_string',)
