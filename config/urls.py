from django.contrib import admin
from django.urls import path
from subscriptions import views, sync

urlpatterns = [
    path('manage/<str:kind>/new/', views.editor, name='record-add'),
    path('manage/<str:kind>/<int:pk>/', views.editor, name='record-edit'),
    path('', views.dashboard),
    path('hotels/<int:pk>/', views.detail, name='hotel-detail'),
    path('api/installations/<uuid:identifier>/report/', sync.report),
    path('admin/', admin.site.urls),
]


