from django.conf import settings


def send_email(to: str | list, subject: str, text: str) -> bool:
    """Отправляет письмо через Resend API. Возвращает True при успехе."""
    api_key = getattr(settings, 'RESEND_API_KEY', '')
    if not api_key or api_key == 'ВСТАВЬ_КЛЮЧ_СЮДА':
        # Fallback: выводим в консоль (dev-режим)
        print(f'\n[EMAIL TO {to}]\nSubject: {subject}\n{text}\n')
        return True

    import resend
    resend.api_key = api_key

    recipients = [to] if isinstance(to, str) else to
    from_addr = getattr(settings, 'DEFAULT_FROM_EMAIL', 'Доставка МИГ <onboarding@resend.dev>')

    try:
        resend.Emails.send({
            'from': from_addr,
            'to': recipients,
            'subject': subject,
            'text': text,
        })
        return True
    except Exception as e:
        print(f'[EMAIL ERROR] {e}')
        raise
