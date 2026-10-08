import os
import html

from flask import (
    Flask,
    send_from_directory,
    redirect,
    session,
    request,
    jsonify
)

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


# =========================================================
# LOCAL GOOGLE OAUTH
# =========================================================

# ONLY use this for local HTTP development.
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


# =========================================================
# FLASK
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

app = Flask(
    __name__,
    root_path=BASE_DIR
)

app.secret_key = "spamguard-secret-key-change-this-later"


# =========================================================
# GOOGLE SETTINGS (RENDER ONLINE REDIRECT URI)
# =========================================================

CLIENT_SECRETS_FILE = os.path.join(
    BASE_DIR,
    "credentials.json"
)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify"
]

# Render ပေါ်တွင် အလုပ်လုပ်ရန် သင့်ရဲ့ Render URL အတိအကျဖြင့် ပြင်ဆင်ထားသည်
REDIRECT_URI = 'https://spamemaildetection-63d0.onrender.com/oauth2callback'


# =========================================================
# GMAIL CONSTANTS
# =========================================================

GMAIL_INBOX_LABEL = "INBOX"
GMAIL_SPAM_LABEL = "SPAM"


# =========================================================
# CACHE CONTROL
# =========================================================

def disable_cache(response):

    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )

    response.headers["Pragma"] = "no-cache"

    response.headers["Expires"] = "0"

    return response


# =========================================================
# ANALYTICS
# =========================================================

@app.route("/analytics")
def analytics():

    response = send_from_directory(
        BASE_DIR,
        "analytics.html"
    )

    return disable_cache(response)


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    response = send_from_directory(
        BASE_DIR,
        "index.html"
    )

    return disable_cache(response)


# =========================================================
# CONNECT GMAIL
# =========================================================

@app.route("/connect-gmail")
def connect_gmail():

    response = send_from_directory(
        BASE_DIR,
        "connect-gmail.html"
    )

    return disable_cache(response)


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "credentials" not in session:

        print(
            "Dashboard blocked - no Gmail credentials."
        )

        response = redirect(
            "/connect-gmail"
        )

        return disable_cache(response)

    response = send_from_directory(
        BASE_DIR,
        "dashboard.html"
    )

    return disable_cache(response)


# =========================================================
# EMAIL DETAILS PAGE
# =========================================================

@app.route(
    "/email-details/<message_id>"
)
def email_details(message_id):

    try:

        print()
        print("=" * 60)
        print("EMAIL DETAILS PAGE")
        print("=" * 60)

        print(
            "Message ID:",
            message_id
        )

        if "credentials" not in session:

            print(
                "Email details blocked - "
                "no Gmail credentials."
            )

            response = redirect(
                "/connect-gmail"
            )

            return disable_cache(
                response
            )

        response = send_from_directory(
            BASE_DIR,
            "email-details.html"
        )

        return disable_cache(
            response
        )

    except Exception as e:

        print()
        print("=" * 60)
        print("EMAIL DETAILS PAGE ERROR")
        print("=" * 60)

        print(e)

        error_response = f"""
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
Email Details Error
</title>

<style>

body {{

    margin: 0;

    padding: 50px;

    font-family:
        Arial,
        Helvetica,
        sans-serif;

    background: #070914;

    color: white;
}}

a {{

    color: #8da2ff;

    text-decoration: none;
}}

</style>

</head>

<body>

<h1>
Email Details Error
</h1>

<p>
{html.escape(str(e))}
</p>

<br>

<a href="/dashboard">
Back to Dashboard
</a>

</body>

</html>
"""

        return error_response, 500


# =========================================================
# CSS
# =========================================================

@app.route("/style.css")
def style_css():

    response = send_from_directory(
        BASE_DIR,
        "style.css"
    )

    return disable_cache(response)


@app.route("/connect-gmail.css")
def connect_gmail_css():

    response = send_from_directory(
        BASE_DIR,
        "connect-gmail.css"
    )

    return disable_cache(response)


# =========================================================
# JAVASCRIPT
# =========================================================

@app.route("/script.js")
def script_js():

    response = send_from_directory(
        BASE_DIR,
        "script.js"
    )

    return disable_cache(response)


# =========================================================
# GOOGLE LOGIN
# =========================================================

