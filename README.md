# Well Plated

Python Django models for liquid in plates and tubes

For planning what should happen, with strong constraints, and tracking what actually happened.

## Features
* Prevent out-of-range well rows and columns
* Generate identifying codes (ready to be printed out as barcodes)
* Record externally generated barcodes (track pre-barcoded tubes and plates)

## TODO
* Add Validators for Python-level checks
* Complete HTML5 validation support, like the `pattern` attribute
* Enforce append-only behavior for most or all models/tables by continuing to grant SELECT and
  INSERT permissions but revoking UPDATE permission
* Integrate with [OR Tools](https://developers.google.com/optimization/cp/cp_example)
  for finding solutions that satisfy the constraints and minimize time or other dimensions.
* API endpoints like Django REST Framework, Graphene-Django
* Examples of attaching common measurements to Wells
* Start datetimes and durations
* Plans for transfers and measurements and corresponding queries:
    * What Plans have been started and need finishing?
    * What Plans haven't been started yet?
    * What Plans were canceled before they were finished, or finished with a failure, and need a replacement Plan created?

## Open questions
* Will append-only work? Will it scale?
* How to implement digital signatures?
    * PostgreSQL
        * https://momjian.us/main/blogs/pgblog/2018.html#September_5_2018
        * Chaining signatures should allow deletions to be detected
    * Git
        * https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits
        * https://git-scm.com/book/ms/v2/Git-Tools-Signing-Your-Work
    * Blockchain?
* Data partitioning
    * Supports finite retention, and adds a layer of read-only enforcement
    * Sqlite database per final Container?
    * Different database for every year?
* How can the models provide a complete system while remaining as simple as possible?
* Tracking work: should a `Plan` have:
    * Zero or one `Start`?
    * Zero or more `Update`s?
    * Zero or one `Result`?
* Where should volume constraints be recorded? Enforced?
