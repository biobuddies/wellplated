from re import compile
from django.db.models import (
    CharField,
    DateTimeField,
    ForeignKey,
    JSONField,
    Manager,
    Model,
    PROTECT,
    PositiveIntegerField,
    PositiveSmallIntegerField,
    TextChoices,
    IntegerChoices,
    TextField,
    UniqueConstraint,
)
from django.contrib.auth.models import User
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.forms.models import WagtailAdminModelForm
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.snippets.models import register_snippet

label_1536 = compile(r'^(?P<high_row>A?)(?P<low_row>[A-Z])(?P<column>[0-9]+)$')

class ContainerTypeManager(Manager):
    def get_untracked(self) -> 'ContainerType':
        return self.get(purpose='untracked')


@register_snippet
class ContainerType(Model):
    """
    Combination of physical dimensions and usage
    """
    last_number = PositiveIntegerField(default=0)
    barcode_format = CharField(max_length=128, unique=True)
    purpose = TextField(unique=True)  # How the contents of wells should be interpreted

    objects = ContainerTypeManager()

    def __str__(self) -> str:
        return f'{self.purpose}'


class ContainerManager(Manager):
    def get_untracked(self) -> 'Container':
        return self.get(barcode='untracked')


@register_snippet
class Container(ClusterableModel):
    barcode = CharField(max_length=128, primary_key=True)
    container_type = ForeignKey(ContainerType, on_delete=PROTECT)
    created_at = DateTimeField(auto_now_add=True)

    objects = ContainerManager()

    panels = [
        FieldPanel('barcode'),
        FieldPanel('created_at', read_only=True),
        FieldPanel('container_type'),
        InlinePanel('wells'),
    ]

    def __truediv__(self, label: str) -> 'Well':
        try:
            label_parts = label_1536.match(label).groupdict()
        except AttributeError:
            raise ValueError(f'Invalid label {label}')
        row = (26 if label_parts['high_row'] else 0) + ord(label_parts['low_row']) - ord('A')
        column = int(label_parts['column'], 10) - 1
        # TODO prevent out-of-bounds
        return self.wells.get(row=row, column=column)


    def __str__(self) -> str:
        return self.barcode


class Well(Model):
    """
    One of multiple positions on a plate, or the singular position of a tube.

    Positions are stored as zero-indexed row and column but displayed in
    "Battleship notation".

    https://mscreen.lsi.umich.edu/mscreenwiki/index.php?title=COORDINATE
    96-well plate coordinates range from A01 to H12
    384-well plates coordinates range from A01 to P24
    1536-well plates coordinates range from A01 to AF48
    """

    container = ParentalKey(Container, on_delete=PROTECT, related_name='wells')
    row = PositiveIntegerField()
    column = PositiveSmallIntegerField()

    class Meta:
        constraints = [
            UniqueConstraint(fields=['container', 'row', 'column'], name='unique_well'),
        ]

    @property
    def label(self) -> str:
        row_character = chr(ord('A') + self.row)
        return f'{row_character}{self.column+1:02}'

    def __str__(self) -> str:
        return f'{self.container}/{self.label}'


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
    assigned_to = ForeignKey(User, on_delete=PROTECT, null=True, blank=True, related_name='plans_assigned')

    def __str__(self) -> str:
        return f'plan {self.pk} {self.assigned_to.username if self.assigned_to else "unassigned"}'

@register_snippet
class Transfer(Model):
    """
    Transfer from one well to another.

    The same (to, fro) may appear multiple times in the same plan to enable transferring
    a volume exceeding the pipette or tip size.
    
    The same (to, fro) may appear in multiple plans to enable multiple rounds of
    liquid transfer and drying.
    """
    fro = ForeignKey(Well, on_delete=PROTECT, related_name='+')
    to = ForeignKey(Well, on_delete=PROTECT, related_name='+')
    plan = ForeignKey(Plan, on_delete=PROTECT, related_name='transfers')

    def __str__(self) -> str:
        return f'{self.fro} -> {self.to}'