"""Test the models"""

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from pytest import mark, raises

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from wellplated.models import User

from wellplated.models import Container, Format, Plan, Transfer, Well


def get_test_user() -> 'User':
    """Get or create a test user."""
    return get_user_model().objects.get_or_create(username='test.user')[0]


@mark.django_db
def test_untracked_data() -> None:
    """Initial data for start and end of tracking must exist as expected."""
    assert Format.objects.filter(purpose__in=('start', 'end')).count() == 2

    assert Container.objects.filter(code__in=('A01start0000000', 'A01end000000999')).count() == 2

    assert (
        Well.objects.filter(
            container_code_label__in=('A01start0000000.A01', 'A01end000000999.A01')
        ).count()
        == 2
    )

    assert Well.objects.start.label == 'A01'
    assert Well.objects.end.label == 'A01'

    assert Well.objects.start.container.format.purpose == 'start'
    assert Well.objects.end.container.format.purpose == 'end'


@mark.django_db
def test_format_purpose_uniqueness() -> None:
    """Formats must have unique purposes."""
    Format.objects.create(prefix='ft1', purpose='final-tube')
    with raises(IntegrityError):
        Format.objects.create(prefix='ft2', purpose='final-tube')


@mark.django_db
def test_format_prefix_uniqueness() -> None:
    """Formats must have unique prefix strings."""
    Format.objects.create(prefix='t', purpose='final-tube')
    with raises(IntegrityError):
        Format.objects.create(prefix='t', purpose='mix-tube')


@mark.django_db
@mark.parametrize(
    ('bottom_row', 'right_column'),
    [('@', 1), ('Q', 1), ('A', -1), ('A', 0), ('A', 25), ('A', 100), ('AA', 1)],
)
def test_format_row_column_constraints(bottom_row: str, right_column: int) -> None:
    """Format rows and columns must stay in range."""
    with raises(IntegrityError):
        Format.objects.create(
            prefix='t', purpose='test', bottom_row=bottom_row, right_column=right_column
        )


@mark.django_db
def test_format_dot_prevention() -> None:
    """Format prefixes must never contain periods `.`."""
    with raises(IntegrityError):
        Format.objects.create(prefix='.', purpose='dot')


@mark.django_db
def test_container_code_uniqueness() -> None:
    """Containers must have unique codes."""
    final_tube = Format.objects.create(prefix='f', purpose='final-tube')
    Container.objects.create(pk=1000, format=final_tube)
    with raises(IntegrityError):
        Container.objects.create(pk=1000, format=final_tube)


@mark.django_db
def test_container_creation() -> None:
    """All ways of creating Container must work."""
    final_tube = Format.objects.create(prefix='f', purpose='final-tube')
    first_new_container_pk = Container.objects.create(format=final_tube).pk
    final_tube.containers.add(Container(format=final_tube), bulk=False)
    Container.objects.bulk_create([Container(format=final_tube)])
    assert Container.objects.filter(format=final_tube).latest('pk').pk - first_new_container_pk == 2


@mark.django_db
def test_container_external_id() -> None:
    """Use external ID for container code when provided without sacrificing uniqueness."""
    f1 = Format.objects.create(prefix='t1', purpose='tube-one')
    f2 = Format.objects.create(prefix='t2', purpose='tube-two')
    f3 = Format.objects.create(prefix='t3', purpose='tube-three')
    c1 = Container.objects.create(format=f1)
    c2 = Container.objects.create(format=f2, external_id=c1.pk)
    c3 = Container.objects.create(format=f3, external_id=c1.pk)
    for code in Container.objects.filter(format__in={f1, f2, f3}).values_list('code', flat=True):
        assert int(code[5:]) == c1.pk

    with raises(IntegrityError):
        Container.objects.create(format=f1, external_id=c1.pk)


@mark.django_db
def test_container_dot_well_label(mocker: 'MockerFixture') -> None:
    """Containers must accept dot labels to access wells."""
    wip_tube = Container.objects.create(
        format=Format.objects.create(
            bottom_row='P', right_column=24, prefix='wip', purpose='work-in-process-tube'
        )
    )
    mock_wells = mocker.patch.object(Container, 'wells', autospec=True)
    _ = wip_tube.A01  # top left
    _ = wip_tube.H12  # bottom right of 8 * 12 == 96-well plate
    _ = wip_tube.P24  # bottom right of 16 * 24 == 384-well plate
    assert mock_wells.method_calls == [
        mocker.call.get(label='A01'),
        mocker.call.get(label='H12'),
        mocker.call.get(label='P24'),
    ]


@mark.django_db
@mark.parametrize(
    ('bottom_row', 'right_column'),
    [('@', 1), ('Q', 1), ('A', -1), ('A', 0), ('A', 25), ('A', 100), ('AA', 1)],
)
def test_well_creation_range(bottom_row: int, right_column: str) -> None:
    """Wells must stay in range."""
    with raises(IntegrityError):
        Well.objects.create(
            container=Container.objects.create(
                format=Format.objects.create(prefix='pl', purpose='plate')
            ),
            label=f'{bottom_row}{right_column:02}',
        )


@mark.django_db
def test_overlapping_well_creation() -> None:
    """Wells must not overlap."""
    plate = Container.objects.create(format=Format.objects.create(prefix='pl', purpose='plate'))
    Well.objects.create(container=plate, label='A01')
    with raises(IntegrityError):
        Well.objects.create(container=plate, label='A01')


@mark.django_db
def test_plan_and_transfers() -> None:
    """Test Plan and Transfer creation and relationships."""
    plan = Plan.objects.create(created_by=get_test_user())
    assert plan.created_by.username == 'test.user'
    transfer = Transfer.objects.create(plan=plan, source=Well.objects.start, sink=Well.objects.end)
    assert set(Well.objects.start.sinks.all()) == {Well.objects.end}
    assert set(Well.objects.end.sources.all()) == {Well.objects.start}
    assert plan.transfers.get() == transfer
