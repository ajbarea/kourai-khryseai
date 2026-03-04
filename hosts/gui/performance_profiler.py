"""Performance profiler for monitoring GUI performance."""

import time
from collections import deque


class PerformanceProfiler:
    """Monitors GUI performance metrics."""

    def __init__(self, max_samples: int = 100):
        """Initialize performance profiler.

        Args:
            max_samples: Maximum number of frame samples to keep.
        """
        self.max_samples = max_samples
        self.frame_times = deque(maxlen=max_samples)
        self.component_times: dict[str, deque] = {}
        self.frame_start: float | None = None
        self.target_fps = 60
        self.target_frame_time = 1.0 / self.target_fps

    def start_frame(self) -> None:
        """Start frame timing."""
        self.frame_start = time.perf_counter()

    def end_frame(self) -> None:
        """End frame timing and record frame time."""
        if self.frame_start is None:
            return

        frame_time = (time.perf_counter() - self.frame_start) * 1000  # Convert to ms
        self.frame_times.append(frame_time)

    def start_component(self, component_name: str) -> None:
        """Start timing a component.

        Args:
            component_name: Name of the component.
        """
        if component_name not in self.component_times:
            self.component_times[component_name] = deque(maxlen=self.max_samples)

        # Store start time in a temporary attribute
        setattr(self, f"_start_{component_name}", time.perf_counter())

    def end_component(self, component_name: str) -> None:
        """End timing a component.

        Args:
            component_name: Name of the component.
        """
        start_attr = f"_start_{component_name}"
        if not hasattr(self, start_attr):
            return

        start_time = getattr(self, start_attr)
        component_time = (time.perf_counter() - start_time) * 1000  # Convert to ms

        if component_name not in self.component_times:
            self.component_times[component_name] = deque(maxlen=self.max_samples)

        self.component_times[component_name].append(component_time)
        delattr(self, start_attr)

    def get_fps(self) -> float:
        """Get current FPS.

        Returns:
            Frames per second.
        """
        if not self.frame_times:
            return 0.0

        avg_frame_time = sum(self.frame_times) / len(self.frame_times)
        return 1000.0 / avg_frame_time if avg_frame_time > 0 else 0.0

    def get_average_frame_time(self) -> float:
        """Get average frame time in milliseconds.

        Returns:
            Average frame time in ms.
        """
        if not self.frame_times:
            return 0.0

        return sum(self.frame_times) / len(self.frame_times)

    def get_max_frame_time(self) -> float:
        """Get maximum frame time in milliseconds.

        Returns:
            Maximum frame time in ms.
        """
        if not self.frame_times:
            return 0.0

        return max(self.frame_times)

    def get_min_frame_time(self) -> float:
        """Get minimum frame time in milliseconds.

        Returns:
            Minimum frame time in ms.
        """
        if not self.frame_times:
            return 0.0

        return min(self.frame_times)

    def get_component_average_time(self, component_name: str) -> float:
        """Get average time for a component in milliseconds.

        Args:
            component_name: Name of the component.

        Returns:
            Average component time in ms.
        """
        if component_name not in self.component_times:
            return 0.0

        times = self.component_times[component_name]
        if not times:
            return 0.0

        return sum(times) / len(times)

    def get_component_max_time(self, component_name: str) -> float:
        """Get maximum time for a component in milliseconds.

        Args:
            component_name: Name of the component.

        Returns:
            Maximum component time in ms.
        """
        if component_name not in self.component_times:
            return 0.0

        times = self.component_times[component_name]
        return max(times) if times else 0.0

    def get_performance_report(self) -> dict:
        """Get comprehensive performance report.

        Returns:
            Dictionary with performance metrics.
        """
        return {
            "fps": self.get_fps(),
            "avg_frame_time_ms": self.get_average_frame_time(),
            "max_frame_time_ms": self.get_max_frame_time(),
            "min_frame_time_ms": self.get_min_frame_time(),
            "target_fps": self.target_fps,
            "target_frame_time_ms": self.target_frame_time * 1000,
            "components": {
                name: {
                    "avg_ms": self.get_component_average_time(name),
                    "max_ms": self.get_component_max_time(name),
                }
                for name in self.component_times
            },
        }

    def is_meeting_target_fps(self) -> bool:
        """Check if meeting target FPS.

        Returns:
            True if average FPS meets target.
        """
        return self.get_fps() >= self.target_fps * 0.95  # Allow 5% variance

    def reset(self) -> None:
        """Reset all profiling data."""
        self.frame_times.clear()
        self.component_times.clear()