@app.route("/google-login")
def google_login():

    try:

        print()
        print("=" * 60)
        print("STARTING GOOGLE LOGIN")
        print("=" * 60)

        old_email = session.get(
            "gmail_email"
        )

        if old_email:

            print(
                "Removing previous Gmail session:",
                old_email
            )

        session.clear()

        flow = Flow.from_client_secrets_file(

            CLIENT_SECRETS_FILE,

            scopes=SCOPES

        )

        flow.redirect_uri = REDIRECT_URI

        authorization_url, state = (
            flow.authorization_url(

                access_type="offline",

                include_granted_scopes=False,

                prompt="select_account consent"

            )
        )

        session["oauth_state"] = state

        session["code_verifier"] = (
            flow.code_verifier
        )

        session.modified = True

        print(
            "OAuth state saved:",
            bool(state)
        )

        print(
            "Code verifier saved:",
            bool(flow.code_verifier)
        )

        return redirect(
            authorization_url
        )

    except Exception as e:

        print()
        print("=" * 60)
        print("GOOGLE LOGIN ERROR")
        print("=" * 60)

        print(e)

        return f"""
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<title>
Google Authentication Failed
</title>

</head>

<body style="
    font-family: Arial, sans-serif;
    padding: 50px;
">

<h1>
Google Authentication Failed
</h1>

<p>
{html.escape(str(e))}
</p>

<br>

<a href="/connect-gmail">
Try Again
</a>

</body>

</html>
""", 500


# =========================================================
# GOOGLE OAUTH CALLBACK
# =========================================================

@app.route("/oauth2callback")
def oauth2callback():

    try:

        print()
        print("=" * 60)
        print("GOOGLE CALLBACK")
        print("=" * 60)

        state = session.get(
            "oauth_state"
        )

        code_verifier = session.get(
            "code_verifier"
        )

        print(
            "State exists:",
            bool(state)
        )

        print(
            "Code verifier exists:",
            bool(code_verifier)
        )

        if not state:

            return """
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<title>
OAuth Session Expired
</title>

</head>

<body style="
    font-family: Arial;
    padding: 50px;
">

<h1>
OAuth Session Expired
</h1>

<p>
Please start Google login again.
</p>

<a href="/connect-gmail">
Try Again
</a>

</body>

</html>
""", 400

        if not code_verifier:

            return """
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<title>
OAuth Code Verifier Missing
</title>

</head>

<body style="
    font-family: Arial;
    padding: 50px;
">

<h1>
OAuth Code Verifier Missing
</h1>

<p>
Please start Google login again.
</p>

<a href="/connect-gmail">
Try Again
</a>

</body>

</html>
""", 400

        flow = Flow.from_client_secrets_file(

            CLIENT_SECRETS_FILE,

            scopes=SCOPES,

            state=state

        )

        flow.redirect_uri = REDIRECT_URI

        flow.code_verifier = code_verifier

        print(
            "Exchanging authorization code..."
        )

        flow.fetch_token(
            authorization_response=request.url
        )

        credentials = flow.credentials

        print(
            "Google authentication successful!"
        )

        service = build(
            "gmail",
            "v1",
            credentials=credentials
        )

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
            "Logged-in Gmail account:",
            email_address
        )

        session["credentials"] = {

            "token":
                credentials.token,

            "refresh_token":
                credentials.refresh_token,

            "token_uri":
                credentials.token_uri,

            "client_id":
                credentials.client_id,

            "client_secret":
                credentials.client_secret,

            "scopes":
                list(
                    credentials.scopes or SCOPES
                )

        }

        session["gmail_email"] = (
            email_address
        )

        session.pop(
            "oauth_state",
            None
        )

        session.pop(
            "code_verifier",
            None
        )

        session.modified = True

        print(
            "New Gmail session saved."
        )

        response = redirect(
            "/dashboard"
        )

        return disable_cache(
            response
        )

    except Exception as e:

        print()
        print("=" * 60)
        print("OAUTH CALLBACK ERROR")
        print("=" * 60)

        print(e)

        session.pop(
            "oauth_state",
            None
        )

        session.pop(
            "code_verifier",
            None
        )

        return f"""
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<title>
Google Authentication Failed
</title>

</head>

<body style="
    font-family: Arial;
    padding: 50px;
">

<h1>
Google Authentication Failed
</h1>

<p>
{html.escape(str(e))}
</p>

<br>

<a href="/connect-gmail">
Try Again
</a>

</body>

</html>
""", 500


