from typing import Self

from django.contrib.admin import ModelAdmin, TabularInline, register
from django.forms import Media
from django.utils.safestring import SafeText

from wellplated.models import Container, Format, Position


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
    readonly_fields = ('diagram', 'bottom_right_prefix', 'created_at')

    def diagram(self: Self, instance: Format) -> SafeText:
        style = 'style="text-align: center; text-transform: none; vertical-align: middle;"'
        html = f'<table><caption {style}>{instance.purpose}</caption><thead>'
        for row in range(ord(instance.bottom_row) - ord('A') + 2):
            html += '<tr>'
            for column in range(instance.right_column + 1):
                if row == 0:
                    if column == 0:
                        html += f'<th {style}>{instance.prefix}</th>'
                    else:
                        html += f'<th scope="col" {style}>{column:02}</th>'
                elif column == 0:
                    html += f'<th scope="row" {style}>{chr(ord("A") + row - 1)}</th>'
                else:
                    html += f'<td {style}>◯</td>'
            html += '</tr>'
        html += '</table>'
        return SafeText(html)

    @property
    def media(self) -> Media:
        return super().media + Media(css={'all': ['wellplated.css']})


class PositionInline(TabularInline):
    model = Position
    extra = 0


@register(Container)
class ContainerAdmin(ModelAdmin):
    inlines = (PositionInline,)
    list_display = ('code', 'format', 'created_at')
    readonly_fields = ('code', 'created_at')
