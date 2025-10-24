from django.contrib import admin
from django.urls import path
from django.conf.urls.static import static
from django.conf import settings


from intune.views.index import IndexView
from intune.views.accounts import LoginView, LogoutView
from intune.views.team import DashboardView, UploadView, ChatView, ChatConversationView, CreateTeamView

# fmt: off
urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", LoginView.as_view(), name="login"),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),
    path("<uuid:team_id>/upload/", UploadView.as_view(), name="upload"),
    path("<uuid:team_id>/chat/", ChatView.as_view(), name="chat"),
    path("<uuid:team_id>/chat/<uuid:chat_id>/", ChatConversationView.as_view(),name="chat-conversation"),
    path("<uuid:team_id>/", DashboardView.as_view(), name="dashboard"),
    path("", IndexView.as_view(), name="index"),
    path('create/', CreateTeamView.as_view(), name='create_team'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
