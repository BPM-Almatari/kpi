# coding: utf-8
import json

from django.db.models import Lookup, Field
from django.db.models.expressions import Func, Value


@Field.register_lookup
class InArray(Lookup):

    lookup_name = 'in_array'
    prepare_rhs = False

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + tuple(rhs_params)
        return '%s ?| %s' % (lhs, rhs), params


class IncrementValue(Func):

    function = 'jsonb_set'
    template = (
        "%(function)s(%(expressions)s,"
        "'{\"%(keyname)s\"}',"
        "(COALESCE(%(expressions)s ->> '%(keyname)s', '0')::int "
        "+ %(increment)s)::text::jsonb)"
    )
    arity = 1

    def __init__(self, expression: str, keyname: str, increment: int, **extra):
        super().__init__(
            expression,
            keyname=keyname,
            increment=increment,
            **extra,
        )


class OrderRandom(Func):

    function = 'array_position'
    template = '%(function)s(ARRAY%(order_list)s, %(expressions)s)'
    arity = 1

    def __init__(self, expression: str, order_list: list, **extra):

        if expression.startswith('-'):
            order_list.reverse()
            expression = expression[1:]

        super().__init__(expression, order_list=order_list, **extra)


class ReplaceValues(Func):
    """
    Updates several properties at once of a models.JSONField without overwriting the
    whole document.
    Avoids race conditions when document is saved in two different transactions
    at the same time. (i.e.: `Asset._deployment['status']`)
    https://www.postgresql.org/docs/current/functions-json.html

    Notes from postgres docs:
    > Does not operate recursively: only the top-level array or object
    > structure is merged
    """
    arg_joiner = ' || '
    template = "%(expressions)s"
    arity = 2

    def __init__(
        self,
        expression: str,
        updates: dict,
        **extra,
    ):
        super().__init__(
            expression,
            Value(json.dumps(updates)),
            **extra,
        )
