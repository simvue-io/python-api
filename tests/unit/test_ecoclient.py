import tempfile
import pytest
import time
import pytest_mock

import simvue.eco.api_client as sv_eco_api
import simvue.eco.emissions_monitor as sv_eco_ems

@pytest.mark.eco
def test_api_client_get_loc_info(mock_co2_signal) -> None:
    _client = sv_eco_api.APIClient()
    assert _client.latitude
    assert _client.longitude
    assert _client.country_code


@pytest.mark.eco
def test_api_client_query(mock_co2_signal: dict[str, dict | str]) -> None:
    _client = sv_eco_api.APIClient()
    _response: sv_eco_api.CO2SignalResponse = _client.get()
    assert _response.carbon_intensity_units == mock_co2_signal["units"]["carbonIntensity"]
    assert _response.country_code == mock_co2_signal["countryCode"]
    assert _response.data.carbon_intensity == mock_co2_signal["data"]["carbonIntensity"]
    assert _response.data.fossil_fuel_percentage == mock_co2_signal["data"]["fossilFuelPercentage"]


@pytest.mark.eco
@pytest.mark.parametrize(
    "refresh", (True, False), ids=("refresh", "no-refresh")
)
def test_outdated_data_check(
    mock_co2_signal,
    refresh: bool,
    mocker: pytest_mock.MockerFixture,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    _spy = mocker.spy(sv_eco_api.APIClient, "get")
    monkeypatch.setattr(sv_eco_ems, "CO2_SIGNAL_API_INTERVAL_LIMIT", 0.1)
    with tempfile.TemporaryDirectory() as tempd:
        _ems_monitor = sv_eco_ems.CO2Monitor(
            thermal_design_power_per_cpu=80,
            thermal_design_power_per_gpu=130,
            local_data_directory=tempd,
            intensity_refresh_interval=1 if refresh else 2,
            co2_intensity=None,
            co2_signal_api_token=None
        )   
        _measure_params = {
            "process_id": "test_outdated_data_check",
            "cpu_percent": 20,
            "gpu_percent": 40,
            "measure_interval": 1
        }
        _ems_monitor.estimate_co2_emissions(**_measure_params)
        time.sleep(3)
        _ems_monitor.estimate_co2_emissions(**_measure_params)

        assert _spy.call_count == 2 if refresh else 1, f"{_spy.call_count} != {2 if refresh else 1}"


def test_co2_monitor_properties(mock_co2_signal) -> None:
    with tempfile.TemporaryDirectory() as tempd:
        _ems_monitor = sv_eco_ems.CO2Monitor(
            thermal_design_power_per_cpu=80,
            thermal_design_power_per_gpu=130,
            local_data_directory=tempd,
            intensity_refresh_interval=1 if refresh else 2,
            co2_intensity=None,
            co2_signal_api_token=None
        )   
        _measure_params = {
            "process_id": "test_outdated_data_check",
            "cpu_percent": 20,
            "gpu_percent": 40,
            "measure_interval": 1
        }
        _ems_monitor.estimate_co2_emissions(**_measure_params)
        assert _ems_monitor.current_carbon_intensity
        assert _ems_monitor.process_data["test_outdated_data_check"]
        assert _ems_monitor.total_power_usage
        assert _ems_monitor.total_co2_emission
        assert _ems_monitor.total_co2_delta
        assert _ems_monitor.total_energy
        assert _ems_monitor.total_energy_delta
