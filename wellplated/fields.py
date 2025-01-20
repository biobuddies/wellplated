"""Models with database constraints, validators, and HTML5 attributes"""

from django.db.models import CharField, CheckConstraint, Model, PositiveSmallIntegerField, Q
from django.db.models.functions import Cast, Left, Length, Substr

CharField.register_lookup(Length)


class CheckedCharField(CharField):
    """HTML, Django serializer, and database constraints for fixed-length strings"""

    max_length: int
    max_value: str
    min_length: int
    min_value: str
    omits: str

    def __init__(
        self,
        *args,
        # https://docs.djangoproject.com/en/5.1/ref/databases/#character-fields
        max_length: int = 255,
        max_value: Left | str = '',
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

    def contribute_to_class(self, cls: type[Model], name: str, private_only: bool = False):
        super().contribute_to_class(cls, name)

        if cls.__module__ == '__fake__':
            return  # Avoid duplicate constraints when migrating

        # Ensure ModelState.from_model() considers constraints
        cls._meta.original_attrs['constraints'] = cls._meta.original_attrs.get('constraints', [])

        constraints = cls._meta.constraints

        def check(message: str, **kwargs) -> None:
            """Add a constraint check"""
            lookup, sql_value = kwargs.popitem()
            if isinstance(sql_value, Left):
                python_value = (
                    f'{cls._meta.db_table}.{sql_value.source_expressions[0].name}'
                    + f'[:{sql_value.source_expressions[1].value}]'
                )
            else:
                python_value = repr(sql_value)
            constraints.append(
                CheckConstraint(
                    # Lookup classes can also work: `LessThanOrEqual(F(name), self.max_value)`
                    # But column names need to be wrapped either in functions like Length() or
                    # with F() to ensure that in the generated SQL, they are double quoted columns
                    # instead of single quoted string literals.
                    condition=Q((f'{name}__{lookup}', sql_value)),
                    name=message.format(column=f'{cls._meta.db_table}.{name}', value=python_value),
                )
            )

        if self.max_length == self.min_length:
            check('len({column}) == {value}', length=self.max_length)
        else:
            check('len({column}) <= {value}', length__lte=self.max_length)
            if self.min_length:
                check('len({column}) >= {value}', length__gte=self.min_length)

        if self.max_value:
            check('{column} <= {value}', lte=self.max_value)
        if self.min_value:
            check('{column} >= {value}', gte=self.min_value)
        if self.omits:
            (check('{value} not in {column}', contains=self.omits),)
            constraints[-1].condition = ~constraints[-1].condition

        def formfield(self, *_args, **kwargs):
            attributes = {'max_length': self.max_length, 'min_length': self.min_length}
            if self.max_length == 1 and self.max_value and self.min_length == 1 and self.min_value:
                attributes['pattern'] = f'[{self.min_value}-{self.max_value}]'
            return super().formfield(attributes | kwargs)


class CheckedPositiveSmallIntegerField(PositiveSmallIntegerField):
    """HTML, Django serializer, and database constraints for positive small integers"""

    max_length: int
    max_value: Cast | int
    min_value: int

    def __init__(self, *args, min_value=0, max_value=32767, **kwargs) -> None:
        """PostgreSQL smallint https://code.djangoproject.com/ticket/12030#comment:14"""
        self.max_value = max_value
        self.min_value = min_value
        super().__init__(*args, **kwargs)
        # To aid fixed-length string calculations; defined late because superclass would remove
        self.max_length = len(str(max_value))

    def __str__(self) -> str:
        # TODO what about description?
        return f'Integer between {self.min_value} and {self.max_value} inclusive'

    def _check_max_length_warning(self) -> list:
        return []

    def contribute_to_class(self, cls: type[Model], name: str, private_only: bool = False):  # noqa: FBT002
        super().contribute_to_class(cls, name, private_only=private_only)

        if cls.__module__ == '__fake__':
            return  # Avoid duplicating constraints during migrate

        if 'constraints' not in cls._meta.original_attrs:
            # Ensure ModelState.from_model() considers constraints
            cls._meta.original_attrs['constraints'] = []

        cls._meta.constraints.append(
            CheckConstraint(
                condition=Q(**{f'{name}__gte': self.min_value}),
                name=f'{cls._meta.db_table}.{name} >= {self.min_value}',
            )
        )
        if (
            isinstance(self.max_value, Cast)
            and isinstance(self.max_value.output_field, PositiveSmallIntegerField)
            and isinstance(self.max_value.source_expressions[0], Substr)
        ):
            python_value = (
                f'int({cls._meta.db_table}.{self.max_value.source_expressions[0].source_expressions[0].name}'
                + f'[{self.max_value.source_expressions[0].source_expressions[1].value - 1}:'
                + f'{self.max_value.source_expressions[0].source_expressions[2].value - 2}])'
            )
        else:
            python_value = self.max_value
        cls._meta.constraints.append(
            CheckConstraint(
                condition=Q(**{f'{name}__lte': self.max_value}),
                name=f'{cls._meta.db_table}.{name} <= {python_value}',
            )
        )

    def deconstruct(self) -> tuple:
        name, path, args, kwargs = super().deconstruct()
        del kwargs['max_length']
        if self.max_value != 32767:
            kwargs['max_value'] = self.max_value
        if self.min_value:
            kwargs['min_value'] = self.min_value
        return name, path, args, kwargs

    @property
    def description(self) -> str:
        return f'Integer between {self.min_value} and {self.max_value} (inclusive)'

    def formfield(self, *_args, **kwargs):
        return super().formfield(
            **{'min_value': self.min_value, 'max_value': self.max_value, **kwargs}
        )