# =========================================================
# GET GMAIL CREDENTIALS
# =========================================================

def get_credentials():

    if "credentials" not in session:

        raise Exception(
            "Gmail is not connected. "
            "Please connect Gmail first."
        )

    data = session.get(
        "credentials"
    )

    if not data:

        raise Exception(
            "Gmail credentials are missing."
        )

    credentials = Credentials(

        token=data.get(
            "token"
        ),

        refresh_token=data.get(
            "refresh_token"
        ),

        token_uri=data.get(
            "token_uri"
        ),

        client_id=data.get(
            "client_id"
        ),

        client_secret=data.get(
            "client_secret"
        ),

        scopes=data.get(
            "scopes",
            SCOPES
        )

    )

    if (
        credentials.expired
        and credentials.refresh_token
    ):

        from google.auth.transport.requests import Request

        print(
            "Refreshing Gmail access token..."
        )

        credentials.refresh(
            Request()
        )

        session["credentials"]["token"] = (
            credentials.token
        )

        session.modified = True

    return credentials


# =========================================================
# GET GMAIL SERVICE
# =========================================================

def get_gmail_service():

    credentials = get_credentials()

    service = build(
        "gmail",
        "v1",
        credentials=credentials
    )

    return service


# =========================================================
# GET GMAIL PROFILE
# =========================================================

def get_gmail_profile(service):

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

    session["gmail_email"] = (
        email_address
    )

    session.modified = True

    return email_address


# =========================================================
# GET HEADER
# =========================================================

def get_message_header(
    headers,
    name
):

    wanted = name.lower()

    for header in headers:

        if (
            header.get(
                "name",
                ""
            ).lower()
            == wanted
        ):

            return header.get(
                "value",
                ""
            )

    return ""


# =========================================================
# EXTRACT EMAIL ADDRESS
# =========================================================

def extract_sender_email(sender):

    if not sender:

        return ""

    sender = str(sender)

    if "<" in sender and ">" in sender:

        start = sender.rfind("<") + 1

        end = sender.rfind(">")

        if end > start:

            return sender[
                start:end
            ].strip()

    return sender.strip()


# =========================================================
# GET ALL GMAIL MESSAGE IDS
# =========================================================

def get_all_gmail_message_ids(
    service,
    label_id,
    max_messages=None
):

    all_messages = []

    page_token = None

    while True:

        request_kwargs = {

            "userId":
                "me",

            "labelIds":
                [label_id],

            "maxResults":
                500

        }

        if page_token:

            request_kwargs[
                "pageToken"
            ] = page_token

        response = (
            service.users()
            .messages()
            .list(
                **request_kwargs
            )
            .execute()
        )

        messages = response.get(
            "messages",
            []
        )

        all_messages.extend(
            messages
        )

        if (
            max_messages is not None
            and
            len(all_messages)
            >= max_messages
        ):

            all_messages = (
                all_messages[
                    :max_messages
                ]
            )

            break

        page_token = response.get(
            "nextPageToken"
        )

        if not page_token:

            break

    return all_messages


# =========================================================
# BUILD GMAIL MESSAGE OBJECT
# =========================================================

