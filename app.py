from flask import Flask, render_template, request, jsonify, send_from_directory
import cv2
import numpy as np
import os
from tensorflow.keras.models import load_model

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# =========================
# LOAD MODEL
# =========================
IMG_SIZE = 128
model = None

try:
    model_path = os.path.join(os.getcwd(), "unet_model.h5")
    model = load_model(model_path, compile=False)
    print("✅ Model loaded successfully")
except Exception as e:
    print("❌ Model loading failed:", e)

# =========================
# COLORS
# =========================
COLORS = {
    0: [0, 0, 0],        # background
    1: [0, 255, 0],      # gingiva
    2: [0, 255, 255],    # plaque
}

# =========================
# 🔥 RECESSION DETECTION (RULE BASED)
# =========================
def detect_recession_rule_based(image):

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Pale root detection
    lower = np.array([0, 0, 180])
    upper = np.array([180, 60, 255])

    mask = cv2.inRange(hsv, lower, upper)

    kernel = np.ones((5,5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    ratio = cv2.countNonZero(mask) / (image.shape[0] * image.shape[1])

    return ratio, mask

# =========================
# MAIN AI FUNCTION
# =========================
def analyze_with_ai(image_path):

    image = cv2.imread(image_path)

    if image is None:
        return ["Error loading image"], None

    original = image.copy()

    # Resize for model
    img_resized = cv2.resize(image, (IMG_SIZE, IMG_SIZE))
    img_input = img_resized / 255.0
    img_input = np.expand_dims(img_input, axis=0)

    # =========================
    # PREDICT
    # =========================
    if model is None:
        return ["Model not loaded"], None
       
    pred = model.predict(img_input)[0]
    pred_mask = np.argmax(pred, axis=-1)

    print("Unique classes:", np.unique(pred_mask))

    # Resize back
    pred_mask = cv2.resize(pred_mask.astype(np.uint8),
                           (original.shape[1], original.shape[0]),
                           interpolation=cv2.INTER_NEAREST)

    # =========================
    # 🔥 RECESSION DETECTION
    # =========================
    recession_ratio, recession_mask = detect_recession_rule_based(original)

    # =========================
    # CREATE OVERLAY
    # =========================
    colored_mask = np.zeros_like(original)

    for cls, color in COLORS.items():
        colored_mask[pred_mask == cls] = color

    # 🔥 ADD RECESSION (BLUE)
    colored_mask[recession_mask > 0] = [255, 0, 0]

    overlay = cv2.addWeighted(original, 0.7, colored_mask, 0.3, 0)

    # =========================
    # CLINICAL LOGIC
    # =========================
    total_pixels = pred_mask.size

    plaque_ratio = np.sum(pred_mask == 2) / total_pixels
    gingiva_ratio = np.sum(pred_mask == 1) / total_pixels

    findings = []

    if plaque_ratio > 0.01:
        findings.append("Plaque detected")

    if recession_ratio > 0.05:
        findings.append("Gingival recession detected")

    if gingiva_ratio < 0.05:
        findings.append("Inadequate attached gingiva")
    else:
        findings.append("Attached gingiva adequate")

    if len(findings) == 1 and "adequate" in findings[0]:
        findings = ["Healthy periodontium"]

    return findings, overlay

# =========================
# ROUTES
# =========================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/report")
def report():
    return render_template("report.html")

@app.route("/analyze", methods=["POST"])
def analyze():

    file = request.files["image"]
    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)

    findings, overlay = analyze_with_ai(path)

    filename = "output_" + file.filename
    output_path = os.path.join(UPLOAD_FOLDER, filename)

    if overlay is not None:
        cv2.imwrite(output_path, overlay)

    return jsonify({
        "findings": findings,
        "output_image": "uploads/" + filename
    })

# =========================
# RUN
# =========================
if __name__ == "__main__":
     app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
        
