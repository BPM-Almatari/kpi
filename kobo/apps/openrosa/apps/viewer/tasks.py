# coding: utf-8
import logging
import re
import sys
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from celery import shared_task
from django.conf import settings
from django.core.mail import mail_admins

from kobo.apps.openrosa.apps.viewer.models.export import Export
from kobo.apps.openrosa.libs.exceptions import NoRecordsFoundError
from kobo.apps.openrosa.libs.utils.export_tools import (
    generate_export,
    generate_attachments_zip_export,
    generate_kml_export
)
from kobo.apps.openrosa.libs.utils.logger_tools import (
    mongo_sync_status,
    report_exception,
)
from kobo.celery import celery_app


def create_async_export(xform, export_type, query, force_xlsx, options=None):
    username = xform.user.username
    id_string = xform.id_string

    def _create_export(xform, export_type):
        return Export.objects.create(xform=xform, export_type=export_type)

    # Generate a placeholder `Export` object to be populated with the export file.
    export = _create_export(xform, export_type)
    result = None
    arguments = {
        'username': username,
        'id_string': id_string,
        'export_id': export.id,
        'query': query,
    }
    if export_type in [Export.XLS_EXPORT, Export.CSV_EXPORT]:
        if options and "group_delimiter" in options:
            arguments["group_delimiter"] = options["group_delimiter"]
        if options and "split_select_multiples" in options:
            arguments["split_select_multiples"] =\
                options["split_select_multiples"]
        if options and "binary_select_multiples" in options:
            arguments["binary_select_multiples"] =\
                options["binary_select_multiples"]

        # start async export
        if export_type == Export.XLS_EXPORT:
            result = create_xls_export.apply_async((), arguments, countdown=10)
        elif export_type == Export.CSV_EXPORT:
            result = create_csv_export.apply_async(
                (), arguments, countdown=10)
        else:
            raise Export.ExportTypeError
    elif export_type == Export.ZIP_EXPORT:
        # start async export
        result = create_zip_export.apply_async(
            (), arguments, countdown=10)
    elif export_type == Export.KML_EXPORT:
        # start async export
        result = create_kml_export.apply_async(
            (), arguments, countdown=10)
    else:
        raise Export.ExportTypeError
    if result:
        # when celery is running eager, the export has been generated by the
        # time we get here so lets retrieve the export object a fresh before we
        # save
        if settings.CELERY_TASK_ALWAYS_EAGER:
            export = Export.objects.get(id=export.id)
        export.task_id = result.task_id
        export.save()
        return export, result
    return None


@celery_app.task()
def create_xls_export(username, id_string, export_id, query=None,
                      force_xlsx=True, group_delimiter='/',
                      split_select_multiples=True,
                      binary_select_multiples=False):
    # we re-query the db instead of passing model objects according to
    # http://docs.celeryproject.org/en/latest/userguide/tasks.html#state
    ext = 'xls' if not force_xlsx else 'xlsx'

    try:
        export = Export.objects.get(id=export_id)
    except Export.DoesNotExist:
        # no export for this ID return None.
        return None

    # though export is not available when for has 0 submissions, we
    # catch this since it potentially stops celery
    try:
        gen_export = generate_export(
            Export.XLS_EXPORT, ext, username, id_string, export_id, query,
            group_delimiter, split_select_multiples, binary_select_multiples)
    except (Exception, NoRecordsFoundError) as e:
        export.internal_status = Export.FAILED
        export.save()
        # mail admins
        details = {
            'export_id': export_id,
            'username': username,
            'id_string': id_string
        }
        report_exception("XLS Export Exception: Export ID - "
                         "%(export_id)s, /%(username)s/%(id_string)s"
                         % details, e, sys.exc_info())
        # Raise for now to let celery know we failed
        # - doesnt seem to break celery`
        raise
    else:
        return gen_export.id


@celery_app.task()
def create_csv_export(username, id_string, export_id, query=None,
                      group_delimiter='/', split_select_multiples=True,
                      binary_select_multiples=False):
    # we re-query the db instead of passing model objects according to
    # http://docs.celeryproject.org/en/latest/userguide/tasks.html#state
    export = Export.objects.get(id=export_id)
    try:
        # though export is not available when for has 0 submissions, we
        # catch this since it potentially stops celery
        gen_export = generate_export(
            Export.CSV_EXPORT, 'csv', username, id_string, export_id, query,
            group_delimiter, split_select_multiples, binary_select_multiples)
    except NoRecordsFoundError:
        # not much we can do but we don't want to report this as the user
        # should not even be on this page if the survey has no records
        export.internal_status = Export.FAILED
        export.save()
    except Exception as e:
        export.internal_status = Export.FAILED
        export.save()
        # mail admins
        details = {
            'export_id': export_id,
            'username': username,
            'id_string': id_string
        }
        report_exception("CSV Export Exception: Export ID - "
                         "%(export_id)s, /%(username)s/%(id_string)s"
                         % details, e, sys.exc_info())
        raise
    else:
        return gen_export.id


