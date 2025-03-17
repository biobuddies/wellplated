## Research Use Only (RUO) Versus Current Good Manufacturing Practices (CGMP)
Some features are general and relevant to both contexts. Some features only make sense in one
context. Some features need to be implemented differently in each context.

Hopefully the initial features fall into the former dual use category. As features emerge
that are only relevant to one environment, or need specialized implementations, the best
approach for organizing them will hopefully become clearer. Theoretically, possible approaches
include:
* A CGMP base, which the RUO build extends
* A common, shared base which both a CGMP extension and an RUO extension

We should keep in mind the risk reduction benefits of graduating software from 1. development and
testing, to 2. RUO production use, feedback, and software iteration, to 3. CGMP production use.

## Models
### Container
To support plates, a `Container` models a two-dimensional matrix of `Position`s. Treat individual
tubes as a simple or "degenerate" case with one row and one column. When multiple tubes are held in
one or more physical racks, holders, or fixtures, they can be treated as one logical `Container`
with rows and columns convenient multiples of the physical racks.

For easy checking, the coordinate system matches the "Battleship notation" commonly molded onto
plates, with a character for the row and a number for the column. Zero padding to a uniform width
makes sorting exported data easy, and keeps displays tidy.

To avoid mixups, each `Container` is assigned a unique alphanumberic human and machine readable
identifier called `code`. It is designed to support the following physical labeling:
* Handwriting the letters and numbers on the `Container` (better than unidentified; maybe well
  suited to quick development; for consistent legibility consider the alternatives below)
* Printing and sticking a label with human readable letters and numbers to the `Container`
* Printing and sticking a barcode representation of the letters and numbers to the `Container`
* Scanning pre-barcoded `Containers` and recording their values in the database

### Format
The number of rows and columns in a `Container`, and intended usage and code prefix, define a
`Format`.


### System Limits
Separate models per `Format`, and a unified model with separately incrementing numbers per prefix,
were considered, but the code complexity of those approaches seems unwarranted. The first model to
overflow will probably be `Position`. The maximum value for BigAutoField is 9223372036854775807. If
`Position`s were fully populated, 9223372036854775807 // 384 == 24019198012642645 (17 digits)
`Containers` would be supported. If `Positions`s are sparsely populated and plates have 384
or fewer wells, then the limit is a bit higher.

Horizontal space for printing barcodes might be more limiting than database integer size. To start
with, the maximum allowed `code` width is twelve characters. A more end-to-end check would be to generate
a label and check that everything fits, but wellplated does not yet include label generation.

While resource exhaustion is a common failure mode, it is easy to track and forecast. TODO: extend
django-healthcheck for AutoField/BigAutoField exhaustion, somewhat similar to free disk space.

#### Large Plates
Plates with double-character (more than 26) rows are not yet supported because of open questions.

https://web.archive.org/web/20210506171929/http://mscreen.lsi.umich.edu/mscreenwiki/index.php/COORDINATE
documented

> The alphanumeric well position on a plate.
>
> 96-well plate coordinates range from A01 to H12
> 384-well plates coordinates range from A01 to P24
> 1536-well plates coordinates range from A01 to AF48

Thunor takes the same approach to row characters (but does not zero-pad column numbers)
https://github.com/alubbock/thunor/blob/84d7a293cf352cf7fa3a1441561801f8c7ac73e6/thunor/io.py#L66-L71

What's the best way to implement support for this transposed Excel style? Should the first 26 rows
be padded with a character that sorts before `A`? If so, should that character be
` `, `-`, `.`, `0`, `:`, or something else?

Some plates appear to have physical molding assigning four wells at a time to a single character
https://shop.gbo.com/en/usa/products/bioscience/microplates/1536-well-microplates/
I'm guessing then that AA1, AB2, ..., HC47, HD48 would describe the diagonal.

Should only one of these be supported? Should both be supported? Are there other conventions?
