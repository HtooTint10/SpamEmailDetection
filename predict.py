
import os
import re
import math
import joblib

# =========================================================
# PROJECT PATHS AND MODEL SETTINGS
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "saved_models")

MODEL_NAME = "linear_svm"
DISPLAY_NAME = "Linear SVM"
MODEL_FILE = "linear_svm.pkl"
VECTORIZER_FILE = "tfidf_vectorizer.pkl"
MODEL_ACCURACY = 97.93


# =========================================================
# MODEL INFORMATION
# =========================================================

def available_models():
    return {DISPLAY_NAME: MODEL_ACCURACY}


def get_model_accuracy(model_name=MODEL_NAME):
    return MODEL_ACCURACY


def normalize_model_name(model_name=None):
    if model_name and str(model_name).strip().lower() not in {
        "linear_svm",
        "linear svm",
        "svm",
    }:
        raise ValueError("Only the Linear SVM model is available.")
    return MODEL_NAME


# =========================================================
# SAFE SHORT CONVERSATIONAL MESSAGES
# =========================================================

SAFE_SHORT_MESSAGES = {
    "hello",
    "hi",
    "hey",
    "hello friend",
    "hi friend",
    "hey friend",
    "dear friend",
    "friend",
    "good morning",
    "good afternoon",
    "good evening",
    "good night",
    "morning",
    "afternoon",
    "evening",
    "night",
    "how are you",
    "how are you doing",
    "how are things",
    "thank you",
    "thanks",
    "many thanks",
    "please",
    "take care",
    "see you",
    "see you soon",
    "talk soon",
    "have a nice day",
    "have a good day",
    "have a good night",
    "good day",
    "welcome",
    "long time no see",
    "what are you doing",
    "what's up",
    "Hello friend,what are you doing?",
    "Hello friend, how are you doing?",
    "Hello friend, how are you?",
    "Hello friend, how are things?",
    "Hello friend, how are you doing today?",
}

SAFE_GREETING_WORDS = {
    "hello",
    "hi",
    "hey",
    "friend",
    "dear",
    "morning",
    "afternoon",
    "evening",
    "night",
    "thanks",
    "thank",
    "please",
    "welcome",
}

SUSPICIOUS_WORDS = {
    "click",
    "claim",
    "prize",
    "winner",
    "won",
    "free",
    "urgent",
    "verify",
    "verification",
    "password",
    "account",
    "login",
    "signin",
    "payment",
    "invoice",
    "refund",
    "bitcoin",
    "crypto",
    "money",
    "cash",
    "offer",
    "bonus",
    "unsubscribe",
    "download",
    "attachment",
    "limited",
    "security",
    "confirm",
    "wire",
    "gift",
    "lottery",
}


# =========================================================
# SPAM PREDICTOR
# =========================================================

