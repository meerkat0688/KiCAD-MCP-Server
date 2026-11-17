"""Offline specification model only; no sensor, flash, Wi-Fi, or LINE driver.

DP-01 clears the median window after invalid/missed samples. Full latch and
event identity survive faults. Monotonic timers never survive restore().
"""

from collections import deque
from dataclasses import dataclass
from math import isfinite
from statistics import median
from typing import Optional
from uuid import uuid4


@dataclass(frozen=True)
class Observation:
    health: str
    full_latched: bool
    distance_mm: Optional[float]
    fill_pct: Optional[float]
    event_id: Optional[str]
    transition: Optional[str]


class Detector:
    def __init__(self, height_mm=None, *, boot_time=0.0,
                 full_latched=False, event_id=None):
        if height_mm is not None and (not isfinite(height_mm) or height_mm <= 0):
            raise ValueError("calibration height must be positive and finite")
        if not isfinite(boot_time):
            raise ValueError("boot time must be finite")
        if bool(full_latched) != bool(event_id):
            raise ValueError("full latch and active event identity must agree")
        self.height_mm = height_mm
        self.full_latched = full_latched
        self.event_id = event_id
        self.boot_time = self.last_call = float(boot_time)
        self.last_sample = self.last_valid = None
        self.samples = deque(maxlen=3)
        self.full_since = self.clear_since = None

    def _time(self, now):
        if not isfinite(now) or now < self.last_call:
            raise ValueError("time must be finite and monotonic")
        self.last_call = now

    def _reset_continuity(self):
        self.samples.clear()
        self.full_since = self.clear_since = None

    def _result(self, now, transition=None):
        if self.height_mm is None:
            health = "UNCALIBRATED"
        elif now - (self.boot_time if self.last_valid is None else self.last_valid) >= 30:
            health = "SENSOR_FAULT"
        elif len(self.samples) < 3:
            health = "WARMUP"
        else:
            health = "OK"
        distance = median(self.samples) if health == "OK" else None
        fill = None if distance is None else max(
            0.0, min(100.0, (self.height_mm-distance)/self.height_mm*100))
        return Observation(health, self.full_latched, distance, fill,
                           self.event_id, transition)

    def tick(self, now):
        """Independent watchdog; must run even when a sensor call times out."""
        self._time(now)
        if self.last_sample is not None and now-self.last_sample > 7.5:
            self._reset_continuity()
        return self._result(now)

    def step(self, now, distance_mm=None, *, valid=True):
        if self.last_sample is not None and now <= self.last_sample:
            raise ValueError("a sample must have a new timestamp")
        self._time(now)
        if self.last_sample is not None and now-self.last_sample > 7.5:
            self._reset_continuity()
        self.last_sample = now
        if (not valid or distance_mm is None or not isfinite(distance_mm)
                or not 40 <= distance_mm <= 4000):
            self._reset_continuity()
            return self._result(now)
        # Bounds only screen the candidate's nominal range. The caller must
        # also supply the real sensor's range status through valid=False.
        self.last_valid = now
        if self.height_mm is None:
            return self._result(now)
        self.samples.append(float(distance_mm))
        result = self._result(now)
        if result.fill_pct is None:
            return result
        transition = None
        if result.fill_pct >= 80:
            self.clear_since = None
            if not self.full_latched:
                if self.full_since is None:
                    self.full_since = now
                if now-self.full_since >= 60:
                    self.full_latched = True
                    self.event_id = str(uuid4())
                    self.full_since = None
                    transition = "full_confirmed"
        else:
            self.full_since = None
        if result.fill_pct <= 50 and self.full_latched:
            if self.clear_since is None:
                self.clear_since = now
            if now-self.clear_since >= 120:
                self.full_latched = False
                self.event_id = None
                self.clear_since = None
                transition = "cleared"
        elif result.fill_pct > 50:
            self.clear_since = None
        return self._result(now, transition)

    def snapshot(self):
        """Only stable state; production firmware needs atomic durable storage."""
        return {"height_mm": self.height_mm,
                "full_latched": self.full_latched, "event_id": self.event_id}

    @classmethod
    def restore(cls, snapshot, boot_time=0.0):
        return cls(**snapshot, boot_time=boot_time)
