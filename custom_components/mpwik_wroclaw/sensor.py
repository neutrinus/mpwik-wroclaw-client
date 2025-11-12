"""Sensor platform for MPWiK Wrocław integration."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MPWiKDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MPWiK Wrocław sensors based on a config entry."""
    coordinator: MPWiKDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        MPWiKDailyConsumptionSensor(coordinator, entry),
        MPWiKHourlyConsumptionSensor(coordinator, entry),
        MPWiKTotalConsumptionSensor(coordinator, entry),
        MPWiKLastReadingSensor(coordinator, entry),
    ]

    async_add_entities(sensors)


class MPWiKSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for MPWiK sensors."""

    def __init__(
        self,
        coordinator: MPWiKDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entry = entry
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"MPWiK Wrocław - {entry.data['username']}",
            "manufacturer": "MPWiK Wrocław",
            "model": "Water Meter",
        }


class MPWiKDailyConsumptionSensor(MPWiKSensorBase):
    """Sensor for daily water consumption."""

    _attr_name = "Daily Consumption"
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:water"

    def __init__(
        self,
        coordinator: MPWiKDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_daily_consumption"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("latest_daily_consumption")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None
        
        attrs = {}
        if date := self.coordinator.data.get("latest_daily_date"):
            attrs["reading_date"] = date
        if reading := self.coordinator.data.get("latest_daily_reading"):
            attrs["meter_reading"] = reading
        
        return attrs


class MPWiKHourlyConsumptionSensor(MPWiKSensorBase):
    """Sensor for latest hourly water consumption."""

    _attr_name = "Hourly Consumption"
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:water-outline"

    def __init__(
        self,
        coordinator: MPWiKDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_hourly_consumption"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("latest_hourly_consumption")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None
        
        attrs = {}
        if date := self.coordinator.data.get("latest_hourly_date"):
            attrs["reading_date"] = date
        if reading := self.coordinator.data.get("latest_hourly_reading"):
            attrs["meter_reading"] = reading
        
        return attrs


class MPWiKTotalConsumptionSensor(MPWiKSensorBase):
    """Sensor for total water consumption."""

    _attr_name = "Total Consumption"
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:water-pump"

    def __init__(
        self,
        coordinator: MPWiKDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_total_consumption"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        # Use the latest meter reading as the total
        return self.coordinator.data.get("latest_daily_reading")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None
        
        attrs = {}
        if date := self.coordinator.data.get("latest_daily_date"):
            attrs["reading_date"] = date
        
        # Include period consumption
        if consumption := self.coordinator.data.get("total_consumption"):
            attrs["period_consumption"] = consumption
        
        return attrs


class MPWiKLastReadingSensor(MPWiKSensorBase):
    """Sensor for last reading timestamp."""

    _attr_name = "Last Reading"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        coordinator: MPWiKDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_reading"

    @property
    def native_value(self) -> datetime | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        
        # Try to get the latest reading date
        date_str = self.coordinator.data.get("latest_daily_date")
        if not date_str:
            date_str = self.coordinator.data.get("latest_hourly_date")
        
        if date_str:
            try:
                # Parse ISO format datetime
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                _LOGGER.warning(f"Failed to parse date: {date_str}")
        
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None
        
        attrs = {}
        if last_update := self.coordinator.data.get("last_update"):
            attrs["last_update"] = last_update
        
        return attrs
