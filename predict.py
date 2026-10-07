import os
import re
import math
import joblib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "saved_models")

MODEL_NAME = "linear_svm"
DISPLAY_NAME = "Linear SVM"
MODEL_FILE = "linear_svm.pkl"
VECTORIZER_FILE = "tfidf_vectorizer.pkl"
MODEL_ACCURACY = 97.93


def available_models():
    """Only Linear SVM is supported by this application."""
    return {DISPLAY_NAME: MODEL_ACCURACY}


def get_model_accuracy(model_name=MODEL_NAME):
    return MODEL_ACCURACY


def normalize_model_name(model_name=None):
    """Reject every model except Linear SVM."""
    if model_name and str(model_name).strip().lower() not in {
        "linear_svm", "linear svm", "svm"
    }:
        raise ValueError("Only the Linear SVM model is available.")
    return MODEL_NAME


class SpamPredictor:
    def __init__(self, model_name=MODEL_NAME, model_path=None, vectorizer_path=None):
        normalize_model_name(model_name)

        self.model_name = MODEL_NAME
        self.display_name = DISPLAY_NAME
        self.model_path = model_path or os.path.join(MODEL_DIR, MODEL_FILE)
        self.vectorizer_path = vectorizer_path or os.path.join(MODEL_DIR, VECTORIZER_FILE)
        self.accuracy = MODEL_ACCURACY

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Linear SVM model not found:\n{self.model_path}")
        if not os.path.exists(self.vectorizer_path):
            raise FileNotFoundError(f"TF-IDF vectorizer not found:\n{self.vectorizer_path}")

        self.model = joblib.load(self.model_path)
        self.vectorizer = joblib.load(self.vectorizer_path)

    def preprocess(self, text):
        text = "" if text is None else str(text)
        text = text.lower()
        text = re.sub(r"^(subject:|from:|to:|cc:|date:)", " ", text, flags=re.MULTILINE)
        text = re.sub(r"https?://\S+|www\.\S+", " ", text)
        text = re.sub(r"[^a-z\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _get_confidence(self, vectorized_text, prediction):
        if hasattr(self.model, "decision_function"):
            try:
                score = self.model.decision_function(vectorized_text)
                if hasattr(score, "__len__"):
                    score = score[0]
                score = max(-20.0, min(20.0, float(score)))
                spam_probability = 1.0 / (1.0 + math.exp(-score))
                ham_probability = 1.0 - spam_probability
                confidence = spam_probability if prediction == 1 else ham_probability
                return spam_probability, ham_probability, confidence
            except Exception as exc:
                print("Linear SVM confidence error:", exc)

        return (1.0, 0.0, 1.0) if prediction == 1 else (0.0, 1.0, 1.0)

    def predict(self, raw_email_text):
        cleaned = self.preprocess(raw_email_text)
        vectorized = self.vectorizer.transform([cleaned])
        prediction = int(self.model.predict(vectorized)[0])

        spam_probability, ham_probability, confidence = self._get_confidence(
            vectorized, prediction
        )

        return {
            "is_spam": prediction == 1,
            "label": "SPAM" if prediction == 1 else "HAM",
            "confidence": round(confidence * 100, 2),
            "spam_probability": round(spam_probability * 100, 2),
            "ham_probability": round(ham_probability * 100, 2),
            "model": MODEL_NAME,
            "model_name": DISPLAY_NAME,
            "model_accuracy": self.accuracy,
        }


if __name__ == "__main__":
    detector = SpamPredictor()
    print(detector.predict(
        "Subject: Urgent account notice. Please verify your account immediately."
    ))
