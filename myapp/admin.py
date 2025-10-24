from django.contrib import admin
from .models import Trainee, Trainer, Course, Certificate

# Customize the admin site
admin.site.site_header = 'VTS Training Management'
admin.site.site_title = 'VTS Admin Portal'
admin.site.index_title = 'Course Management System'

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'mode', 'is_active', 'trainer')
    list_filter = ('category', 'mode', 'is_active')
    search_fields = ('name', 'code', 'description')
    list_editable = ('is_active',)
    ordering = ('name',)

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description')
        }),
        ('Course Details', {
            'fields': ('duration', 'category', 'mode', 'is_active')
        }),
        ('Media & Resources', {
            'fields': ('cover_image', 'syllabus', 'learning_outcomes')
        }),
        ('Trainer Assignment', {
            'fields': ('trainer',),
            'classes': ('collapse',)
        }),
    )

admin.site.register(Trainee)
admin.site.register(Trainer)
admin.site.register(Certificate)
