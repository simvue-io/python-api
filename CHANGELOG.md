# Change Log

## Unreleased

- Added ability to specify above one server in the `simvue.toml` file using `profiles`.
- Enforced keyword arguments for readability and certainty in intent within initialiser for `simvue.Run`.

## [v2.3.0](https://github.com/simvue-io/client/releases/tag/v2.3.0) - 2025-12-11

- Refactored sender functionality introducing new `Sender` class.
- Added missing `created` property to `User` and `Tenant` LLAPI objects.

## [v2.2.4](https://github.com/simvue-io/client/releases/tag/v2.2.4) - 2025-11-13

- Added fixes for future servers which disallow extra arguments in requests.

## [v2.2.3](https://github.com/simvue-io/client/releases/tag/v2.2.3) - 2025-11-10

- Use `msgpack` for `GridMetrics` in a manner similar to `Metrics`.
- Fix incorrect setting of global log level.
- Fix alert duplication in offline mode and other offline fixes.

## [v2.2.2](https://github.com/simvue-io/client/releases/tag/v2.2.2) - 2025-10-14

- Enforced use of UTC for all datetime recording.
- Added support for Python3.14.

## ~~[v2.2.1](https://github.com/simvue-io/client/releases/tag/v2.2.1) - 2025-10-13~~

**Broken release yanked from PyPi**

## [v2.2.0](https://github.com/simvue-io/client/releases/tag/v2.2.0) - 2025-09-22

- Improves handling of Conda based environments in metadata collection.
- Adds additional options to `Client.get_runs`.
- Added ability to include environment variables within metadata for runs.
- Added new feature allowing users to log tensors as multidimensional metrics after defining a grid.
- Improves checks on `offline.cache` directory specification in config file.
- Added ability to upload multiple runs as a batch via the low level API.

## [v2.1.2](https://github.com/simvue-io/client/releases/tag/v2.1.2) - 2025-06-25

- Fixed issue in downloading files from tenant runs.
- Fixed bug in pagination whereby the count value specified by the user is ignored.
- Fixed bug where uploading larger files timed out leading to file of size 0B.
- Fixed bug where if the range or threshold of an alert is zero the alert type validation fails.
- Fixed bug in `Folder.ids` where `kwargs` were not being passed to `GET`.
- Ensured all threads have `daemon=True` to prevent hanging on termination.
- Added error when `close()` method is called within the `simvue.Run` context manager.

## [v2.1.1](https://github.com/simvue-io/client/releases/tag/v2.1.1) - 2025-04-25

- Changed from CO2 Signal to ElectricityMaps
- Fixed a number of bugs in how offline mode is handled with emissions
- Streamlined EmissionsMonitor class and handling
- Fixed bugs in client getting results from Simvue server arising from pagination
- Fixed bug in setting visibility in `run.init` method
- Default setting in `Client.get_runs` is now `show_shared=True`

## [v2.1.0](https://github.com/simvue-io/client/releases/tag/v2.1.0) - 2025-03-28

- Removed CodeCarbon dependence in favour of a slimmer solution using the CO2 Signal API.
- Added sorting to server queries, users can now specify to sort by columns during data retrieval from the database.
- Added pagination of results from server to reduce await time in responses.
- Added equivalent of folder details modification function to `Client` class.

## [v2.0.1](https://github.com/simvue-io/client/releases/tag/v2.0.1) - 2025-03-24

- Improvements to docstrings on methods, classes and functions.

## [v2.0.0](https://github.com/simvue-io/client/releases/tag/v2.0.0) - 2025-03-07

