from django.contrib.admin import ModelAdmin, TabularInline, register
from django.forms import Media

from wellplated.models import Container, Format, Well


@register(Format)
class FormatAdmin(ModelAdmin):
    list_display = (
        'bottom_right_prefix',
        'purpose',
        'bottom_row',
        'right_column',
        'prefix',
        'created_at',
    )
    readonly_fields = ('bottom_right_prefix', 'created_at')

    @property
    def media(self):
        return super().media + Media(css={'all': ['wellplated.css']})


class WellInline(TabularInline):
    model = Well
    extra = 0


@register(Container)
class ContainerAdmin(ModelAdmin):
    inlines = (WellInline,)
    list_display = ('code', 'format', 'created_at')
    readonly_fields = ('code', 'created_at')
