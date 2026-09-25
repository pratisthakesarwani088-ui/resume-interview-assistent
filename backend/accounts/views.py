from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import ChangePasswordSerializer, ProfileSerializer, SignupSerializer

User = get_user_model()


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------
class SignupView(generics.CreateAPIView):
    """POST /api/auth/signup/  -> creates a user. Public endpoint."""

    queryset = User.objects.all()
    serializer_class = SignupSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "message": "Account created successfully.",
                "user": {"id": user.id, "name": user.name, "email": user.email},
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Login (JWT) — extends simplejwt's obtain-pair view to also return user info
# ---------------------------------------------------------------------------
class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)  # raises 401 on bad credentials
        data["user"] = {
            "id": self.user.id,
            "name": self.user.name,
            "email": self.user.email,
        }
        return data


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/  -> {access, refresh, user}. Public endpoint."""

    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]


# ---------------------------------------------------------------------------
# Logout — blacklists the refresh token so it can't be reused
# ---------------------------------------------------------------------------
class LogoutView(APIView):
    """POST /api/auth/logout/  body: {refresh}. Requires auth."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response({"detail": "Invalid or expired refresh token."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Profile — the logged-in user's own record only (isolation enforced by
# always returning/operating on request.user, never a pk from the URL)
# ---------------------------------------------------------------------------
class ProfileView(generics.RetrieveUpdateAPIView):
    """GET/PUT/PATCH /api/auth/profile/  -> name + email only. Requires auth."""

    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------
class ChangePasswordView(APIView):
    """POST /api/auth/change-password/  body: {old_password, new_password, confirm_new_password}."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)
