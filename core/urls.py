from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django_ratelimit.decorators import ratelimit

# The Django admin ships its own login view, and none of the rate limiting in
# `users` reaches it — those decorators are on our views only. That left the
# superuser credential, the most valuable one in the app, taking unlimited
# guesses on the most scanned path on the internet, while an ordinary user was
# capped at five. Same limits as users.views.login_view, for the same reasons.
#
# Patched onto the site instance before `admin.site.urls` is read below:
# AdminSite.get_urls() binds `self.login` when the URLconf is built, so a later
# assignment would resolve to the original view.
admin.site.login = ratelimit(key="ip", rate="10/5m", method="POST", block=True)(
    ratelimit(key="post:username", rate="5/5m", method="POST", block=True)(
        admin.site.login
    )
)

# Default keeps the familiar path; production sets it to something unguessable
# so credential-stuffing bots never reach the form at all. Obscurity is not the
# control here — the rate limit above is — but it removes the constant
# background noise of automated attempts.
ADMIN_PATH = settings.ADMIN_PATH

urlpatterns = [
    path(ADMIN_PATH, admin.site.urls),
    path("", include("main.urls")),
    path("users/", include("users.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("log/", include("logs.urls")),
]

# dev only
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
