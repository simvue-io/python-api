# Change log

## v0.11.1

* Support different runs having different metadata in `get_runs` dataframe output.
* (Bug fix) Error message when creating a duplicate run is now more clear.
* (Bug fix) Correction to stopping the worker thread in situations where the run never started.

## v0.11.0

* Support optional dataframe output from `get_runs`.

## v0.10.1

* The worker process now no longer gives a long delay when a run has finished (now at most ~1 second).
* The worker process ends when the `Run()` context ends or `close` is called, rather than only when the main process exits.

## v0.10.0

* The `client` class can now be used to retrieve runs.

## v0.9.1

* (Bug fix) Retries in POST/PUTs to REST APIs didn't happen.
* Warn users if `allow_pickle=True` is required.

## v0.9.0

* Set status to `failed` or `terminated` if the context manager is used and there is an exception.

## v0.8.0

* Support NumPy arrays, PyTorch tensors, Matplotlib and Plotly plots and picklable Python objects as artifacts.
* (Bug fix) Events in offline mode didn't work.

## v0.7.2

* Pydantic model is used for input validation.
* Support NaN, -inf and inf in metadata and metrics.

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
