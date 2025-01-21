"""
Simvue Laboratory
=================

Module defining sandbox methods for monitoring and logging
on the fly.

"""

import inspect
import sys
import typing
import types
from simvue import Run


TraceFunction: typing.TypeAlias = typing.Callable[[types.FrameType, str, typing.Any], typing.Callable | None]

# Define a trace function to monitor variables within
# the wrapped executed function
def _create_variable_monitoring_callback(
    input_parameters: dict[str, typing.Any],
    previous_values: dict[str, typing.Any],
    simvue_run: Run,
    alert_id: str,
    function_name: str,
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
    def _monitor_function(
        frame: types.FrameType,
        event: typing.Literal["call", "line", "return", "exception", "opcode"],
        argument: typing.Any | tuple[Exception, Exception, types.TracebackType]
    ) -> TraceFunction:
        if event == "call":
            return _monitor_function # type: ignore
        
        # Monitor variables during execution
        # if event is a line or return event
        if event in {"line", "return"}:
            _current_locals = frame.f_locals
            
            # Compare current local variables with previous values
            for var, value in _current_locals.items():
                # Ignore any private variables or unsupported types
                if any([
                    var.startswith("_") or not isinstance(value, (int, float, bool, dict)),
                    isinstance(value, dict) and not all(isinstance(v, (int, float, bool)) for v in value.values())
                ]):
                    continue

                # Trigger callback only if an input is modified or a new variable is created
                if any([
                    (var in input_parameters and previous_values.get(var) != value),
                    (var not in previous_values and var not in input_parameters)
                ]):
                    previous_values[var] = value
                    
                    if isinstance(value, dict):
                        simvue_run.log_metrics(value)
                    else:
                        simvue_run.log_metrics({var: value})
            
            # Remove variables no longer in scope
            for var in list(previous_values.keys()):
                if var not in _current_locals:
                    del previous_values[var]
        
        # If an exception is thrown during execution log an event with details
        # and also raise user alert
        elif event == "exception":
            _exception_type, _exception_value, _exception_traceback = argument
            simvue_run.log_event(
                f"Function {function_name} raised an exception:\n"
                f"\t{_exception_type}: {_exception_value}"
                f"\n{_exception_traceback}"
            )
            simvue_run.log_alert(alert_id, state="critical")
            simvue_run.set_status("failed")

        return _monitor_function  # type: ignore
    return _monitor_function # type: ignore

def trace(
    mode: typing.Literal["online", "offline"] = "online",
    debug: bool = False, **sv_run_kwargs
) -> typing.Callable:
    """Decorator to track variable changes within a function and send the new values as metrics to the Simvue server
    
    Values must be a sorted data type. This includes floats, integers and booleans.

    Parameters
    ----------
    mode: Literal['online', 'offline'], optional
        mode of execution, default is "online"
    debug: bool, optional
        whether to run in debug mode, default is False
    **sv_run_kwargs
        keyword arguments to pass to the Simvue Run
    """
    def decorator(func: typing.Callable) -> typing.Callable:
        def wrapper(*args, **kwargs) -> typing.Any:
            # Cache for storing current variable values
            _previous_values: dict[str, typing.Any] = {}

            # Retrieve the signature for the input function
            # and bind the arguments to the function signature
            _function_signature: inspect.Signature = inspect.signature(func)
            _bounded_arguments: inspect.BoundArguments = _function_signature.bind(*args, **kwargs)
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

                # Set a trace function to monitor the execution of the wrapped function
                sys.settrace(
                    _create_variable_monitoring_callback(
                        _input_params,
                        _previous_values,
                        _run,
                        _alert_id,
                        func.__name__
                    )
                )
                try:
                    result = func(*args, **kwargs)
                finally:
                    sys.settrace(None)  # Clean up the trace function after execution
            _run.log_alert(_alert_id, state="ok")
            return result
        return wrapper
    return decorator
