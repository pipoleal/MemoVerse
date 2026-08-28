from django.urls import path

from .views import (
    DraftClaimView,
    DraftDetailView,
    DraftListCreateView,
    DraftPublishView,
    GalaxyIntroVideoView,
    MediaDeleteView,
    MediaUploadCompleteView,
    MediaUploadIntentView,
    ReceivedExperiencesListView,
    SaveExperienceToGalaxyView,
    ThemeListView,
)


urlpatterns = [
    path("themes/", ThemeListView.as_view(), name="theme-list"),
    path("galaxy-intro-video/", GalaxyIntroVideoView.as_view(), name="galaxy-intro-video"),
    path("drafts/", DraftListCreateView.as_view(), name="draft-list-create"),
    path("drafts/<uuid:draft_id>/", DraftDetailView.as_view(), name="draft-detail"),
    path("drafts/<uuid:draft_id>/publish/", DraftPublishView.as_view(), name="draft-publish"),
    path("drafts/<uuid:draft_id>/claim/", DraftClaimView.as_view(), name="draft-claim"),
    path("drafts/<uuid:draft_id>/media/upload-intents/", MediaUploadIntentView.as_view(), name="media-upload-intent"),
    path("drafts/<uuid:draft_id>/media/<uuid:media_id>/complete/", MediaUploadCompleteView.as_view(), name="media-upload-complete"),
    path("drafts/<uuid:draft_id>/media/<uuid:media_id>/", MediaDeleteView.as_view(), name="media-delete"),
    # Etapa Minha Galáxia (destinatário): namespace "public/" de propósito,
    # espelhando api/public/experiences/<slug>/ em config/urls.py — deixa
    # explícito, só pela URL, que este endpoint resolve por slug público
    # (nunca por draft_id privado), mesmo que ele exija autenticação para
    # gravar a associação.
    path("public/<slug:slug>/save/", SaveExperienceToGalaxyView.as_view(), name="experience-save-to-galaxy"),
    path("received/", ReceivedExperiencesListView.as_view(), name="received-list"),
]
