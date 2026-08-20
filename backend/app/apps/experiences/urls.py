from django.urls import path

from .views import (
    DraftDetailView,
    DraftListCreateView,
    DraftPublishView,
    MediaDeleteView,
    MediaUploadCompleteView,
    MediaUploadIntentView,
    ThemeListView,
)


urlpatterns = [
    path("themes/", ThemeListView.as_view(), name="theme-list"),
    path("drafts/", DraftListCreateView.as_view(), name="draft-list-create"),
    path("drafts/<uuid:draft_id>/", DraftDetailView.as_view(), name="draft-detail"),
    path("drafts/<uuid:draft_id>/publish/", DraftPublishView.as_view(), name="draft-publish"),
    path("drafts/<uuid:draft_id>/media/upload-intents/", MediaUploadIntentView.as_view(), name="media-upload-intent"),
    path("drafts/<uuid:draft_id>/media/<uuid:media_id>/complete/", MediaUploadCompleteView.as_view(), name="media-upload-complete"),
    path("drafts/<uuid:draft_id>/media/<uuid:media_id>/", MediaDeleteView.as_view(), name="media-delete"),
]
