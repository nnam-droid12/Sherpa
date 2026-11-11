import os

os.environ.setdefault("SHERPA_ENV", "test")
os.environ.setdefault("SHERPA_API_KEY", "")
# The public demo pauses coding stages and caps audits; tests set their own caps where they test them.
os.environ.setdefault("SHERPA_DAILY_CODING_RUNS", "1000")
os.environ.setdefault("SHERPA_DAILY_AUDIT_RUNS", "1000")
