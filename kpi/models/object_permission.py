from django.db import models, transaction
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User, AnonymousUser, Permission
from django.conf import settings
from django.shortcuts import _get_queryset
from shortuuid import ShortUUID
import copy
import re

OBJECT_PERMISSION_UID_LENGTH = 22

def perm_parse(perm, obj=None):
    if obj is not None:
        obj_app_label = ContentType.objects.get_for_model(obj).app_label
    else:
        obj_app_label = None
    try:
        app_label, codename = perm.split('.', 1)
        if obj_app_label is not None and app_label != obj_app_label:
            raise ValidationError('The given object does not belong to the app '
                'specified in the permission string.')
    except ValueError:
        app_label = obj_app_label
        codename = perm
    return app_label, codename

def get_all_objects_for_user(user, klass):
    ''' Return all objects of type klass to which user has been assigned any
    permission. '''
    return klass.objects.filter(pk__in=ObjectPermission.objects.filter(
        user=user,
        content_type=ContentType.objects.get_for_model(klass)
    ).values_list('object_id', flat=True))

def get_objects_for_user(user, perms, klass=None):
    """
    A simplified version of django-guardian's get_objects_for_user shortcut.
    Returns queryset of objects for which a given ``user`` has *all*
    permissions present at ``perms``.
    :param user: ``User`` or ``AnonymousUser`` instance for which objects would
      be returned.
    :param perms: single permission string, or sequence of permission strings
      which should be checked.
      If ``klass`` parameter is not given, those should be full permission
      names rather than only codenames (i.e. ``auth.change_user``). If more than
      one permission is present within sequence, their content type **must** be
      the same or ``MixedContentTypeError`` exception would be raised.
    :param klass: may be a Model, Manager or QuerySet object. If not given
      this parameter would be computed based on given ``params``.
    """
    if isinstance(perms, basestring):
        perms = [perms]
    ctype = None
    app_label = None
    codenames = set()

    # Compute codenames set and ctype if possible
    for perm in perms:
        if '.' in perm:
            new_app_label, codename = perm.split('.', 1)
            if app_label is not None and app_label != new_app_label:
                raise ValidationError("Given perms must have same app "
                    "label (%s != %s)" % (app_label, new_app_label))
            else:
                app_label = new_app_label
        else:
            codename = perm
        codenames.add(codename)
        if app_label is not None:
            new_ctype = ContentType.objects.get(app_label=app_label,
                permission__codename=codename)
            if ctype is not None and ctype != new_ctype:
                raise ValidationError("Computed ContentTypes do not match "
                    "(%s != %s)" % (ctype, new_ctype))
            else:
                ctype = new_ctype

    # Compute queryset and ctype if still missing
    if ctype is None and klass is None:
        raise ValidationError("Cannot determine content type")
    elif ctype is None and klass is not None:
        queryset = _get_queryset(klass)
        ctype = ContentType.objects.get_for_model(queryset.model)
    elif ctype is not None and klass is None:
        queryset = _get_queryset(ctype.model_class())
    else:
        queryset = _get_queryset(klass)
        if ctype.model_class() != queryset.model:
            raise ValidationError("Content type for given perms and "
                "klass differs")

    # At this point, we should have both ctype and queryset and they should
    # match which means: ctype.model_class() == queryset.model
    # we should also have ``codenames`` list

    # First check if user is superuser and if so, return queryset immediately
    if user.is_superuser:
        return queryset

    # Check if the user is anonymous. The
    # django.contrib.auth.models.AnonymousUser object doesn't work for
    # queries, and it's nice to be able to pass in request.user blindly.
    if user.is_anonymous():
        user = get_anonymous_user()

    # Now we should extract list of pk values for which we would filter queryset
    # TODO: omit objects for which the user has only a deny permission
    user_obj_perms_queryset = (ObjectPermission.objects
        .filter(user=user)
        .filter(permission__content_type=ctype)
        .filter(permission__codename__in=codenames))
    fields = ['object_id', 'permission__codename']

    if len(codenames) > 1:
        counts = user_obj_perms_queryset.values(fields[0]).annotate(
            object_pk_count=models.Count(fields[0]))
        user_obj_perms_queryset = counts.filter(object_pk_count__gte=len(codenames))

    values = user_obj_perms_queryset.values_list(fields[0], flat=True)
    values = list(values)
    objects = queryset.filter(pk__in=values)

    return objects