class SpamPredictor:

    def __init__(
        self,
        model_name=MODEL_NAME,
        model_path=None,
        vectorizer_path=None,
    ):
        normalize_model_name(model_name)

        self.model_name = MODEL_NAME
        self.display_name = DISPLAY_NAME

        self.model_path = model_path or os.path.join(
            MODEL_DIR, MODEL_FILE
        )
        self.vectorizer_path = vectorizer_path or os.path.join(
            MODEL_DIR, VECTORIZER_FILE
        )

        self.accuracy = MODEL_ACCURACY

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"Linear SVM model not found:\n{self.model_path}"
            )

        if not os.path.exists(self.vectorizer_path):
            raise FileNotFoundError(
                f"TF-IDF vectorizer not found:\n{self.vectorizer_path}"
            )

        self.model = joblib.load(self.model_path)
        self.vectorizer = joblib.load(self.vectorizer_path)

    # -----------------------------------------------------
    # TEXT PREPROCESSING
    # -----------------------------------------------------

    def preprocess(self, text):
        text = "" if text is None else str(text)
        text = text.lower()

        text = re.sub(
            r"^(subject:|from:|to:|cc:|date:)",
            " ",
            text,
            flags=re.MULTILINE | re.IGNORECASE,
        )

        text = re.sub(
            r"https?://\S+|www\.\S+",
            " ",
            text,
        )

        text = re.sub(r"[^a-z\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    # -----------------------------------------------------
    # CONFIDENCE CALCULATION
    # -----------------------------------------------------

    def _get_confidence(self, vectorized_text, prediction):
        if hasattr(self.model, "decision_function"):
            try:
                score = self.model.decision_function(
                    vectorized_text
                )

                if hasattr(score, "__len__"):
                    score = score[0]

                score = max(-20.0, min(20.0, float(score)))

                spam_probability = 1.0 / (
                    1.0 + math.exp(-score)
                )
                ham_probability = 1.0 - spam_probability

                confidence = (
                    spam_probability
                    if prediction == 1
                    else ham_probability
                )

                return (
                    spam_probability,
                    ham_probability,
                    confidence,
                )

            except Exception as exc:
                print("Linear SVM confidence error:", exc)

        if prediction == 1:
            return 1.0, 0.0, 1.0

        return 0.0, 1.0, 1.0

    # -----------------------------------------------------
    # SAFE MESSAGE RULE
    # -----------------------------------------------------

    def _is_obvious_safe_short_message(self, cleaned):
        if not cleaned:
            return False

        words = cleaned.split()

        # Suspicious words prevent the safe-message override.
        if any(word in SUSPICIOUS_WORDS for word in words):
            return False

        # Exact safe phrases, regardless of original letter case.
        if cleaned in SAFE_SHORT_MESSAGES:
            return True

        # Short, ordinary greetings such as:
        # HELLO THERE, Hi my friend, GOOD MORNING FRIEND.
        if len(words) <= 5:
            if any(word in SAFE_GREETING_WORDS for word in words):
                return True

        return False

    # -----------------------------------------------------
    # PREDICTION
    # -----------------------------------------------------

    def predict(self, raw_email_text):
        cleaned = self.preprocess(raw_email_text)

        # Always check safe-message rules before the SVM.
        if self._is_obvious_safe_short_message(cleaned):
            return {
                "is_spam": False,
                "label": "HAM",
                "confidence": 99.0,
                "spam_probability": 0.0,
                "ham_probability": 99.0,
                "model": MODEL_NAME,
                "model_name": DISPLAY_NAME,
                "model_accuracy": self.accuracy,
                "prediction_source": "short_safe_message_rule",
            }

        # Use the trained Linear SVM for all other messages.
        vectorized = self.vectorizer.transform([cleaned])
        prediction = int(self.model.predict(vectorized)[0])

        spam_probability, ham_probability, confidence = (
            self._get_confidence(vectorized, prediction)
        )

        return {
            "is_spam": prediction == 1,
            "label": "SPAM" if prediction == 1 else "HAM",
            "confidence": round(confidence * 100, 2),
            "spam_probability": round(
                spam_probability * 100, 2
            ),
            "ham_probability": round(
                ham_probability * 100, 2
            ),
            "model": MODEL_NAME,
            "model_name": DISPLAY_NAME,
            "model_accuracy": self.accuracy,
            "prediction_source": "linear_svm",
        }


# =========================================================
# DIRECT TEST
# =========================================================

if __name__ == "__main__":
    detector = SpamPredictor()

    tests = [
        "HELLO",
        "hello",
        "HeLLo",
        "GOOD MORNING",
        "Good morning friend",
        "THANK YOU",
        "How are you?",
        "Subject: HELLO",
        "Subject: Good night",
        "Hello, click here to claim your prize",
        "Urgent account notice. Please verify your account immediately.",
    ]

    for email_text in tests:
        result = detector.predict(email_text)

        print(
            f"{email_text!r} -> "
            f"{result['label']} | "
            f"{result['confidence']}% | "
            f"{result['prediction_source']}"
        )