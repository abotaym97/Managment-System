from django.contrib import admin
from .models import Hotel, Installation, License
from .token_service import rotate_sync_token, TokenConflict

admin.site.site_header = 'إدارة اشتراكات OMDA'
admin.site.register(Hotel)
@admin.register(Installation)
class InstallationAdmin(admin.ModelAdmin):
    actions = ('rotate_sync_token',)
    readonly_fields = ('last_sync_at',)

    @admin.action(permissions=['change'], description='إصدار أو استبدال رمز المزامنة')
    def rotate_sync_token(self, request, queryset):
        items = list(queryset[:2])
        if not request.user.is_superuser or len(items) != 1:
            self.message_user(request, 'يلزم حساب مدير النظام واختيار تثبيت واحد.')
            return
        try:
            token = rotate_sync_token(request.user, items[0])
        except TokenConflict:
            self.message_user(request, 'Token changed. Reload and try again.', level='error')
            return
        from .views import token_result
        return token_result(request, token, items[0])

@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ('serial', 'installation', 'plan', 'ends_on', 'activated')
    list_filter = ('activated', 'plan')
    search_fields = ('serial', 'installation__hotel__name')


