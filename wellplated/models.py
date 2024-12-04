from django.db.models import (
    Q,
    QuerySet,
    CharField,
    CheckConstraint,
    DateTimeField,
    F,
    ForeignKey,
    GeneratedField,
    JSONField,
    Manager,
    ManyToManyField,
    Model,
    PROTECT,
    PositiveIntegerField,
    PositiveSmallIntegerField,
    TextChoices,
    IntegerChoices,
    TextField,
    UniqueConstraint,
    Value,
)
from django.db.models.functions import Cast, Chr, Concat, LPad, Length, Ord
from django.contrib.auth.models import User
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.forms.models import WagtailAdminModelForm
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.snippets.models import register_snippet


CharField.register_lookup(Length)


@register_snippet
class Format(Model):
    """
    Combination of physical dimensions and planned usage
    """

    prefix = CharField(editable=False, max_length=128, primary_key=True)  # Prefix string for Container serial codes
    pad_to = PositiveIntegerField(default=8, editable=False)  # Suffix length for Container serial codes
    last = PositiveIntegerField(default=0)  # Last assigned numerical suffix for Container serial codes

    # Rows must range between 'A' and this (inclusive)
    bottom_row = CharField(default='H', editable=False, max_length=2)
    # Columns must range between 1 and this (inclusive)
    right_column = PositiveSmallIntegerField(default=12, editable=False)
    created_at = DateTimeField(auto_now_add=True)

    # Optimization: variable length fields last
    purpose = TextField(unique=True)  # How the contents of wells should be interpreted

    class Meta:
        constraints = (
            CheckConstraint(check=~Q(prefix__contains='.'), name='no-dot-in-prefix'),
        )

    def encode(self, number: int) -> str:
        return self.prefix + ('{:0%d}' % self.pad_to).format(self.last)

    def __str__(self) -> str:
        return self.encode(self.last) + ' ' + self.purpose


class ContainerManager(Manager):
    def create(self, *args, format: Format, **kwargs) -> 'Container':
        """
        Create a new container and (unless the code parameter is overridden) assign it the
        next available serial code.
        """
        # TODO also address ContainerType.containers.add() and .extend()
        if 'code' not in kwargs:
            format = Format.objects.select_for_update().get(pk=format.pk)
            new_last_number = format.last + 1
            format.last = new_last_number
            format.save(update_fields=['last'])
            kwargs['code'] = format.encode(new_last_number)
        container = super().create(*args, format=format, **kwargs)
        return container


@register_snippet
class Container(Model):  # TODO get ClusterableModel working
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

    class Meta:
        constraints = (
            CheckConstraint(check=~Q(prefix__contains='.'), name='no-dot-in-prefix'),
        )

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


class Well(Model):
    """
    One of multiple positions on a plate, or the singular position of a tube.

    Positions are stored and displayed as "Battleship notation" labels with alphabetical row and
    numerical column, the latter zero-padded for easy sorting and consistent length.

    https://mscreen.lsi.umich.edu/mscreenwiki/index.php?title=COORDINATE
    96-well plate coordinates range from A01 to H12
    384-well plate coordinates range from A01 to P24
    1536-well plate coordinates range from A01 to AF48
    """

    # TODO crush container and label together
    container = ParentalKey(Container, editable=False, on_delete=PROTECT, related_name='wells')
    label = CharField(editable=False, max_length=4)
    sources = ManyToManyField(
        'self',
        through='Transfer',
        through_fields=('source', 'sink'),
        symmetrical=False,
        related_name='sinks'
    )

    objects = WellManager()

    class Meta:
        constraints = (
            UniqueConstraint(fields=('container', 'label'), name='unique_container_well_label'),
            #CheckConstraint('label_length', check=Q(label__length=F('container__container_type__bottom_row__'))
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
