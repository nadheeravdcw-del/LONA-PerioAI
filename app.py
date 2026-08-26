from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import base64
import json
import traceback

from full_pipeline import analyze_image
from bone_pipeline import analyze_radiograph_image

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# =========================
# MEMORY STORAGE
# =========================
patients = []
current_patient = {}

# =========================
# IMAGE TO BASE64
# =========================
def image_to_base64(image_path):

    if not image_path or not os.path.exists(image_path):
        return ""

    with open(image_path, "rb") as img:
        encoded = base64.b64encode(img.read()).decode("utf-8")

    ext = image_path.split(".")[-1]

    return f"data:image/{ext};base64,{encoded}"

# =========================
# HOME
# =========================
@app.route("/")
def home():
    return render_template("index.html")

# =========================
# SERVE UPLOADS
# =========================
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# =========================
# INTRAORAL AI PIPELINE
# =========================
@app.route("/analyze", methods=["POST"])
def analyze():

    global current_patient

    try:
        file = request.files.get("image")

        if not file:
            return jsonify({
                "status": "error",
                "message": "No image uploaded"
            }), 400

        # =========================
        # SAVE IMAGE
        # =========================
        path = os.path.join(UPLOAD_FOLDER, "intra_" + file.filename)
        file.save(path)

        # =========================
        # CLINICAL CHART (optional)
        # =========================
        clinical_chart = json.loads(
            request.form.get("clinical_chart", "[]")
        )

        # =========================
        # SCALE (IMPORTANT FIX)
        # =========================
        mm_per_pixel = request.form.get("mm_per_pixel")

        if mm_per_pixel is not None and mm_per_pixel != "":
            try:
                mm_per_pixel = float(mm_per_pixel)
            except:
                mm_per_pixel = None
        else:
            mm_per_pixel = None

        print("🔍 mm_per_pixel received:", mm_per_pixel)

        # =========================
        # RUN PIPELINE
        # =========================
        try:
            results, output_img = analyze_image(path, mm_per_pixel)
        except Exception as pipeline_error:
            print("PIPELINE ERROR:", pipeline_error)
            traceback.print_exc()

            return jsonify({
                "status": "error",
                "message": "AI pipeline failed",
                "details": str(pipeline_error)
            }), 500

        if results is None:
            results = []

        # =========================
        # STORE PATIENT DATA
        # =========================
        current_patient["clinical_image"] = image_to_base64(path)
        current_patient["findings"] = results

        # store full AGW list (not just first tooth)
        current_patient["attached_gingiva"] = [
            r.get("attached_gingiva_width_mm")
            for r in results
        ]

        return jsonify({
            "status": "success",
            "results": results,
            "output_image": "/uploads/" + os.path.basename(path)
        })

    except Exception as e:

        print("🔥 SERVER ERROR:", str(e))
        traceback.print_exc()

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# =========================
# RADIOGRAPH AI
# =========================
@app.route("/analyze_radiograph", methods=["POST"])
def analyze_radiograph():

    global current_patient

    try:
        file = request.files.get("image")

        if not file:
            return jsonify({
                "status": "error",
                "message": "No image uploaded"
            }), 400

        path = os.path.join(UPLOAD_FOLDER, "rx_" + file.filename)
        file.save(path)

        result = analyze_radiograph_image(path) or {}

        current_patient["radiographic_image"] = image_to_base64(path)
        current_patient["bone_loss"] = result.get("bone_loss", 0)
        current_patient["efp_stage"] = result.get("efp_stage", "-")

        return jsonify({
            "status": "success",
            "bone_loss": current_patient["bone_loss"],
            "efp_stage": current_patient["efp_stage"]
        })

    except Exception as e:

        print("RADIOGRAPH ERROR:", str(e))

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# =========================
# SAVE PATIENT
# =========================
@app.route("/save_patient", methods=["POST"])
def save_patient():

    global current_patient
    global patients

    try:
        data = request.json

        if not data:
            return jsonify({
                "status": "error",
                "message": "No data received"
            }), 400

        current_patient.update(data)
        patients.append(current_patient.copy())
        current_patient = {}

        return jsonify({
            "status": "saved",
            "total_patients": len(patients)
        })

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# =========================
# GET PATIENTS
# =========================
@app.route("/patients")
def get_patients():
    return jsonify(patients)

# =========================
# REPORT PAGE
# =========================
@app.route("/report/<int:index>")
def report(index):

    if index < 0 or index >= len(patients):
        return "Patient not found", 404

    return render_template("report.html", data=patients[index])

# =========================
# RUN SERVER
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