def get_anonymous_user():
    ''' Return a real User in the database to represent AnonymousUser. '''
    try:
        user = User.objects.get(pk=settings.ANONYMOUS_USER_ID)
    except User.DoesNotExist:
        username = getattr(
            settings,
            'ANONYMOUS_DEFAULT_USERNAME_VALUE',
            'AnonymousUser'
        )
        permissions_to_assign = []
        # Users must have both model-level and object-level permissions to
        # satisfy DRF, so assign the anonymous user all allowed permissions at
        # the model level
        for p in settings.ALLOWED_ANONYMOUS_PERMISSIONS:
            app_label, codename = perm_parse(p)
            permissions_to_assign.append(
                Permission.objects.get(
                    content_type__app_label=app_label,
                    codename=codename
                )
            )
        user = User.objects.create(
            pk=settings.ANONYMOUS_USER_ID,
            username=username
        )
        user.user_permissions = permissions_to_assign
    return user


class ObjectPermissionManager(models.Manager):
    def _rewrite_query_args(self, method, content_object, **kwargs):
        ''' Rewrite content_object into object_id and content_type, then pass
        those together with **kwargs to the given method. '''
        content_type = ContentType.objects.get_for_model(content_object)
        kwargs['object_id'] = content_object.pk
        kwargs['content_type'] = content_type
        return method(**kwargs)

    def get_for_object(self, content_object, **kwargs):
        ''' Wrapper to allow get() queries using a generic foreign key. '''
        return self._rewrite_query_args(
            super(ObjectPermissionManager, self).get,
            content_object, **kwargs
        )

    def filter(self, *args, **kwargs):
        return super(ObjectPermissionManager, self).filter(*args, **kwargs)

    def filter_for_object(self, content_object, **kwargs):
        ''' Wrapper to allow filter() queries using a generic foreign key. '''
        return self._rewrite_query_args(
            super(ObjectPermissionManager, self).filter,
            content_object, **kwargs
        )

    def get_or_create_for_object(self, content_object, **kwargs):
        ''' Wrapper to allow get_or_create() calls using a generic foreign
        key. '''
        return self._rewrite_query_args(
            super(ObjectPermissionManager, self).get_or_create,
            content_object, **kwargs
        )


class ObjectPermission(models.Model):
    ''' An application of an auth.Permission instance to a specific
    content_object. Call ObjectPermission.objects.get_for_object() or
    filter_for_object() to run queries using the content_object field. '''
    user = models.ForeignKey('auth.User')
    permission = models.ForeignKey('auth.Permission')
    deny = models.BooleanField(
        default=False,
        help_text='Blocks inheritance of this permission when set to True'
    )
    inherited = models.BooleanField(default=False)
    object_id = models.PositiveIntegerField()
    # We can't do something like GenericForeignKey('permission__content_type'),
    # so duplicate the content_type field here.
    content_type = models.ForeignKey(ContentType)
    content_object = GenericForeignKey('content_type', 'object_id')
    uid = models.CharField(max_length=OBJECT_PERMISSION_UID_LENGTH, default='')
    objects = ObjectPermissionManager()

    @property
    def kind(self):
        return self._meta.model_name

    def _populate_uid(self):
        if self.uid == '':
            self.uid = self._generate_uid()

    def _generate_uid(self):
        return 'p' + ShortUUID().random(OBJECT_PERMISSION_UID_LENGTH-1)

    class Meta:
        unique_together = ('user', 'permission', 'deny', 'inherited',
            'object_id', 'content_type')

    def save(self, *args, **kwargs):
        if self.permission.content_type_id is not self.content_type_id:
            raise ValidationError('The content type of the permission does '
                'not match that of the object.')
        # populate uid field if it's empty
        self._populate_uid()
        super(ObjectPermission, self).save(*args, **kwargs)

    def __unicode__(self):
        for required_field in ('user', 'permission'):
            if not hasattr(self, required_field):
                return u'incomplete ObjectPermission'
        return u'{}{} {} {}'.format(
            'inherited ' if self.inherited else '',
            unicode(self.permission.codename),
            'denied from' if self.deny else 'granted to',
            unicode(self.user)
        )


