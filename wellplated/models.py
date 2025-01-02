from re import compile

from django.contrib.auth.models import User
from django.db.models import (
    PROTECT,
    CharField,
    CheckConstraint,
    DateTimeField,
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
from django.db.models.functions import Cast, Concat, Left, Length, LPad, StrIndex, Substr
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.snippets.models import register_snippet

LABEL_384 = compile(r'^(?P<row>[A-P])(?P<column>[012]?[0-9])$')
MAX_CODE_LENGTH = 12  # TODO make this configurable

CharField.register_lookup(Length)


@register_snippet
class Format(Model):
    """
    Rows, columns, and planned usage
    """

    # Rows must range between 'A' and this (inclusive)
    bottom_row = CharField(default='H', editable=False, max_length=1)
    # Columns must range between 1 and this (inclusive)
    right_column = PositiveSmallIntegerField(default=12, editable=False)
    # Zero padding to ease sorting and tidy displays
    pad_column_to = GeneratedField(
        db_persist=True,
        editable=False,
        expression=Length(Cast('right_column', CharField())),
        output_field=PositiveSmallIntegerField(),
    )

    prefix = CharField(editable=False, max_length=MAX_CODE_LENGTH - 1)

    # GeneratedFields cannot be primary keys, but ForeignKey can reference any unique field.
    # So pack the maximum row, maximum column, and prefix together so Container can use them
    # in its own GeneratedFields, and Well can ForeignKey and constrain on them.
    bottom_right_prefix = GeneratedField(
        db_persist=True,
        editable=False,
        expression=Concat('bottom_row', 'right_column', Value('.'), 'prefix'),
        output_field=CharField(max_length=bottom_row.max_length + 3 + prefix.max_length),
        unique=True,
    )

    created_at = DateTimeField(auto_now_add=True)

    # Optimization: variable length fields last
    purpose = TextField(blank=False, unique=True)  # How the contents of wells should be interpreted

    class Meta:
        # Maximum row character and column number are currently set for 16*24 == 384-well plates.
        # Up to 26 rows ('Z') and 32767 columns would be easy to support if anyone has a need.
        # documentation/design.md discusses possibilities for 32*48 == 1536-well plate support.
        constraints = (
            CheckConstraint(condition=condition, name=name)
            for name, condition in {
                'single-character-bottom-row': Q(bottom_row__length=1),
                'minimum-bottom-row-A': Q(bottom_row__gte='A'),
                'maximum-bottom-row-P': Q(bottom_row__lte='P'),
                'minimum-right-column-1': Q(right_column__gte=1),
                'maximum-right-column-24': Q(right_column__lte=24),
                # Dot/period separates Container serial code from Well label
                'dot-free-prefix': ~Q(prefix__contains='.'),
            }.items()
        )

    def __str__(self) -> str:
        return f'{self.bottom_right_prefix}'


@register_snippet
class Container(ClusterableModel):
    """
    A Container is uniquely identified by its serial code and has Wells
    """

    code = GeneratedField(
        db_persist=True,
        # TODO fix zero padding
        expression=Concat(
            Substr('format', StrIndex('format', Value('.')) + Value(1)),
            LPad(
                Cast('id', CharField()),
                Length(Left('format', StrIndex('format', Value('.')))),
                Value('0'),
            ),
        ),
        editable=False,
        output_field=CharField(max_length=MAX_CODE_LENGTH),
        unique=True,
    )

    created_at = DateTimeField(auto_now_add=True)
    format = ForeignKey(
        Format,
        editable=False,
        null=False,
        on_delete=PROTECT,
        related_name='containers',
        to_field='bottom_right_prefix',
    )

    panels = [
        FieldPanel('code', read_only=True),
        FieldPanel('created_at', read_only=True),
        FieldPanel('format', read_only=True),
        InlinePanel('wells'),
    ]

    def __getattr__(self, label: str) -> 'Well':
        # ClusterableModel or other packages need an AttributeError for the following:
        # _cluster_related_objects
        # _prefetched_objects_cache
        # get_source_expressions
        # resolve_expression

        label_match = LABEL_384.match(label)
        if not label_match or label_match.groupdict().keys() != {'row', 'column'}:
            raise AttributeError(f'Failed to parse {label}')
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

        return self.wells.get(label=row + ('{:0%d}' % self.format.pad_column_to).format(column))

    def __str__(self) -> str:
        return self.code


class WellManager(Manager):
    def get_queryset(self) -> QuerySet['Well']:
        return super().get_queryset().prefetch_related('container')

    def create(self, *args, container: Container, **kwargs) -> 'Well':
        # split label row, column and check if in range of container format
        well = super().create(*args, format=format, **kwargs)
        return well

    @property
    def start(self) -> 'Well':
        return self.get(container__format__purpose='start', label='A1')

    @property
    def end(self) -> 'Well':
        return self.get(container__format__purpose='end', label='A1')


class Well(Model):
    """
    One of multiple positions on a plate, or the singular position of a tube.

    Positions are stored and displayed as "Battleship notation" labels with alphabetical row and
    numerical column, the latter zero-padded for easy sorting and consistent length.

    1-well   tube/trough  coordinate is   A1
    6-well   plate coordinates range from A1 to B3
    24-well  plate coordinates range from A1 to D6
    96-well  plate coordinates range from A01 to H12
    384-well plate coordinates range from A01 to P24
    """

    # TODO crush container and label together for natural primary keying?
    container = ParentalKey(Container, editable=False, on_delete=PROTECT, related_name='wells')
    label = CharField(editable=False, max_length=3)
    sources = ManyToManyField(
        'self',
        through='Transfer',
        through_fields=('source', 'sink'),
        symmetrical=False,
        related_name='sinks',
    )

    objects = WellManager()

    class Meta:
        constraints = (
            UniqueConstraint(fields=('container', 'label'), name='unique_container_well_label'),
            # TODO constrain to max row and column from format
        )

    def __str__(self) -> str:
        return f'{self.container}.{self.label}'


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
