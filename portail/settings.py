"""Configuration du portail prestataires.

Toutes les valeurs sensibles viennent de variables d'environnement
(voir .env.example). Les valeurs par défaut sont sûres pour la production :
le mode debug doit être activé explicitement.
"""

import json
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(nom, defaut=None):
    return os.environ.get(nom, defaut)


def env_bool(nom, defaut=False):
    return env(nom, str(defaut)).lower() in {"1", "true", "oui", "yes"}


def env_liste(nom, defaut=""):
    return [v.strip() for v in env(nom, defaut).split(",") if v.strip()]


DEBUG = env_bool("PORTAIL_DEBUG", False)

SECRET_KEY = env("PORTAIL_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-uniquement-ne-pas-utiliser-en-production"
    else:
        raise ImproperlyConfigured("PORTAIL_SECRET_KEY doit être défini.")

ALLOWED_HOSTS = env_liste("PORTAIL_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_liste("PORTAIL_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "mozilla_django_oidc",
    "audit",
    "comptes",
    "prestataires",
    "charte",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "portail.middleware.EntetesSecuriteMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "comptes.middleware.MfaObligatoireMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "portail.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "comptes.context_processors.roles",
            ],
        },
    },
]

WSGI_APPLICATION = "portail.wsgi.application"

if env("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER", "portail"),
            "PASSWORD": env("POSTGRES_PASSWORD", ""),
            "HOST": env("POSTGRES_HOST", "localhost"),
            "PORT": env("POSTGRES_PORT", "5432"),
            "OPTIONS": {"sslmode": env("POSTGRES_SSLMODE", "prefer")},
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "comptes.Utilisateur"

AUTHENTICATION_BACKENDS = [
    "comptes.oidc.EntraIdBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.ScryptPasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

LOGIN_URL = "comptes:connexion"
LOGIN_REDIRECT_URL = "accueil"
LOGOUT_REDIRECT_URL = "comptes:connexion"

# --- SSO Entra ID (personnel interne) -------------------------------------
# Laisser OIDC_RP_CLIENT_ID vide désactive le bouton « Se connecter avec Entra ID ».
ENTRA_TENANT_ID = env("ENTRA_TENANT_ID", "")
OIDC_RP_CLIENT_ID = env("OIDC_RP_CLIENT_ID", "")
OIDC_RP_CLIENT_SECRET = env("OIDC_RP_CLIENT_SECRET", "")
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_RP_SCOPES = "openid email profile"
_entra = f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}"
OIDC_OP_AUTHORIZATION_ENDPOINT = f"{_entra}/oauth2/v2.0/authorize"
OIDC_OP_TOKEN_ENDPOINT = f"{_entra}/oauth2/v2.0/token"
OIDC_OP_USER_ENDPOINT = "https://graph.microsoft.com/oidc/userinfo"
OIDC_OP_JWKS_ENDPOINT = f"{_entra}/discovery/v2.0/keys"
OIDC_USE_PKCE = True
OIDC_STORE_ID_TOKEN = True
# Correspondance identifiant de groupe Entra ID / AD -> rôle du portail, en JSON.
# Exemple : {"5b1c...": "RSSI", "9a2d...": "Référent applicatif"}
OIDC_GROUPES_ROLES = json.loads(env("OIDC_GROUPES_ROLES", "{}"))

# --- Sessions et cookies --------------------------------------------------
SESSION_COOKIE_AGE = int(env("PORTAIL_SESSION_SECONDES", 30 * 60))
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_NAME = "__Host-portail" if not DEBUG else "portail"
CSRF_COOKIE_NAME = "__Host-csrf" if not DEBUG else "csrftoken"

# --- En-têtes de sécurité -------------------------------------------------
SECURE_SSL_REDIRECT = env_bool("PORTAIL_SSL_REDIRECT", not DEBUG)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
# Adresses des reverse proxies de confiance : seule source acceptée pour X-Forwarded-For.
PORTAIL_PROXIES_DE_CONFIANCE = env_liste("PORTAIL_PROXIES_DE_CONFIANCE")

# --- Métier ---------------------------------------------------------------
PORTAIL_NOM_ETABLISSEMENT = env("PORTAIL_NOM_ETABLISSEMENT", "Établissement")
OTP_TOTP_ISSUER = env("PORTAIL_OTP_EMETTEUR", "Portail prestataires")
INVITATION_VALIDITE_JOURS = int(env("PORTAIL_INVITATION_JOURS", 7))
PASSWORD_RESET_TIMEOUT = INVITATION_VALIDITE_JOURS * 24 * 3600

EMAIL_BACKEND = env("PORTAIL_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("PORTAIL_SMTP_HOTE", "localhost")
EMAIL_PORT = int(env("PORTAIL_SMTP_PORT", 25))
EMAIL_USE_TLS = env_bool("PORTAIL_SMTP_TLS", False)
DEFAULT_FROM_EMAIL = env("PORTAIL_EMAIL_EXPEDITEUR", "portail-prestataires@localhost")

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("PORTAIL_LOG_LEVEL", "INFO")},
}

# Portail interne : pas d'inscription à la liste de préchargement HSTS des navigateurs.
SILENCED_SYSTEM_CHECKS = ["security.W021"]
