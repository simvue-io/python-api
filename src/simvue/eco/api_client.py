"""
CO2 Signal API Client
=====================

Provides inteface to the CO2 Signal API,
which provides real-time data on the carbon intensity of
electricity generation in different countries.
"""

__date__ = "2025-02-27"

import requests
import pydantic
import functools
import http
import logging
import datetime
import geocoder
import geocoder.location
import typing

CO2_SIGNAL_API_ENDPOINT: str = (
    "https://api.electricitymap.org/v3/carbon-intensity/latest"
)


class CO2SignalData(pydantic.BaseModel):
    datetime: datetime.datetime
    carbon_intensity: float


class CO2SignalResponse(pydantic.BaseModel):
    country_code: str
    data: CO2SignalData
    carbon_intensity_units: str

    @classmethod
    def from_json_response(cls, json_response: dict) -> "CO2SignalResponse":
        _co2_signal_data = CO2SignalData(
            datetime=datetime.datetime.fromisoformat(
                json_response["datetime"].replace("Z", "+00:00")
            ),
            carbon_intensity=json_response["carbonIntensity"],
        )
        return cls(
            country_code=json_response["zone"],
            data=_co2_signal_data,
            carbon_intensity_units="gCO2e/kWh",
        )


@functools.lru_cache()
def _call_geocoder_query() -> typing.Any:
    """Call GeoCoder API for IP location

    Cached so this API is only called once per session as required.
    """
    return geocoder.ip("me")


class APIClient(pydantic.BaseModel):
    """
    CO2 Signal API Client

    Provides an interface to the Electricity Maps API.
    """

    co2_api_endpoint: pydantic.HttpUrl = pydantic.HttpUrl(CO2_SIGNAL_API_ENDPOINT)
    co2_api_token: pydantic.SecretStr | None = None
    timeout: pydantic.PositiveInt = 10

    def __init__(self, *args, **kwargs) -> None:
        """Initialise the CO2 Signal API client.

        Parameters
        ----------
        co2_api_endpoint : str
            endpoint for CO2 signal API
        co2_api_token: str
            The API token for the ElectricityMaps API, default is None.
        timeout : int
            timeout for API
        """
        super().__init__(*args, **kwargs)
        self._logger = logging.getLogger(self.__class__.__name__)

        if not self.co2_api_token:
            raise ValueError("API token is required for ElectricityMaps API.")

        self._get_user_location_info()

    def _get_user_location_info(self) -> None:
        """Retrieve location information for the current user."""
        self._logger.info("📍 Determining current user location.")
        _current_user_loc_data: geocoder.location.BBox = _call_geocoder_query()
        self._latitude: float
        self._longitude: float
        self._latitude, self._longitude = _current_user_loc_data.latlng
        self._two_letter_country_code: str = _current_user_loc_data.country  # type: ignore

    def get(self) -> CO2SignalResponse:
        """Get the current data"""
        _params: dict[str, float | str] = {
            "zone": self._two_letter_country_code,
        }

        if self.co2_api_token:
            _params["auth-token"] = self.co2_api_token.get_secret_value()

        self._logger.debug(f"🍃 Retrieving carbon intensity data for: {_params}")
        _response = requests.get(f"{self.co2_api_endpoint}", headers=_params)

        if _response.status_code != http.HTTPStatus.OK:
            try:
                _error = _response.json()["error"]
            except (AttributeError, KeyError):
                _error = _response.text
            raise RuntimeError(
                f"[{_response.status_code}] Failed to retrieve current CO2 signal data for"
                f" country '{self._two_letter_country_code}': {_error}"
            )

        return CO2SignalResponse.from_json_response(_response.json())

    @property
    def country_code(self) -> str:
        """Returns the country code"""
        return self._two_letter_country_code

    @property
    def latitude(self) -> float:
        """Returns current latitude"""
        return self._latitude

    @property
    def longitude(self) -> float:
        """Returns current longitude"""
        return self._longitude
