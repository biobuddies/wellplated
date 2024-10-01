# Well Plated

Python Django models for planning and tracking liquid transfers.

## TODO
* Generate N (default 1) containers using barcode_format and select_for_update on ContainerType.last_number
* JSONField constraints for [OR Tools](https://developers.google.com/optimization/cp/cp_example) to check or optimize. `ContainerType.get_untracked()` should be a special case allowing infinite volume in and out.
* Enforce append-only behavior for most or all models/tables by continuing to grant SELECT and INSERT permissions but revoking UPDATE permission
* Volume and absorbance measurements
* Additional measurements
* Duration measurements and aggregations
* Todo list queries:
    * What Plans have been started and need finishing?
    * What Plans haven't been started yet?
    * What Plans were canceled before they were finished, or finished with a failure, and need a replacement Plan created?

## Open questions
* Will append-only work? Will it scale?
* How can the models provide a complete system while remaining as simple as possible? Should ContainerType be replaced or augmented by PlanType which can define constraints for all the Containers in a Plan (and their Wells)?
* Tracking work: should a `Plan` have:
    * Zero or one `Start`?
    * Zero or more `Update`s?
    * Zero or one `Result`?
