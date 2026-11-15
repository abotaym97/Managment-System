from django.contrib import admin
from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.admin.forms import AdminAuthenticationForm
from subscriptions import views, sync
from subscriptions.issuer import issue_license

urlpatterns = [
    path('manage/<str:kind>/new/', views.editor, name='record-add'),
    path('manage/<str:kind>/<int:pk>/', views.editor, name='record-edit'),
    path('', views.dashboard, name='dashboard'),
    path('hotels/', views.hotel_directory, name='hotels'),
    path('installations/<int:pk>/token/', views.installation_token, name='installation-token'),
    path('installations/', views.installation_register, name='installations'),
    path('licenses/<int:pk>/', views.license_detail, name='license-detail'),
    path('system/', views.system_administration, name='system'),
    path('licenses/issue/', issue_license, name='issue-license'),
    path('licenses/', views.license_register, name='licenses'),
    path('login/', LoginView.as_view(template_name='admin/login.html', authentication_form=AdminAuthenticationForm,
                                     redirect_authenticated_user=True, next_page='/'), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('hotels/<int:pk>/', views.detail, name='hotel-detail'),
    path('api/installations/<uuid:identifier>/report/', sync.report),
    path('admin/', admin.site.urls),
]


