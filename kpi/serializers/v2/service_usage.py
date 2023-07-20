from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from rest_framework import serializers
from rest_framework.fields import empty

from kobo.apps.organizations.models import Organization
from kobo.apps.project_views.models.assignment import User
from kobo.apps.trackers.models import NLPUsageCounter
from kpi.constants import ASSET_TYPE_SURVEY
from kpi.deployment_backends.kc_access.shadow_models import (
    KobocatXForm,
    ReadOnlyKobocatDailyXFormSubmissionCounter,
)
from kpi.deployment_backends.kobocat_backend import KobocatDeploymentBackend
from kpi.models.asset import Asset


class AssetUsageSerializer(serializers.HyperlinkedModelSerializer):
    asset = serializers.HyperlinkedIdentityField(
        lookup_field='uid',
        view_name='asset-detail',
    )
    asset__name = serializers.ReadOnlyField(source='name')
    nlp_usage_current_month = serializers.SerializerMethodField()
    nlp_usage_current_year = serializers.SerializerMethodField()
    nlp_usage_all_time = serializers.SerializerMethodField()
    storage_bytes = serializers.SerializerMethodField()
    submission_count_current_month = serializers.SerializerMethodField()
    submission_count_current_year = serializers.SerializerMethodField()
    submission_count_all_time = serializers.SerializerMethodField()
    _now = timezone.now().date()

    class Meta:
        model = Asset
        lookup_field = 'uid'
        fields = (
            'asset',
            'asset__name',
            'nlp_usage_current_month',
            'nlp_usage_current_year',
            'nlp_usage_all_time',
            'storage_bytes',
            'submission_count_current_month',
            'submission_count_current_year',
            'submission_count_all_time',
        )

    def get_nlp_usage_current_month(self, asset):
        start_date = self._now.replace(day=1)
        return self._get_nlp_tracking_data(asset, start_date)

    def get_nlp_usage_current_year(self, asset):
        start_date = self._now.replace(day=1, month=1)
        return self._get_nlp_tracking_data(asset, start_date)

    def get_nlp_usage_all_time(self, asset):
        return self._get_nlp_tracking_data(asset)

    def get_submission_count_current_month(self, asset):
        if not asset.has_deployment:
            return 0
        start_date = self._now.replace(day=1)
        return asset.deployment.submission_count_since_date(start_date)

    def get_submission_count_current_year(self, asset):
        if not asset.has_deployment:
            return 0
        start_date = self._now.replace(day=1, month=1)
        return asset.deployment.submission_count_since_date(start_date)

    def get_submission_count_all_time(self, asset):
        if not asset.has_deployment:
            return 0

        return asset.deployment.submission_count_since_date()

    def get_storage_bytes(self, asset):
        # Get value from asset deployment (if it has deployment)
        if not asset.has_deployment:
            return 0

        return asset.deployment.attachment_storage_bytes

    def _get_nlp_tracking_data(self, asset, start_date=None):
        if not asset.has_deployment:
            return {
                'total_nlp_asr_seconds': 0,
                'total_nlp_mt_characters': 0,
            }
        return KobocatDeploymentBackend.nlp_tracking_data(
            asset_ids=[asset.id], start_date=start_date
        )


