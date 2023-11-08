# coding: utf-8
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from rest_framework import (
    renderers,
    viewsets,
)
from rest_framework.response import Response

from kpi.permissions import IsAuthenticated
from kpi.serializers.v2.service_usage import ServiceUsageSerializer
from kpi.utils.object_permission import get_database_user


# @method_decorator(cache_page(settings.ENDPOINT_CACHE_DURATION), name='list')
# @method_decorator(vary_on_cookie, name='list')
class ServiceUsageViewSet(viewsets.GenericViewSet):
    """
    ## Service Usage Tracker
    <p>Tracks the total usage of different services for the logged-in user</p>
    <p>Tracks the submissions and NLP seconds/characters for the current month/year/all time</p>
    <p>Tracks the current total storage used</p>
    <strong>This endpoint is cached for an amount of time determined by ENDPOINT_CACHE_DURATION</strong>

    <pre class="prettyprint">
    <b>GET</b> /api/v2/service_usage/
    </pre>

    > Example
    >
    >       curl -X GET https://[kpi]/api/v2/service_usage/
    >       {
    >           "total_nlp_usage": {
    >               "asr_seconds_current_month": {integer},
    >               "asr_seconds_current_year": {integer},
    >               "asr_seconds_all_time": {integer},
    >               "mt_characters_current_month": {integer},
    >               "mt_characters_current_year": {integer},
    >               "mt_characters_all_time": {integer},
    >           },
    >           "total_storage_bytes": {integer},
    >           "total_submission_count": {
    >               "current_month": {integer},
    >               "current_year": {integer},
    >               "all_time": {integer},
    >           },
    >           "current_month_start": {string (date), YYYY-MM-DD format},
    >           "current_year_start": {string (date), YYYY-MM-DD format},
    >       }


    ### CURRENT ENDPOINT
    """

    renderer_classes = (
        renderers.BrowsableAPIRenderer,
        renderers.JSONRenderer,
    )
    pagination_class = None
    permission_classes = (IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        serializer = ServiceUsageSerializer(
            get_database_user(request.user),
            context=self.get_serializer_context(),
        )
        return Response(data=serializer.data)
