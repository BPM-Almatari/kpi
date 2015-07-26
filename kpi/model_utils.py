import copy
import re
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User, Permission
from django.conf import settings
from .models import Asset
from .models import Collection
from .models.object_permission import perm_parse

'''
This circular import will bite you if you don't import kpi.models before
importing kpi.model_utils:
  File "kpi/model_utils.py", line 6, in <module>
    from .models import Asset
  File "kpi/models/__init__.py", line 5, in <module>
    from kpi.models.import_task import ImportTask
  File "kpi/models/import_task.py", line 6, in <module>
    from kpi.model_utils import create_assets
'''

TAG_RE = r'tag:(.*)'
from collections import defaultdict

def _load_library_content(structure):
    content = structure.get('content', {})
    if 'library' not in content:
        raise Exception('to load a library, you must have a sheet called "library"')
    library_sheet = content.get('library', [])
    del content['library']

    grouped = defaultdict(list)
    for row in library_sheet:
        # preserve the additional sheets of imported library (but not the library)
        row_tags = []
        for key, val in row.items():
            if unicode(val).lower() in ['false', '0', 'no', 'n', '', 'none']:
                continue
            if re.search(TAG_RE, key):
                row_tags.append(re.match(TAG_RE, key).groups()[0])
                del row[key]
        block_name = row.get('block', None)
        grouped[block_name].append((row, row_tags,))

    collection = Collection.objects.create(owner=structure['owner'], name=structure['name'])

    for block_name, rows in grouped.items():
        if block_name is None:
            for (row, row_tags) in rows:
                scontent = copy.deepcopy(content)
                scontent['survey'] = [row]
                sa = Asset.objects.create(content=scontent, asset_type='question',
                                            owner=structure['owner'], parent=collection)
                sa.tags.add(*row_tags)
        else:
            block_rows = []
            block_tags = set()
            for (row, row_tags) in rows:
                for tag in row_tags:
                    block_tags.add(tag)
                block_rows.append(row)
            scontent = copy.deepcopy(content)
            scontent['survey'] = block_rows
            sa = Asset.objects.create(content=scontent, asset_type='block',
                                        owner=structure['owner'], parent=collection)
            sa.tags.add(*list(block_tags))
    return collection

def create_assets(kls, structure, **options):
    if kls == "collection":
        obj = Collection.objects.create(**structure)
    elif kls == "asset":
        if 'library' in structure.get('content', {}):
            obj = _load_library_content(structure)
        else:
            obj = Asset.objects.create(**structure)
    return obj

def grant_all_model_level_perms(
        user, models, permissions_manager=Permission.objects
    ):
    ''' Utility function that gives ``user`` unrestricted model-level access
    to everything listed in ``models``. Without this, actions on individual
    instances are immediately denied and object-level permissions are never
    considered.
    The ``permissions_manager`` argument is for use in data migrations.
    '''
    content_types = []
    try:
        for model in models:
            content_types.append(ContentType.objects.get_for_model(model))
    except TypeError:
        # models is a single model, not an iterable
        content_types.append(ContentType.objects.get_for_model(models))
    permissions_to_assign = permissions_manager.filter(
        content_type__in=content_types)
    if user.pk == settings.ANONYMOUS_USER_ID:
        # The user is anonymous, so pare down the permissions to only those
        # that the configuration allows for anonymous users
        q_query = Q()
        for allowed_permission in settings.ALLOWED_ANONYMOUS_PERMISSIONS:
            app_label, codename = perm_parse(allowed_permission)
            q_query |= Q(content_type__app_label=app_label, codename=codename)
        permissions_to_assign = permissions_to_assign.filter(q_query)
    user.user_permissions.add(*permissions_to_assign)