def build_gmail_message_object(
    service,
    message_info,
    mailbox
):

    message_id = message_info.get(
        "id"
    )

    if not message_id:

        return None

    message = (
        service.users()
        .messages()
        .get(

            userId="me",

            id=message_id,

            format="metadata",

            metadataHeaders=[
                "Subject",
                "From",
                "To",
                "Date"
            ]

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

    subject = get_message_header(
        headers,
        "Subject"
    )

    sender = get_message_header(
        headers,
        "From"
    )

    receiver = get_message_header(
        headers,
        "To"
    )

    date = get_message_header(
        headers,
        "Date"
    )

    if not subject:

        subject = "(No Subject)"

    if not sender:

        sender = "Unknown Sender"

    if not receiver:

        receiver = "Unknown"

    if not date:

        date = "Unknown"

    label_ids = message.get(
        "labelIds",
        []
    )

    if GMAIL_SPAM_LABEL in label_ids:

        actual_label = (
            GMAIL_SPAM_LABEL
        )

        actual_mailbox = "spam"

    elif GMAIL_INBOX_LABEL in label_ids:

        actual_label = (
            GMAIL_INBOX_LABEL
        )

        actual_mailbox = "inbox"

    else:

        actual_label = mailbox

        actual_mailbox = (
            "spam"
            if mailbox == GMAIL_SPAM_LABEL
            else "inbox"
        )

    return {

        "id":
            message_id,

        "threadId":
            message_info.get(
                "threadId"
            ),

        "subject":
            subject,

        "sender":
            sender,

        "sender_email":
            extract_sender_email(
                sender
            ),

        "to":
            receiver,

        "date":
            date,

        "gmail_label":
            actual_label,

        "mailbox":
            actual_mailbox,

        "is_gmail_spam":
            actual_label == GMAIL_SPAM_LABEL,

        "scanned":
            False,

        "label":
            "NOT SCANNED",

        "is_spam":
            None,

        "confidence":
            None,

        "model":
            None,

        "model_name":
            None,

        "model_accuracy":
            None

    }


# =========================================================
# GET MESSAGES FROM ONE GMAIL FOLDER
# =========================================================

def get_messages_from_gmail_folder(
    service,
    label_id,
    mailbox
):

    message_infos = (
        get_all_gmail_message_ids(
            service,
            label_id
        )
    )

    emails = []

    for message_info in message_infos:

        message_id = message_info.get(
            "id"
        )

        try:

            email = (
                build_gmail_message_object(
                    service,
                    message_info,
                    mailbox
                )
            )

            if email:

                emails.append(
                    email
                )

        except Exception as item_error:

            print(
                "GMAIL MESSAGE ERROR:",
                message_id,
                item_error
            )

            continue

    return emails


# =========================================================
# GMAIL TEST
# =========================================================

@app.route("/gmail-test")
def gmail_test():

    try:

        service = get_gmail_service()

        email_address = (
            get_gmail_profile(
                service
            )
        )

        response = jsonify({

            "success":
                True,

            "email":
                email_address,

            "message":
                "Gmail connection is working."

        })

        return disable_cache(
            response
        )

    except Exception as e:

        print(
            "GMAIL TEST ERROR:",
            e
        )

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# =========================================================
# CURRENT GMAIL ACCOUNT
# =========================================================

@app.route("/gmail-account")
def gmail_account():

    try:

        service = get_gmail_service()

        email_address = (
            get_gmail_profile(
                service
            )
        )

        response = jsonify({

            "success":
                True,

            "email":
                email_address

        })

        return disable_cache(
            response
        )

    except Exception as e:

        print(
            "GMAIL ACCOUNT ERROR:",
            e
        )

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 401


# =========================================================
# GMAIL INBOX + SPAM
# =========================================================

@app.route("/gmail-inbox")
def gmail_inbox():

    try:

        print()
        print("=" * 60)
        print("LOADING REAL GMAIL INBOX + SPAM")
        print("=" * 60)

        service = get_gmail_service()

        email_address = (
            get_gmail_profile(
                service
            )
        )

        inbox_emails = (
            get_messages_from_gmail_folder(
                service,
                GMAIL_INBOX_LABEL,
                "inbox"
            )
        )

        print(
            "Real Gmail Inbox messages:",
            len(inbox_emails)
        )

        spam_emails = (
            get_messages_from_gmail_folder(
                service,
                GMAIL_SPAM_LABEL,
                "spam"
            )
        )

        print(
            "Real Gmail Spam messages:",
            len(spam_emails)
        )

        emails = (
            inbox_emails
            +
            spam_emails
        )

        unique_emails = {}

        for email in emails:

            email_id = email.get(
                "id"
            )

            if email_id:

                unique_emails[
                    email_id
                ] = email

        emails = list(
            unique_emails.values()
        )

        response = jsonify({

            "success":
                True,

            "email":
                email_address,

            "total":
                len(emails),

            "inbox_total":
                len(inbox_emails),

            "spam_total":
                len(spam_emails),

            "emails":
                emails

        })

        return disable_cache(
            response
        )

    except Exception as e:

        print()
        print("=" * 60)
        print("GMAIL INBOX ERROR")
        print("=" * 60)

        print(e)

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# =========================================================
# REAL GMAIL SPAM ENDPOINT
# =========================================================

@app.route("/gmail-spam")
def gmail_spam():

    try:

        print()
        print("=" * 60)
        print("LOADING REAL GMAIL SPAM")
        print("=" * 60)

        service = get_gmail_service()

        email_address = (
            get_gmail_profile(
                service
            )
        )

        emails = (
            get_messages_from_gmail_folder(
                service,
                GMAIL_SPAM_LABEL,
                "spam"
            )
        )

        response = jsonify({

            "success":
                True,

            "email":
                email_address,

            "total":
                len(emails),

            "emails":
                emails

        })

        return disable_cache(
            response
        )

    except Exception as e:

        print(
            "GMAIL SPAM ERROR:",
            e
        )

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# =========================================================
# GET ONE EMAIL API
# =========================================================

@app.route(
    "/api/email/<message_id>"
)
def api_email(message_id):

    try:

        print()
        print("=" * 60)
        print("GET EMAIL API")
        print("=" * 60)

        print(
            "Message ID:",
            message_id
        )

        if "credentials" not in session:

            return jsonify({

                "success":
                    False,

                "error":
                    "Gmail is not connected."

            }), 401

        service = get_gmail_service()

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

        from scan_gmail import (
            get_header,
            extract_email_body
        )

        subject = get_header(
            headers,
            "Subject"
        )

        sender = get_header(
            headers,
            "From"
        )

        receiver = get_header(
            headers,
            "To"
        )

        date = get_header(
            headers,
            "Date"
        )

        if not subject:

            subject = "(No Subject)"

        if not sender:

            sender = "Unknown Sender"

        if not receiver:

            receiver = "Unknown"

        if not date:

            date = "Unknown"

        body = extract_email_body(
            payload
        )

        if not body:

            body = (
                "No readable text "
                "was found in this email."
            )

        label_ids = message.get(
            "labelIds",
            []
        )

        if GMAIL_SPAM_LABEL in label_ids:

            gmail_label = (
                GMAIL_SPAM_LABEL
            )

            mailbox = "spam"

        elif GMAIL_INBOX_LABEL in label_ids:

            gmail_label = (
                GMAIL_INBOX_LABEL
            )

            mailbox = "inbox"

        else:

            gmail_label = None

            mailbox = "other"

        result = {

            "id":
                message_id,

            "threadId":
                message.get(
                    "threadId"
                ),

            "subject":
                subject,

            "sender":
                sender,

            "sender_email":
                extract_sender_email(
                    sender
                ),

            "to":
                receiver,

            "date":
                date,

            "body":
                body,

            "gmail_label":
                gmail_label,

            "mailbox":
                mailbox,

            "is_gmail_spam":
                mailbox == "spam",

            "scanned":
                False,

            "label":
                "NOT SCANNED",

            "is_spam":
                None,

            "confidence":
                None,

            "model":
                None,

            "model_name":
                None,

            "model_accuracy":
                None

        }

        response = jsonify({

            "success":
                True,

            "email":
                session.get(
                    "gmail_email",
                    "Unknown"
                ),

            "result":
                result

        })

        return disable_cache(
            response
        )

    except Exception as e:

        print()
        print("=" * 60)
        print("GET EMAIL API ERROR")
        print("=" * 60)

        print(e)

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# =========================================================
# SCAN ONE EMAIL
# =========================================================

@app.route(
    "/scan-email/<message_id>",
    methods=["POST"]
)
def scan_one_email_route(
    message_id
):

    try:

        print()
        print("=" * 60)
        print("SCANNING ONE EMAIL")
        print("=" * 60)

        print(
            "Message ID:",
            message_id
        )

        credentials = get_credentials()

        service = build(
            "gmail",
            "v1",
            credentials=credentials
        )

        from scan_gmail import (
            get_email_details
        )

        from predict import (
            SpamPredictor
        )

        email = get_email_details(
            session["credentials"],
            message_id
        )

        model_name = "linear_svm"

        detector = SpamPredictor(
            model_name=model_name
        )

        full_content = (
            "Subject: "
            + email.get(
                "subject",
                ""
            )
            + "\n\n"
            + email.get(
                "body",
                ""
            )
        )

        prediction = detector.predict(
            full_content
        )

        is_spam = bool(
            prediction["is_spam"]
        )

        real_message = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata"
            )
            .execute()
        )

        gmail_labels = real_message.get(
            "labelIds",
            []
        )

        if GMAIL_SPAM_LABEL in gmail_labels:

            gmail_label = (
                GMAIL_SPAM_LABEL
            )

            mailbox = "spam"

        elif GMAIL_INBOX_LABEL in gmail_labels:

            gmail_label = (
                GMAIL_INBOX_LABEL
            )

            mailbox = "inbox"

        else:

            gmail_label = None

            mailbox = "other"

        result = {

            "id":
                message_id,

            "subject":
                email.get(
                    "subject",
                    "(No Subject)"
                ),

            "sender":
                email.get(
                    "sender",
                    "Unknown Sender"
                ),

            "sender_email":
                email.get(
                    "sender_email",
                    ""
                ),

            "to":
                email.get(
                    "to",
                    ""
                ),

            "date":
                email.get(
                    "date",
                    "Unknown"
                ),

            "label":
                "SPAM"
                if is_spam
                else
                "SAFE",

            "is_spam":
                is_spam,

            "confidence":
                prediction.get(
                    "confidence"
                ),

            "model":
                prediction.get(
                    "model",
                    "linear_svm"
                ),

            "model_name":
                prediction.get(
                    "model_name",
                    "Linear SVM"
                ),

            "model_accuracy":
                prediction.get(
                    "model_accuracy",
                    97.93
                ),

            "scanned":
                True,

            "gmail_label":
                gmail_label,

            "mailbox":
                mailbox,

            "is_gmail_spam":
                mailbox == "spam"

        }

        print(
            "Linear SVM result:",
            "SPAM" if is_spam else "SAFE"
        )

        print(
            "Real Gmail mailbox:",
            mailbox
        )

        response = jsonify({

            "success":
                True,

            "email":
                session.get(
                    "gmail_email",
                    "Unknown"
                ),

            "result":
                result

        })

        return disable_cache(
            response
        )

    except Exception as e:

        print()
        print("=" * 60)
        print("SINGLE EMAIL SCAN ERROR")
        print("=" * 60)

        print(e)

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# =========================================================
# SCAN GMAIL
# =========================================================

