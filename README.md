# Well Plated

Python Django models for liquid in plates and tubes

For planning what should happen, with strong constraints, and tracking what actually happened.

## TODO
* Well-in-range database constraints
* Pre-barcoded containers (externally generated codes)
* JSONField constraints for [OR Tools](https://developers.google.com/optimization/cp/cp_example) to
  check or optimize. start and end purpose formats will be special cases allowing infinite
  volume out and in.
* Enforce append-only behavior for most or all models/tables by continuing to grant SELECT and
  INSERT permissions but revoking UPDATE permission
* Examples of attaching common measurements to Wells
* Start datetimes and durations
* Plans for transfers and measurements and corresponding queries:
    * What Plans have been started and need finishing?
    * What Plans haven't been started yet?
    * What Plans were canceled before they were finished, or finished with a failure, and need a replacement Plan created?

## Open questions
* Will append-only work? Will it scale? Is there a better way like a sqlite database per final Container?
* Cryptographic signing?
* How can the models provide a complete system while remaining as simple as possible?
* How to enforce the same constraints at all levels:
    * At the database
    * In Django models
    * In non-Django Python code (like REST Framework API clients)
    * In web interfaces https://developer.mozilla.org/en-US/docs/Web/HTML/Attributes/pattern
* Tracking work: should a `Plan` have:
    * Zero or one `Start`?
    * Zero or more `Update`s?
    * Zero or one `Result`?
