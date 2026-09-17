import json
import logging
import threading
from django.conf import settings

logger = logging.getLogger(__name__)

def _send_push_to_subscriptions(subscriptions_data, payload_json):
    """Worker function executed in background thread to deliver Web Push messages."""
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.error("[WebPush] pywebpush is not installed. Web Push cannot be dispatched.")
        return

    vapid_private_key = getattr(settings, 'WEBPUSH_VAPID_PRIVATE_KEY', None)
    admin_email = getattr(settings, 'WEBPUSH_VAPID_ADMIN_EMAIL', 'admin@geminiinsights.local')

    if not vapid_private_key:
        logger.warning("[WebPush] WEBPUSH_VAPID_PRIVATE_KEY is not configured.")
        return

    try:
        from py_vapid import Vapid
        if isinstance(vapid_private_key, str):
            if 'BEGIN PRIVATE KEY' in vapid_private_key:
                vapid_key_obj = Vapid.from_pem(vapid_private_key.encode('utf-8'))
            else:
                vapid_key_obj = Vapid.from_string(vapid_private_key)
        else:
            vapid_key_obj = vapid_private_key
    except Exception as e:
        logger.error(f"[WebPush] Failed to parse VAPID key: {e}")
        return

    vapid_claims = {"sub": f"mailto:{admin_email}"}

    from accounts.models import PushSubscription

    for sub_item in subscriptions_data:
        sub_id = sub_item['id']
        sub_info = {
            "endpoint": sub_item['endpoint'],
            "keys": {
                "p256dh": sub_item['p256dh'],
                "auth": sub_item['auth'],
            }
        }

        try:
            webpush(
                subscription_info=sub_info,
                data=payload_json,
                vapid_private_key=vapid_key_obj,
                vapid_claims=vapid_claims,
                ttl=86400,  # 24 hours delivery window if device is currently offline
                headers={"Urgency": "high"}
            )
            logger.info(f"[WebPush] Successfully sent push notification to subscription {sub_id}")
        except WebPushException as ex:
            # 404 Not Found or 410 Gone means the browser subscription has expired or was revoked
            status_code = getattr(ex.response, 'status_code', None) if hasattr(ex, 'response') else None
            logger.warning(f"[WebPush] Push failed for subscription {sub_id}: {ex} (Status: {status_code})")
            if status_code in (404, 410):
                logger.info(f"[WebPush] Deleting expired subscription {sub_id}")
                PushSubscription.objects.filter(id=sub_id).delete()
        except Exception as ex:
            logger.warning(f"[WebPush] Unexpected error sending push to subscription {sub_id}: {ex}")


def send_push_notification_to_user(user, title, body, url='/tasks/', tag=None, icon=None, badge=None):
    """
    Dispatches a native Web Push notification to all active devices of the given user.
    Executes in a background thread to prevent blocking web request handling.
    """
    if not user or not user.is_authenticated:
        return

    from accounts.models import PushSubscription

    subscriptions = list(
        PushSubscription.objects.filter(user=user).values('id', 'endpoint', 'p256dh', 'auth')
    )

    if not subscriptions:
        return

    payload_dict = {
        "title": str(title),
        "body": str(body),
        "url": url or '/tasks/',
        "tag": tag or 'gemini-notification',
        "icon": icon or '/static/pwa/icons/icon-192x192.png',
        "badge": badge or '/static/pwa/icons/favicon-32x32.png',
    }
    payload_json = json.dumps(payload_dict)

    thread = threading.Thread(
        target=_send_push_to_subscriptions,
        args=(subscriptions, payload_json),
        daemon=True
    )
    thread.start()