@celery_app.task()
def create_kml_export(username, id_string, export_id, query=None):
    # we re-query the db instead of passing model objects according to
    # http://docs.celeryproject.org/en/latest/userguide/tasks.html#state

    export = Export.objects.get(id=export_id)
    try:
        # though export is not available when for has 0 submissions, we
        # catch this since it potentially stops celery
        gen_export = generate_kml_export(
            Export.KML_EXPORT, 'kml', username, id_string, export_id, query)
    except (Exception, NoRecordsFoundError) as e:
        export.internal_status = Export.FAILED
        export.save()
        # mail admins
        details = {
            'export_id': export_id,
            'username': username,
            'id_string': id_string
        }
        report_exception("KML Export Exception: Export ID - "
                         "%(export_id)s, /%(username)s/%(id_string)s"
                         % details, e, sys.exc_info())
        raise
    else:
        return gen_export.id


@celery_app.task()
def create_zip_export(username, id_string, export_id, query=None):
    export = Export.objects.get(id=export_id)
    try:
        gen_export = generate_attachments_zip_export(
            Export.ZIP_EXPORT, 'zip', username, id_string, export_id, query)
    except (Exception, NoRecordsFoundError) as e:
        export.internal_status = Export.FAILED
        export.save()
        # mail admins
        details = {
            'export_id': export_id,
            'username': username,
            'id_string': id_string
        }
        report_exception("Zip Export Exception: Export ID - "
                         "%(export_id)s, /%(username)s/%(id_string)s"
                         % details, e)
        raise
    else:
        if not settings.TESTING:
            delete_export.apply_async(
                (), {'export_id': gen_export.id},
                countdown=settings.ZIP_EXPORT_COUNTDOWN)
        return gen_export.id


@celery_app.task()
def delete_export(export_id):
    try:
        export = Export.objects.get(id=export_id)
    except Export.DoesNotExist:
        pass
    else:
        export.delete()
        return True
    return False


SYNC_MONGO_MANUAL_INSTRUCTIONS = """
To re-sync manually, ssh into the server and run:

python manage.py sync_mongo -r [username] [id_string]\
--settings='settings.local_settings'

To force complete delete and re-creation, use the -a option:

python manage.py sync_mongo -ra [username] [id_string]\
--settings='settings.local_settings'
"""

REMONGO_PATTERN = re.compile(r'Total # of records to remongo: -?[1-9]+',
                             re.IGNORECASE)


@celery_app.task()
def email_mongo_sync_status():
    """Check the status of records in the mysql db versus mongodb, and, if
    necessary, invoke the command to re-sync the two databases, sending an
    email report to the admins of before and after, so that manual syncing (if
    necessary) can be done."""

    before_report = mongo_sync_status()
    if REMONGO_PATTERN.search(before_report):
        # synchronization is necessary
        after_report = mongo_sync_status(remongo=True)
    else:
        # no synchronization is needed
        after_report = "No synchronization needed"

    # send the before and after reports, along with instructions for
    # syncing manually, as an email to the administrators
    mail_admins("Mongo DB sync status",
                '\n\n'.join([before_report,
                             after_report,
                             SYNC_MONGO_MANUAL_INSTRUCTIONS]))


@shared_task(soft_time_limit=60, time_limit=90)
def log_stuck_exports_and_mark_failed():
    # How long can an export possibly run, not including time spent waiting in
    # the Celery queue?
    max_export_run_time = getattr(settings, 'CELERY_TASK_TIME_LIMIT', 2100)
    # Allow a generous grace period
    max_allowed_export_age = timedelta(seconds=max_export_run_time * 4)
    this_moment = datetime.now(tz=ZoneInfo('UTC'))
    oldest_allowed_timestamp = this_moment - max_allowed_export_age
    stuck_exports = Export.objects.filter(
        internal_status=Export.PENDING,
        created_on__lt=oldest_allowed_timestamp
    )
    for stuck_export in stuck_exports:
        logging.warning(
            'Stuck export: pk {}, type {}, username {}, id_string {}, '
            'age {}'.format(
                stuck_export.pk,
                stuck_export.export_type,
                stuck_export.xform.user.username,
                stuck_export.xform.id_string,
                this_moment - stuck_export.created_on
            )
        )
        # Export.save() is a busybody; bypass it with update()
        stuck_exports.filter(pk=stuck_export.pk).update(
            internal_status=Export.FAILED)
