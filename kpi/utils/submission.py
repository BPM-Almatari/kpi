from django.core.exceptions import SuspiciousFileOperation

from kpi.deployment_backends.kc_access.storage import default_kobocat_storage
from kpi.utils.log import logging


def get_attachment_filenames_and_xpaths(
    submission: dict, attachment_xpaths: list
) -> dict:
    """
    Return a dictionary of all valid attachment filenames of a submission mapped
    to their respective XPath.
    """

    return_dict = {}
    for key, value in submission.items():
        if isinstance(value, list):
            for item_list in value:
                if isinstance(item_list, dict):
                    return_dict.update(
                        get_attachment_filenames_and_xpaths(
                            item_list, attachment_xpaths
                        )
                    )
        elif isinstance(value, dict):
            return_dict.update(
                get_attachment_filenames_and_xpaths(value, attachment_xpaths)
            )
        else:
            if key in attachment_xpaths:
                try:
                    value = default_kobocat_storage.get_valid_name(value)
                except SuspiciousFileOperation:
                    logging.error(f'Could not get valid name from {value}')
                    continue
                return_dict[value] = key

    return return_dict