- Add new example notebooks
- Update and refactor examples to work with v2.0
- Fix bug in offline artifacts using wrong file path
- Change names of sustainability metrics
- Fix `Self` being used in typing Generators so that Simvue works with Python 3.10 in Conda
- Updated codecarbon to work with new API
- Codecarbon now works with offline mode
- Codecarbon metadata dict is now nested
- Add PID to sender lock file so it can recover from crashes
- Add accept Gzip encoding
- Fixed list of processes to add / remove from existing list of objects
- Add step to resource metrics
- Fix bug where process user alerts should not be overridden if manually set by the user
- Removed 'no config file' and 'unstaged changes' warnings from Offline mode as they do not apply
- Made `staging_check` not apply in Offline mode
- Added heartbeat functionality to Offline mode
- Moved away from `FlatDict` module for metadata collection, fixes Simvue in Jupyter notebooks
- Fixed `reconnect()` by setting `read_only` to False and added tests
- Fixed resource metrics collection to return measurement on startup and use short interval for more accurate measurements
- Fixed `set_pid` so that resource metrics are also collected for child processes of it
- Improved sender by having all cached files read at start and lock file so only one sender runs at once
- Added `name` option in `log_alert` and added tests
- Fixed client `get_alerts` and improved tests
- Removed all server config checks in Offline mode
- Fixed `add_alerts` so that it now works with both IDs and names
- Improved alert and folder deduplication methods to rely on 409 responses from server upon creation
- Added `attach_to_run` option to create alerts methods so that alerts can be created without a run attached
- Improved merging of local staging file and \_staged dict using `deepmerge` - fixes bugs with tags, alerts and metadata in offline mode
- Added `started`, `created` and `ended` timestamps to runs in offline mode
- Remove all erronous server calls in offline mode
- Fixed method to find simvue.toml config files, now just looks in cwd and home
- Added run notification option to `run.init` so that users can now get emails upon their runs completing
- Fixed artifact retrieval by run so that `category` parameter works correctly
- Fixed bug where file artifacts wouldn't be saved correctly in offline mode if sender runs in different location to script
- Fixed bug where DEBUG log messages were spamming to the console
- Fixed link to run dashboard printed to the console by removing `/api`
- Fixed bug where offline mode wouldn't work if no run name provided
- Fixed bug where errors would be thrown if a traceback was logged as an event when a run was already terminated
- Fixed hierarchical artifact retrieval to maintain directory structure
- Loosened Numpy requirement to >2.0.0
- Add support for defining Simvue run defaults using `tool.simvue` in a project `pyproject.toml` file.
- Drop support for INI based configuration files.
- Retrieve all metric values if `max_points` is unspecified or set to `None`.
- Add support for PyTorch in Python 3.13
- Create lower level API for directly interacting with the Simvue RestAPI endpoints.
- **Removes support for Python <3.10 due to dependency constraints.**
- Separates `create_alert` into specific methods `create_event_alert` etc.
- Adds additional functionality and support for offline mode.
- Support for Simvue servers `>=3`.

## [v1.1.4](https://github.com/simvue-io/python-api/releases/tag/v1.1.4) - 2024-12-11

- Remove incorrect identifier reference for latest Simvue servers during reconnection.
- Fixed missing online mode selection when retrieving configuration for `Client` class.

## [v1.1.3](https://github.com/simvue-io/python-api/releases/tag/v1.1.3) - 2024-12-09

- Fixed bug with `requirements.txt` metadata read.
- Added Simvue server version check.
- Remove checking of server version in offline mode and add default run mode to configuration options.
- Fix offline mode class initialisation, and propagation of configuration.

## [v1.1.2](https://github.com/simvue-io/python-api/releases/tag/v1.1.2) - 2024-11-06

- Fix bug in offline mode directory retrieval.

## [v1.1.1](https://github.com/simvue-io/python-api/releases/tag/v1.1.1) - 2024-10-22

- Add missing `offline.cache` key to TOML config.
- Fix repetition of server URL validation for each call to configuration.

## [v1.1.0](https://github.com/simvue-io/python-api/releases/tag/v1.1.0) - 2024-10-21

- Add option to specify a callback executed when an alert is triggered for a run.
- Allow retrieval of all alerts when no constraints are specified.
- Add carbon emissions statistics as optional metrics.
- Include Python and Rust environment metadata.
- Allow the disabling of heartbeat to allow runs to continue indefinitely.
- Verify Simvue server URL as early as possible.
- Indicate the source used for token and URL.
- Migrate to `simvue.toml` from `simvue.ini`, allowing more defaults to be set during runs.

