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
### Containers
To support plates, a `Container` models a two-dimensional matrix of `Well`s. Tubes are treated as
a degenerate case with a single row and a single column. For easy checking, the coordinate system
matches what is commonly molded onto plates, with a character for the row and a number for the
column. Zero padding to a uniform width is performed to make sorting exported data easy, for
tidy display.

To avoid mixups, each `Container` is assigned a unique alphanumberic human and machine readable identifier called `code`. The following ways of making the `code` physically visible are supported:
* Handwriting the letters and numbers on the `Container` (better than unidentified; maybe well suited to quick development; for consistent legibility consider the alternatives below)
* Printing and sticking a label with with letters and numbers to the `Container`
* Printing and sticking a barcode representation of the letters and numbers to the `Container`
* Using `Containers` which already have a barcode representation of the letters and numbers printed on them

Tubes in a rack can be modeled as many single-`Well` `Container`s. This is a good choice when the tubes are only in this arrangement for one workflow step. If helpful, information about the rack can be recorded in related `Plan` or `Result` objects.

Tubes in a rack can also be modeled as one multi-`Well` `Container`. This is a good choice when the tubes remain in the same arrangement for multiple workflow steps. If helpful, information about the tubes (such as tube-specific barcodes) can be be recorded in related `Plan` or `Result` objects.

Separate models per `Format`, and a unified model with separately incrementing numbers per prefix,
were considered, but the code complexity of those approaches seems unwarranted. The first model to
overflow will probably be `Well`. The maximum value for BigAutoField is 9223372036854775807. If
`Well`s were fully populated, 9223372036854775807 // 1536 == 6004799503160661 (16 digits)
`Containers` would be supported. If `Well`s are sparsely populated and plates have 384
or fewer wells, then the limit is a bit higher.

Resource exhaustion is a classic failure mode, but easily tracked and forecasted. TODO: add
django-healthcheck for AutoField/BigAutoField exhaustion, similar to free disk space.

### Container Formats
Containers are defined as sharing the same type if the following are exactly equal:
* Number of rows
* Number of columns
* Code format string

#### Future Work
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

Should only one of these be supported? Should both be supported?



## Separate or Together?
Should `Container` be a single table, with each row relating to its `ContainerType`? Type-specific Python code could be implemented using the [Proxy Models](https://docs.djangoproject.com/en/5.1/topics/db/models/#proxy-models). Queries selecting every `Container` used in a
