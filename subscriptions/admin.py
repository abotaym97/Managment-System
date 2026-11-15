import hashlib
import secrets
from django.contrib import admin
from .models import Hotel, Installation, License

admin.site.site_header = 'إدارة اشتراكات OMDA'
admin.site.register(Hotel)
@admin.register(Installation)
class InstallationAdmin(admin.ModelAdmin):
    actions = ('rotate_sync_token',)
    readonly_fields = ('last_sync_at',)

    @admin.action(permissions=['change'], description='إصدار أو استبدال رمز المزامنة')
    def rotate_sync_token(self, request, queryset):
        if not request.user.is_superuser or queryset.count() != 1:
            self.message_user(request, 'يلزم حساب مدير النظام واختيار تثبيت واحد.')
            return
        token = secrets.token_urlsafe(32)
        queryset.update(sync_token_hash=hashlib.sha256(token.encode()).hexdigest())
        self.message_user(request, f'انسخ الرمز الآن: {token}')

@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ('serial', 'installation', 'plan', 'ends_on', 'activated')
    list_filter = ('activated', 'plan')
    search_fields = ('serial', 'installation__hotel__name')


