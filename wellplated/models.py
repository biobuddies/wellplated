"""Database tables (Models) and columns (Fields) for liquid in plates and tubes"""

from re import compile
from typing import Self

from django.contrib.auth.models import User
from django.db.models import (
    PROTECT,
    CharField,
    CheckConstraint,
    DateTimeField,
    F,
    ForeignKey,
    GeneratedField,
    Manager,
    ManyToManyField,
    Model,
    PositiveSmallIntegerField,
    Q,
    QuerySet,
    TextField,
    UniqueConstraint,
    Value,
)
from django.db.models.functions import Cast, Concat, Left, Length, LPad, Replace, Right, Substr
from django.db.models.lookups import GreaterThanOrEqual, LessThanOrEqual
from django_stubs_ext.db.models import TypedModelMeta
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.snippets.models import register_snippet

LABEL_384 = compile(r'^(?P<row>[A-P])(?P<column>[012]?[0-9])$')
MAX_CODE_LENGTH = 12  # TODO make this configurable

CharField.register_lookup(Length)


format_checks = {
    'format-bottom-row-exact-length': Q(bottom_row__length=1),
    'format-bottom-row-minimum': Q(bottom_row__gte='A'),
    'format-bottom-row-maximum': Q(bottom_row__lte='P'),
    'format-right-column-minimum': Q(right_column__gte=1),
    'format-right-column-maximum': Q(right_column__lte=24),
    # Dot/period separates Container serial code from Well label
    'format-prefix-no-dots': ~Q(prefix__contains='.'),
    'format-prefix-maximum-length': Q(prefix__length__lte=11),
}


@register_snippet
class Format(Model):
    """Rows, columns, and planned usage"""

    # Rows must range between 'A' and this (inclusive)
    bottom_row = CharField(default='H', editable=False, max_length=1)
    # Columns must range between 1 and this (inclusive)
    right_column = PositiveSmallIntegerField(default=12, editable=False, max_length=2)

    prefix = CharField(editable=False, max_length=MAX_CODE_LENGTH - 1)

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
            max_length=bottom_row.max_length + right_column.max_length + prefix.max_length
        ),  # type: ignore[operator]
        unique=True,
    )

    created_at = DateTimeField(auto_now_add=True)

    # Optimization: variable length fields last
    purpose = TextField(blank=False, unique=True)  # How the contents of wells should be interpreted

    containers: Manager['Container']

    class Meta(TypedModelMeta):
        """
        Maximum row character and column number are currently set for 16*24 == 384-well plates.

        Up to 26 rows ('Z') and 32767 columns would be easy to support if anyone has a need.
        documentation/design.md discusses possibilities for 32*48 == 1536-well plate support.
        """

        constraints = [  # noqa: RUF012
            CheckConstraint(condition=condition, name=name)
            for name, condition in format_checks.items()
        ]

    def __str__(self) -> str:
        return f'{self.bottom_right_prefix}'


@register_snippet
class Container(ClusterableModel):
    """A Container is uniquely identified by its serial code and has Wells"""

    code = GeneratedField(
        db_persist=True,
        expression=Concat(
            'format', LPad(Cast('id', CharField()), MAX_CODE_LENGTH - Length('format'), Value('0'))
        ),
        editable=False,
        output_field=CharField(max_length=1 + 2 + MAX_CODE_LENGTH),  # bottom row, right column
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
        FieldPanel('code', read_only=True),
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
        return self.get(container_code_label='A01start0000000.A01')

    @property
    def end(self) -> 'Well':
        """Return the special infinite sink well."""
        return self.get(container_code_label='A01end000000999.A01')


well_checks = {
    'well-bottom-row-minimum': GreaterThanOrEqual(Left('label', 1), 'A'),
    'well-bottom-row-maximum': LessThanOrEqual(Left('label', 1), Left('container', 1)),
    'well-right-column-minimum': GreaterThanOrEqual(
        Cast(Right('label', 2), PositiveSmallIntegerField()),
        1
    ),
    'well-maximum-right-column': LessThanOrEqual(
        Right('label', 2),
        Cast(Substr('container', 2, 4), PositiveSmallIntegerField())
    ),
    'well-contains-one-dot': Q(
        container_code_label__length=(
            Length(Replace('container_code_label', Value('.'), Value(''))) + 1
        )
    ),
}

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
        Container, db_column='container_code', editable=False, on_delete=PROTECT, related_name='wells', to_field='code'
    )
    label = CharField(editable=False, max_length=3)
    container_code_label = GeneratedField(
        db_persist=True,
        editable=False,
        expression=Concat('container', Value('.'), 'label'),
        # format bottom row, format right column, code, dot, label row, label column
        output_field=CharField(max_length=1 + 2 + MAX_CODE_LENGTH + 1 + 1 + 2),
        unique=True,
    )

    sources: ManyToManyField[Self, Self] = ManyToManyField(
        'self',
        through='Transfer',
        through_fields=('source', 'sink'),
        symmetrical=False,
        related_name='sinks',
    )

    objects = WellManager()

    class Meta(TypedModelMeta):
        constraints = [  # noqa: RUF012
            CheckConstraint(condition=condition, name=name)
            for name, condition in well_checks.items()
        ]

    def __str__(self) -> str:
        return f'{self.container_code_label}'


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
