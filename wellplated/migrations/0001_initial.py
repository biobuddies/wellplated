# Generated by Django 5.1.1 on 2024-10-01 11:22

import django.db.models.deletion
import modelcluster.fields
from django.conf import settings
from django.db import migrations, models


def create_untracked(apps, _schema_editor):
    container = apps.get_model('wellplated', 'Container').objects.create(
        barcode='untracked',
        container_type=apps.get_model('wellplated', 'ContainerType').objects.create(
            barcode_format='untracked', purpose='untracked'
        ),
    )
    container.well_set.add(apps.get_model('wellplated', 'Well')(row=0, column=0))
    container.well_set.commit()


def delete_untracked(apps, _schema_editor):
    apps.get_model('wellplated', 'Well').objects.get(container__barcode='untracked').delete()
    apps.get_model('wellplated', 'Container').objects.get(barcode='untracked').delete()
    apps.get_model('wellplated', 'ContainerType').objects.get(purpose='untracked').delete()


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name='ContainerType',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                ('last_number', models.PositiveIntegerField(default=1)),
                ('barcode_format', models.CharField(max_length=128, unique=True)),
                ('purpose', models.TextField(unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='Container',
            fields=[
                ('barcode', models.CharField(max_length=128, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'container_type',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to='wellplated.containertype'
                    ),
                ),
            ],
            options={'abstract': False},
        ),
        migrations.CreateModel(
            name='Plan',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'assigned_to',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='plans_assigned',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'created_by',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='plans_created',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='Well',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                ('row', models.PositiveIntegerField()),
                ('column', models.PositiveSmallIntegerField()),
                (
                    'container',
                    modelcluster.fields.ParentalKey(
                        on_delete=django.db.models.deletion.PROTECT, to='wellplated.container'
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='Transfer',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                (
                    'plan',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to='wellplated.plan'
                    ),
                ),
                (
                    'fro',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='transfers_from',
                        to='wellplated.well',
                    ),
                ),
                (
                    'to',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='transfers_to',
                        to='wellplated.well',
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name='well',
            constraint=models.UniqueConstraint(
                fields=('container', 'row', 'column'), name='unique_well'
            ),
        ),
        migrations.RunPython(create_untracked, delete_untracked),
    ]