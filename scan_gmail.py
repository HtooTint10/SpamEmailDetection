import base64
import re

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from predict import SpamPredictor


# =========================================================
# EXTRACT EMAIL BODY
# =========================================================

def extract_email_body(payload):

    if not payload:
        return ""

    body = ""

    # =====================================================
    # DIRECT BODY
    # =====================================================

    body_data = (
        payload
        .get("body", {})
        .get("data")
    )

    if body_data:

        try:

            padding = "=" * (
                -len(body_data) % 4
            )

            decoded = (
                base64.urlsafe_b64decode(
                    body_data + padding
                )
                .decode(
                    "utf-8",
                    errors="ignore"
                )
            )

            body += decoded

        except Exception as e:

            print(
                "Body decode error:",
                e
            )

    # =====================================================
    # PARTS
    # =====================================================

    parts = payload.get(
        "parts",
        []
    )

    for part in parts:

        mime_type = part.get(
            "mimeType",
            ""
        )

        # -------------------------------------------------
        # PLAIN TEXT
        # -------------------------------------------------

        if mime_type == "text/plain":

            data = (
                part
                .get("body", {})
                .get("data")
            )

            if data:

                try:

                    padding = "=" * (
                        -len(data) % 4
                    )

                    decoded = (
                        base64.urlsafe_b64decode(
                            data + padding
                        )
                        .decode(
                            "utf-8",
                            errors="ignore"
                        )
                    )

                    body += decoded

                except Exception as e:

                    print(
                        "Plain text decode error:",
                        e
                    )

        # -------------------------------------------------
        # HTML
        # -------------------------------------------------

        elif mime_type == "text/html":

            # We prefer plain text.
            # Do not add HTML if plain text
            # was already found.

            if not body:

                data = (
                    part
                    .get("body", {})
                    .get("data")
                )

                if data:

                    try:

                        padding = "=" * (
                            -len(data) % 4
                        )

                        decoded = (
                            base64.urlsafe_b64decode(
                                data + padding
                            )
                            .decode(
                                "utf-8",
                                errors="ignore"
                            )
                        )

                        body += decoded

                    except Exception as e:

                        print(
                            "HTML decode error:",
                            e
                        )

        # -------------------------------------------------
        # NESTED PARTS
        # -------------------------------------------------

        nested_parts = part.get(
            "parts"
        )

        if nested_parts:

            body += extract_email_body(
                part
            )

    return body.strip()


# =========================================================
# GET EMAIL HEADER
# =========================================================

def get_header(
    headers,
    name
):

    for header in headers:

        if (
            header.get(
                "name",
                ""
            ).lower()
            == name.lower()
        ):

            return header.get(
                "value",
                ""
            )

    return ""


# =========================================================
# EXTRACT EMAIL ADDRESS
# =========================================================

def extract_email_address(
    sender
):

    if not sender:

        return ""

    match = re.search(
        r"<([^>]+)>",
        sender
    )

    if match:

        return match.group(
            1
        ).strip()

    return sender.strip()


# =========================================================
# CREATE GMAIL SERVICE
# =========================================================

def create_gmail_service(
    session_credentials
):

    credentials = Credentials(

        token=session_credentials.get(
            "token"
        ),

        refresh_token=session_credentials.get(
            "refresh_token"
        ),

        token_uri=session_credentials.get(
            "token_uri"
        ),

        client_id=session_credentials.get(
            "client_id"
        ),

        client_secret=session_credentials.get(
            "client_secret"
        ),

        scopes=session_credentials.get(
            "scopes"
        )
    )

    return build(
        "gmail",
        "v1",
        credentials=credentials
    )


# =========================================================
# GET ALL GMAIL MESSAGES
# =========================================================

def get_all_messages(
    service,
    query="in:inbox"
):

    messages = []

    page_token = None

    print()
    print(
        "Getting Gmail messages..."
    )

    print(
        "Query:",
        query
    )

    while True:

        response = (
            service.users()
            .messages()
            .list(

                userId="me",

                q=query,

                pageToken=page_token

            )
            .execute()
        )

        page_messages = response.get(
            "messages",
            []
        )

        messages.extend(
            page_messages
        )

        print(
            "Loaded:",
            len(page_messages),
            "emails"
        )

        page_token = response.get(
            "nextPageToken"
        )

        if not page_token:

            break

    print(
        "TOTAL EMAILS FOUND:",
        len(messages)
    )

    return messages


# =========================================================
# SCAN GMAIL
# =========================================================