@app.route("/scan-gmail")
def scan_gmail_route():

    try:

        print()
        print("=" * 60)
        print("GMAIL SCAN REQUEST")
        print("=" * 60)

        if "credentials" not in session:

            return jsonify({

                "success":
                    False,

                "error":
                    "Gmail is not connected."

            }), 401

        print(
            "Scanning account:",
            session.get(
                "gmail_email",
                "Unknown"
            )
        )

        from scan_gmail import (
            scan_gmail_for_web
        )

        model_name = "linear_svm"

        results = scan_gmail_for_web(

            session_credentials=
                session["credentials"],

            model_name=
                model_name

        )

        response = jsonify(
            results
        )

        return disable_cache(
            response
        )

    except Exception as e:

        print()
        print("=" * 60)
        print("SCAN ERROR")
        print("=" * 60)

        print(e)

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# =========================================================
# MODEL INFORMATION
# =========================================================

@app.route("/model-info")
def model_info():

    response = jsonify({

        "success":
            True,

        "models": [

            {

                "key":
                    "linear_svm",

                "name":
                    "Linear SVM",

                "accuracy":
                    97.93,

                "precision":
                    97.93,

                "recall":
                    97.93,

                "f1_score":
                    97.93,

                "confusion_matrix":
                    {},

                "test_samples":
                    0,

                "ham_test_samples":
                    0,

                "spam_test_samples":
                    0

            }

        ],

        "dataset":
            {}

    })

    return disable_cache(
        response
    )


