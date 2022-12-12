from typing import Optional, Union


class StandardizeSearchableFieldMixin:

    def standardize_json_field(
        self,
        field_name: str,
        property_name: str,
        property_type: Union[str, list, dict],
        default: Optional[Union[str, list, dict]] = None,
    ):
        """
        Standardize a property inside a jsonb field to match expected
        structure.
        It helps the search with the query parser.
        """

        field = getattr(self, field_name)
        try:
            value = field.get(property_name)
        except AttributeError:
            # JSONB Field contains a string instead of a json
            field = {}
            value = ''

        if property_type is list:
            if not value or value == [None] or isinstance(value, str):
                value = default if default else []
            elif isinstance(value, dict):
                value = default if default else [value]
        elif property_type is dict:
            if not value or isinstance(value, str) or value == [None]:
                value = default if default else {}
        elif property_type is str:
            if value is None:
                value = default if default else ""
        else:
            raise NotImplementedError

        field[property_name] = value
        setattr(self, field_name, field)

    def standardize_field(
        self, field_name: str, default: str = "", allows_null=True
    ):
        """
        Standardize the default value of a field.
        It helps the search with the query parser.

        Note: Not used anywhere. It is just a future-proof utility in case
        some fields allows '' and null, or 0 and null.
        """

        value = getattr(self, field_name)

        if not value:
            if allows_null and value is None:
                return

            setattr(self, field_name, default)
