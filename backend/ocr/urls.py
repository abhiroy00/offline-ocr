from django.urls import path

from . import views

urlpatterns = [
    path("auth/login/", views.login_view, name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("ocr/upload/", views.UploadView.as_view(), name="ocr-upload"),
    path("ocr/jobs/<int:job_id>/start/", views.StartJobView.as_view(), name="ocr-job-start"),
    path("ocr/jobs/<int:job_id>/pause/", views.JobActionView.as_view(action="pause"), name="ocr-job-pause"),
    path("ocr/jobs/<int:job_id>/stop/", views.JobActionView.as_view(action="stop"), name="ocr-job-stop"),
    path("ocr/jobs/<int:job_id>/", views.JobDetailView.as_view(), name="ocr-job-detail"),
    path("ocr/jobs/<int:job_id>/results/", views.JobResultsView.as_view(), name="ocr-job-results"),
    path("ocr/jobs/<int:job_id>/export/", views.JobExportView.as_view(), name="ocr-job-export"),
    path("ocr/jobs/<int:job_id>/failed-export/", views.JobFailedExportView.as_view(), name="ocr-job-failed-export"),
    path("ocr/jobs/<int:job_id>/clear/", views.JobClearView.as_view(), name="ocr-job-clear"),
    path("ocr/certificates/bulk-delete/", views.CertificateBulkDeleteView.as_view(), name="ocr-cert-bulk-delete"),
    path(
        "ocr/certificate-fields/<int:field_id>/review/",
        views.CertificateFieldReviewView.as_view(),
        name="ocr-field-review",
    ),
    path("ocr/system-status/", views.SystemStatusView.as_view(), name="ocr-system-status"),
]
