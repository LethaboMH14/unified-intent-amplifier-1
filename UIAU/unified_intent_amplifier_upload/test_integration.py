"""
test_integration.py — Integration tests for Unified Intent Amplifier.
Run with: python test_integration.py
All tests must pass before recording the demo video.
"""

import sys
import os
import time
import unittest
from pathlib import Path

# Add parent to path so imports work from any directory
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("CREWAI_TELEMETRY_OPT_OUT", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")


class TestConfig(unittest.TestCase):
    """Verify config values are within expected ranges."""

    def test_kalman_params(self):
        """Kalman Q and R must be positive floats."""
        from config import KALMAN_Q, KALMAN_R
        self.assertGreater(KALMAN_Q, 0)
        self.assertGreater(KALMAN_R, 0)

    def test_gaze_thresholds(self):
        """Gaze EAR threshold must be between 0 and 1."""
        from config import GAZE_BLINK_EAR_THRESHOLD
        self.assertGreater(GAZE_BLINK_EAR_THRESHOLD, 0)
        self.assertLess(GAZE_BLINK_EAR_THRESHOLD, 1)

    def test_supported_languages(self):
        """At least 4 languages must be configured."""
        from config import SUPPORTED_LANGUAGES
        self.assertGreaterEqual(len(SUPPORTED_LANGUAGES), 4)
        self.assertIn("English", SUPPORTED_LANGUAGES)
        self.assertIn("isiZulu", SUPPORTED_LANGUAGES)


class TestDatabase(unittest.TestCase):
    """Verify SQLite profile database initialises correctly."""

    def test_init_db(self):
        """Database should initialise without errors."""
        from user_profile import init_db, get_active_profile
        init_db()
        profile = get_active_profile()
        self.assertIn("name", profile)
        self.assertIn("language", profile)

    def test_save_load_setting(self):
        """Settings should persist across save/load."""
        from user_profile import init_db, save_setting, load_setting
        init_db()
        save_setting("test_key", {"value": 42})
        result = load_setting("test_key")
        self.assertEqual(result, {"value": 42})

    def test_log_event(self):
        """Event logging should not raise."""
        from user_profile import init_db, log_event
        init_db()
        log_event("test_event", {"detail": "integration test"})


class TestKalmanFilter(unittest.TestCase):
    """Verify the Kalman filter smooths correctly."""

    def test_smoothing_reduces_noise(self):
        """Kalman output should be smoother than noisy input."""
        from motor_engine import KalmanFilter1D
        import numpy as np
        kf = KalmanFilter1D()
        noisy = [100 + np.random.randn() * 10 for _ in range(50)]
        smoothed = [kf.update(v) for v in noisy]
        noise_std = float(np.std(noisy))
        smooth_std = float(np.std(smoothed))
        self.assertLess(smooth_std, noise_std,
                        "Kalman output should have lower variance than input")

    def test_filter_reset(self):
        """Filter reset should set state to given value."""
        from motor_engine import KalmanFilter1D
        kf = KalmanFilter1D()
        kf.update(999.0)
        kf.reset(0.0)
        self.assertAlmostEqual(kf.x, 0.0)


class TestTremorSmoother(unittest.TestCase):
    """Verify the 2D tremor smoother works on mouse coordinates."""

    def test_smoother_output_shape(self):
        """Smoother should return two floats."""
        from motor_engine import TremorSmoother
        smoother = TremorSmoother()
        x, y = smoother.smooth(500.0, 300.0)
        self.assertIsInstance(x, float)
        self.assertIsInstance(y, float)

    def test_smoother_convergence(self):
        """Repeated identical inputs should converge to that value."""
        from motor_engine import TremorSmoother
        smoother = TremorSmoother()
        for _ in range(100):
            x, y = smoother.smooth(500.0, 300.0)
        self.assertAlmostEqual(x, 500.0, delta=1.0)
        self.assertAlmostEqual(y, 300.0, delta=1.0)


class TestTypingCorrector(unittest.TestCase):
    """Verify double-keystroke suppression logic."""

    def test_duplicate_detected(self):
        """Second press within window should be flagged as duplicate."""
        from motor_engine import TypingCorrector
        tc = TypingCorrector(window_ms=200)
        self.assertFalse(tc.is_duplicate("a"))   # First press: not duplicate
        self.assertTrue(tc.is_duplicate("a"))    # Immediate second: duplicate

    def test_non_duplicate_after_wait(self):
        """Press after window expires should not be flagged."""
        from motor_engine import TypingCorrector
        tc = TypingCorrector(window_ms=50)
        tc.is_duplicate("b")
        time.sleep(0.1)  # Wait longer than the 50ms window
        self.assertFalse(tc.is_duplicate("b"))


class TestAudioEngine(unittest.TestCase):
    """Verify audio engine initialises and queues speech."""

    def test_start_stop(self):
        """AudioEngine should start and stop without errors."""
        from audio_engine import AudioEngine
        engine = AudioEngine()
        engine.start()
        time.sleep(0.1)
        engine.stop()

    def test_speak_queued(self):
        """speak() should not raise even without pyttsx3."""
        from audio_engine import AudioEngine
        engine = AudioEngine()
        engine.start()
        engine.speak("Test message")
        time.sleep(0.2)
        engine.stop()

    def test_spatial_tone_generation(self):
        """_generate_tone should return a stereo numpy array."""
        from audio_engine import _generate_tone
        import numpy as np
        tone = _generate_tone(440.0, 0.1, 44100, pan=0.5)
        self.assertEqual(tone.ndim, 2)
        self.assertEqual(tone.shape[1], 2)


class TestOfflineFallback(unittest.TestCase):
    """Verify offline coaching tips work without Azure credentials."""

    def test_offline_tip_returned(self):
        """get_coaching_tip should return a non-empty string without API keys."""
        # Clear any Azure env vars to force offline mode
        for key in ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT"]:
            os.environ.pop(key, None)
        from llm_coach import get_coaching_tip
        tip = get_coaching_tip(category="tremor")
        self.assertIsInstance(tip, str)
        self.assertGreater(len(tip), 10)

    def test_all_categories_have_tips(self):
        """Every tip category should return a string."""
        from llm_coach import get_coaching_tip
        for category in ["tremor", "gaze", "typing", "general"]:
            tip = get_coaching_tip(category=category)
            self.assertIsInstance(tip, str)
            self.assertGreater(len(tip), 5, f"Empty tip for category: {category}")


if __name__ == "__main__":
    print("=" * 60)
    print("  Unified Intent Amplifier — Integration Tests")
    print("=" * 60)
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
