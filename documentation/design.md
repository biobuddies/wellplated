## Research Use Only Versus Current Good Manufacturing Practices
Some features are general and relevant to both approaches. Other features are specific
or must 

## Models
### Containers
A `Container` models multi-`Well` plates with multiple rows and multiple columns. It models single-`Well` tubes with a single row and a single column.

To avoid mixups, each `Container` must have a unique alphanumberic human and machine readable identifier called `code`. The following ways of making the `code` physically visible are supported:
* Handwriting the letters and numbers on the `Container` (better than unidentified; maybe well suited to quick development; for consistent legibility consider the alternatives below)
* Printing and sticking a label with with letters and numbers to the `Container`
* Printing and sticking a barcode representation of the letters and numbers to the `Container`
* Using `Containers` which already have a barcode representation of the letters and numbers printed on them

Tubes in a rack can be modeled as many single-`Well` `Container`s. This is a good choice when the tubes are only in this arrangement for one workflow step. If helpful, information about the rack can be recorded in related `Plan` or `Result` objects.

Tubes in a rack can also be modeled as one multi-`Well` `Container`. This is a good choice when the tubes remain in the same arrangement for multiple workflow steps. If helpful, information about the tubes (such as tube-specific barcodes) can be be recorded in related `Plan` or `Result` objects.

### Container Types
Containers are defined as sharing the same type if the following are exactly equal:
* Number of rows
* Number of columns
* Code format string

## Separate or Together?
Should `Container` be a single table, with each row relating to its `ContainerType`? Type-specific Python code could be implemented using the [Proxy Models](https://docs.djangoproject.com/en/5.1/topics/db/models/#proxy-models). Queries selecting every `Container` used in a 
