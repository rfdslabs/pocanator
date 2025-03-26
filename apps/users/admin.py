from django.contrib import admin
from .models import UserProfile, APIUsage


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin configuration for UserProfile model"""
    
    list_display = ('get_username', 'has_custom_openai_key', 'has_github_token', 'default_model')
    search_fields = ('user__username', 'api_key')
    readonly_fields = ('api_key',)
    
    def get_username(self, obj):
        """Get the username"""
        return obj.user.username
    get_username.short_description = 'Username'
    get_username.admin_order_field = 'user__username'


@admin.register(APIUsage)
class APIUsageAdmin(admin.ModelAdmin):
    """Admin configuration for APIUsage model"""
    
    list_display = ('get_username', 'timestamp', 'endpoint', 'tokens_used', 'model', 'cost')
    list_filter = ('timestamp', 'endpoint', 'model')
    search_fields = ('user__username', 'endpoint')
    date_hierarchy = 'timestamp'
    
    def get_username(self, obj):
        """Get the username"""
        return obj.user.username
    get_username.short_description = 'Username'
    get_username.admin_order_field = 'user__username'