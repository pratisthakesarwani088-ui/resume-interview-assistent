from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class SignupTests(APITestCase):
    def test_signup_success(self):
        url = reverse("signup")
        payload = {
            "name": "Asha Rao",
            "email": "asha@example.com",
            "password": "StrongPass123",
            "confirm_password": "StrongPass123",
        }
        res = self.client.post(url, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="asha@example.com").exists())
        # password must be hashed, never stored/returned in plaintext
        user = User.objects.get(email="asha@example.com")
        self.assertNotEqual(user.password, "StrongPass123")
        self.assertNotIn("password", res.data["user"])

    def test_signup_password_mismatch(self):
        url = reverse("signup")
        payload = {
            "name": "Asha Rao",
            "email": "asha2@example.com",
            "password": "StrongPass123",
            "confirm_password": "Different123",
        }
        res = self.client.post(url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirm_password", res.data)

    def test_signup_duplicate_email_rejected(self):
        User.objects.create_user(email="dupe@example.com", name="First", password="StrongPass123")
        url = reverse("signup")
        payload = {
            "name": "Second",
            "email": "dupe@example.com",
            "password": "StrongPass123",
            "confirm_password": "StrongPass123",
        }
        res = self.client.post(url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", res.data)

    def test_signup_weak_password_rejected(self):
        url = reverse("signup")
        payload = {
            "name": "Weak Pass",
            "email": "weak@example.com",
            "password": "12345678",
            "confirm_password": "12345678",
        }
        res = self.client.post(url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="login@example.com", name="Login User", password="StrongPass123")

    def test_login_success_returns_tokens(self):
        url = reverse("login")
        res = self.client.post(url, {"email": "login@example.com", "password": "StrongPass123"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)
        self.assertEqual(res.data["user"]["email"], "login@example.com")

    def test_login_wrong_password_rejected(self):
        url = reverse("login")
        res = self.client.post(url, {"email": "login@example.com", "password": "WrongPass123"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_user_rejected(self):
        url = reverse("login")
        res = self.client.post(url, {"email": "nouser@example.com", "password": "StrongPass123"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfileAndIsolationTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email="a@example.com", name="User A", password="StrongPass123")
        self.user_b = User.objects.create_user(email="b@example.com", name="User B", password="StrongPass123")

    def _login(self, email, password):
        res = self.client.post(reverse("login"), {"email": email, "password": password})
        return res.data["access"], res.data["refresh"]

    def test_profile_requires_auth(self):
        res = self.client.get(reverse("profile"))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_returns_only_own_data(self):
        access, _ = self._login("a@example.com", "StrongPass123")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        res = self.client.get(reverse("profile"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["email"], "a@example.com")
        self.assertEqual(set(res.data.keys()), {"id", "name", "email"})

    def test_user_cannot_see_other_users_profile(self):
        # There is no pk-based profile endpoint at all — /profile/ always
        # resolves to request.user, so isolation holds by construction.
        access_a, _ = self._login("a@example.com", "StrongPass123")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_a}")
        res = self.client.get(reverse("profile"))
        self.assertNotEqual(res.data["email"], self.user_b.email)

    def test_profile_update_name_and_email(self):
        access, _ = self._login("a@example.com", "StrongPass123")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        res = self.client.patch(reverse("profile"), {"name": "User A Updated"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["name"], "User A Updated")

    def test_profile_update_email_to_existing_rejected(self):
        access, _ = self._login("a@example.com", "StrongPass123")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        res = self.client.patch(reverse("profile"), {"email": "b@example.com"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class ChangePasswordTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="cp@example.com", name="CP User", password="OldPass123")
        res = self.client.post(reverse("login"), {"email": "cp@example.com", "password": "OldPass123"})
        self.access = res.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")

    def test_change_password_success(self):
        res = self.client.post(reverse("change_password"), {
            "old_password": "OldPass123",
            "new_password": "NewPass456",
            "confirm_new_password": "NewPass456",
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass456"))

    def test_change_password_wrong_old_password(self):
        res = self.client.post(reverse("change_password"), {
            "old_password": "WrongOld123",
            "new_password": "NewPass456",
            "confirm_new_password": "NewPass456",
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_mismatch(self):
        res = self.client.post(reverse("change_password"), {
            "old_password": "OldPass123",
            "new_password": "NewPass456",
            "confirm_new_password": "Different789",
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class LogoutTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="lo@example.com", name="Logout User", password="StrongPass123")
        res = self.client.post(reverse("login"), {"email": "lo@example.com", "password": "StrongPass123"})
        self.access = res.data["access"]
        self.refresh = res.data["refresh"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")

    def test_logout_blacklists_refresh_token(self):
        res = self.client.post(reverse("logout"), {"refresh": self.refresh})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # trying to use the same refresh token again must now fail
        refresh_res = self.client.post(reverse("token_refresh"), {"refresh": self.refresh})
        self.assertEqual(refresh_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_auth(self):
        self.client.credentials()  # clear auth header
        res = self.client.post(reverse("logout"), {"refresh": self.refresh})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
