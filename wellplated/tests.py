from django.db.utils import IntegrityError
from pytest import mark, raises
from wellplated.models import Container, ContainerType, Well


@mark.django_db
def test_untracked_data_migration():
    """
    Initial data must exist as expected.
    """
    untracked_container_type = ContainerType.objects.get_untracked()
    assert untracked_container_type.purpose == 'untracked'

    untracked_container = Container.objects.get_untracked()
    assert untracked_container.barcode == 'untracked'

    assert untracked_container.container_type == untracked_container_type

    assert set(map(str, untracked_container.wells.all())) == {'untracked.A01'}


@mark.django_db
def test_containertype_purpose_uniqueness():
    """
    ContainerTypes must have unique purposes.
    """
    ContainerType.objects.create(purpose='final-tube', barcode_format='t{}')
    with raises(IntegrityError):
        ContainerType.objects.create(purpose='final-tube', barcode_format='tube{}')

@mark.django_db
def test_containertype_barcodeformat_uniqueness():
    """
    ContainerTypes must have unique barcode formats.
    """
    ContainerType.objects.create(purpose='final-tube', barcode_format='t{}')
    with raises(IntegrityError):
        ContainerType.objects.create(purpose='mix-tube', barcode_format='t{}')

@mark.django_db
def test_container_barcode_uniqueness():
    """
    Containers must have unique barcodes.
    """
    Container.objects.create(barcode='t0', container_type=ContainerType.objects.get_untracked())
    with raises(IntegrityError):
        Container.objects.create(barcode='t0', container_type=ContainerType.objects.get_untracked())

def test_container_slash_well(mocker):
    """
    Containers must correctly translate "Battleship notation" labels to zero-indexed rows and columns.
    """
    t0 = Container(barcode='t0')
    mock_wells = mocker.patch.object(Container, 'wells', autospec=True)
    t0 / 'A01'  # uppercase row, zero padded column, top left
    t0 / 'H12'  # double digit column, bottom right of 96-well plate
    t0 / 'P24'  # bottom right of 384-well plate
    t0 / 'AF48'  # double letter row, bottom right of 1536-well plate
    assert mock_wells.method_calls == [
        mocker.call.get(row=0, column=0),
        mocker.call.get(row=7, column=11),  # 8 * 12 == 96
        mocker.call.get(row=15, column=23),  # 16 * 24 == 384
        mocker.call.get(row=31, column=47),  # 32 * 48 == 1536
    ]

def test_container_slash_well_mismatch(mocker):
    t0 = Container(barcode='t0')
    mock_wells = mocker.patch.object(Container, 'wells', autospec=True)
    with raises(ValueError):
        t0 / ''
    with raises(ValueError):
        t0 / 'A'
    with raises(ValueError):
        t0 / '0'
    # TODO check A0, AG01, etc. once bounds checking has been implemented
    assert mock_wells.method_calls == []
