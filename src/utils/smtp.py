# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Smtp Module
# =============================================================================
# Description:
#   Утилиты для отправки и получения электронных писем по протоколам SMTP и IMAP.
#
# Usage Examples:
#   Python API:
#     from src.utils.smtp import send
#
#     res = send(subject="Test", body="Hello")
#
# File: smtp.py
# Project: ai-windows-admin
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:38:00
# =============================================================================

"""Утилиты для отправки и получения электронных писем по протоколам SMTP и IMAP."""

import email
from email.mime.text import MIMEText
import imaplib
import os
import smtplib
from typing import Dict, List, Optional

from logger import logger

_DEFAULT_SMTP_TIMEOUT = 15.0

_connection = {
    'server': os.environ.get('SMTP_SERVER', 'smtp.example.com'),
    'port': int(os.environ.get('SMTP_PORT', 587)),
    'user': os.environ.get('SMTP_USER'),
    'password': os.environ.get('SMTP_PASSWORD'),
    'receiver': os.environ.get('SMTP_RECEIVER', 'one.last.bit@gmail.com'),
}


def send(
    subject: str = '',
    body: str = '',
    to: str = 'one.last.bit@gmail.com',
    timeout: float = _DEFAULT_SMTP_TIMEOUT,
) -> bool:
    """Отправляет электронное письмо через SMTP с явным таймаутом и гарантированным закрытием сокета.

    Args:
        subject (str): Тема письма.
        body (str): Текст письма.
        to (str): Адрес получателя.
        timeout (float): Таймаут сетевого соединения в секундах (по умолчанию 15.0).

    Returns:
        bool: True при успешной отправке, иначе False.
    """
    smtp: Optional[smtplib.SMTP] = None
    try:
        smtp = smtplib.SMTP(_connection['server'], _connection['port'], timeout=timeout)
        smtp.ehlo()
        smtp.starttls()
        smtp.login(_connection['user'] or '', _connection['password'] or '')
        message = MIMEText(body, _charset='utf-8')
        message['Subject'] = subject
        message['From'] = _connection['user'] or ''
        message['To'] = to
        smtp.sendmail(_connection['user'] or '', to, message.as_string())
        return True
    except Exception as ex:
        # Не логируем тело письма (body) во избежание утечки конфиденциальных данных/PII
        logger.error(f'Ошибка отправки email. Тема: {subject!r}, Получатель: {to!r}. Ошибка: {ex}', exc_info=True)
        return False
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except Exception:
                try:
                    smtp.close()
                except Exception:
                    pass


def receive(
    imap_server: str,
    user: str,
    password: str,
    folder: str = 'inbox',
    timeout: float = _DEFAULT_SMTP_TIMEOUT,
) -> Optional[List[Dict[str, str]]]:
    """Получает список писем с IMAP-сервера с явным таймаутом и закрытием сессии.

    Args:
        imap_server (str): Хост IMAP-сервера.
        user (str): Имя пользователя.
        password (str): Пароль.
        folder (str): Папка почтового ящика (по умолчанию 'inbox').
        timeout (float): Таймаут соединения в секундах (по умолчанию 15.0).

    Returns:
        Optional[List[Dict[str, str]]]: Список словарей с письмами или None при ошибке.
    """
    mail: Optional[imaplib.IMAP4_SSL] = None
    try:
        mail = imaplib.IMAP4_SSL(imap_server, timeout=timeout)
        mail.login(user, password)
        mail.select(folder)
        _, data = mail.search(None, 'ALL')
        email_ids = data[0].split() if data and data[0] else []
        emails: List[Dict[str, str]] = []
        for email_id in email_ids:
            _, fetch_data = mail.fetch(email_id, '(RFC822)')
            if not fetch_data or not fetch_data[0]:
                continue
            raw_email = fetch_data[0][1]
            if not isinstance(raw_email, (bytes, bytearray)):
                continue
            msg = email.message_from_bytes(raw_email)
            payload = msg.get_payload(decode=True)
            body_text = payload.decode('utf-8', 'ignore') if isinstance(payload, (bytes, bytearray)) else str(payload or '')
            email_data = {
                'subject': str(msg.get('subject', '')),
                'from': str(msg.get('from', '')),
                'body': body_text,
            }
            emails.append(email_data)
        return emails
    except Exception as ex:
        logger.error(f'Ошибка при получении писем с IMAP-сервера {imap_server}: {ex}', exc_info=True)
        return None
    finally:
        if mail is not None:
            try:
                mail.close()
            except Exception:
                pass
            try:
                mail.logout()
            except Exception:
                pass
