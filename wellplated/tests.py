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
def test_untracked_data_migration():
    """
    Initial data must exist as expected.
    """
    untracked_formats = Format.objects.filter(purpose__in=('start', 'end'))
    assert set(untracked_formats.values_list('prefix', flat=True)) == {'start', 'end'}

    untracked_container_wells = Well.objects.filter(container__format__in=untracked_formats)
    assert set(map(str, untracked_container_wells)) == {'start.A1', 'end.A1'}


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
    Container.objects.create(code='t0', format=Format.objects.get(purpose='start'))
    with raises(IntegrityError):
        Container.objects.create(code='t0', format=Format.objects.get(purpose='start'))


@mark.django_db
def test_container_serial_codes():
    """
    Sequential calls to create must generate monotonically increasing numbers.
    """
    final_tube = Format.objects.create(prefix='f', purpose='test')
    codes = (
        Container.objects.filter(
            pk__in=[Container.objects.create(format=final_tube).pk for _ in range(10)]
        )
        .order_by('pk')
        .annotate(number=Cast(Substr('code', 2), PositiveSmallIntegerField()))
        .values_list('number', flat=True)
    )
    assert tuple(codes) == tuple(range(1, 11))


def test_container_dot_well_label(mocker):
    """
    Containers must accept dot labels to access wells.
    """
    t0 = Container(code='t0')
    mock_wells = mocker.patch.object(Container, 'wells', autospec=True)
    t0.A01  # top left
    t0.H12  # bottom right of 8 * 12 == 96-well plate
    t0.P24  # bottom right of 16 * 24 == 384-well plate
    t0.AF48  # double letter row, bottom right of 32 * 48 == 1536-well plate
    assert mock_wells.method_calls == [
        mocker.call.get(label='A01'),
        mocker.call.get(label='H12'),
        mocker.call.get(label='P24'),
        mocker.call.get(label='AF48'),
    ]


@mark.django_db
def test_plan_and_transfers():
    plan = Plan.objects.create(created_by=get_test_user())
    assert plan.created_by.username == 'test.user'
    transfer = Transfer.objects.create(
        plan=plan,
        source=Container.objects.get(code='start').A01,
        sink=Container.objects.get(code='end').A01,
    )
    assert set(Container.objects.get(code='start').sinks) == {Container.objects.get(code='end').A01}
    assert plan.transfers.get() == transfer
