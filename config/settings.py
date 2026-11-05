"""Django ayarları. Veritabanı kullanılmaz: simülasyon her istekte modelden hesaplanır."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Yerel geliştirme için varsayılanlar. Başka bir ortamda ortam değişkenleriyle değiştirin.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "gelistirme-icin-guvensiz-anahtar")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

INSTALLED_APPS = ["simulasyon"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
}]

DATABASES = {}

LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

# Yüklenen log dosyaları için üst sınır (bayt)
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
