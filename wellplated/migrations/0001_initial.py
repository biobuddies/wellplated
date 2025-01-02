# Generated by Django 5.1.1 on 2024-12-02 13:47


import modelcluster.fields
from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations import state
from django.db.models import (
    BigAutoField,
    CharField,
    CheckConstraint,
    DateTimeField,
    ForeignKey,
    GeneratedField,
    ManyToManyField,
    PositiveSmallIntegerField,
    Q,
    TextField,
    UniqueConstraint,
    Value,
)
from django.db.models.deletion import PROTECT
from django.db.models.functions import Cast, Concat, Left, Length, LPad, StrIndex, Substr


def constrain_format() -> list[migrations.AddConstraint]:
    constraints = []
    for name, condition in {
        'single-character-bottom-row': Q(bottom_row__length=1),
        'minimum-bottom-row-A': Q(bottom_row__gte='A'),
        'maximum-bottom-row-P': Q(bottom_row__lte='P'),
        'minimum-right-column-1': Q(right_column__gte=1),
        'maximum-right-column-24': Q(right_column__lte=24),
        'dot-free-prefix': ~Q(prefix__contains='.'),
    }.items():
        constraints.append(
            migrations.AddConstraint(
                model_name='format', constraint=CheckConstraint(condition=condition, name=name)
            )
        )
    return constraints


def create_untracked(apps: state.StateApps, _schema_editor: BaseDatabaseSchemaEditor) -> None:
    # Leave unused low numbers between start and end for customization
    for pk, purpose in {0: 'start', 999: 'end'}.items():
        container = apps.get_model('wellplated', 'Container').objects.create(
            id=pk,
            code=purpose,
            format=apps.get_model('wellplated', 'Format').objects.create(
                bottom_row='A', right_column=1, prefix=purpose, purpose=purpose
            ),
        )
        container.wells.add(apps.get_model('wellplated', 'Well')(label='A1'))
        container.wells.commit()


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name='Format',
            fields=[
                (
                    'id',
                    BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                ('bottom_row', CharField(default='H', editable=False, max_length=1)),
                ('right_column', PositiveSmallIntegerField(default=12, editable=False)),
                (
                    'pad_column_to',
                    GeneratedField(
                        db_persist=True,
                        editable=False,
                        expression=Length(Cast('right_column', CharField())),
                        output_field=PositiveSmallIntegerField(),
                    ),
                ),
                ('prefix', CharField(editable=False, max_length=11)),
                (
                    'bottom_right_prefix',
                    GeneratedField(
                        db_persist=True,
                        expression=Concat('bottom_row', 'right_column', Value('.'), 'prefix'),
                        output_field=CharField(max_length=1 + 2 + 1 + 11),
                        unique=True,
                    ),
                ),
                ('created_at', DateTimeField(auto_now_add=True, editable=False)),
                ('purpose', TextField(unique=True)),
            ],
        ),
        *constrain_format(),
        migrations.CreateModel(
            name='Container',
            fields=[
                (
                    'id',
                    BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                (
                    'code',
                    GeneratedField(
                        db_persist=True,
                        expression=Concat(
                            Substr('format', StrIndex('format', Value('.')) + Value(1)),
                            LPad(
                                Cast('id', CharField()),
                                Length(Left('format', StrIndex('format', Value('.')))),
                                Value('0'),
                            ),
                        ),
                        editable=False,
                        output_field=CharField(max_length=12),
                        unique=True,
                    ),
                ),
                ('created_at', DateTimeField(auto_now_add=True, editable=False)),
                (
                    'format',
                    ForeignKey(
                        editable=False,
                        on_delete=PROTECT,
                        related_name='containers',
                        to='wellplated.format',
                        to_field='bottom_right_prefix',
                    ),
                ),
            ],
            options={'abstract': False},
        ),
        migrations.CreateModel(
            name='Well',
            fields=[
                (
                    'id',
                    BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                (
                    'container',
                    modelcluster.fields.ParentalKey(
                        editable=False,
                        on_delete=PROTECT,
                        related_name='wells',
                        to='wellplated.container',
                    ),
                ),
                ('label', CharField(editable=False, max_length=3)),
            ],
        ),
        migrations.AddConstraint(
            model_name='well',
            constraint=UniqueConstraint(
                fields=('container', 'label'), name='unique_container_well_label'
            ),
        ),
        migrations.RunPython(create_untracked, migrations.RunPython.noop),
        migrations.CreateModel(
            name='Plan',
            fields=[
                (
                    'id',
                    BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                ('created_at', DateTimeField(auto_now_add=True)),
                (
                    'created_by',
                    ForeignKey(
                        on_delete=PROTECT, related_name='plans_created', to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='Transfer',
            fields=[
                (
                    'id',
                    BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                (
                    'plan',
                    ForeignKey(on_delete=PROTECT, related_name='transfers', to='wellplated.plan'),
                ),
                ('source', ForeignKey(on_delete=PROTECT, related_name='+', to='wellplated.well')),
                ('sink', ForeignKey(on_delete=PROTECT, related_name='+', to='wellplated.well')),
            ],
        ),
        migrations.AddField(
            model_name='well',
            name='sources',
            field=ManyToManyField(
                related_name='sinks', through='wellplated.Transfer', to='wellplated.well'
            ),
        ),
    ]
