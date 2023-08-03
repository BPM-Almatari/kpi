from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.forms import SignupForm
from constance import config
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.db import transaction
from django.shortcuts import resolve_url
from django.template.response import TemplateResponse
from django.utils import timezone
from trench.utils import get_mfa_model, user_token_generator

from .mfa.forms import MfaTokenForm
from .mfa.views import MfaTokenView


class AccountAdapter(DefaultAccountAdapter):

    def pre_login(self, request, user, **kwargs):

        if parent_response := super().pre_login(request, user, **kwargs):
            # A response from the parent means the login process must be
            # interrupted, e.g. due to the user being inactive or not having
            # validated their email address
            return parent_response

        # If MFA is activated, display the token form before let them in
        if get_mfa_model().objects.filter(is_active=True, user=user).exists():

            ephemeral_token_cache = user_token_generator.make_token(user)
            mfa_token_form = MfaTokenForm(
                initial={'ephemeral_token': ephemeral_token_cache}
            )

            next_url = (
                kwargs.get('redirect_url')
                or resolve_url(settings.LOGIN_REDIRECT_URL)
            )
            context = {
                REDIRECT_FIELD_NAME: next_url,
                'view': MfaTokenView,
                'form': mfa_token_form,
            }

            return TemplateResponse(
                request=request,
                template='mfa_token.html',
                context=context,
            )

    def is_open_for_signup(self, request):
        return config.REGISTRATION_OPEN

    def save_user(self, request, user, form, commit=True):
        # Compare allauth SignupForm with our custom field
        standard_fields = set(SignupForm().fields.keys())
        extra_fields = set(form.fields.keys()).difference(standard_fields)
        with transaction.atomic():
            user = super().save_user(request, user, form, commit)
            extra_data = {k: form.cleaned_data[k] for k in extra_fields}
            user.extra_details.data.update(extra_data)
            if commit:
                user.extra_details.save()
        return user

    def set_password(self, user, password):
        with transaction.atomic():
            user.extra_details.password_date_changed = timezone.now()
            user.extra_details.validated_password = True
            user.extra_details.save(
                update_fields=['password_date_changed', 'validated_password']
            )
            user.set_password(password)
            user.save()
