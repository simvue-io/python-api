# Change log

## v0.7.0

* Collect CPU, GPU and memory resource metrics.
* Automatically delete temporary files used in offline mode once runs have entered a terminal state.
* Warn users if their access token has expired.
* Remove dependency on the randomname module, instead handle name generation server side.

## v0.6.0

* `offline` and `disabled` options replaced with single `mode` flag.

## v0.5.0

* Added option to disable all monitoring.

## v0.4.0

* Offline mode added, enabling tracking of simulations running on worker nodes without outgoing network access.
* Argument to `init` enabling runs to be left in the `created` state changed from `status="created"` to `running=True`.
* Improvements to error handling.

## v0.3.0

* Update `add_alert` method to support either metrics or events based alerts.

## v0.2.0

* The previous `Simvue` class has been split into `Run` and `Client`. When creating a run use the new `Run` class rather than `Simvue`.

## v0.1.0

* First release.
