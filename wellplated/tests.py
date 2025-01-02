from django.contrib.auth import get_user_model
from django.db.models import PositiveSmallIntegerField
from django.db.models.functions import Cast, Substr
from django.db.utils import IntegrityError
from pytest import mark, raises

from wellplated.models import Container, Format, Plan, Transfer, Well


def get_test_user() -> 'User':
    user, _ = get_user_model().objects.get_or_create(username='test.user')
    return user


@mark.django_db
def test_untracked_data():
    """
    Initial data for start and end of tracking must exist as expected.
    """
    formats = Format.objects.filter(purpose__in=('start', 'end')).order_by('pk')
    assert set(formats.values_list('prefix', flat=True)) == {'start', 'end'}

    assert set(Container.objects.filter(format__in=formats).values_list('code', flat=True)) == {
        'start000',
        'end999',
    }

    assert set(map(str, Well.objects.filter(container__format__in=formats).order_by('pk'))) == {
        'start000.A1',
        'end999.A1',
    }

    assert Well.objects.start.label == 'A1'
    assert Well.objects.end.label == 'A1'

    assert Well.objects.start.container.format.purpose == 'start'
    assert Well.objects.end.container.format.purpose == 'end'


@mark.django_db
def test_format_purpose_uniqueness():
    """
    Formats must have unique purposes.
    """
    Format.objects.create(prefix='ft1', purpose='final-tube')
    with raises(IntegrityError):
        Format.objects.create(prefix='ft2', purpose='final-tube')


@mark.django_db
def test_format_prefix_uniqueness():
    """
    Formats must have unique prefix strings.
    """
    Format.objects.create(prefix='t', purpose='final-tube')
    with raises(IntegrityError):
        Format.objects.create(prefix='t', purpose='mix-tube')


@mark.django_db
@mark.parametrize(
    'bottom_row,right_column',
    (('@', 1), ('Q', 1), ('A', -1), ('A', 0), ('A', 25), ('A', 100), ('AA', 1)),
)
def test_format_row_column_constraints(bottom_row, right_column):
    """
    Format rows and columns must stay in range.
    """
    with raises(IntegrityError):
        Format.objects.create(
            prefix='t', purpose='test', bottom_row=bottom_row, right_column=right_column
        )


@mark.django_db
def test_format_dot_prevention():
    """
    Format prefixes must never contain periods `.`
    """
    with raises(IntegrityError):
        Format.objects.create(prefix='.', purpose='dot')


@mark.django_db
def test_container_code_uniqueness():
    """
    Containers must have unique codes.
    """
    final_tube = Format.objects.create(prefix='f', purpose='final-tube')
    Container.objects.create(code='t0', format=final_tube)
    # TODO rebuild this when support for external codes (pre-barcoded containers) is added
    # with raises(IntegrityError):
    #    Container.objects.create(code='t0', format=final_tube)


@mark.django_db
def test_container_creation_codes():
    """
    Sequential calls to create must generate monotonically increasing numbers.
    """
    final_tube = Format.objects.create(prefix='f', purpose='final-tube')
    new_container_pks = [
        Container.objects.create(format=final_tube).pk,
        Container.objects.create(format=final_tube).pk,
        Container.objects.create(format=final_tube).pk,
    ]
    created_codes = (
        Container.objects.filter(pk__in=new_container_pks)
        .order_by('pk')
        .annotate(number=Cast(Substr('code', 2), PositiveSmallIntegerField()))
        .values_list('number', flat=True)
    )
    assert tuple(created_codes) == (1000, 1001, 1002)

    for _ in range(3):
        final_tube.containers.add(Container(format=final_tube), bulk=False)
    assert (
        Container.objects.filter(format=final_tube).latest('pk').pk
        - Container.objects.filter(format=final_tube).earliest('pk').pk
        == 5
    )

    Container.objects.bulk_create(Container(format=final_tube) for _ in range(3))
    assert (
        Container.objects.filter(format=final_tube).latest('pk').pk
        - Container.objects.filter(format=final_tube).earliest('pk').pk
        == 8
    )


@mark.django_db
def test_container_dot_well_label(mocker):
    """
    Containers must accept dot labels to access wells.
    """
    wip_tube = Container.objects.create(
        format=Format.objects.create(
            bottom_row='P', right_column=24, prefix='wip', purpose='work-in-process-tube'
        )
    )
    mock_wells = mocker.patch.object(Container, 'wells', autospec=True)
    wip_tube.A01  # top left
    wip_tube.H12  # bottom right of 8 * 12 == 96-well plate
    wip_tube.P24  # bottom right of 16 * 24 == 384-well plate
    assert mock_wells.method_calls == [
        mocker.call.get(label='A01'),
        mocker.call.get(label='H12'),
        mocker.call.get(label='P24'),
    ]


@mark.django_db
def test_plan_and_transfers():
    plan = Plan.objects.create(created_by=get_test_user())
    assert plan.created_by.username == 'test.user'
    transfer = Transfer.objects.create(plan=plan, source=Well.objects.start, sink=Well.objects.end)
    Well.objects.start.refresh_from_db()
    Well.objects.end.refresh_from_db()
    print(Well.objects.start.sinks.all())
    print(Well.objects.end.sources.all())
    # assert set(Well.objects.start.sinks.all()) == {Well.objects.end}
    # assert set(Well.objects.end.sources.all()) == {Well.objects.start}
    assert plan.transfers.get() == transfer
