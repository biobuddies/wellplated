"""Database tables (Models) and columns (Fields) for liquid in plates and tubes"""

from re import compile
from typing import ClassVar, Self

from django.contrib.auth.models import User
from django.db.models import (
    PROTECT,
    CharField,
    DateTimeField,
    ForeignKey,
    GeneratedField,
    Manager,
    ManyToManyField,
    Model,
    PositiveSmallIntegerField,
    TextField,
    UniqueConstraint,
    Value,
)
from django.db.models.functions import Cast, Coalesce, Concat, Left, Length, LPad, Substr
from django.templatetags.static import static
from django.utils.html import format_html
from django_stubs_ext.db.models import TypedModelMeta
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail import hooks
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from wellplated.fields import CheckedCharField, CheckedPositiveSmallIntegerField

POSITIONS_384 = compile(r'^(?P<row>[A-P])(?P<column>[012]?[0-9])$')
PREFIX_ID_LENGTH = 12  # TODO make this configurable
CONTAINER_CODE_LENGTH = 1 + 2 + PREFIX_ID_LENGTH  # bottom row, right column

CharField.register_lookup(Length)


@hooks.register('insert_global_admin_css')
def global_admin_css() -> str:
    """Customize Wagtail admin Cascade Style Sheets (CSS)"""
    return format_html(
        '<link rel="stylesheet" href="{}">', static('wellplated/static/wellplated.css')
    )


# type issue night be caused by ClusterableModel missing type annotations
# https://github.com/typeddjango/django-stubs/issues/1023
class Format(Model):  # type: ignore[django-manager-missing]
    """
    Rows, columns, and planned usage

    Bottom (maximum) row character and right (maximum) column number are currently set for
    16*24 == 384-well plates. Up to 26 rows ('Z') and 32767 columns would be easy to support if
    anyone has a need. documentation/design.md discusses possibilities and questions for
    32*48 == 1536-well plate support.
    """

    # Rows must range between 'A' and this (inclusive); default to H for 8*12 96-well plate
    bottom_row = CheckedCharField(
        default='H', max_length=1, max_value='P', min_length=1, min_value='A'
    )
    # Columns must range between 1 and this (inclusive); default to 12 for 8*12 96-well plate
    right_column = CheckedPositiveSmallIntegerField(default=12, min_value=1, max_value=24)

    prefix = CheckedCharField(
        max_length=PREFIX_ID_LENGTH - 1,
        min_length=0,
        omits='.',  # Dot/period separates Container serial code from Well position
        unique=True,
    )

    # GeneratedFields cannot be primary keys, but ForeignKey can reference any unique field.
    # So pack the maximum row, maximum column, and prefix together so Container can use them
    # in its own GeneratedFields, and Well can ForeignKey and constrain on them.
    bottom_right_prefix = GeneratedField(
        db_persist=True,
        # editable=False,
        expression=Concat(
            'bottom_row', LPad(Cast('right_column', CharField()), 2, Value('0')), 'prefix'
        ),
        output_field=CharField(
            max_length=bottom_row.max_length + right_column.max_length + prefix.max_length  # type: ignore[operator]
        ),
        unique=True,
    )

    attribute_example = 'Attribute example'

    created_at = DateTimeField(auto_now_add=True)

    # Optimization: variable length fields last
    purpose = TextField(blank=False, unique=True)  # How contents should be interpreted
    # TODO forms.fields.TextField(min_length=1)

    def __str__(self) -> str:
        return self.prefix


class FormatViewSet(SnippetViewSet):
    """Customize /manage/snippets/wellplated/format interface"""

    model = Format
    list_display = ('bottom_right_prefix', 'purpose', 'bottom_row', 'right_column', 'prefix')


register_snippet(Format, FormatViewSet)


