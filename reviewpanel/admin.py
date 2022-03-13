from django.contrib import admin

from formative.admin import site
from .models import Template, TemplateSection, Reference, Presentation


class TemplateSectionInline(admin.StackedInline):
    model = TemplateSection
    extra = 0


@admin.register(Template, site=site)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'program')
    inlines = [TemplateSectionInline]


@admin.register(Reference, site=site)
class ReferenceAdmin(admin.ModelAdmin):
    list_display = ('id', 'collection', 'name', 'section')
    list_filter = ('presentation',)
    readonly_fields = ('_rank',)


@admin.register(Presentation, site=site)
class PresentationAdmin(admin.ModelAdmin):
    list_display = ('name', 'created', 'template', 'form')
    list_filter = ('form',)
