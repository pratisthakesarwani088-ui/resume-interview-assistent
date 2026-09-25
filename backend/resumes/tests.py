from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


def build_minimal_pdf(text="Hello Resume"):
    """
    Hand-builds a small, well-formed, single-page PDF (correct xref byte
    offsets included) so tests exercise the real PyMuPDF extraction path
    instead of mocking it out.
    """
    objects = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    stream = f"BT /F1 24 Tf 72 700 Td ({text}) Tj ET".encode()
    objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")

    header = b"%PDF-1.4\n"
    body = header
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += b"%d 0 obj\n" % i + obj + b"\nendobj\n"

    xref_offset = len(body)
    xref = b"xref\n0 %d\n" % (len(objects) + 1)
    xref += b"0000000000 65535 f \n"
    for off in offsets:
        xref += b"%010d 00000 n \n" % off

    trailer = (
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF"
        % (len(objects) + 1, xref_offset)
    )

    return body + xref + trailer


VALID_PDF_BYTES = build_minimal_pdf()


def make_pdf_upload(name="resume.pdf", content=None, content_type="application/pdf"):
    return SimpleUploadedFile(name, content or VALID_PDF_BYTES, content_type=content_type)


class ResumeUploadTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="cand@example.com", name="Candidate", password="StrongPass123")
        res = self.client.post(reverse("login"), {"email": "cand@example.com", "password": "StrongPass123"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_upload_requires_auth(self):
        self.client.credentials()
        res = self.client.post(reverse("resume_upload"), {"file": make_pdf_upload()}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_upload_success_extracts_text(self):
        res = self.client.post(reverse("resume_upload"), {"file": make_pdf_upload()}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["status"], "processed")
        self.assertIn("Hello Resume", res.data["extracted_text"])
        self.assertEqual(res.data["page_count"], 1)
        self.assertEqual(res.data["original_filename"], "resume.pdf")

    def test_upload_rejects_non_pdf_extension(self):
        bad_file = SimpleUploadedFile("resume.txt", b"just text", content_type="text/plain")
        res = self.client.post(reverse("resume_upload"), {"file": bad_file}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_rejects_spoofed_content_type(self):
        # .pdf extension + correct content_type header, but the bytes aren't a PDF at all.
        fake = SimpleUploadedFile("resume.pdf", b"not really a pdf", content_type="application/pdf")
        res = self.client.post(reverse("resume_upload"), {"file": fake}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_rejects_oversized_file(self):
        from django.conf import settings

        oversized = SimpleUploadedFile(
            "resume.pdf",
            VALID_PDF_BYTES + b"0" * (settings.MAX_RESUME_SIZE_MB * 1024 * 1024 + 1),
            content_type="application/pdf",
        )
        res = self.client.post(reverse("resume_upload"), {"file": oversized}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_second_upload_rejected(self):
        first = self.client.post(reverse("resume_upload"), {"file": make_pdf_upload()}, format="multipart")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post(reverse("resume_upload"), {"file": make_pdf_upload()}, format="multipart")
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)


class ResumeStatusAndIsolationTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email="a@example.com", name="User A", password="StrongPass123")
        self.user_b = User.objects.create_user(email="b@example.com", name="User B", password="StrongPass123")

    def _auth_as(self, email, password):
        res = self.client.post(reverse("login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_status_requires_auth(self):
        res = self.client.get(reverse("resume_status"))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_status_no_resume_yet(self):
        self._auth_as("a@example.com", "StrongPass123")
        res = self.client.get(reverse("resume_status"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, {"has_resume": False})

    def test_status_reflects_own_resume_only(self):
        self._auth_as("a@example.com", "StrongPass123")
        self.client.post(reverse("resume_upload"), {"file": make_pdf_upload()}, format="multipart")

        # User A sees their own processed resume.
        res_a = self.client.get(reverse("resume_status"))
        self.assertTrue(res_a.data["has_resume"])
        self.assertEqual(res_a.data["resume"]["status"], "processed")

        # User B, who never uploaded anything, sees nothing — not user A's file.
        self._auth_as("b@example.com", "StrongPass123")
        res_b = self.client.get(reverse("resume_status"))
        self.assertEqual(res_b.data, {"has_resume": False})
