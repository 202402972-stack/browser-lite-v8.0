"""Stable, secret-free diagnostics for model requests."""
import asyncio
import httpx
from pydantic import ValidationError

class VisionProbeFailed(ValueError):
    pass


def model_error(exc):
    """Return a code and safe explanation without including provider payloads."""
    if isinstance(exc, VisionProbeFailed):
        return 'MODEL_VISION_FAILED', 'الموديل رد، لكن لم يتعرّف على صورة الاختبار؛ راجع دعم الصور أو اختَر موديل رؤية.'
    status = getattr(exc, 'status_code', None)
    if status == 400:
        return 'MODEL_BAD_REQUEST', 'المزوّد لم يقبل صيغة الطلب؛ راجع توافق الموديل وإعداد الصور.'
    if status == 401:
        return 'MODEL_AUTH', 'المزوّد رفض المصادقة؛ راجع المفتاح وطريقة الاتصال.'
    if status == 402:
        return 'MODEL_PAYMENT_REQUIRED', 'المزوّد يطلب رصيدًا أو تفعيل الفوترة؛ راجع حسابك.'
    if status == 403:
        return 'MODEL_FORBIDDEN', 'الحساب لا يملك صلاحية الطلب؛ راجع صلاحيات المزوّد والموديل.'
    if status == 404:
        return 'MODEL_NOT_FOUND', 'الموديل أو عنوان الخدمة غير موجود؛ راجع الإعدادات.'
    if status == 429:
        return 'MODEL_RATE_LIMIT', 'وصلت لحد الطلبات أو الرصيد لدى المزوّد؛ حاول لاحقًا أو راجع الحساب.'
    if isinstance(status, int) and 500 <= status <= 599:
        return 'MODEL_PROVIDER_ERROR', 'خدمة الموديل تواجه مشكلة؛ حاول لاحقًا.'
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)):
        return 'MODEL_TIMEOUT', 'الموديل لم يرد في الوقت المحدد؛ حاول الاستكمال.'
    if isinstance(exc, (ConnectionError, httpx.NetworkError)):
        return 'MODEL_CONNECTION', 'تعذر الاتصال بالموديل؛ راجع الشبكة والبروكسي.'
    if isinstance(exc, (ValidationError, ValueError)):
        return 'MODEL_INVALID_RESPONSE', 'رد الموديل لم يطابق المطلوب؛ جرّب موديلًا يدعم الرد المنظّم.'
    return 'MODEL_REQUEST_FAILED', 'تعذر طلب الموديل؛ راجع الإعدادات وحالة المزوّد.'