@register_snippet
class Container(ClusterableModel):
    """A Container is uniquely identified by its serial code and has Positions"""

    external_id = CheckedPositiveSmallIntegerField(
        blank=True, default=None, max_value=int('9' * (PREFIX_ID_LENGTH - 1)), null=True
    )
    code = GeneratedField(
        db_persist=True,
        expression=Concat(
            'format',
            LPad(
                Cast(Coalesce('external_id', 'id'), CharField()),
                CONTAINER_CODE_LENGTH - Length('format'),
                Value('0'),
            ),
        ),
        editable=False,
        output_field=CharField(max_length=CONTAINER_CODE_LENGTH),
        unique=True,
    )

    created_at: DateTimeField = DateTimeField(auto_now_add=True)
    format: ForeignKey[Format] = ForeignKey(
        Format,
        editable=False,
        null=False,
        on_delete=PROTECT,
        related_name='containers',
        to_field='bottom_right_prefix',
    )

    panels = (
        FieldPanel('created_at', read_only=True),
        FieldPanel('format', read_only=True),
        InlinePanel('positions'),
    )

    positions: Manager['Position']

    def __getattr__(self, position: str) -> 'Position | None':
        # These attributes seem to be added after __init__ but raising an AttributeError for them
        # breaks the the Django admin and Wagtail manage interfaces.
        if position in ('code', 'format'):
            return None

        position_match = POSITIONS_384.match(position)
        if not position_match or position_match.groupdict().keys() != {'row', 'column'}:
            # ClusterableModel and maybe other code catches AttributeError but not DoesNotExist.
            # Observed with the following attributes:
            # _cluster_related_objects, _prefetched_objects_cache, get_source_expressions,
            # resolve_expression
            raise AttributeError(f'Failed to parse {position}')  # noqa: TRY003
        column = int(position_match.groupdict()['column'], 10)

        return self.positions.get(row=position_match.groupdict()['row'], column=column)

    def __str__(self) -> str:
        return self.code[1 + 2 :]  # row, column


class PositionManager(Manager['Position']):
    """Customize Position.objects."""

    @property
    def start(self) -> 'Position':
        """Return the special infinite source position."""
        return self.get(container='A01start0000000', row='A', column=1)

    @property
    def end(self) -> 'Position':
        """Return the special infinite sink position."""
        return self.get(container='A01end000000999', row='A', column=1)


class Position(Model):
    """
    One of multiple positions on a plate, or the singular position of a vial, tube, or trough.

    Positions are stored and displayed in "Battleship notation" with alphabetical row and
    numerical column. For easy sorting and consistent length, the former is one characting
    beginning with `A`, and the latter is zero padded two digits beginning with `01`.

    1-well   vial/tube/trough position  A01
    6-well   plate positions range from A01 to B03
    24-well  plate positions range from A01 to D06
    96-well  plate positions range from A01 to H12
    384-well plate positions range from A01 to P24
    """

    container = ParentalKey(
        Container,
        db_column='container_code',
        editable=False,
        on_delete=PROTECT,
        related_name='positions',
        to_field='code',
    )
    row = CheckedCharField(
        max_length=1, max_value=Left('container', 1), min_length=1, min_value='A'
    )
    column = CheckedPositiveSmallIntegerField(
        max_value=Cast(Substr('container', 2, 2), PositiveSmallIntegerField()), min_value=1
    )

    sinks: ManyToManyField[Self, Self] = ManyToManyField(
        'self',
        through='Transfer',
        through_fields=('source', 'sink'),
        symmetrical=False,
        related_name='sources',
    )

    objects = PositionManager()

    class Meta(TypedModelMeta):
        constraints: ClassVar = [
            UniqueConstraint(
                fields=['container', 'row', 'column'], name='unique_container_row_column'
            )
        ]

    def __str__(self) -> str:
        return f'{self.container_id[1 + 2:]}.{self.row}{self.column:02}'  # row, column


@register_snippet
class Plan(Model):
    """
    A set of transfers describing what should happen.

    See results for measurements or assumptions of what actually happened.

    Plans with no results are the todo list.

    Plans with one result are the common finished case.

    Plans may have multiple results when reworking with the same containers.

    Create a new plan to rework using different containers.
    """

    created_at = DateTimeField(auto_now_add=True)
    created_by = ForeignKey(User, on_delete=PROTECT, related_name='plans_created')

    def __str__(self) -> str:
        return f'plan {self.pk}'


@register_snippet
class Transfer(Model):
    """
    Movement from one position to another.

    The same (source, sink) may appear multiple times in the same plan to enable transferring
    a volume exceeding pipette or tip size.

    The same (source, sink) may appear in multiple plans to enable multiple rounds of
    liquid transfer and drying.
    """

    plan = ForeignKey(Plan, on_delete=PROTECT, related_name='transfers')
    source = ForeignKey(Position, on_delete=PROTECT, related_name='+')
    sink = ForeignKey(Position, on_delete=PROTECT, related_name='+')

    def __str__(self) -> str:
        return f'{self.source} -> {self.sink}'
