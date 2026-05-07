import logging
import time
from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.conf import settings

logger = logging.getLogger('security')

# Максимальное количество неудачных попыток входа с одного IP
LOGIN_ATTEMPT_LIMIT = getattr(settings, 'LOGIN_ATTEMPT_LIMIT', 5)
# Время блокировки IP в секундах (по умолчанию 15 минут)
LOGIN_LOCKOUT_SECONDS = getattr(settings, 'LOGIN_LOCKOUT_SECONDS', 900)


def _get_client_ip(request):
    """Возвращает реальный IP клиента с учётом прокси."""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


class LoginRateLimitMiddleware:
    """
    Защита от брутфорса: блокирует IP после N неудачных попыток входа.
    Хранит счётчики в кэше (Redis).
    """

    LOGIN_URL = '/accounts/login/'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == self.LOGIN_URL and request.method == 'POST':
            ip = _get_client_ip(request)
            lockout_key = f'lockout:{ip}'
            attempts_key = f'login_attempts:{ip}'

            # IP заблокирован
            if cache.get(lockout_key):
                logger.warning('Заблокированный IP %s попытался войти', ip)
                return HttpResponseForbidden(
                    '<h2>Слишком много неудачных попыток входа. '
                    'Попробуйте через 15 минут.</h2>',
                    content_type='text/html; charset=utf-8',
                )

            response = self.get_response(request)

            # Неудачная попытка: форма вернула 200 (не редирект)
            if response.status_code == 200:
                attempts = cache.get(attempts_key, 0) + 1
                cache.set(attempts_key, attempts, timeout=LOGIN_LOCKOUT_SECONDS)

                remaining = LOGIN_ATTEMPT_LIMIT - attempts
                logger.warning(
                    'Неудачная попытка входа с IP %s. '
                    'Попыток: %d, осталось: %d',
                    ip, attempts, max(remaining, 0),
                )

                if attempts >= LOGIN_ATTEMPT_LIMIT:
                    cache.set(lockout_key, True, timeout=LOGIN_LOCKOUT_SECONDS)
                    cache.delete(attempts_key)
                    logger.warning('IP %s заблокирован на %d сек', ip, LOGIN_LOCKOUT_SECONDS)

            # Успешный вход — сбрасываем счётчик
            elif response.status_code == 302:
                cache.delete(attempts_key)
                cache.delete(lockout_key)

            return response

        return self.get_response(request)


class SecurityHeadersMiddleware:
    """
    Добавляет заголовки безопасности к каждому ответу.
    Покрывает ПК 4.4: защита ПО программными средствами.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Запрет встраивания в iframe (защита от clickjacking)
        response['X-Frame-Options'] = 'DENY'
        # Запрет угадывания MIME-типа браузером
        response['X-Content-Type-Options'] = 'nosniff'
        # Включение XSS-фильтра браузера
        response['X-XSS-Protection'] = '1; mode=block'
        # Политика реферера
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # Ограничение функций браузера
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

        return response


class RequestLoggingMiddleware:
    """
    Логирует все входящие запросы с временем выполнения.
    Покрывает ПК 4.2: измерение эксплуатационных характеристик.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = (time.monotonic() - start) * 1000

        # Пропускаем статику и медиа
        if not request.path.startswith(('/static/', '/media/')):
            logger.info(
                '%s %s → %d [%.1f ms] IP=%s',
                request.method,
                request.path,
                response.status_code,
                duration_ms,
                _get_client_ip(request),
            )

        return response
