import os
import re
import json
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "saved_models")
os.makedirs(MODEL_DIR, exist_ok=True)

DATASET_FILES = ["CEAS_08.csv", "Enron.csv", "SpamAssasin.csv"]
TARGET_TOTAL = 30000
TARGET_HAM = 15000
TARGET_SPAM = 15000
TEST_SIZE = 0.20
RANDOM_STATE = 42


def clean_text(text):
    if pd.isna(text):
        return ""
    text = str(text).lower()
    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"\S+@\S+", " ", text)
    text = re.sub(r"[^a-z\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_label(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)) and value in (0, 1):
        return int(value)
    value = str(value).strip().lower()
    if value in {"spam", "1", "true", "yes", "junk", "phishing"}:
        return 1
    if value in {"ham", "0", "false", "no", "safe", "legitimate", "legit", "not spam", "not_spam"}:
        return 0
    return None


def load_dataset(filename):
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    df = pd.read_csv(path, low_memory=False)
    if "label" not in df.columns or "body" not in df.columns:
        raise ValueError(f"{filename} must contain 'label' and 'body' columns.")
    if "subject" not in df.columns:
        df["subject"] = ""
    df["text"] = (
        "Subject: " + df["subject"].fillna("").astype(str) +
        "\n" + df["body"].fillna("").astype(str)
    )
    df["label_numeric"] = df["label"].apply(normalize_label)
    df = df[["text", "label_numeric"]].dropna(subset=["label_numeric"])
    df["label_numeric"] = df["label_numeric"].astype(int)
    return df[df["text"].str.strip() != ""]


def main():
    print("=" * 70)
    print("SPAM EMAIL DETECTION - LINEAR SVM TRAINING")
    print("=" * 70)

    data = pd.concat([load_dataset(f) for f in DATASET_FILES], ignore_index=True)
    data = data.drop_duplicates(subset=["text"]).reset_index(drop=True)

    ham = data[data["label_numeric"] == 0]
    spam = data[data["label_numeric"] == 1]
    if len(ham) < TARGET_HAM or len(spam) < TARGET_SPAM:
        target_ham = len(ham)
        target_spam = len(spam)
    else:
        target_ham, target_spam = TARGET_HAM, TARGET_SPAM

    sampled = pd.concat([
        ham.sample(target_ham, random_state=RANDOM_STATE),
        spam.sample(target_spam, random_state=RANDOM_STATE)
    ], ignore_index=True).sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)

    x = sampled["text"].map(clean_text)
    y = sampled["label_numeric"]

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )

    vectorizer = TfidfVectorizer(
        max_features=100000,
        ngram_range=(1, 2),
        min_df=2,
        sublinear_tf=True
    )
    x_train_vec = vectorizer.fit_transform(x_train)
    x_test_vec = vectorizer.transform(x_test)

    model = LinearSVC(random_state=RANDOM_STATE)
    model.fit(x_train_vec, y_train)
    predictions = model.predict(x_test_vec)

    accuracy = accuracy_score(y_test, predictions) * 100
    precision = precision_score(y_test, predictions, zero_division=0) * 100
    recall = recall_score(y_test, predictions, zero_division=0) * 100
    f1 = f1_score(y_test, predictions, zero_division=0) * 100
    cm = confusion_matrix(y_test, predictions).tolist()

    joblib.dump(model, os.path.join(MODEL_DIR, "linear_svm.pkl"))
    joblib.dump(vectorizer, os.path.join(MODEL_DIR, "tfidf_vectorizer.pkl"))

    metrics = {
        "models": {
            "Linear SVM": {
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "confusion_matrix": cm,
                "test_samples": len(y_test),
                "ham_test_samples": int((y_test == 0).sum()),
                "spam_test_samples": int((y_test == 1).sum())
            }
        },
        "dataset": {
            "total_samples": len(sampled),
            "ham_samples": int((y == 0).sum()),
            "spam_samples": int((y == 1).sum()),
            "test_size": TEST_SIZE
        }
    }
    with open(os.path.join(MODEL_DIR, "model_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    with open(os.path.join(MODEL_DIR, "model_accuracies.json"), "w", encoding="utf-8") as f:
        json.dump({"accuracies": {"Linear SVM": accuracy}}, f, indent=2)

    print(f"Linear SVM accuracy: {accuracy:.2f}%")
    print("Saved: saved_models/linear_svm.pkl")
    print("Saved: saved_models/tfidf_vectorizer.pkl")


if __name__ == "__main__":
    main()
