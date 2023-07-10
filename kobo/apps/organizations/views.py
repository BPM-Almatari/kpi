from django.db.models import QuerySet
from organizations.backends import invitation_backend
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Organization, OrganizationUser, create_organization
from .permissions import IsOrgAdminOrReadOnly
from .serializers import (
    OrganizationSerializer,
    OrganizationUserInvitationSerializer,
    OrganizationUserSerializer,
)


class OrganizationViewSet(viewsets.ModelViewSet):
    """
    Organizations are groups of users with assigned permissions and configurations

    - Organization admins can manage the organization and it's membership
    - Connect to authentication mechanisms and enforce policy
    - Create teams and projects under the organization
    """

    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    lookup_field = 'id'
    permission_classes = (IsAuthenticated, IsOrgAdminOrReadOnly)

    def get_queryset(self) -> QuerySet:
        user = self.request.user
        queryset = super().get_queryset().filter(users=user)
        if self.action == "list" and not queryset:
            # Very inefficient get or create queryset.
            # It's temporary and should be removed later.
            create_organization(user, f"{user.username}'s organization")
            queryset = queryset.all()  # refresh
        return queryset


class OrganizationUserViewSet(viewsets.ModelViewSet):
    queryset = OrganizationUser.objects.all()
    serializer_class = OrganizationUserSerializer
    permission_classes = (IsAuthenticated, IsOrgAdminOrReadOnly)

    def get_serializer_class(self):
        if self.action in ["create"]:
            return OrganizationUserInvitationSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                organization__users=self.request.user,
                organization_id=self.kwargs.get("organization_id"),
            )
        )

    def perform_create(self, serializer):
        invitation_backend().send_invitation(org_user)