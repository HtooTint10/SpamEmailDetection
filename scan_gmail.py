
import base64
import re
from html import unescape

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from predict import SpamPredictor


# =========================================================
# DETECTOR INITIALIZATION
# =========================================================

_DETECTORS = None


def get_detectors():
    """
    Initialize the spam detector once.

    The second tuple item is None for compatibility with code
    that previously expected a phishing detector.
    """
    global _DETECTORS

    if _DETECTORS is None:
        _DETECTORS = (
            SpamPredictor(model_name="linear_svm"),
            None,
        )

    return _DETECTORS


# =========================================================
# GMAIL HELPERS
# =========================================================

def get_header(headers, name, default=""):
    """Get a Gmail header value without case sensitivity."""
    target = name.lower()

    for header in headers or []:
        if str(header.get("name", "")).lower() == target:
            return header.get("value", default) or default

    return default


def extract_email_address(sender):
    """Extract an email address from a sender header."""
    if not sender:
        return ""

    match = re.search(r"<([^>]+)>", sender)

    if match:
        return match.group(1).strip()

    return sender.strip()


def decode_part(data):
    """Decode a Gmail API URL-safe Base64 body."""
    if not data:
        return ""

    try:
        padding = "=" * (-len(data) % 4)
        decoded = base64.urlsafe_b64decode(data + padding)

        return decoded.decode("utf-8", errors="ignore")

    except (ValueError, TypeError) as exc:
        print(f"Email body decoding error: {exc}")
        return ""


def strip_html(value):
    """Remove HTML tags and normalize the remaining text."""
    if not value:
        return ""

    value = re.sub(
        r"<script\b[^>]*>.*?</script\s*>",
        " ",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )

    value = re.sub(
        r"<style\b[^>]*>.*?</style\s*>",
        " ",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )

    value = re.sub(
        r"<br\s*/?>",
        "\n",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"</(?:p|div|li|tr)\s*>",
        "\n",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)

    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    value = re.sub(r"\n{2,}", "\n", value)

    return value.strip()


def extract_email_body(payload):
    """Extract plain-text content, falling back to HTML."""
    if not payload:
        return ""

    plain_parts = []
    html_parts = []

    def walk(part):
        mime_type = (part.get("mimeType") or "").lower()
        body_data = (part.get("body") or {}).get("data")

        if body_data:
            decoded_text = decode_part(body_data)

            if mime_type == "text/plain":
                plain_parts.append(decoded_text)

            elif mime_type == "text/html":
                html_parts.append(strip_html(decoded_text))

        for child in part.get("parts") or []:
            walk(child)

    walk(payload)

    plain_text = "\n".join(
        part for part in plain_parts if part.strip()
    ).strip()

    if plain_text:
        return plain_text

    html_text = "\n".join(
        part for part in html_parts if part.strip()
    ).strip()

    if html_text:
        return html_text

    # Handle a message whose body is stored at the root.
    body_data = (payload.get("body") or {}).get("data")

    if body_data:
        decoded_text = decode_part(body_data)

        if (payload.get("mimeType") or "").lower() == "text/html":
            return strip_html(decoded_text)

        return decoded_text.strip()

    return ""


# =========================================================
# GMAIL AUTHENTICATION
# =========================================================

def create_gmail_service(session_credentials):
    """Create an authenticated Gmail API service."""
    if not session_credentials:
        raise RuntimeError(
            "Gmail credentials are missing. Please reconnect Gmail."
        )

    credentials = Credentials(
        token=session_credentials.get("token"),
        refresh_token=session_credentials.get("refresh_token"),
        token_uri=session_credentials.get("token_uri"),
        client_id=session_credentials.get("client_id"),
        client_secret=session_credentials.get("client_secret"),
        scopes=session_credentials.get("scopes"),
    )

    if credentials.expired and credentials.refresh_token:
        from google.auth.transport.requests import Request

        credentials.refresh(Request())

    if not credentials.valid:
        raise RuntimeError(
            "Gmail credentials are invalid or expired. "
            "Please reconnect Gmail."
        )

    return build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )


def get_recent_messages(service, limit=25):
    """Retrieve recent inbox message IDs."""
    limit = max(1, min(int(limit), 50))

    response = (
        service.users()
        .messages()
        .list(
            userId="me",
            q="in:inbox",
            maxResults=limit,
        )
        .execute()
    )

    return response.get("messages", [])


# =========================================================
# EMAIL CONTENT
# =========================================================

def build_email_content(message):
    """Build email metadata and the text sent to the classifier."""
    payload = message.get("payload") or {}
    headers = payload.get("headers") or []

    subject = get_header(headers, "Subject", "")
    sender = get_header(headers, "From", "")
    recipient = get_header(headers, "To", "")
    date = get_header(headers, "Date", "")

    body = extract_email_body(payload)

    full_content = "\n".join(
        part for part in (subject, body) if part
    ).strip()

    email = {
        "id": message.get("id", ""),
        "message_id": message.get("id", ""),
        "subject": subject or "(No subject)",
        "from": sender,
        "sender": sender,
        "sender_email": extract_email_address(sender),
        "to": recipient,
        "date": date,
        "body": body,
        "snippet": message.get("snippet", ""),
        "thread_id": message.get("threadId", ""),
    }

    return email, full_content


# =========================================================
# SAFE SHORT-MESSAGE OVERRIDE
# =========================================================

