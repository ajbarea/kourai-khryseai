"""Tests for performance profiler."""

import time

from hosts.gui.performance_profiler import PerformanceProfiler


class TestPerformanceProfiler:
    """Test performance profiler functionality."""

    def test_initialization(self):
        """Test initialization of profiler."""
        profiler = PerformanceProfiler()
        assert profiler.max_samples == 100
        assert profiler.target_fps == 60
        assert len(profiler.frame_times) == 0

    def test_frame_timing(self):
        """Test frame timing."""
        profiler = PerformanceProfiler()
        profiler.start_frame()
        time.sleep(0.001)  # Sleep for 1ms
        profiler.end_frame()

        assert len(profiler.frame_times) == 1
        assert profiler.frame_times[0] >= 1.0  # At least 1ms

    def test_get_fps(self):
        """Test getting FPS."""
        profiler = PerformanceProfiler()

        # Simulate 60 FPS (16.67ms per frame)
        for _ in range(10):
            profiler.start_frame()
            time.sleep(0.0167)
            profiler.end_frame()

        fps = profiler.get_fps()
        assert fps > 20  # Loose bound — Windows sleep granularity is ~15ms

    def test_get_average_frame_time(self):
        """Test getting average frame time."""
        profiler = PerformanceProfiler()

        for _ in range(5):
            profiler.start_frame()
            time.sleep(0.001)
            profiler.end_frame()

        avg_time = profiler.get_average_frame_time()
        assert avg_time >= 1.0

    def test_get_max_frame_time(self):
        """Test getting maximum frame time."""
        profiler = PerformanceProfiler()

        profiler.start_frame()
        time.sleep(0.001)
        profiler.end_frame()

        profiler.start_frame()
        time.sleep(0.002)
        profiler.end_frame()

        max_time = profiler.get_max_frame_time()
        assert max_time >= 2.0

    def test_get_min_frame_time(self):
        """Test getting minimum frame time."""
        profiler = PerformanceProfiler()

        profiler.start_frame()
        time.sleep(0.001)
        profiler.end_frame()

        profiler.start_frame()
        time.sleep(0.002)
        profiler.end_frame()

        min_time = profiler.get_min_frame_time()
        assert min_time >= 1.0

    def test_component_timing(self):
        """Test component timing."""
        profiler = PerformanceProfiler()

        profiler.start_component("render")
        time.sleep(0.001)
        profiler.end_component("render")

        assert "render" in profiler.component_times
        assert len(profiler.component_times["render"]) == 1

    def test_get_component_average_time(self):
        """Test getting component average time."""
        profiler = PerformanceProfiler()

        for _ in range(3):
            profiler.start_component("render")
            time.sleep(0.001)
            profiler.end_component("render")

        avg_time = profiler.get_component_average_time("render")
        assert avg_time >= 1.0

    def test_get_component_max_time(self):
        """Test getting component maximum time."""
        profiler = PerformanceProfiler()

        profiler.start_component("render")
        time.sleep(0.001)
        profiler.end_component("render")

        profiler.start_component("render")
        time.sleep(0.002)
        profiler.end_component("render")

        max_time = profiler.get_component_max_time("render")
        assert max_time >= 2.0

    def test_get_performance_report(self):
        """Test getting performance report."""
        profiler = PerformanceProfiler()

        profiler.start_frame()
        time.sleep(0.001)
        profiler.end_frame()

        profiler.start_component("render")
        time.sleep(0.001)
        profiler.end_component("render")

        report = profiler.get_performance_report()

        assert "fps" in report
        assert "avg_frame_time_ms" in report
        assert "max_frame_time_ms" in report
        assert "min_frame_time_ms" in report
        assert "target_fps" in report
        assert "components" in report

    def test_is_meeting_target_fps(self):
        """Test checking if meeting target FPS."""
        profiler = PerformanceProfiler()

        # Simulate perfect 60 FPS times (16.67ms) directly to avoid sleep jitter
        for _ in range(10):
            profiler.frame_times.append(16.67)

        assert profiler.is_meeting_target_fps()

    def test_reset(self):
        """Test resetting profiler."""
        profiler = PerformanceProfiler()

        profiler.start_frame()
        time.sleep(0.001)
        profiler.end_frame()

        profiler.start_component("render")
        time.sleep(0.001)
        profiler.end_component("render")

        profiler.reset()

        assert len(profiler.frame_times) == 0
        assert len(profiler.component_times) == 0

    def test_empty_profiler_metrics(self):
        """Test metrics on empty profiler."""
        profiler = PerformanceProfiler()

        assert profiler.get_fps() == 0.0
        assert profiler.get_average_frame_time() == 0.0
        assert profiler.get_max_frame_time() == 0.0
        assert profiler.get_min_frame_time() == 0.0

    def test_max_samples_limit(self):
        """Test that max samples limit is enforced."""
        profiler = PerformanceProfiler(max_samples=5)

        for _ in range(10):
            profiler.start_frame()
            time.sleep(0.001)
            profiler.end_frame()

        assert len(profiler.frame_times) == 5
