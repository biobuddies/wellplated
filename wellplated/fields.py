"""Models with database constraints, validators, and HTML5 attributes"""

from functools import partial
from typing import Any, Self, cast

from django.db.models import CharField, CheckConstraint, Model, PositiveSmallIntegerField, Q, Value
from django.db.models.functions import Cast, Left, Length, Substr
from django.db.models.options import Options
from django.forms import Field

CharField.register_lookup(Length)


class CheckedCharField(CharField):
    """HTML, Django serializer, and database constraints for fixed-length strings"""

    max_length: int
    max_value: Left | str
    min_length: int
    min_value: str
    omits: str

    def __init__(
        self,
        *args: Any,
        # https://docs.djangoproject.com/en/5.1/ref/databases/#character-fields
        max_length: int = 255,
        max_value: Left | str = '',
        min_length: int = 1,
        min_value: str = '',
        omits: str = '',  # Could become `str | Sequence[str]`
        **kwargs: Any,
    ) -> None:
        self.max_length = max_length
        self.max_value = max_value
        self.min_length = min_length
        self.min_value = min_value
        self.omits = omits

        kwargs['max_length'] = max_length
        super().__init__(*args, **kwargs)

    @staticmethod
    def check_constraint(
        meta: Options,
        name: str,
        message: str,
        *,
        as_needed: bool = True,
        invert: bool = False,
        **kwargs: Left | int | str,
    ) -> None:
        """Add a constraint check"""
        lookup, sql_value = kwargs.popitem()
        if as_needed and not sql_value:
            return

        # Lookup classes can also work: `LessThanOrEqual(F(name), self.max_value)`
        # But column names need to be wrapped either in functions like Length() or
        # with F() to ensure that in the generated SQL, they are double quoted columns
        # instead of single quoted string literals.
        condition = Q((f'{name}__{lookup}', sql_value))
        if invert:
            condition = ~condition

        if isinstance(sql_value, Left):
            right_side_column = cast(Left, sql_value.source_expressions[0]).name
            length = cast(Value, sql_value.source_expressions[1]).value
            python_value = f'{meta.db_table}.{right_side_column}[:{length}]'
        else:
            python_value = repr(sql_value)

        meta.constraints.append(
            CheckConstraint(
                condition=condition,
                name=message.format(column=f'{meta.db_table}.{name}', value=python_value),
            )
        )

    def contribute_to_class(self, cls: type[Model], name: str, private_only: bool = False) -> None:  # noqa: FBT001, FBT002
        """
        Set table constraints.

        These could evolve to column constraints one day to better organize the SQL.
        """
        super().contribute_to_class(cls, name, private_only=private_only)

        if cls.__module__ == '__fake__':
            return  # Avoid duplicate constraints when migrating

        # Ensure ModelState.from_model() considers constraints
        cls._meta.original_attrs['constraints'] = cls._meta.original_attrs.get('constraints', [])

        check = partial(self.check_constraint, cls._meta, name)

        if self.max_length == self.min_length:
            check('len({column}) == {value}', as_needed=False, length=self.max_length)
        else:
            check('len({column}) <= {value}', as_needed=False, length__lte=self.max_length)
            check('len({column}) >= {value}', length__gte=self.min_length)

        check('{column} <= {value}', lte=self.max_value)
        check('{column} >= {value}', gte=self.min_value)
        if self.omits:
            check('{value} not in {column}', invert=True, contains=self.omits)

        def formfield(self: Self, form_class: type[Field], **kwargs: Any) -> Field | None:
            kwargs['max_length'].setdefault(self.max_length)
            kwargs['min_length'].setdefault(self.min_length)
            if self.max_length == self.min_length == 1 and self.max_value and self.min_value:
                kwargs['pattern'] = f'[{self.min_value}-{self.max_value}]'
            return super().formfield(form_class, **kwargs)


class CheckedPositiveSmallIntegerField(PositiveSmallIntegerField):
    """HTML, Django serializer, and database constraints for positive small integers"""

    max_length: int
    max_value: Cast | int
    min_value: int

    def __init__(
        self, *args: Any, min_value: int = 0, max_value: Cast | int = 32767, **kwargs: Any
    ) -> None:
        """PostgreSQL smallint https://code.djangoproject.com/ticket/12030#comment:14"""
        self.max_value = max_value
        self.min_value = min_value
        super().__init__(*args, **kwargs)
        # To aid fixed-length string calculations; defined late because superclass would remove
        self.max_length = len(str(max_value))

    def __str__(self) -> str:
        return f'Integer between {self.min_value} and {self.max_value} inclusive'

    def _check_max_length_warning(self) -> list:
        """Silence parent class warning."""
        return []

    def contribute_to_class(self, cls: type[Model], name: str, private_only: bool = False) -> None:  # noqa: FBT001, FBT002
        """
        Set table constraints.

        These could evolve to column constraints one day to better organize the SQL.
        """
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
            zero_indexed_start: int = (
                cast(Value, self.max_value.source_expressions[0].source_expressions[1]).value - 1
            )
            python_value = (
                f'int({cls._meta.db_table}.'
                + cast(Substr, self.max_value.source_expressions[0].source_expressions[0]).name
                + f'[{zero_indexed_start}:'
                + str(
                    zero_indexed_start
                    + cast(Value, self.max_value.source_expressions[0].source_expressions[2]).value
                )
                + '])'
            )
        else:
            python_value = str(self.max_value)
        cls._meta.constraints.append(
            CheckConstraint(
                condition=Q(**{f'{name}__lte': self.max_value}),
                name=f'{cls._meta.db_table}.{name} <= {python_value}',
            )
        )

    def deconstruct(self) -> tuple:
        """Omit calculated max_length and include specified max_value and min_value."""
        name, path, args, kwargs = super().deconstruct()
        del kwargs['max_length']
        if self.max_value != 32767:
            kwargs['max_value'] = self.max_value
        if self.min_value:
            kwargs['min_value'] = self.min_value
        return name, path, args, kwargs

    def formfield(self, *_args: Any, **kwargs: Any) -> Field | None:
        """Set input min and max."""
        return super().formfield(
            **{'min_value': self.min_value, 'max_value': self.max_value, **kwargs}
        )
