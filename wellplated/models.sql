CREATE TABLE IF NOT EXISTS "wellplated_format" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    "bottom_row" varchar(1) NOT NULL,
    "right_column" smallint unsigned NOT NULL CHECK ("right_column" >= 0),
    "prefix" varchar(11) NOT NULL UNIQUE,
    "bottom_right_prefix" varchar(14) GENERATED ALWAYS AS (
        (
            COALESCE("bottom_row", '')
            || COALESCE(
                (
                    COALESCE(LPAD(CAST("right_column" AS text), 2, '0'), '')
                    || COALESCE("prefix", '')
                ),
                ''
            )
        )
    ) STORED UNIQUE,
    "created_at" datetime NOT NULL,
    "purpose" text NOT NULL UNIQUE,
    CONSTRAINT "len(wellplated_format.bottom_row) == 1" CHECK (LENGTH("bottom_row") = 1),
    CONSTRAINT "wellplated_format.bottom_row <= 'P'" CHECK ("bottom_row" <= 'P'),
    CONSTRAINT "wellplated_format.bottom_row >= 'A'" CHECK ("bottom_row" >= 'A'),
    CONSTRAINT "wellplated_format.right_column >= 1" CHECK ("right_column" >= 1),
    CONSTRAINT "wellplated_format.right_column <= 24" CHECK ("right_column" <= 24),
    CONSTRAINT "len(wellplated_format.prefix) <= 11" CHECK (LENGTH("prefix") <= 11),
    CONSTRAINT "'.' not in wellplated_format.prefix" CHECK (NOT ("prefix" LIKE '%.%' ESCAPE '\'))
);
CREATE TABLE IF NOT EXISTS "wellplated_container" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    "external_id" smallint unsigned NULL CHECK ("external_id" >= 0),
    "code" varchar(15) GENERATED ALWAYS AS (
        (
            COALESCE("format_id", '')
            || COALESCE(
                LPAD(CAST(COALESCE("external_id", "id") AS text), (15 - LENGTH("format_id")), '0'),
                ''
            )
        )
    ) STORED UNIQUE,
    "created_at" datetime NOT NULL,
    "format_id" varchar(14) NOT NULL REFERENCES "wellplated_format" (
        "bottom_right_prefix"
    ) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT "wellplated_container.external_id >= 0" CHECK ("external_id" >= 0),
    CONSTRAINT "wellplated_container.external_id <= 99999999999" CHECK (
        "external_id" <= 99999999999
    )
);
CREATE INDEX "wellplated_container_format_id_05523590" ON "wellplated_container" ("format_id");
CREATE TABLE IF NOT EXISTS "wellplated_plan" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    "created_at" datetime NOT NULL,
    "created_by_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "wellplated_transfer" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    "plan_id" bigint NOT NULL REFERENCES "wellplated_plan" ("id") DEFERRABLE INITIALLY DEFERRED,
    "source_id" bigint NOT NULL REFERENCES "wellplated_position" (
        "id"
    ) DEFERRABLE INITIALLY DEFERRED,
    "sink_id" bigint NOT NULL REFERENCES "wellplated_position" ("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "wellplated_position" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    "container_code" varchar(15) NOT NULL REFERENCES "wellplated_container" (
        "code"
    ) DEFERRABLE INITIALLY DEFERRED,
    "row" varchar(1) NOT NULL,
    "column" smallint unsigned NOT NULL CHECK ("column" >= 0),
    CONSTRAINT "len(wellplated_position.row) == 1" CHECK (LENGTH("row") = 1),
    CONSTRAINT "wellplated_position.row >= 'A'" CHECK ("row" >= 'A'),
    CONSTRAINT "wellplated_position.row <= wellplated_position.container[:1]" CHECK (
        "row" <= (SUBSTR("container_code", 1, 1))
    ),
    CONSTRAINT "wellplated_position.column >= 1" CHECK ("column" >= 1),
    CONSTRAINT "wellplated_position.column <= int(wellplated_position.container[1:3])" CHECK (
        "column" <= (CAST(SUBSTR("container_code", 2, 2) AS smallint unsigned))
    ),
    CONSTRAINT "unique_container_row_column" UNIQUE ("container_code", "row", "column")
);
CREATE INDEX "wellplated_plan_created_by_id_01adc7f1" ON "wellplated_plan" ("created_by_id");
CREATE INDEX "wellplated_transfer_plan_id_589452da" ON "wellplated_transfer" ("plan_id");
CREATE INDEX "wellplated_transfer_source_id_cd5d530b" ON "wellplated_transfer" ("source_id");
CREATE INDEX "wellplated_transfer_sink_id_15f47874" ON "wellplated_transfer" ("sink_id");
CREATE INDEX "wellplated_position_container_code_046b2b7b" ON "wellplated_position" (
    "container_code"
);