# =========================================================
# MOVE MESSAGE TO REAL GMAIL SPAM
# =========================================================

@app.route(
    "/move-to-spam/<message_id>",
    methods=["POST"]
)
def move_to_spam_route(
    message_id
):

    try:

        print()
        print("=" * 60)
        print("MOVE MESSAGE TO REAL GMAIL SPAM")
        print("=" * 60)

        print(
            "Message ID:",
            message_id
        )

        if "credentials" not in session:

            return jsonify({

                "success":
                    False,

                "error":
                    "Gmail is not connected."

            }), 401

        service = get_gmail_service()

        modified_message = (
            service.users()
            .messages()
            .modify(

                userId="me",

                id=message_id,

                body={

                    "addLabelIds": [
                        GMAIL_SPAM_LABEL
                    ],

                    "removeLabelIds": [
                        GMAIL_INBOX_LABEL
                    ]

                }

            )
            .execute()
        )

        labels_after = modified_message.get(
            "labelIds",
            []
        )

        is_spam = (
            GMAIL_SPAM_LABEL
            in labels_after
        )

        print(
            "Moved to real Gmail Spam:",
            is_spam
        )

        if not is_spam:

            return jsonify({

                "success":
                    False,

                "error":
                    "Gmail did not confirm the message is in Spam."

            }), 500

        response = jsonify({

            "success":
                True,

            "message":
                "Email moved to Gmail Spam.",

            "id":
                message_id,

            "gmail_label":
                GMAIL_SPAM_LABEL,

            "mailbox":
                "spam",

            "is_gmail_spam":
                True

        })

        return disable_cache(
            response
        )

    except Exception as e:

        print()
        print("=" * 60)
        print("MOVE TO SPAM ERROR")
        print("=" * 60)

        print(e)

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# =========================================================
# MOVE MESSAGE TO REAL GMAIL INBOX / SAFE
# =========================================================

