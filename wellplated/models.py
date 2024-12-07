from django.contrib.auth.models import User
from django.db.models import (
    PROTECT,
    CharField,
    CheckConstraint,
    DateTimeField,
    F,
    ForeignKey,
    Manager,
    ManyToManyField,
    Model,
    PositiveIntegerField,
    PositiveSmallIntegerField,
    Q,
    QuerySet,
    TextField,
    UniqueConstraint,
)
from django.db.models.functions import Cast, Length
from django.db.models.lookups import LessThanOrEqual
from modelcluster.models import ClusterableModel
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.snippets.models import register_snippet

CharField.register_lookup(Length)


@register_snippet
class Format(Model):
    """
    Combination of physical dimensions and planned usage
    """

    # Rows must range between 'A' and this (inclusive)
    bottom_row = CharField(default='H', editable=False, max_length=1)
    # Columns must range between 1 and this (inclusive)
    right_column = PositiveSmallIntegerField(default=12, editable=False)

    # Prefix string for Container serial codes
    prefix = CharField(editable=False, max_length=128, primary_key=True)
    # Last assigned number suffix for Container serial codes
    current_number = PositiveIntegerField(default=0)
    # Maximum possible number suffix for Container serial codes
    max_number = PositiveIntegerField(default=99999999, editable=False)

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
                'minimum-bottom-row-A': Q(bottom_row__gte='A'),
                'maximum-bottom-row-P': Q(bottom_row__lte='P'),
                'minimum-right-column-1': Q(right_column__gte=1),
                'maximum-right-column-24': Q(right_column__lte=24),
                # Dot/period separates Container serial code from well label
                'dot-free-prefix': ~Q(prefix__contains='.'),
                # Container serial codes must never overflow barcodes or human-readable labels
                # TODO: configurable limit
                'twelve-or-fewer-character-code': LessThanOrEqual(Length('prefix') + Length(Cast('max_number', CharField())), 12),
            }.items()
        )

    def __str__(self) -> str:
        return f'{self.prefix}{self.max_number} {self.purpose}'


class ContainerManager(Manager):
    def create(self, *args, format: Format, **kwargs) -> 'Container':
        """
        Create a new container and (unless the code parameter is overridden) assign it the
        next available serial code.
        """
        print('create')
        if 'code' not in kwargs:
            format = Format.objects.select_for_update().get(pk=format.pk)
            format.current_number += 1
            format.save(update_fields=['current_number'])
            kwargs['code'] = format.prefix + ('{:0%sd}' % len(str(format.max_number))).format(format.current_number)
        if not kwargs['code'].startswith(format.prefix):
            raise ValueError(f'Container code {kwargs["code"]} must start with format prefix {format.prefix}')
        number = int(kwargs['code'][len(format.prefix):])
        if number > format.max_number:
            raise ValueError(f'Container code {kwargs["code"]} exceeds format maximum {format.max_number}')
        container = super().create(*args, format=format, **kwargs)
        return container


@register_snippet
class Container(ClusterableModel):
    """
    A Container is uniquely identified by its serial code and has Wells
    """

    format = ForeignKey(Format, editable=False, on_delete=PROTECT, related_name='containers')
    created_at = DateTimeField(auto_now_add=True)

    # Optimization: variable length fields last
    code = CharField(editable=False, max_length=128, primary_key=True)

    objects = ContainerManager()

    # Do these need read_only?
    panels = [
        FieldPanel('code', read_only=True),
        FieldPanel('created_at', read_only=True),
        FieldPanel('format', read_only=True),
        InlinePanel('wells'),
    ]

    def __getattr__(self, label: str) -> 'Well':
        if label in (
            '_cluster_related_objects',
            '_prefetched_objects_cache',
            'get_source_expressions',
            'resolve_expression',
        ):
            raise AttributeError(f'{label} not set yet')

        # Can be expanded later to 96, 384, 1536 wells
        if label == 'A01':
            return self.wells.get(label='A01')

        raise Exception(f'Unknown label {label}')

    def __str__(self) -> str:
        return self.code


class WellManager(Manager):
    def get_queryset(self) -> QuerySet['Well']:
        return super().get_queryset().prefetch_related('container')

    def create(self, *args, container: Container, **kwargs) -> 'Well':
        # split label row, column and check if in range of container format
        well = super().create(*args, format=format, **kwargs)
        return well



class Well(Model):
    """
    One of multiple positions on a plate, or the singular position of a tube.

    Positions are stored and displayed as "Battleship notation" labels with alphabetical row and
    numerical column, the latter zero-padded for easy sorting and consistent length.

    1-well tube/trough coordinate is A1
    6-well plate coordinates range from A1 to B3
    24-well plate coordinates range from A1 to D6

    https://mscreen.lsi.umich.edu/mscreenwiki/index.php?title=COORDINATE
    96-well plate coordinates range from A01 to H12
    384-well plate coordinates range from A01 to P24
    1536-well plate coordinates range from A01 to AF48
    """

    # TODO crush container and label together for natural primary keying
    container = ParentalKey(Container, editable=False, on_delete=PROTECT, related_name='wells')
    label = CharField(editable=False, max_length=4)
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
            # CheckConstraint('label_length', check=Q(label__length=F('container__container_type__bottom_row__'))
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
