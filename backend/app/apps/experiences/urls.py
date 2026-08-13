from django.urls import path

from .views import DraftDetailView, DraftListCreateView, MediaUploadCompleteView, MediaUploadIntentView


urlpatterns = [
    path("drafts/", DraftListCreateView.as_view(), name="draft-list-create"),
    path("drafts/<uuid:draft_id>/", DraftDetailView.as_view(), name="draft-detail"),
    path("drafts/<uuid:draft_id>/media/upload-intents/", MediaUploadIntentView.as_view(), name="media-upload-intent"),
    path("drafts/<uuid:draft_id>/media/<uuid:media_id>/complete/", MediaUploadCompleteView.as_view(), name="media-upload-complete"),
]