class ObjectPermissionMixin(object):
    ''' A mixin class that adds the methods necessary for object-level
    permissions to a model (either models.Model or MPTTModel). The model must
    define parent, get_descendants_list(), ASSIGNABLE_PERMISSIONS,
    CALCULATED_PERMISSIONS, and, if parent references a different model,
    MAPPED_PARENT_PERMISSIONS. A post_delete signal receiver should also clean
    up any ObjectPermission records associated with the model instance.
    The MRO is important, so be sure to include this mixin before the base
    class in your model definition, e.g.
        class MyAwesomeModel(ObjectPermissionMixin, models.Model)
    '''
    @transaction.atomic
    def save(self, *args, **kwargs):
        # Make sure we exist in the database before proceeding
        super(ObjectPermissionMixin, self).save(*args, **kwargs)
        # Recalculate self and all descendants, re-fetching ourself first to
        # guard against stale MPTT values
        fresh_self = type(self).objects.get(pk=self.pk)
        fresh_self._recalculate_inherited_perms()
        for descendant in fresh_self.get_descendants_list():
            descendant._recalculate_inherited_perms()

    def _filter_anonymous_perms(self, unfiltered_set):
        ''' Restrict a set of tuples in the format (user_id, permission_id) to
        only those permissions that apply to the content_type of this object
        and are listed in settings.ALLOWED_ANONYMOUS_PERMISSIONS. '''
        content_type = ContentType.objects.get_for_model(self)
        # Translate settings.ALLOWED_ANONYMOUS_PERMISSIONS to primary keys
        codenames = set()
        for perm in settings.ALLOWED_ANONYMOUS_PERMISSIONS:
            app_label, codename = perm_parse(perm)
            if app_label == content_type.app_label:
                codenames.add(codename)
        allowed_permissions = Permission.objects.filter(
            content_type=content_type, codename__in=codenames
        ).values_list('pk', flat=True)
        filtered_set = copy.copy(unfiltered_set)
        for user_id, permission_id in unfiltered_set:
            if user_id == settings.ANONYMOUS_USER_ID:
                if permission_id not in allowed_permissions:
                    filtered_set.remove((user_id, permission_id))
        return filtered_set

    def _get_effective_perms(
        self, user=None, codename=None, include_calculated=True
    ):
        ''' Reconcile all grant and deny permissions, and return an
        authoritative set of grant permissions (i.e. deny=False) for the
        current object. '''
        # Including calculated permissions means we can't just pass kwargs
        # through to filter(), but we'll map the ones we understand.
        kwargs = {}
        if user is not None:
            kwargs['user'] = user
        if codename is not None:
            # share_ requires loading change_ from the database
            if codename.startswith('share_'):
                kwargs['permission__codename'] = re.sub(
                    '^share_', 'change_', codename, 1)
            else:
                kwargs['permission__codename'] = codename
        grant_perms = set(ObjectPermission.objects.filter_for_object(self,
            deny=False, **kwargs).values_list('user_id', 'permission_id'))
        deny_perms = set(ObjectPermission.objects.filter_for_object(self,
            deny=True, **kwargs).values_list('user_id', 'permission_id'))
        effective_perms = grant_perms.difference(deny_perms)
        # Sometimes only the explicitly assigned permissions are wanted,
        # e.g. when calculating inherited permissions
        if not include_calculated:
            # Double-check that the list includes only permissions for
            # anonymous users that are allowed by the settings. Other
            # permissions would be denied by has_perm() anyway.
            if user is None or user.pk == settings.ANONYMOUS_USER_ID:
                return self._filter_anonymous_perms(effective_perms)
            else:
                # Anonymous users weren't considered; no filtering is necessary
                return effective_perms

        # Add on the calculated permissions
        content_type = ContentType.objects.get_for_model(self)
        if codename in self.CALCULATED_PERMISSIONS:
            # A sepecific query for a calculated permission should not return
            # any explicitly assigned permissions, e.g. share_ should not
            # include change_
            effective_perms_copy = effective_perms
            effective_perms = set()
        else:
            effective_perms_copy = copy.copy(effective_perms)
        if self.editors_can_change_permissions and (
            codename is None or codename.startswith('share_')):
            # Everyone with change_ should also get share_
            change_permission = Permission.objects.get(
                content_type=content_type,
                codename__startswith='change_'
            )
            share_permission = Permission.objects.get(
                content_type=content_type,
                codename__startswith='share_'
            )
            for user_id, permission_id in effective_perms_copy:
                if permission_id == change_permission.pk:
                    effective_perms.add((user_id, share_permission.pk))
        # The owner has the delete_ permission
        if self.owner is not None and (
            user is None or user.pk == self.owner.pk) and (
            codename is None or codename.startswith('delete_')):
            delete_permission = Permission.objects.get(
                content_type=content_type,
                codename__startswith='delete_'
            )
            effective_perms.add((self.owner.pk, delete_permission.pk))
        # We may have calculated more permissions for anonymous users
        # than they are allowed to have. Remove them.
        if user is None or user.pk == settings.ANONYMOUS_USER_ID:
            return self._filter_anonymous_perms(effective_perms)
        else:
            # Anonymous users weren't considered; no filtering is necessary
            return effective_perms

    def _recalculate_inherited_perms(self):
        ''' Copy all of our parent's effective permissions to ourself,
        marking the copies as inherited permissions. The owner's rights are
        also made explicit as "inherited" permissions. '''
        # Start with a clean slate
        ObjectPermission.objects.filter_for_object(
            self,
            inherited=True
        ).delete()
        # Is there anything to inherit?
        if self.parent is not None:
            # All our parent's effective permissions become our inherited
            # permissions
            # Store translations in a dictionary here to minimize invocations
            # of the Django machinery
            translate_perm = {}
            for user_id, permission_id in self.parent._get_effective_perms(
                include_calculated=False
            ):
                if hasattr(self, 'MAPPED_PARENT_PERMISSIONS'):
                    try:
                        translated_id = translate_perm[permission_id]
                    except KeyError:
                        parent_perm = Permission.objects.get(pk=permission_id)
                        try:
                            translated_codename = \
                                self.MAPPED_PARENT_PERMISSIONS[
                                    parent_perm.codename]
                        except KeyError:
                            # We haven't been configured to inherit this
                            # permission from our parent, so skip it
                            continue
                        permission_id = Permission.objects.get(
                            content_type__app_label=\
                                parent_perm.content_type.app_label,
                            codename=translated_codename
                        ).pk
                elif type(self) is not type(self.parent):
                    raise ImproperlyConfigured(
                        'Parent of {} is a {}, but the child has not defined '
                        'MAPPED_PARENT_PERMISSIONS.'.format(
                            type(self), type(self.parent))
                    )
                ObjectPermission.objects.create(
                    content_object=self,
                    user_id=user_id,
                    permission_id=permission_id,
                    inherited=True
                )
        # The owner gets every assignable permission
        if self.owner is not None:
            content_type = ContentType.objects.get_for_model(self)
            for perm in Permission.objects.filter(
                content_type=content_type,
                codename__in=self.ASSIGNABLE_PERMISSIONS
            ):
                # Use get_or_create in case the owner already has permissions
                ObjectPermission.objects.get_or_create_for_object(
                    self,
                    user=self.owner,
                    permission=perm,
                    inherited=True
                )

    def assign_perm(self, user_obj, perm, deny=False, defer_recalc=False):
        ''' Assign user_obj the given perm on this object. To break
        inheritance from a parent object, use deny=True. '''
        app_label, codename = perm_parse(perm, self)
        if codename not in self.ASSIGNABLE_PERMISSIONS:
            # Some permissions are calculated and not stored in the database
            raise ValidationError('{} cannot be assigned explicitly.'.format(
                codename)
            )
        if isinstance(user_obj, AnonymousUser) or (
            user_obj.pk == settings.ANONYMOUS_USER_ID
        ):
            # Is an anonymous user allowed to have this permission?
            fq_permission = '{}.{}'.format(app_label, codename)
            if not fq_permission in settings.ALLOWED_ANONYMOUS_PERMISSIONS:
                raise ValidationError(
                    'Anonymous users cannot have the permission {}.'.format(
                        codename)
                )
            # Get the User database representation for AnonymousUser
            user_obj = get_anonymous_user()
        perm_model = Permission.objects.get(
            content_type__app_label=app_label,
            codename=codename
        )
        existing_perms = ObjectPermission.objects.filter_for_object(
            self,
            user=user_obj,
        )
        identical_existing_perm = existing_perms.filter(
            inherited=False,
            permission_id=perm_model.pk,
            deny=deny,
        )
        if identical_existing_perm.exists():
            # The user already has this permission directly applied
            return identical_existing_perm.first()
        # Remove any explicitly-defined contradictory grants or denials
        existing_perms.filter(user=user_obj,
            permission_id=perm_model.pk,
            deny=not deny,
            inherited=False
        ).delete()
        # Create the new permission
        new_permission = ObjectPermission.objects.create(
            content_object=self,
            user=user_obj,
            permission_id=perm_model.pk,
            deny=deny,
            inherited=False
        )
        # Granting change implies granting view
        if codename.startswith('change_') and not deny:
            change_codename = re.sub('^change_', 'view_', codename)
            self.assign_perm(user_obj, change_codename, defer_recalc=True)
        # Denying view implies denying change
        if deny and codename.startswith('view_'):
            change_codename = re.sub('^view_', 'change_', codename)
            self.assign_perm(user_obj, change_codename,
                             deny=True, defer_recalc=True)
        # We might have been called by ourself to assign a related
        # permission. In that case, don't recalculate here.
        if defer_recalc:
            return new_permission
        # Recalculate all descendants, re-fetching ourself first to guard
        # against stale MPTT values
        fresh_self = type(self).objects.get(pk=self.pk)
        for descendant in fresh_self.get_descendants_list():
            descendant._recalculate_inherited_perms()
        return new_permission

    def get_perms(self, user_obj):
        ''' Return a list of codenames of all effective grant permissions that
        user_obj has on this object. '''
        user_perm_ids = self._get_effective_perms(user=user_obj)
        perm_ids = [x[1] for x in user_perm_ids]
        return Permission.objects.filter(pk__in=perm_ids).values_list(
            'codename', flat=True)

    def get_users_with_perms(self, attach_perms=False):
        ''' Return a QuerySet of all users with any effective grant permission
        on this object. If attach_perms=True, then return a dict with
        users as the keys and lists of their permissions as the values. '''
        user_perm_ids = self._get_effective_perms()
        if attach_perms:
            user_perm_dict = {}
            for user_id, perm_id in user_perm_ids:
                perm_list = user_perm_dict.get(user_id, [])
                perm_list.append(Permission.objects.get(pk=perm_id).codename)
                user_perm_dict[user_id] = perm_list
            # Resolve user ids into actual user objects
            user_perm_dict = {User.objects.get(pk=key): value for (key, value)
                in user_perm_dict.iteritems()}
            return user_perm_dict
        else:
            # Use a set to avoid duplicate users
            user_ids = {x[0] for x in user_perm_ids}
            return User.objects.filter(pk__in=user_ids)

    def has_perm(self, user_obj, perm):
        ''' Does user_obj have perm on this object? (True/False) '''
        app_label, codename = perm_parse(perm, self)
        is_anonymous = False
        if isinstance(user_obj, AnonymousUser):
            # Get the User database representation for AnonymousUser
            user_obj = get_anonymous_user()
        if user_obj.pk == settings.ANONYMOUS_USER_ID:
            is_anonymous = True
        # Treat superusers the way django.contrib.auth does
        if user_obj.is_active and user_obj.is_superuser:
            return True
        # Look for matching permissions
        result = len(self._get_effective_perms(
            user=user_obj,
            codename=codename
        )) == 1
        if not result and not is_anonymous:
            # The user-specific test failed, but does the public have access?
            result = self.has_perm(AnonymousUser(), perm)
        if result and is_anonymous:
            # Is an anonymous user allowed to have this permission?
            fq_permission = '{}.{}'.format(app_label, codename)
            if not fq_permission in settings.ALLOWED_ANONYMOUS_PERMISSIONS:
                return False
        return result

    def remove_perm(self, user_obj, perm):
        ''' Revoke perm on this object from user_obj. May delete granted
        permissions or add deny permissions as appropriate:
        Current access      Action
        ==============      ======
        None                None
        Direct              Remove direct permission
        Inherited           Add deny permission
        Direct & Inherited  Remove direct permission; add deny permission
        '''
        if isinstance(user_obj, AnonymousUser):
            # Get the User database representation for AnonymousUser
            user_obj = get_anonymous_user()
        app_label, codename = perm_parse(perm, self)
        if codename not in self.ASSIGNABLE_PERMISSIONS:
            # Some permissions are calculated and not stored in the database
            raise ValidationError('{} cannot be removed explicitly.'.format(
                codename)
            )
        all_permissions = ObjectPermission.objects.filter_for_object(
            self,
            user=user_obj,
            permission__codename=codename,
            deny=False
        )
        direct_permissions = all_permissions.filter(inherited=False)
        inherited_permissions = all_permissions.filter(inherited=True)
        # Delete directly assigned permissions, if any
        direct_permissions.delete()
        if inherited_permissions.exists():
            # Delete inherited permissions
            inherited_permissions.delete()
            # Add a deny permission to block future inheritance
            self.assign_perm(user_obj, perm, deny=True, defer_recalc=True)
        # Recalculate all descendants, re-fetching ourself first to guard
        # against stale MPTT values
        fresh_self = type(self).objects.get(pk=self.pk)
        for descendant in fresh_self.get_descendants_list():
            descendant._recalculate_inherited_perms()