def scan_gmail_for_web(
    session_credentials,
    model_name="linear_svm"
):

    print()
    print("=" * 60)
    print("STARTING GMAIL SCAN")
    print("=" * 60)

    # =====================================================
    # GMAIL SERVICE
    # =====================================================

    service = create_gmail_service(
        session_credentials
    )

    # =====================================================
    # ACCOUNT
    # =====================================================

    profile = (
        service.users()
        .getProfile(
            userId="me"
        )
        .execute()
    )

    email_address = profile.get(
        "emailAddress",
        "Unknown"
    )

    print(
        "Gmail account:",
        email_address
    )

    # =====================================================
    # GET INBOX EMAILS
    # =====================================================

    messages = get_all_messages(
        service,
        query="in:inbox"
    )

    # =====================================================
    # AI MODEL
    # =====================================================

    detector = SpamPredictor(model_name="linear_svm")

    results = []

    total = 0
    safe = 0
    spam = 0

    # =====================================================
    # PROCESS EMAILS
    # =====================================================

    for message_info in messages:

        message_id = message_info.get(
            "id"
        )

        if not message_id:

            continue

        try:

            message = (
                service.users()
                .messages()
                .get(

                    userId="me",

                    id=message_id,

                    format="full"

                )
                .execute()
            )

            payload = message.get(
                "payload",
                {}
            )

            headers = payload.get(
                "headers",
                []
            )

            # =================================================
            # SUBJECT
            # =================================================

            subject = get_header(
                headers,
                "Subject"
            )

            if not subject:

                subject = "(No Subject)"

            # =================================================
            # SENDER
            # =================================================

            sender = get_header(
                headers,
                "From"
            )

            if not sender:

                sender = "Unknown Sender"

            # =================================================
            # DATE
            # =================================================

            date = get_header(
                headers,
                "Date"
            )

            # =================================================
            # BODY
            # =================================================

            body = extract_email_body(
                payload
            )

            # =================================================
            # AI INPUT
            # =================================================

            full_content = (
                "Subject: "
                + subject
                + "\n\n"
                + body
            )

            # =================================================
            # PREDICTION
            # =================================================

            prediction = detector.predict(
                full_content
            )

            is_spam = bool(
                prediction.get(
                    "is_spam",
                    False
                )
            )

            confidence = prediction.get(
                "confidence",
                0
            )

            try:

                confidence = round(
                    float(confidence),
                    2
                )

            except Exception:

                confidence = 0

            # =================================================
            # LABEL
            # =================================================

            if is_spam:

                label = "SPAM"

                spam += 1

            else:

                label = "SAFE"

                safe += 1

            total += 1

            # =================================================
            # SAVE RESULT
            # =================================================

            results.append({

                "id":
                    message_id,

                "subject":
                    subject,

                "sender":
                    sender,

                "sender_email":
                    extract_email_address(
                        sender
                    ),

                "date":
                    date,

                "label":
                    label,

                "is_spam":
                    is_spam,

                "confidence":
                    confidence

            })

            print(
                f"{total}. "
                f"{label} | "
                f"{confidence}% | "
                f"{subject}"
            )

        except Exception as e:

            print()
            print(
                "EMAIL PROCESSING ERROR"
            )

            print(
                "Message ID:",
                message_id
            )

            print(
                "Error:",
                e
            )

            continue

    # =====================================================
    # FINAL RESULT
    # =====================================================

    result = {

        "success":
            True,

        "email":
            email_address,

        "total":
            total,

        "safe":
            safe,

        "spam":
            spam,

        "results":
            results,

        "model":
            detector.model_name,

        "model_name":
            detector.display_name,

        "model_accuracy":
            detector.accuracy

    }

    print()
    print("=" * 60)
    print("SCAN FINISHED")
    print("=" * 60)

    print(
        "Total:",
        total
    )

    print(
        "Safe:",
        safe
    )

    print(
        "Spam:",
        spam
    )

    return result


# =========================================================
# GET ONE EMAIL DETAILS
# =========================================================

def get_email_details(
    session_credentials,
    message_id
):

    service = create_gmail_service(
        session_credentials
    )

    message = (
        service.users()
        .messages()
        .get(

            userId="me",

            id=message_id,

            format="full"

        )
        .execute()
    )

    payload = message.get(
        "payload",
        {}
    )

    headers = payload.get(
        "headers",
        []
    )

    subject = get_header(
        headers,
        "Subject"
    )

    sender = get_header(
        headers,
        "From"
    )

    to = get_header(
        headers,
        "To"
    )

    date = get_header(
        headers,
        "Date"
    )

    body = extract_email_body(
        payload
    )

    if not subject:

        subject = "(No Subject)"

    if not sender:

        sender = "Unknown Sender"

    if not to:

        to = "Unknown"

    if not date:

        date = "Unknown"

    if not body:

        body = (
            "No readable text "
            "was found."
        )

    return {

        "id":
            message_id,

        "subject":
            subject,

        "sender":
            sender,

        "to":
            to,

        "date":
            date,

        "body":
            body

    }


# =========================================================
# MOVE TO SPAM
# =========================================================

def move_to_spam(
    session_credentials,
    message_id
):

    service = create_gmail_service(
        session_credentials
    )

    service.users().messages().modify(

        userId="me",

        id=message_id,

        body={

            "addLabelIds": [
                "SPAM"
            ],

            "removeLabelIds": [
                "INBOX"
            ]

        }

    ).execute()

    return {

        "success":
            True,

        "message":
            "Email moved to Spam."

    }


# =========================================================
# MOVE TO SAFE
# =========================================================

def move_to_safe(
    session_credentials,
    message_id
):

    service = create_gmail_service(
        session_credentials
    )

    service.users().messages().modify(

        userId="me",

        id=message_id,

        body={

            "addLabelIds": [
                "INBOX"
            ],

            "removeLabelIds": [
                "SPAM"
            ]

        }

    ).execute()

    return {

        "success":
            True,

        "message":
            "Email moved to Inbox."

    }


# =========================================================
# BLOCK SENDER
# =========================================================

def block_sender(
    session_credentials,
    sender
):

    service = create_gmail_service(
        session_credentials
    )

    email_address = extract_email_address(
        sender
    )

    if not email_address:

        raise Exception(
            "Could not determine sender email address."
        )

    filter_data = {

        "criteria": {

            "from":
                email_address

        },

        "action": {

            "addLabelIds": [
                "SPAM"
            ],

            "removeLabelIds": [
                "INBOX"
            ]

        }

    }

    service.users().settings().filters().create(

        userId="me",

        body=filter_data

    ).execute()

    return {

        "success":
            True,

        "message":
            f"Sender {email_address} has been blocked."

    }