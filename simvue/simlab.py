"""
Simvue Laboratory
=================

Module defining sandbox methods for monitoring and logging
on the fly.

"""

import inspect
import sys
import typing
import fnmatch
import types
from simvue import Run


TraceFunction: typing.TypeAlias = typing.Callable[
    [types.FrameType, str, typing.Any], typing.Callable | None
]


# Define a trace function to monitor variables within
# the wrapped executed function
def _create_variable_monitoring_callback(
    previous_values: dict[str, typing.Any],
    simvue_run: Run,
    alert_id: str,
    exclude: list[str] | None,
    include: list[str] | None,
    trace_info_dict: dict[str, typing.Any],
) -> TraceFunction:
    """Function to monitor variables

    Parameters
    ----------
    frame : types.FrameType
        representation of code execution state at a given point in time
    event : str
        event triggered as part of the execution process
    _ : typing.Any

    Returns
    -------
    TraceFunction
        the same function to ensure monitoring is active throughout whole execution
    """
    _input_parameters = trace_info_dict["inputs"]["input_parameters"]
    _function_name = trace_info_dict["inputs"]["function"]

    def _monitor_function(
        frame: types.FrameType,
        event: typing.Literal["call", "line", "return", "exception", "opcode"],
        argument: typing.Any | tuple[Exception, Exception, types.TracebackType],
        **kwargs,
    ) -> TraceFunction:
        if event == "call":
            return _monitor_function  # type: ignore

        # Monitor variables during execution
        # if event is a line or return event
        if event in {"line", "return"}:
            _current_locals = frame.f_locals

            # Compare current local variables with previous values
            for var, value in _current_locals.items():
                # Ignore any private variables or unsupported types
                if var.startswith("_") or not isinstance(value, (int, float, bool)):
                    continue

                # Trigger callback only if an input is modified or a new variable is created
                if any(
                    [
                        (
                            var in _input_parameters
                            and previous_values.get(var) != value
                        ),
                        (var not in previous_values or previous_values[var] != value),
                    ]
                ) and all(
                    [
                        not (
                            any(fnmatch.fnmatch(var, pattern) for pattern in exclude)
                            if exclude
                            else False
                        ),
                        (
                            any(fnmatch.fnmatch(var, pattern) for pattern in include)
                            if include
                            else True
                        ),
                    ]
                ):
                    previous_values[var] = value

                    if var not in trace_info_dict["metrics"]:
                        trace_info_dict["metrics"][var] = []

                    trace_info_dict["metrics"][var].append(value)
                    simvue_run.log_metrics({var: value})

            # Remove variables no longer in scope
            for var in list(previous_values.keys()):
                if var not in _current_locals:
                    del previous_values[var]

        # If an exception is thrown during execution log an event with details
        # and also raise user alert
        elif event == "exception":
            _exception_type, _exception_value, _exception_traceback = argument
            _event_message = (
                f"Function {_function_name} raised an exception:\n"
                f"\t{_exception_type}: {_exception_value}"
                f"\n{_exception_traceback}"
            )
            trace_info_dict["events"].append(_event_message)
            simvue_run.log_event(_event_message)
            simvue_run.log_alert(alert_id, state="critical")
            trace_info_dict["alert"]["state"] = "critical"
            simvue_run.set_status("failed")

        return _monitor_function  # type: ignore

    return _monitor_function  # type: ignore


def trace(
    mode: typing.Literal["online", "offline"] = "online",
    debug: bool = False,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    trace_info_dict: dict[str, typing.Any] | None = None,
    **sv_run_kwargs,
) -> typing.Callable:
    """Decorator to track variable changes within a function and send the new values as metrics to the Simvue server

    Values must be a sorted data type. This includes floats, integers and booleans.

    Parameters
    ----------
    mode: Literal['online', 'offline'], optional
        mode of execution, default is "online"
    debug: bool, optional
        whether to run in debug mode, default is False
    include : list[str], optional
        variable names/regular expressions to include
    exclude : list[str], optional
        variable names/regular expressions to ignore
    **sv_run_kwargs
        keyword arguments to pass to the Simvue Run
    """
    # If the user did not attach a dictionary create one
    # to allow this feature to be monitored in a debugger
    # they just will not be able to access this information
    # outside the wrapped function call
    if not trace_info_dict:
        trace_info_dict = {}

    def decorator(
        func: typing.Callable, trace_info_dict=trace_info_dict
    ) -> typing.Callable:
        def wrapper(*args, trace_info_dict=trace_info_dict, **kwargs) -> typing.Any:
            # Cache for storing current variable values
            _previous_values: dict[str, typing.Any] = {}

            # Retrieve the signature for the input function
            # and bind the arguments to the function signature
            _function_signature: inspect.Signature = inspect.signature(func)
            _bounded_arguments: inspect.BoundArguments = _function_signature.bind(
                *args, **kwargs
            )
            _bounded_arguments.apply_defaults()

            # First record any initial values from the parameters
            # of this input function in case these are modified
            _input_params = _bounded_arguments.arguments
            _previous_values.update(_input_params)

            # Start a Simvue Run
            with Run(mode=mode, debug=debug) as _run:
                # Initialise the run with the provided keyword arguments
                _run.init(**sv_run_kwargs)
                _alert_id: str = _run.create_user_alert(
                    name=f"execute_{func.__name__}",
                    description=f"Executing function {func.__name__} with the following parameters: {_input_params}",
                )

                trace_info_dict |= {
                    "inputs": {
                        "function": func.__name__,
                        "input_parameters": _input_params,
                        "include": include,
                        "exclude": exclude,
                    },
                    "metrics": {},
                    "events": [],
                    "alert": {},
                }

                # Set a trace function to monitor the execution of the wrapped function
                sys.settrace(
                    _create_variable_monitoring_callback(
                        previous_values=_previous_values,
                        simvue_run=_run,
                        alert_id=_alert_id,
                        exclude=exclude,
                        include=include,
                        trace_info_dict=trace_info_dict or {},
                    )
                )
                try:
                    result = func(*args, **kwargs)
                finally:
                    sys.settrace(None)  # Clean up the trace function after execution
            _run.log_alert(_alert_id, state="ok")

            if trace_info_dict:
                trace_info_dict["alert"]["state"] = "ok"
                trace_info_dict["alert"]["id"] = _alert_id
                trace_info_dict["run"] = _run.id
            return result

        return wrapper

    return decorator
