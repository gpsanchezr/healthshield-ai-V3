import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

def pytest_configure(config):
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
    django.setup()
