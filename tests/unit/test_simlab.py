import pytest
import time
import typing
import simvue.simlab as sv_lab

@pytest.mark.simlab
@pytest.mark.parametrize("mode", ["include", "exclude", "normal"])
def test_simlab_trace(mode: typing.Literal["include", "exclude", "normal"]) -> None:
    _trace_info_dict = {}
    _exclude = ["ignored_*"] if mode == "exclude" else None
    _include = ["monitored_*"] if mode == "include" else None
    @sv_lab.trace(exclude=_exclude, include=_include, trace_info_dict=_trace_info_dict)
    def my_simulation(time_interval: float, n_steps: int) -> None:
        _private_value = 0
        monitored_float = 1.0
        monitored_int = 2
        ignored_int = 3
        passive_float = 3.0
        monitored_bool = True

        for i in range(n_steps):
            time.sleep(time_interval)
            monitored_float += i**2
            monitored_int += i
            passive_float += i * 2.0
            ignored_int += i * 4
            monitored_bool = not monitored_bool
            _private_value += i

    my_simulation(0.1, 5)

    assert len(_trace_info_dict.get("metrics", {}).get("monitored_float")) == 5

    if mode == "exclude":
        assert not any(
            k.startswith("ignored_") for k in _trace_info_dict["metrics"]
        )
        assert any(
            k.startswith("monitored_") for k in _trace_info_dict["metrics"]
        )
        assert any(
           k.startswith("passive_") for k in _trace_info_dict["metrics"]
        )
    elif mode == "include":
        assert any(
            k.startswith("monitored_") for k in _trace_info_dict["metrics"]
        )
        assert not any(
            k.startswith("passive_") for k in _trace_info_dict["metrics"]
        )
    else:
        assert any(
            k.startswith("monitored_") for k in _trace_info_dict["metrics"]
        )
        assert any(
            k.startswith("ignored_") for k in _trace_info_dict["metrics"]
        )
        assert any(
            k.startswith("passive_") for k in _trace_info_dict["metrics"]
        )

    assert not any(
        k.startswith("_") for k in _trace_info_dict["metrics"]
    )