## [v1.0.6](https://github.com/simvue-io/python-api/releases/tag/v1.0.6) - 2024-10-10

- Fix incorrect usage of `retry` when attempting connections to the server.

## [v1.0.5](https://github.com/simvue-io/python-api/releases/tag/v1.0.5) - 2024-10-09

- Ensure all functionality is deactivated when mode is set to `disabled`.
- When an exception is thrown an event is sent to Simvue displaying the traceback.
- If `add_process` is used and an exception is thrown, `.err` and `.out` files are still uploaded.

## [v1.0.4](https://github.com/simvue-io/python-api/releases/tag/v1.0.4) - 2024-09-24

- Set resource metrics to be recorded by default.

## [v1.0.3](https://github.com/simvue-io/python-api/releases/tag/v1.0.3) - 2024-09-23

- Fix issue of hanging threads when exception raised by script using the API.

## [v1.0.2](https://github.com/simvue-io/python-api/releases/tag/v1.0.2) - 2024-08-21

- Fix incorrect HTTP status code in `Client` when checking if object exists.
- Fix issue with `running=False` when launching a `Run` caused by incorrect system metadata being sent to the server.

## [v1.0.1](https://github.com/simvue-io/python-api/releases/tag/v1.0.1) - 2024-07-16

- Fix to `add_process` with list of strings as arguments, the executable no longer returns the string `"None"`.
- Fix callbacks and triggers for `add_process` being executed only on `Run` class termination, not on process completion.

## [v1.0.0](https://github.com/simvue-io/python-api/releases/tag/v1.0.0) - 2024-06-14

