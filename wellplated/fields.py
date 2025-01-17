"""Models where keyword arguments imply database constraints and validators"""

from django.core.checks import CheckMessage
from django.db.models import CharField, CheckConstraint, Model, PositiveSmallIntegerField, Q
from django.db.models.functions import Length
from django.db.models.lookups import Contains

CharField.register_lookup(Length)


def Equal(left, right):
    return Q(left=right)


class CheckedCharField(CharField):
    """HTML, Django serializer, and database constraints for fixed-length strings"""

    max_length: int
    max_value: str
    min_length: int
    min_value: str
    omits: str

    def __init__(
        self,
        # https://docs.djangoproject.com/en/5.1/ref/databases/#character-fields
        *args,
        max_length: int = 255,
        max_value: str = '',
        min_length: int = 1,
        min_value: str = '',
        omits: str = '',  # Could become `str | Sequence[str]`
        **kwargs,
    ) -> None:
        self.max_length = max_length
        self.max_value = max_value
        self.min_length = min_length
        self.min_value = min_value
        self.omits = omits

        super().__init__(*args, max_length=max_length, **kwargs)

    def check(self, **kwargs) -> list[CheckMessage]:
        return [
            *super().check(**kwargs)
            ## TODO check stuff like
            # lengths are non-negative
        ]

    def contribute_to_class(self, cls: type[Model], name: str, private_only: bool = False):
        super().contribute_to_class(cls, name)
        constraints = cls._meta.constraints

        def check(message: str, **kwargs) -> None:
            """Add a constraint check"""
            lookup, value = kwargs.popitem()
            constraints.append(
                CheckConstraint(
                    # Lookup classes also work: `LessThanOrEqual(F(name), self.max_value)`
                    # But column names need to be wrapped either in a functions like Length() or
                    # with F() to ensure that in the generated SQL, they are double quoted instead
                    # of single quoted like string literals.
                    condition=Q((f'{name}__{lookup}', value)),
                    name=message.format(column=f'{cls._meta.db_table}.{name}', value=value),
                )
            )

        if self.max_length == self.min_length:
            check('len({column}) == {value}', length=self.max_length)
        else:
            check('len({column}) <= {value}', length__lte=self.max_length)
            if self.min_length:
                check('len({column}) >= {value}', length__gte=self.min_length)

        if self.max_value:
            check("{column} <= '{value}'", lte=self.max_value)
        if self.min_value:
            check("{column} >= '{value}'", gte=self.min_value)
        if self.omits:
            constraints.append(
                CheckConstraint(
                    condition=~Contains(name, self.omits),
                    name=f"'{self.omits}' not in {cls._meta.db_table}.{name}",
                )
            )

        def formfield(self, *_args, **kwargs):
            attributes = {'max_length': self.max_length, 'min_length': self.min_length}
            if self.max_length == 1 and self.max_value and self.min_length == 1 and self.min_value:
                attributes['pattern'] = f'[{self.min_value}-{self.max_value}]'
            return super().formfield(attributes | kwargs)


class CheckedPositiveSmallIntegerField(PositiveSmallIntegerField):
    """HTML, Django serializer, and database constraints for positive small integers"""

    max_length: int
    max_value: int
    min_value: int

    def __init__(self, *args, min_value=0, max_value=32767, **kwargs) -> None:
        """PostgreSQL smallint https://code.djangoproject.com/ticket/12030#comment:14"""
        self.max_value = max_value
        self.min_value = min_value
        super().__init__(*args, **kwargs)
        # To aid fixed-length string calculations; defined late because superclass would remove
        self.max_length = len(str(max_value))

    def _check_max_length_warning(self) -> list:
        return []

    def check(self, **kwargs) -> list[CheckMessage]:
        """TODO Silence the warning about max_length on PositiveSmallIntegerField"""
        # TODO check min_value and max_value on self instance are within range those on PositiveSmallIntegerField class
        return [*super().check(**kwargs)]

    def contribute_to_class(self, cls: type[Model], name: str, private_only: bool = False):  # noqa: FBT002
        super().contribute_to_class(cls, name)
        cls._meta.constraints.extend(
            [
                CheckConstraint(
                    condition=Q(**{f'{name}__gte': self.min_value}),
                    name=f'{cls._meta.db_table}.{name} >= {self.min_value}',
                ),
                CheckConstraint(
                    condition=Q(**{f'{name}__lte': self.max_value}),
                    name=f'{cls._meta.db_table}.{name} <= {self.max_value}',
                ),
            ]
        )

    @property
    def description(self) -> str:
        return f'Integer between {self.min_value} and {self.max_value} (inclusive)'

    def formfield(self, *_args, **kwargs):
        return super().formfield(
            **{'min_value': self.min_value, 'max_value': self.max_value, **kwargs}
        )
