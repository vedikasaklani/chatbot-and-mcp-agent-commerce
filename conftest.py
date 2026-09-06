"""Pytest configuration shared by the whole test suite.
"""
import os

_TEST_ENV_DEFAULTS = {
    "DATABASE_URL": "postgresql://test:test@localhost/test",
    "SECRET_KEY": "test-secret-key-not-for-real-use",
    "GROQ_API_KEY": "test-groq-key",
    "razorpay_key": "test-razorpay-key",
    "razorpay_secret": "test-razorpay-secret",
    "razorpay_webhook_secret": "test-razorpay-webhook-secret",
}

for _var, _default in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(_var, _default)