class ServiceUsageSerializer(serializers.Serializer):
    total_nlp_usage = serializers.SerializerMethodField()
    total_storage_bytes = serializers.SerializerMethodField()
    total_submission_count = serializers.SerializerMethodField()
    current_month_start = serializers.SerializerMethodField()
    current_year_start = serializers.SerializerMethodField()
    _now = timezone.now().date()

    def __init__(self, instance=None, data=empty, **kwargs):
        super().__init__(instance=instance, data=data, **kwargs)

        self._total_nlp_usage = {}
        self._total_storage_bytes = 0
        self._total_submission_count = {}
        self._current_month_start = None
        self._current_year_start = None
        self._anchor_date = None
        self._period_start = None
        self._subscription_interval = None
        self._get_per_asset_usage(instance)

    def get_total_nlp_usage(self, user):
        return self._total_nlp_usage

    def get_total_submission_count(self, user):
        return self._total_submission_count

    def get_total_storage_bytes(self, user):
        return self._total_storage_bytes

    def get_current_month_start(self, user):
        return self._current_month_start

    def get_current_year_start(self, user):
        return self._current_year_start

    def _get_per_asset_usage(self, user):
        self._users = [user]

        # Get the organization ID passed in from the query parameters
        organization_id = self.context['request'].query_params.get(
            'organization_id'
        )
        self._get_organization_details(organization_id)

        # Only use fields we need to improve SQL query speed
        user_assets = (
            Asset.objects.only(
                'pk',
                'uid',
                '_deployment_data',
                'owner_id',
                'name',
            )
            .select_related('owner')
            .filter(
                owner__in=self._users,
                asset_type=ASSET_TYPE_SURVEY,
                # Make sure we're only getting assets that are deployed
                _deployment_data__has_key='backend',
            )
        )

        xforms = KobocatXForm.objects.only('bytes_sum', 'id').filter(
            kpi_asset_uid__in=[user_asset.uid for user_asset in user_assets]
        )

        total_storage_bytes = xforms.aggregate(
            bytes_sum=Coalesce(Sum('attachment_storage_bytes'), 0),
        )
        self._total_storage_bytes = total_storage_bytes['bytes_sum'] or 0

        self._current_month_start = self._get_current_month_start_date()
        self._current_year_start = self._get_current_year_start_date()
        current_month_filter = Q(
            date__range=[self._current_month_start, self._now]
        )
        current_year_filter = Q(
            date__range=[self._current_year_start, self._now]
        )

        submission_count = (
            ReadOnlyKobocatDailyXFormSubmissionCounter.objects.only(
                'date', 'xform', 'counter'
            )
            .filter(
                xform__in=xforms,
            )
            .aggregate(
                all_time=Coalesce(Sum('counter'), 0),
                current_year=Coalesce(
                    Sum('counter', filter=current_year_filter), 0
                ),
                current_month=Coalesce(
                    Sum('counter', filter=current_month_filter), 0
                ),
            )
        )

        for submission_key, count in submission_count.items():
            self._total_submission_count[submission_key] = (
                count if count is not None else 0
            )

        nlp_tracking = (
            NLPUsageCounter.objects.only(
                'date', 'total_asr_seconds', 'total_mt_characters'
            )
            .filter(
                asset_id__in=user_assets,
            )
            .aggregate(
                asr_seconds_current_year=Coalesce(
                    Sum('total_asr_seconds', filter=current_year_filter), 0
                ),
                mt_characters_current_year=Coalesce(
                    Sum('total_mt_characters', filter=current_year_filter), 0
                ),
                asr_seconds_current_month=Coalesce(
                    Sum('total_asr_seconds', filter=current_month_filter), 0
                ),
                mt_characters_current_month=Coalesce(
                    Sum('total_mt_characters', filter=current_month_filter), 0
                ),
                asr_seconds_all_time=Coalesce(Sum('total_asr_seconds'), 0),
                mt_characters_all_time=Coalesce(Sum('total_mt_characters'), 0),
            )
        )
        for nlp_key, count in nlp_tracking.items():
            self._total_nlp_usage[nlp_key] = count if count is not None else 0

    def _get_current_month_start_date(self):
        # No subscription info, just use the first day of current month
        if not self._anchor_date:
            return self._now.replace(day=1)

        # Subscription is billed monthly, use the current billing period start date
        if self._subscription_interval == 'month':
            return self._period_start

        # Subscription is yearly, calculate the start date based on the anchor day
        anchor_day = self._anchor_date.day
        if self._now.day > anchor_day:
            return self._now.replace(day=anchor_day)
        start_year = self._now.year
        start_month = self._now.month - 1
        if start_month == 0:
            start_month = 12
            start_year -= 1
        return self._now.replace(
            day=anchor_day, month=start_month, year=start_year
        )

    def _get_current_year_start_date(self):
        # No subscription info, just use the first day of current year
        if not self._anchor_date:
            return self._now.replace(day=1, month=1)

        # Subscription is billed yearly, use the provided anchor date as start date
        if self._subscription_interval == 'year':
            return self._period_start

        # Subscription is monthly, calculate this year's start based on anchor date
        if self._anchor_date.replace(year=self._now.year) > self._now:
            return self._anchor_date.replace(year=self._now.year - 1)
        return self._anchor_date.replace(year=self._now.year)

    def _get_organization_details(self, organization_id=None):
        if not organization_id:
            return

        organization = Organization.objects.filter(
            owner__organization_user__user=self.context.get('request').user,
            id=organization_id,
        ).first()

        if not organization:
            # Couldn't find organization, proceed as normal
            return

        # If the user is in an organization, get all org users so we can query their total org usage
        self._users = User.objects.filter(
            organizations_organization__id=organization_id
        )

        # If they have a subscription, use its start date to calculate beginning of current month/year's usage
        billing_details = organization.active_subscription_billing_details
        if billing_details:
            self._anchor_date = billing_details['billing_cycle_anchor'].date()
            self._period_start = billing_details['current_period_start'].date()
            self._subscription_interval = billing_details['recurring_interval']
