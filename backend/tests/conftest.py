"""Offline API tests do not download heavyweight model weights."""
import os
os.environ.setdefault('API_KEY','test-key-that-is-long-enough-for-ci')
os.environ.setdefault('APP_ENV','test')