@app.route(
    "/move-to-safe/<message_id>",
    methods=["POST"]
)
def move_to_safe_route(
    message_id
):

    try:

        print()
        print("=" * 60)
        print("MOVE MESSAGE TO REAL GMAIL INBOX")
        print("=" * 60)

        print(
            "Message ID:",
            message_id
        )

        if "credentials" not in session:

            return jsonify({

                "success":
                    False,

                "error":
                    "Gmail is not connected."

            }), 401

        service = get_gmail_service()

        modified_message = (
            service.users()
            .messages()
            .modify(

                userId="me",

                id=message_id,

                body={

                    "addLabelIds": [
                        GMAIL_INBOX_LABEL
                    ],

                    "removeLabelIds": [
                        GMAIL_SPAM_LABEL
                    ]

                }

            )
            .execute()
        )

        labels_after = modified_message.get(
            "labelIds",
            []
        )

        is_inbox = (
            GMAIL_INBOX_LABEL
            in labels_after
        )

        is_spam = (
            GMAIL_SPAM_LABEL
            in labels_after
        )

        print(
            "In Gmail Inbox:",
            is_inbox
        )

        print(
            "Still in Gmail Spam:",
            is_spam
        )

        if (
            not is_inbox
            or
            is_spam
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "Gmail did not confirm the message was moved to Inbox."

            }), 500

        response = jsonify({

            "success":
                True,

            "message":
                "Email moved to Gmail Inbox.",

            "id":
                message_id,

            "gmail_label":
                GMAIL_INBOX_LABEL,

            "mailbox":
                "inbox",

            "is_gmail_spam":
                False

        })

        return disable_cache(
            response
        )

    except Exception as e:

        print()
        print("=" * 60)
        print("MOVE TO SAFE ERROR")
        print("=" * 60)

        print(e)

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    print()
    print("=" * 60)
    print("LOGOUT REQUEST")
    print("=" * 60)

    old_email = session.get(
        "gmail_email"
    )

    print(
        "Logging out account:",
        old_email or "Unknown"
    )

    session.clear()

    print(
        "Session after clear:",
        dict(session)
    )

    response = redirect(
        "/connect-gmail"
    )

    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )

    response.headers["Pragma"] = "no-cache"

    response.headers["Expires"] = "0"

    print(
        "Logout complete."
    )

    return response


# =========================================================
# RUN FLASK SERVER
# =========================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print("SPAMGUARD AI")
    print("=" * 60)

    print(
        "Starting Flask server..."
    )

    print(
        "Local:"
    )

    print(
        "http://127.0.0.1:5000"
    )

    print(
        "Network:"
    )

    print(
        "http://192.168.1.9:5000"
    )

    print("=" * 60)

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )