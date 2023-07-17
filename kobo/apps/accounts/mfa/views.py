# coding: utf-8
from allauth.account.views import LoginView
from django.conf import settings
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.db.models import QuerySet
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url
from django.urls import reverse
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from trench.utils import get_mfa_model

from kobo.apps.stripe.constants import ACTIVE_STRIPE_STATUSES

from .forms import MfaLoginForm, MfaTokenForm
from .serializers import UserMfaMethodSerializer


class MfaLoginView(LoginView):
    form_class = MfaLoginForm

    def form_valid(self, form):
        if form.get_ephemeral_token():
            mfa_token_form = MfaTokenForm(
                initial={'ephemeral_token': form.get_ephemeral_token()}
            )

            context = self.get_context_data(
                view=MfaTokenView,
                form=mfa_token_form,
                next=self.get_success_url(),
            )

            # Prevent users without paid plans from entering step 2 of MFA flow
            if settings.STRIPE_ENABLED:
                redirect = self.login_if_user_has_subscription(form, context)
                if redirect:
                    return redirect

            return self.response_class(
                request=self.request,
                template='mfa_token.html',
                context=context,
                using=self.template_engine,
            )
        else:
            return super().form_valid(form)

    def get_success_url(self):
        """
        Overload parent method to validate `next` url
        """
        redirect_to = super().get_success_url()

        if not redirect_to:
            redirect_to = self.request.POST.get(
                self.redirect_field_name,
                self.request.GET.get(self.redirect_field_name, ''),
            )

        # We do not want to redirect a regular user to `/admin/` if they
        # are not a superuser. Otherwise, they are successfully authenticated,
        # redirected to the admin platform, then disconnected because of the
        # lack of permissions.
        user = self.request.user
        if (
            user.is_authenticated
            and self.redirect_field_name in self.request.POST
            and user.is_superuser
            and redirect_to.startswith(reverse('admin:index'))
        ):
            return ''

        return redirect_to

    def login_if_user_has_subscription(self, form, context):
        """
        Check if the user has an active, paid subscription.
        If they do, log the user in and return an HTTPResponse, skipping MFA token entry.
        If they don't, return None and do nothing.
        """
        username = form.cleaned_data.get('login')
        active_subscription = (
            User.objects.filter(
                organizations_organization__djstripe_customers__subscriber__organization_users__user__username=username,
                organizations_organization__djstripe_customers__subscriptions__status__in=ACTIVE_STRIPE_STATUSES,
            )
            .exclude(
                organizations_organization__djstripe_customers__subscriptions__items__price__unit_amount=0
            )
            .exists()
        )

        if not active_subscription:
            super().form_valid(form)
            next_url = context['redirect_field_value'] or resolve_url(
                settings.LOGIN_REDIRECT_URL
            )

            password = form.cleaned_data.get('password')
            authenticated_user = authenticate(
                username=username, password=password
            )

            # When login is successful, `django.contrib.auth.login()` expects the
            # authentication backend class to be provided.
            # See https://github.com/django/django/blob/b87820668e7bd519dbc05f6ee46f551858fb1d6d/django/contrib/auth/__init__.py#L111
            # Since we do not have a bullet-proof way to detect which authentication
            # class is the good one, we use the first element of the list
            backend = settings.AUTHENTICATION_BACKENDS[0]
            login(self.request, authenticated_user, backend=backend)

            return HttpResponseRedirect(
                resolve_url(self.get_success_url() or next_url)
            )


class MfaTokenView(DjangoLoginView):
    """
    Display the login form and handle the login action.
    """

    form_class = MfaTokenForm
    authentication_form = None
    template_name = 'mfa_token.html'
    redirect_authenticated_user = False
    extra_context = None


class MfaListUserMethodsView(ListAPIView):
    """
    Display user's methods with dates
    """

    serializer_class = UserMfaMethodSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def get_queryset(self) -> QuerySet:
        mfa_model = get_mfa_model()
        return mfa_model.objects.filter(user_id=self.request.user.id)
