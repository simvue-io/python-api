import pytest
import time
import simvue.simlab as sv_lab

@pytest.mark.simlab
def test_simlab_trace() -> None:
    @sv_lab.trace()
    def my_simulation(time_interval: float, n_steps: int) -> None:
        _private_value = 0
        monitored_dict = {"x": 0, "y": 0}
        monitored_int = 2
        monitored_float = 3.0
        monitored_bool = True

        for i in range(n_steps):
            time.sleep(time_interval)
            monitored_dict["x"] += i**2
            monitored_dict["y"] += i**3
            monitored_int += i
            monitored_float += i * 2.0
            monitored_bool = not monitored_bool
            _private_value += i

    my_simulation(0.1, 5)
