import constance
from allauth.account import app_settings
from allauth.account.adapter import get_adapter
from allauth.account.forms import LoginForm as BaseLoginForm
from allauth.account.forms import SignupForm as BaseSignupForm
from allauth.account.utils import (
    get_user_model,
    user_email,
    user_username,
)
from allauth.socialaccount.forms import SignupForm as BaseSocialSignupForm
from django import forms
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils.translation import gettext_lazy as t

from hub.utils.i18n import I18nUtils
from kobo.static_lists import COUNTRIES, USER_METADATA_DEFAULT_LABELS


# Only these fields can be controlled by constance.config.USER_METADATA_FIELDS
CONFIGURABLE_METADATA_FIELDS = (
    'name',
    'organization',
    'gender',
    'sector',
    'country',
)


class LoginForm(BaseLoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['login'].widget.attrs['placeholder'] = ''
        self.fields['password'].widget.attrs['placeholder'] = ''
        self.label_suffix = ''


class KoboSignupMixin(forms.Form):
    name = forms.CharField(
        label=USER_METADATA_DEFAULT_LABELS['name'],
        required=False,
    )
    organization = forms.CharField(
        label=USER_METADATA_DEFAULT_LABELS['organization'],
        required=False,
    )
    gender = forms.ChoiceField(
        label=USER_METADATA_DEFAULT_LABELS['gender'],
        required=False,
        widget=forms.RadioSelect,
        choices=(
            ('male', t('Male')),
            ('female', t('Female')),
            ('other', t('Other')),
        ),
    )
    sector = forms.ChoiceField(
        label=USER_METADATA_DEFAULT_LABELS['sector'],
        required=False,
        # Don't set choices here; set them in the constructor so that changes
        # made in the Django admin interface do not require a server restart
    )
    country = forms.ChoiceField(
        label=USER_METADATA_DEFAULT_LABELS['country'],
        required=False,
        choices=(('', ''),) + COUNTRIES,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove upstream placeholders
        for field_name in ['username', 'email', 'password1', 'password2']:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs['placeholder'] = ''
        if 'password2' in self.fields:
            self.fields['password2'].label = t('Password confirmation')

        # Intentional t() call on dynamic string because the default choices
        # are translated (see static_lists.py)
        # Strip "\r" for legacy data created prior to django-constance 2.7.
        self.fields['sector'].choices = (('', ''),) + tuple(
            (s.strip('\r'), t(s.strip('\r')))
            for s in constance.config.SECTOR_CHOICES.split('\n')
        )

        # It's easier to _remove_ unwanted fields here in the constructor
        # than to add a new fields *shrug*
        desired_metadata_fields = I18nUtils.get_metadata_fields('user')
        desired_metadata_fields = {
            field['name']: field for field in desired_metadata_fields
        }
        for field_name in list(self.fields.keys()):
            if field_name not in CONFIGURABLE_METADATA_FIELDS:
                # This field is not allowed to be configured
                continue

            try:
                desired_field = desired_metadata_fields[field_name]
            except KeyError:
                # This field is unwanted
                self.fields.pop(field_name)
                continue

            field = self.fields[field_name]
            field.required = desired_field.get('required', False)
            self.fields[field_name].label = desired_field['label']

    def clean_email(self):
        email = self.cleaned_data['email']
        domain = email.split('@')[1].lower()
        allowed_domains = (
            constance.config.REGISTRATION_ALLOWED_EMAIL_DOMAINS.strip()
        )
        allowed_domain_list = [
            domain.lower() for domain in allowed_domains.split('\n')
        ]
        # An empty domain list means all domains are allowed
        if domain in allowed_domain_list or not allowed_domains:
            return email
        else:
            raise forms.ValidationError(
                constance.config.REGISTRATION_DOMAIN_NOT_ALLOWED_ERROR_MESSAGE
            )


class SocialSignupForm(KoboSignupMixin, BaseSocialSignupForm):
    field_order = [
        'username',
        'email',
        'name',
        'gender',
        'sector',
        'country',
        'organization',
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if settings.UNSAFE_SSO_REGISTRATION_EMAIL_DISABLE:
            self.fields['email'].widget.attrs['readonly'] = True
        self.label_suffix = ''


class SignupForm(KoboSignupMixin, BaseSignupForm):
    field_order = [
        'name',
        'organization',
        'username',
        'email',
        'sector',
        'country',
    ]

    def clean(self):
        """
        Override parent form to pass extra user's attributes to validation.
        """
        super(BaseSignupForm, self).clean()

        User = get_user_model()  # noqa
        dummy_user = User()
        user_username(dummy_user, self.cleaned_data.get('username'))
        user_email(dummy_user, self.cleaned_data.get('email'))
        setattr(dummy_user, 'organization', self.cleaned_data.get('organization', ''))
        setattr(dummy_user, 'full_name', self.cleaned_data.get('name', ''))

        password = self.cleaned_data.get('password1')
        if password:
            try:
                get_adapter().clean_password(password, user=dummy_user)
            except forms.ValidationError as e:
                self.add_error('password1', e)

        if (
            app_settings.SIGNUP_PASSWORD_ENTER_TWICE
            and 'password1' in self.cleaned_data
            and 'password2' in self.cleaned_data
        ):
            if self.cleaned_data['password1'] != self.cleaned_data['password2']:
                self.add_error(
                    'password2',
                    t('You must type the same password each time.'),
                )
        return self.cleaned_data
