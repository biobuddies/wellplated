"""Database tables (Models) and columns (Fields) for liquid in plates and tubes"""

from re import compile
from typing import Self

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
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from wellplated.fields import CheckedCharField, CheckedPositiveSmallIntegerField

LABEL_384 = compile(r'^(?P<row>[A-P])(?P<column>[012]?[0-9])$')
PREFIX_ID_LENGTH = 12  # TODO make this configurable
CONTAINER_CODE_LENGTH = 1 + 2 + PREFIX_ID_LENGTH  # bottom row, right column

CharField.register_lookup(Length)


class Format(Model):
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
        omits='.',  # Dot/period separates Container serial code from Well label
        unique=True,
    )

    # GeneratedFields cannot be primary keys, but ForeignKey can reference any unique field.
    # So pack the maximum row, maximum column, and prefix together so Container can use them
    # in its own GeneratedFields, and Well can ForeignKey and constrain on them.
    bottom_right_prefix = GeneratedField(
        db_persist=True,
        editable=False,
        expression=Concat(
            'bottom_row', LPad(Cast('right_column', CharField()), 2, Value('0')), 'prefix'
        ),
        output_field=CharField(
            max_length=bottom_row.max_length + right_column.max_length + prefix.max_length  # type: ignore[operator]
        ),
        unique=True,
    )

    created_at = DateTimeField(auto_now_add=True)

    # Optimization: variable length fields last
    purpose = TextField(blank=False, unique=True)  # How the contents of wells should be interpreted
    # TODO forms.fields.TextField(min_length=1)

    containers: Manager['Container']

    def __str__(self) -> str:
        return f'{self.bottom_right_prefix}'


class FormatViewSet(SnippetViewSet):
    """Customize /manage/snippets/wellplated/format interface"""

    model = Format
    list_display = ('bottom_right_prefix', 'purpose', 'bottom_row', 'right_column', 'prefix')


register_snippet(Format, FormatViewSet)


@register_snippet
class Container(ClusterableModel):
    """A Container is uniquely identified by its serial code and has Wells"""

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
        InlinePanel('wells'),
    )

    wells: Manager['Well']

    def __getattr__(self, label: str) -> 'Well':
        # ClusterableModel or other packages need an AttributeError for the following:
        # _cluster_related_objects
        # _prefetched_objects_cache
        # get_source_expressions
        # resolve_expression

        label_match = LABEL_384.match(label)
        if not label_match or label_match.groupdict().keys() != {'row', 'column'}:
            raise AttributeError(f'Failed to parse {label}')  # noqa: TRY003
        row = label_match.groupdict()['row']
        column = int(label_match.groupdict()['column'], 10)

        error = []
        if row < 'A':
            error.append(f'{label} row {row} less than A')
        elif row > self.format.bottom_row:
            error.append(f'{label} row {row} greater than {self.format.bottom_row}')
        if column < 1:
            error.append(f'{label} column {column} less than 1')
        elif column > self.format.right_column:
            error.append(f'{label} column {column} greater than {self.format.right_column}')
        if error:
            raise AttributeError(', '.join(error))

        return self.wells.get(label=f'{row}{column:02}')

    def __str__(self) -> str:
        return self.code


class WellManager(Manager['Well']):
    """Customize Well.objects."""

    @property
    def start(self) -> 'Well':
        """Return the special infinite source well."""
        return self.get(container='A01start0000000', row='A', column=1)

    @property
    def end(self) -> 'Well':
        """Return the special infinite sink well."""
        return self.get(container='A01end000000999', row='A', column=1)


class Well(Model):
    """
    One of multiple positions on a plate, or the singular position of a tube.

    Positions are stored and displayed as "Battleship notation" labels with alphabetical row and
    numerical column, the latter zero-padded for easy sorting and consistent length.

    1-well   tube/trough  coordinate is   A01
    6-well   plate coordinates range from A01 to B03
    24-well  plate coordinates range from A01 to D06
    96-well  plate coordinates range from A01 to H12
    384-well plate coordinates range from A01 to P24
    """

    container = ParentalKey(
        Container,
        db_column='container_code',
        editable=False,
        on_delete=PROTECT,
        related_name='wells',
        to_field='code',
    )
    row = CheckedCharField(
        max_length=1, max_value=Left('container', 1), min_length=1, min_value='A'
    )
    column = CheckedPositiveSmallIntegerField(
        max_value=Cast(Substr('container', 2, 4), PositiveSmallIntegerField()), min_value=1
    )

    sinks: ManyToManyField[Self, Self] = ManyToManyField(
        'self',
        through='Transfer',
        through_fields=('source', 'sink'),
        symmetrical=False,
        related_name='sources',
    )

    objects = WellManager()

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['container', 'row', 'column'], name='unique_container_row_column'
            )
        ]

    def __str__(self) -> str:
        return f'{self.container}.{self.row}{self.column:02}'


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
    Transfer from one well to another.

    The same (source, sink) may appear multiple times in the same plan to enable transferring
    a volume exceeding the pipette or tip size.

    The same (source, sink) may appear in multiple plans to enable multiple rounds of
    liquid transfer and drying.
    """

    plan = ForeignKey(Plan, on_delete=PROTECT, related_name='transfers')
    source = ForeignKey(Well, on_delete=PROTECT, related_name='+')
    sink = ForeignKey(Well, on_delete=PROTECT, related_name='+')

    def __str__(self) -> str:
        return f'{self.source} -> {self.sink}'