def apply_safe_message_rule(spam_detector, spam_prediction, text):
    """
    Override the spam result only if the existing predictor's
    safe-message checker recognizes the normalized text.
    """
    preprocess = getattr(spam_detector, "preprocess", None)
    safe_checker = getattr(
        spam_detector,
        "_is_obvious_safe_short_message",
        None,
    )

    if not callable(preprocess) or not callable(safe_checker):
        print(
            "Safe-message rule is unavailable. Check that predict.py "
            "defines preprocess() and "
            "_is_obvious_safe_short_message()."
        )
        return spam_prediction

    try:
        cleaned = preprocess(text)

        if not safe_checker(cleaned):
            return spam_prediction

    except Exception as exc:
        print(f"Safe-message rule error: {exc}")
        return spam_prediction

    print(
        "Safe-message rule matched:",
        repr(text),
        "->",
        repr(cleaned),
    )

    # Preserve the other fields returned by the model.
    return {
        **spam_prediction,
        "is_spam": False,
        "label": "HAM",
        "confidence": 99.0,
        "spam_probability": 0.0,
        "ham_probability": 99.0,
        "prediction_source": "short_safe_message_rule",
    }


# =========================================================
# RESULT BUILDER
# =========================================================

def _build_result(
    message_id,
    email,
    spam_prediction,
    phishing_prediction=None,
):
    """
    Convert predictions and email metadata into the result
    structure used by the dashboard.
    """
    is_spam = bool(spam_prediction.get("is_spam", False))

    # No phishing detector is defined in the current predict.py.
    is_phishing = False

    spam_confidence = float(
        spam_prediction.get("confidence", 0) or 0
    )

    phishing_confidence = 0.0

    if is_phishing:
        label = "PHISHING"
        confidence = max(spam_confidence, phishing_confidence)

    elif is_spam:
        label = "SPAM"
        confidence = spam_confidence

    else:
        label = "SAFE"
        confidence = spam_confidence

    result = {}

    if isinstance(email, dict):
        result.update(email)

    # Classification fields take priority over email metadata.
    result.update({
        "id": message_id,
        "message_id": message_id,
        "label": label,
        "is_spam": is_spam,
        "is_phishing": is_phishing,
        "confidence": round(confidence, 2),
        "spam_confidence": round(spam_confidence, 2),
        "phishing_confidence": round(phishing_confidence, 2),
        "prediction_source": spam_prediction.get(
            "prediction_source",
            "linear_svm",
        ),
    })

    return result


# =========================================================
# SINGLE EMAIL SCANNING
# =========================================================

def scan_message(
    message,
    spam_detector=None,
    phishing_detector=None,
):
    """Classify a single Gmail API message."""
    if spam_detector is None:
        spam_detector, _ = get_detectors()

    email, full_content = build_email_content(message)
    message_id = message.get("id", "")

    spam_prediction = spam_detector.predict(full_content)

    if not isinstance(spam_prediction, dict):
        raise TypeError(
            "SpamPredictor.predict() must return a dictionary."
        )

    spam_prediction = apply_safe_message_rule(
        spam_detector,
        spam_prediction,
        full_content,
    )

    return _build_result(
        message_id,
        email,
        spam_prediction,
    )


def get_email_details(session_credentials, message_id):
    """Fetch one complete Gmail message and return its details."""
    service = create_gmail_service(session_credentials)

    message = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="full",
        )
        .execute()
    )

    payload = message.get("payload", {})
    headers = payload.get("headers", [])

    return {
        "id": message.get("id", message_id),
        "subject": get_header(headers, "Subject"),
        "sender": get_header(headers, "From"),
        "receiver": get_header(headers, "To"),
        "date": get_header(headers, "Date"),
        "body": extract_email_body(payload),
        "snippet": message.get("snippet", ""),
    }
# =========================================================
# SCAN RECENT INBOX MESSAGES
# =========================================================

def scan_gmail_messages(session_credentials, limit=25):
    """Fetch and classify recent inbox messages."""
    service = create_gmail_service(session_credentials)
    messages = get_recent_messages(service, limit)

    spam_detector, _ = get_detectors()
    results = []

    for message_summary in messages:
        message_id = message_summary.get("id")

        if not message_id:
            continue

        try:
            message = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=message_id,
                    format="full",
                )
                .execute()
            )

            result = scan_message(
                message,
                spam_detector=spam_detector,
            )

            results.append(result)

        except Exception as exc:
            print(
                f"Failed to scan Gmail message "
                f"{message_id}: {exc}"
            )

    return results


# =========================================================
# COMPATIBILITY FUNCTIONS
# =========================================================

def scan_gmail_for_web(session_credentials, limit=25):
    """Compatibility wrapper for existing Flask routes."""
    return scan_gmail_messages(
        session_credentials,
        limit=limit,
    )

def scan_gmail_for_web(
    session_credentials,
    limit=25,
    model_name="linear_svm",
):
    """Compatibility wrapper for the existing Flask route."""
    if model_name != "linear_svm":
        raise ValueError(
            "Only the linear_svm model is supported."
        )

    return scan_gmail_messages(
        session_credentials=session_credentials,
        limit=limit,
    )

def scan_single_gmail_message(session_credentials, message_id):
    """Fetch and classify one Gmail message by ID."""
    service = create_gmail_service(session_credentials)

    message = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="full",
        )
        .execute()
    )

    spam_detector, _ = get_detectors()

    return scan_message(
        message,
        spam_detector=spam_detector,
    )