- Refactor and re-write of codebase to align with latest developments in version 2 of the Simvue server.
- Added `Executor` to Simvue runs allowing users to start shell based processes as part of a run and handle termination of these.
- Removal of obsolete functions due to server change, and renaming of functions and parameters (see [documentation](https://docs.simvue.io)).
- Added pre-request validation to both `Client` and `Run` class methods via Pydantic.
- Separation of save functionality into `save_file` and `save_object`.
- Fixed issue whereby metrics would still have to wait for the next iteration of dispatch before being sent to the server, even if the queue was not full.
- Added support for `'user'` alerts.

## [v0.14.3](https://github.com/simvue-io/python-api/releases/tag/v0.14.3) - 2023-06-29

- Ensure import of the `requests` module is only done if actually used.

## [v0.14.0](https://github.com/simvue-io/python-api/releases/tag/v0.14.0) - 2023-04-04

- Added a method to the `Client` class for retrieving events.

## [v0.13.3](https://github.com/simvue-io/python-api/releases/tag/v0.13.3) - 2023-04-04

- Allow files (`input` and `code` only) to be saved for runs in the `created` state.
- Allow metadata and tags to be updated for runs in the `created` state.

## [v0.13.2](https://github.com/simvue-io/python-api/releases/tag/v0.13.2) - 2023-04-04

- Added `plot_metrics` method to the `Client` class to simplify plotting metrics.
- (Bug fix) `reconnect` works without a uuid being specified when `offline` mode isn't being used.
- (Bug fix) Restrict version of Pydantic to prevent v2 from accidentally being used.

## [v0.13.1](https://github.com/simvue-io/python-api/releases/tag/v0.13.1) - 2023-03-28

- Set `sample_by` to 0 by default (no sampling) in `get_metrics_multiple`.

## [v0.13.0](https://github.com/simvue-io/python-api/releases/tag/v0.13.0) - 2023-03-28

- Added methods to the `Client` class for retrieving metrics.
- CPU architecture and processor obtained on Apple hardware.
- Client now reports to server when files have been successfully uploaded.
- `User-Agent` header now included in HTTP requests.

## [v0.12.0](https://github.com/simvue-io/python-api/releases/tag/v0.12.0) - 2023-03-13

- Add methods to the `Client` class for deleting runs and folders.
- Confusing messages about `process no longer exists` or `NVML Shared Library Not Found` no longer displayed.

## [v0.11.4](https://github.com/simvue-io/python-api/releases/tag/v0.11.4) - 2023-03-13

- (Bug fix) Ensure `simvue_sender` can be run when installed from PyPI.
- (Bug fix) Runs created in `offline` mode using a context manager weren't automatically closed.

## [v0.11.3](https://github.com/simvue-io/python-api/releases/tag/v0.11.3) - 2023-03-07

- Added logging messages for debugging when debug level set to `debug`.

## [v0.11.2](https://github.com/simvue-io/python-api/releases/tag/v0.11.2) - 2023-03-06

- Raise exceptions in `Client` class methods if run does not exist or artifact does not exist.
- (Bug fix) `list_artifacts` optional category restriction now works.

## [v0.11.1](https://github.com/simvue-io/python-api/releases/tag/v0.11.1) - 2023-03-05

- Support different runs having different metadata in `get_runs` dataframe output.
- (Bug fix) Error message when creating a duplicate run is now more clear.
- (Bug fix) Correction to stopping the worker thread in situations where the run never started.

## [v0.11.0](https://github.com/simvue-io/python-api/releases/tag/v0.11.0) - 2023-03-04

- Support optional dataframe output from `get_runs`.

## [v0.10.1](https://github.com/simvue-io/python-api/releases/tag/v0.10.1) - 2023-03-03

- The worker process now no longer gives a long delay when a run has finished (now at most ~1 second).
- The worker process ends when the `Run()` context ends or `close` is called, rather than only when the main process exits.

## [v0.10.0](https://github.com/simvue-io/python-api/releases/tag/v0.10.0) - 2023-02-07

- The `client` class can now be used to retrieve runs.

## [v0.9.1](https://github.com/simvue-io/python-api/releases/tag/v0.9.1) - 2023-01-25

- (Bug fix) Retries in POST/PUTs to REST APIs didn't happen.
- Warn users if `allow_pickle=True` is required.

## [v0.9.0](https://github.com/simvue-io/python-api/releases/tag/v0.9.0) - 2023-01-25

- Set status to `failed` or `terminated` if the context manager is used and there is an exception.

## [v0.8.0](https://github.com/simvue-io/python-api/releases/tag/v0.8.0) - 2023-01-23

- Support NumPy arrays, PyTorch tensors, Matplotlib and Plotly plots and picklable Python objects as artifacts.
- (Bug fix) Events in offline mode didn't work.

## [v0.7.2](https://github.com/simvue-io/python-api/releases/tag/v0.7.2) - 2023-01-08

- Pydantic model is used for input validation.
- Support NaN, -inf and inf in metadata and metrics.

## [v0.7.0](https://github.com/simvue-io/python-api/releases/tag/v0.7.0) - 2022-12-05

- Collect CPU, GPU and memory resource metrics.
- Automatically delete temporary files used in offline mode once runs have entered a terminal state.
- Warn users if their access token has expired.
- Remove dependency on the randomname module, instead handle name generation server side.

## [v0.6.0](https://github.com/simvue-io/python-api/releases/tag/v0.6.0) - 2022-11-07

- `offline` and `disabled` options replaced with single `mode` flag.

## [v0.5.0](https://github.com/simvue-io/python-api/releases/tag/v0.5.0) - 2022-11-03

- Added option to disable all monitoring.

## [v0.4.0](https://github.com/simvue-io/python-api/releases/tag/v0.4.0) - 2022-11-03

- Offline mode added, enabling tracking of simulations running on worker nodes without outgoing network access.
- Argument to `init` enabling runs to be left in the `created` state changed from `status="created"` to `running=True`.
- Improvements to error handling.

## [v0.3.0](https://github.com/simvue-io/python-api/releases/tag/v0.3.0) - 2022-10-31

- Update `add_alert` method to support either metrics or events based alerts.

## [v0.2.0](https://github.com/simvue-io/python-api/releases/tag/v0.2.0) - 2022-10-26

- The previous `Simvue` class has been split into `Run` and `Client`. When creating a run use the new `Run` class rather than `Simvue`.

## [v0.1.0](https://github.com/simvue-io/client/releases/tag/v0.1.0) - 2022-10-25

- First release.
