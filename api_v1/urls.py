from django.conf.urls import patterns, url
from api_v1 import views

urlpatterns = patterns(
    '',
    # Examples:
    # url(r'^$', 'user_reg.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^registration/(?P<uuid>\w+)/approve',
        views.RegistrationApprove.as_view()),
    url(r'^registration/(?P<uuid>\w+)', views.RegistrationDetail.as_view()),
    url(r'^registration', views.RegistrationList.as_view()),
    url(r'^project', views.CreateProject.as_view()),
    url(r'^user', views.AttachUser.as_view()),
    url(r'^reset', views.ResetPassword.as_view()),
    url(r'^token/(?P<id>\w+)', views.TokenDetail.as_view()),
    url(r'^token', views.TokenList.as_view()),
)
