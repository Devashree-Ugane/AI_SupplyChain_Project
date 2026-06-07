import unittest
import numpy as np
import struct

# =========================
# PURE FUNCTION COPIES FOR TESTING
# (mirrors logic in streamlit_app.py so tests run without streamlit)
# =========================

def safe_int(val):
    if isinstance(val, bytes):
        length = len(val)
        fmt    = {1: 'b', 2: '<h', 4: '<i', 8: '<q'}.get(length)
        if fmt:
            return struct.unpack(fmt, val)[0]
        return int.from_bytes(val, byteorder='little', signed=True)
    try:
        return int(val)
    except Exception:
        return 0

def moving_average_forecast(series, window=3, steps=5):
    series   = list(series)
    forecast = []
    for _ in range(steps):
        avg = np.mean(series[-window:])
        forecast.append(round(avg, 2))
        series.append(avg)
    return forecast

def exponential_smoothing_forecast(series, alpha=0.3, steps=5):
    series   = list(series)
    smoothed = [series[0]]
    for val in series[1:]:
        smoothed.append(alpha * val + (1 - alpha) * smoothed[-1])
    forecast = []
    last     = smoothed[-1]
    for _ in range(steps):
        last = alpha * last + (1 - alpha) * last
        forecast.append(round(last, 2))
    return forecast

def compute_risk_pure(stock, budget, avg_distance):
    stock_risk    = max(0, 100 - stock * 5)
    budget_risk   = max(0, 100 - budget / 5000)
    distance_risk = avg_distance / 50
    score         = 0.5 * stock_risk + 0.3 * budget_risk + 0.2 * distance_risk
    return min(100, int(score))

def days_until_stockout(current_stock, daily_demand_forecast):
    stock = current_stock
    for i, demand in enumerate(daily_demand_forecast):
        stock -= demand
        if stock <= 0:
            return i + 1
    return None

def get_distance_fallback(c1, c2):
    FALLBACK = {
        'Mumbai':    {'Delhi': 1400, 'Bangalore': 1000, 'Pune': 150,  'Chennai': 1300, 'Kolkata': 1900},
        'Delhi':     {'Mumbai': 1400,'Bangalore': 2100, 'Pune': 1450, 'Chennai': 2200, 'Kolkata': 1500},
        'Bangalore': {'Mumbai': 1000,'Delhi': 2100,     'Pune': 850,  'Chennai': 350,  'Kolkata': 1800},
        'Pune':      {'Mumbai': 150, 'Delhi': 1450,     'Bangalore': 850,'Chennai': 1200,'Kolkata': 1850},
        'Chennai':   {'Mumbai': 1300,'Delhi': 2200,     'Bangalore': 350,'Pune': 1200,  'Kolkata': 1600}
    }
    if c1 == c2:
        return 0
    return FALLBACK.get(c1, {}).get(c2, 800)

# =========================
# TEST CASES
# =========================

class TestSafeInt(unittest.TestCase):

    def test_normal_int(self):
        self.assertEqual(safe_int(42), 42)

    def test_string_int(self):
        self.assertEqual(safe_int("100"), 100)

    def test_bytes_4(self):
        val = struct.pack('<i', 1234)
        self.assertEqual(safe_int(val), 1234)

    def test_bytes_8(self):
        val = struct.pack('<q', 99999)
        self.assertEqual(safe_int(val), 99999)

    def test_invalid_returns_zero(self):
        self.assertEqual(safe_int("abc"), 0)


class TestMovingAverage(unittest.TestCase):

    def test_output_length(self):
        result = moving_average_forecast([10, 12, 8, 14, 9], steps=5)
        self.assertEqual(len(result), 5)

    def test_all_same_series(self):
        result = moving_average_forecast([10, 10, 10], steps=3)
        self.assertTrue(all(v == 10.0 for v in result))

    def test_no_negative_forecast(self):
        result = moving_average_forecast([1, 1, 1], steps=5)
        self.assertTrue(all(v >= 0 for v in result))

    def test_window_respected(self):
        result = moving_average_forecast([10, 20, 30], window=2, steps=1)
        self.assertEqual(result[0], 25.0)


class TestExponentialSmoothing(unittest.TestCase):

    def test_output_length(self):
        result = exponential_smoothing_forecast([5, 8, 6, 9, 7], steps=4)
        self.assertEqual(len(result), 4)

    def test_stable_series(self):
        result = exponential_smoothing_forecast([10, 10, 10, 10], steps=3)
        self.assertTrue(all(abs(v - 10.0) < 1.0 for v in result))

    def test_alpha_boundary(self):
        result_low  = exponential_smoothing_forecast([5, 15, 5, 15], alpha=0.1, steps=3)
        result_high = exponential_smoothing_forecast([5, 15, 5, 15], alpha=0.9, steps=3)
        self.assertEqual(len(result_low), 3)
        self.assertEqual(len(result_high), 3)


class TestComputeRisk(unittest.TestCase):

    def test_high_risk_low_stock(self):
        score = compute_risk_pure(stock=1, budget=200000, avg_distance=500)
        self.assertGreater(score, 50)

    def test_low_risk_healthy(self):
        score = compute_risk_pure(stock=20, budget=250000, avg_distance=200)
        self.assertLess(score, 50)

    def test_score_bounded(self):
        score = compute_risk_pure(stock=0, budget=0, avg_distance=5000)
        self.assertLessEqual(score, 100)
        self.assertGreaterEqual(score, 0)


class TestStockout(unittest.TestCase):

    def test_stockout_detected(self):
        days = days_until_stockout(10, [5, 5, 5, 5])
        self.assertEqual(days, 2)

    def test_no_stockout(self):
        days = days_until_stockout(100, [1, 1, 1, 1, 1])
        self.assertIsNone(days)

    def test_exact_stockout(self):
        days = days_until_stockout(5, [5, 5])
        self.assertEqual(days, 1)


class TestDistanceFallback(unittest.TestCase):

    def test_same_city(self):
        self.assertEqual(get_distance_fallback('Mumbai', 'Mumbai'), 0)

    def test_known_pair(self):
        self.assertEqual(get_distance_fallback('Mumbai', 'Pune'), 150)

    def test_unknown_city_returns_default(self):
        self.assertEqual(get_distance_fallback('Mumbai', 'Hyderabad'), 800)

    def test_reverse_pair(self):
        self.assertEqual(get_distance_fallback('Pune', 'Mumbai'), 150)


if __name__ == '__main__':
    unittest.main()
