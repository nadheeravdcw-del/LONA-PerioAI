let currentTooth = null
let calValues = []
let rblValues = []
let bopSites = 0
let totalSites = 0
let bopScores = []
let uploadedImage = null
let aiConfidenceScore = 0
let toothChartData = []

// 🔥 EFP TOOTH-LOSS TRACKING
// Only teeth lost BECAUSE OF PERIODONTITIS count toward EFP 2018 staging
// (Stage III: >=1 tooth lost due to perio; Stage IV: >=5 teeth lost due to perio)
let teethLostPerio = 0
let teethLostOther = 0

// 🔥 SCALE VARIABLES
let scalePoints = []
let mm_per_pixel = null
let lastWidthPixels = null

/* =========================
   STAGE NAVIGATION
========================= */
function showStage(n){
    let stages = document.querySelectorAll(".stage")
    stages.forEach(s => s.style.display = "none")
    document.getElementById("stage"+n).style.display = "block"
}

/* =========================
   TOOTH POPUP
========================= */
function openTooth(num){
    currentTooth = num
    document.getElementById("popup").style.display = "block"
    document.getElementById("toothTitle").innerText = "Tooth " + num

    // reset popup fields to a clean "present" state each time it opens
    let statusEl = document.getElementById("toothStatus")
    if(statusEl) statusEl.value = "present"
    let reasonEl = document.getElementById("missingReason")
    if(reasonEl) reasonEl.value = "periodontitis"
    toggleMissingReason()
}

function closePopup(){
    document.getElementById("popup").style.display = "none"
}

/* =========================
   TOOTH STATUS (PRESENT / MISSING)
========================= */
function toggleMissingReason(){
    let statusEl = document.getElementById("toothStatus")
    let box = document.getElementById("missingReasonBox")
    if(!statusEl || !box) return

    let isMissing = statusEl.value === "missing"
    box.style.display = isMissing ? "block" : "none"

    // disable clinical inputs when the tooth is being marked as missing
    ;["pd1","pd2","pd3","pd4","pd5","pd6","rec","enl","bop","furcation"].forEach(id => {
        let el = document.getElementById(id)
        if(el) el.disabled = isMissing
    })
}

/* =========================
   CAL CALCULATION
========================= */
function updateCAL(){
    let pds = [
        parseFloat(document.getElementById("pd1").value)||0,
        parseFloat(document.getElementById("pd2").value)||0,
        parseFloat(document.getElementById("pd3").value)||0,
        parseFloat(document.getElementById("pd4").value)||0,
        parseFloat(document.getElementById("pd5").value)||0,
        parseFloat(document.getElementById("pd6").value)||0
    ]
    let pd = Math.max(...pds)
    let rec = parseFloat(document.getElementById("rec").value)||0
    let enl = parseFloat(document.getElementById("enl").value)||0
    let cal = pd + rec - enl
    document.getElementById("calDisplay").innerText =
        "CAL: " + cal.toFixed(1) + " mm"
}

/* =========================
   SAVE TOOTH
========================= */
function saveTooth(){
    let toothDiv = document.getElementById("t"+currentTooth)
    let statusEl = document.getElementById("toothStatus")
    let toothStatus = statusEl ? statusEl.value : "present"

    // =========================
    // MISSING TOOTH PATH (EFP tooth-loss criterion)
    // =========================
    if(toothStatus === "missing"){
        // remove any prior entry for this tooth so re-editing doesn't double count
        removeExistingToothEntry(currentTooth)

        let reasonEl = document.getElementById("missingReason")
        let reason = reasonEl ? reasonEl.value : "other"

        // ✅ Only periodontitis-attributed loss counts toward EFP 2018
        // Stage III (>=1) / Stage IV (>=5) staging. Caries, trauma,
        // congenital, and other reasons are recorded but excluded.
        if(reason === "periodontitis"){
            teethLostPerio++
        } else {
            teethLostOther++
        }

        toothChartData.push({
            tooth: currentTooth,
            status: "missing",
            reason: reason,
            pd: null,
            cal: null,
            bop: null,
            rec: null,
            enl: null,
            furcation: "N/A"
        })

        toothDiv.classList.add("missing")
        toothDiv.style.background = reason === "periodontitis" ? "#555" : "#999"
        toothDiv.style.color = "#fff"
        toothDiv.innerText = "✖ " + currentTooth
        toothDiv.title = "Missing — " + reason

        updateTeethLostDisplay()
        closePopup()
        return
    }

    // =========================
    // PRESENT TOOTH PATH (existing behavior)
    // =========================
    removeExistingToothEntry(currentTooth)

    let pds = [
        parseFloat(document.getElementById("pd1").value)||0,
        parseFloat(document.getElementById("pd2").value)||0,
        parseFloat(document.getElementById("pd3").value)||0,
        parseFloat(document.getElementById("pd4").value)||0,
        parseFloat(document.getElementById("pd5").value)||0,
        parseFloat(document.getElementById("pd6").value)||0
    ]
    let pd = Math.max(...pds)
    let rec = parseFloat(document.getElementById("rec").value)||0
    let enl = parseFloat(document.getElementById("enl").value)||0
    let bop = parseInt(document.getElementById("bop").value)||0
    let furcation =
        document.getElementById("furcation")?.value || "None"
    let cal = pd + rec - enl

    calValues.push(cal)
    bopScores.push(bop)
    totalSites += 6
    if(bop > 0){
        bopSites++
    }

    toothChartData.push({
        tooth: currentTooth,
        status: "present",
        pd: pd,
        cal: cal,
        bop: bop,
        rec: rec,
        enl: enl,
        furcation: furcation
    })

    let bopPercent =
    totalSites > 0
    ? ((bopSites / totalSites) * 100).toFixed(1)
    : 0

    document.getElementById("bopPrev").innerText =
        "BOP Percentage: " + bopPercent + "%"

    toothDiv.classList.remove("missing")
    toothDiv.innerText = "🦷" + currentTooth

    if(pd >= 6){
        toothDiv.style.background = "red"
    }
    else if(pd >= 4){
        toothDiv.style.background = "orange"
    }
    else{
        toothDiv.style.background = "green"
    }
    toothDiv.style.color = ""

    closePopup()
}

/* remove a previous chart entry for this tooth (re-editing a tooth
   shouldn't double-count BOP sites, CAL values, or tooth-loss tallies) */
function removeExistingToothEntry(toothNum){
    let idx = toothChartData.findIndex(t => t.tooth === toothNum)
    if(idx === -1) return

    let prev = toothChartData[idx]

    if(prev.status === "missing"){
        if(prev.reason === "periodontitis"){
            teethLostPerio = Math.max(0, teethLostPerio - 1)
        } else {
            teethLostOther = Math.max(0, teethLostOther - 1)
        }
    } else if(prev.status === "present"){
        totalSites = Math.max(0, totalSites - 6)
        if(prev.bop > 0){
            bopSites = Math.max(0, bopSites - 1)
        }
        let calIdx = calValues.indexOf(prev.cal)
        if(calIdx !== -1) calValues.splice(calIdx, 1)
    }

    toothChartData.splice(idx, 1)
}

function updateTeethLostDisplay(){
    let el = document.getElementById("teethLostPrev")
    if(el){
        el.innerText = "Teeth Lost (Periodontitis): " + teethLostPerio +
            (teethLostOther > 0 ? "  |  Other reasons: " + teethLostOther : "")
    }
}

function updateBOPPercentage(){
    let bopPercent = totalSites > 0
        ? (bopSites / totalSites) * 100
        : 0
    document.getElementById("bopPrev").innerText =
        "BOP Percentage: " + bopPercent.toFixed(1) + "%"
}

/* =========================
   DIAGNOSIS ENGINE
========================= */
function generateDiagnosis() {
    const output = document.getElementById("diagnosis");

    // =========================
    // VALIDATION
    // =========================
    if (
        !calValues ||
        !rblValues ||
        calValues.length === 0 ||
        rblValues.length === 0
    ) {
        output.innerText = "Insufficient periodontal data";
        return;
    }

    // =========================
    // CORE VALUES
    // =========================
    let maxCAL = Math.max(...calValues);
    let maxRBL = Math.max(...rblValues);
    let bopPercent = totalSites > 0
        ? (bopSites / totalSites) * 100
        : 0;
    let age =
        parseInt(document.getElementById("age")?.value) || 0;

    // ✅ FIX: tooth loss now comes from the tracked EFP counter
    // (teeth marked "Missing (Periodontitis-related)" in the popup),
    // not a nonexistent #toothLoss input.
    let toothLoss = teethLostPerio;

    let furcation =
        parseInt(document.getElementById("furcation")?.value) || 0;
    let smokingPerDay =
        parseInt(document.getElementById("smokingPerDay")?.value) || 0;
    let hba1c =
        parseFloat(document.getElementById("hba1c")?.value) || 0;

    // =========================
    // PERIODONTAL HEALTH
    // =========================
    if (maxCAL === 0 && bopPercent < 10 && toothLoss === 0) {
        output.innerText =
            "EFP 2018 PERIODONTAL DIAGNOSIS\n\n" +
            "Clinical Periodontal Health\n" +
            "Intact Periodontium\n\n" +
            "BOP: " + bopPercent.toFixed(1) + "%";
        return;
    }

    // =========================
    // GINGIVITIS
    // =========================
    if (maxCAL < 1 && bopPercent >= 10 && toothLoss === 0) {
        let gingivitisExtent =
            bopPercent < 30
                ? "Localized"
                : "Generalized";
        output.innerText =
            "EFP 2018 PERIODONTAL DIAGNOSIS\n\n" +
            gingivitisExtent +
            " Plaque-Induced Gingivitis\n\n" +
            "BOP: " + bopPercent.toFixed(1) + "%";
        return;
    }

    // =========================
    // PERIODONTITIS
    // =========================
    let diagnosis = "Periodontitis";

    // =========================
    // STAGING
    // =========================
    let stage = "Stage I";

    // Stage IV
    if (
        toothLoss >= 5 ||
        furcation >= 2
    ) {
        stage = "Stage IV";
    }
    // Stage III
    else if (
        maxCAL >= 5 ||
        maxRBL >= 33 ||
        furcation >= 1 ||
        toothLoss >= 1
    ) {
        stage = "Stage III";
    }
    // Stage II
    else if (
        maxCAL >= 3 ||
        maxRBL >= 15
    ) {
        stage = "Stage II";
    }
    // Stage I
    else {
        stage = "Stage I";
    }

   // =========================
// GRADING (EFP 2018)
// =========================
let boneLossAgeRatio =
    age > 0
        ? maxRBL / age
        : 0;

let grade = "Grade A";

// ---- Grade C ----
if (
    smokingPerDay >= 10 ||
    hba1c >= 7
) {
    grade = "Grade C";
}
// ---- Grade B ----
else if (
    smokingPerDay > 0 ||
    hba1c > 0
) {
    grade = "Grade B";
}
// ---- Bone loss / age ratio ----
else {
    if (boneLossAgeRatio > 1) {
        grade = "Grade C";
    }
    else if (boneLossAgeRatio >= 0.25) {
        grade = "Grade B";
    }
}

    // =========================
    // EXTENT
    // =========================
    let involvedTeeth =
        calValues.filter(c => c >= 3).length;
    let extentPercent =
        (involvedTeeth / calValues.length) * 100;
    let extent =
        extentPercent < 30
            ? "Localized"
            : "Generalized";

    // =========================
    // RISK FACTORS
    // =========================
    let riskFactors = "Absent";
    if (
        smokingPerDay > 0 &&
        hba1c > 0
    ) {
        riskFactors =
            "Smoking + Diabetes";
    }
    else if (smokingPerDay > 0) {
        riskFactors =
            "Smoking";
    }
    else if (hba1c > 0) {
        riskFactors =
            "Diabetes";
    }

    // =========================
    // MANAGEMENT
    // =========================
    let management = "";
    if (stage === "Stage IV") {
        management =
            "Refer to Periodontist (Complex Rehabilitation Required)";
    }
    else if (
        stage === "Stage III" ||
        smokingPerDay >= 10 ||
        hba1c >= 7 ||
        furcation >= 1
    ) {
        management =
            "Shared Care / Periodontist Referral Recommended";
    }
    else {
        management =
            "Manageable by General Dentist with NSPT and Maintenance";
    }

    // =========================
    // FINAL DIAGNOSIS
    // =========================
    output.innerText =
        "EFP 2018 PERIODONTAL DIAGNOSIS\n\n" +
        extent + " " +
        stage + " " +
        grade + " " +
        diagnosis + "\n\n" +
        "BOP: " + bopPercent.toFixed(1) + "%\n" +
        "Maximum CAL: " + maxCAL + " mm\n" +
        "Maximum RBL: " + maxRBL + "%\n" +
        "Bone Loss/Age Ratio: " +
        boneLossAgeRatio.toFixed(2) + "\n" +
        "Tooth Loss (Periodontitis): " + toothLoss + "\n" +
        "Furcation: " + furcation + "\n" +
        "Smoking: " + smokingPerDay + " cigarettes/day\n" +
        "HbA1c: " + hba1c + "%\n" +
        "Risk Factors: " + riskFactors + "\n\n" +
        "Suggested Management:\n" +
        management;
}

/* =========================
   IMAGE PREPROCESS
========================= */
function preprocessImage(file, callback){
    let img = new Image()
    let reader = new FileReader()
    reader.onload = e => img.src = e.target.result
    img.onload = function(){
        let canvas = document.createElement("canvas")
        let ctx = canvas.getContext("2d")
        let SIZE = 512
        canvas.width = SIZE
        canvas.height = SIZE
        ctx.drawImage(img, 0, 0, SIZE, SIZE)
        canvas.toBlob(blob => callback(blob), "image/jpeg", 0.9)
    }
    reader.readAsDataURL(file)
}

/* =========================
   AI FUNCTION (FINAL)
========================= */
function runAI(){
    let fileInput = document.getElementById("imageUpload")
    if(fileInput.files.length === 0){
        alert("Upload image first")
        return
    }
    // reset scale each run
    scalePoints = []
    mm_per_pixel = null
    preprocessImage(fileInput.files[0], function(processedBlob){
        let formData = new FormData()
        formData.append("image", processedBlob, "standard.jpg")
        formData.append(
            "clinical_chart",
            JSON.stringify(toothChartData)
        )
        if (mm_per_pixel !== null) {
        formData.append("mm_per_pixel", mm_per_pixel)
        }
        fetch("/analyze", { method:"POST", body:formData })
        .then(res => res.json())
        .then(data => {
            let table = document.getElementById("resultTable")
            let tbody = table.querySelector("tbody")
            tbody.innerHTML = ""
            let results = Array.isArray(data)
                ? data
                : (data.results || [])
            if(results.length === 0){
                tbody.innerHTML =
                    "<tr><td colspan='4'>No teeth detected</td></tr>"
            }
            results.forEach((tooth, index) => {
                let raw = tooth.attached_gingiva_width_mm
                let width = (
                    raw === null ||
                    raw === undefined ||
                    raw === "-" ||
                    raw === "Not Detected" ||
                    raw === ""
                ) ? null : parseFloat(raw)

                let row = document.createElement("tr")
                row.innerHTML = `
                    <td>${tooth.tooth_number ?? tooth.tooth ?? "-"}</td>
                    <td>${tooth.arch ?? "-"}</td>
                    <td>${
                        width === null || isNaN(width)
                            ? "Not Detected"
                            : width.toFixed(2)
                    }</td>
                    <td>${tooth.status || "Not Detected"}</td>
                `
                tbody.appendChild(row)
            })
            table.style.display = "table"

            if(data.output_image){
                let img = document.getElementById("resultImage")
                img.src = data.output_image + "?t=" + Date.now()
                img.style.display = "block"
            }
        })
        .catch(err => {
            console.error(err)
            alert("AI error")
        })
    })
}

function runRadiographicAI(){
    let rxFile =
        document.getElementById("rxUpload")?.files[0]
    if(!rxFile){
        alert("Upload radiograph first")
        return
    }
    let rxPreview =
        document.getElementById("rxResultImage")
    rxPreview.src =
        URL.createObjectURL(rxFile)
    rxPreview.style.display = "block"

    let rxForm = new FormData()
    rxForm.append("image", rxFile)
    fetch("/analyze_radiograph", {
        method: "POST",
        body: rxForm
    })
    .then(res => res.json())
    .then(rx => {
        console.log(rx)
        let boneLossValue =
            parseFloat(rx.bone_loss)
        if (!isNaN(boneLossValue)) {
            rblValues = [boneLossValue]
        }
        document.getElementById("boneLoss").innerText =
            "Bone Loss: " + rx.bone_loss + "%"
        document.getElementById("efpStage").innerText =
            "EFP Stage: " + rx.efp_stage
        alert("Radiographic analysis completed ✅")
    })
    .catch(err => {
        console.error("Radiograph error:", err)
        alert("Radiograph analysis failed")
    })
}

/* =========================
   SCALE SYSTEM
========================= */
document.addEventListener("DOMContentLoaded", function () {
    let img = document.getElementById("resultImage")
    if (!img) return
    img.addEventListener("click", function (e) {
        let rect = img.getBoundingClientRect()
        let scaleX = img.naturalWidth / rect.width
        let scaleY = img.naturalHeight / rect.height
        scalePoints.push({
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        })
        let dot = document.createElement("div")
        dot.className = "scale-dot"
        dot.style.position = "absolute"
        dot.style.left = (e.clientX - 5) + "px"
        dot.style.top = (e.clientY - 5) + "px"
        dot.style.width = "10px"
        dot.style.height = "10px"
        dot.style.background = "red"
        dot.style.borderRadius = "50%"
        dot.style.pointerEvents = "none"
        document.body.appendChild(dot)
        if (scalePoints.length === 2) {
            let dx = scalePoints[0].x - scalePoints[1].x
            let dy = scalePoints[0].y - scalePoints[1].y
            let pixelDistance = Math.sqrt(dx * dx + dy * dy)
            let real_mm = parseFloat(prompt("Enter real distance (mm)"))
            if (!isNaN(real_mm) && real_mm > 0 && pixelDistance > 0) {
                mm_per_pixel = real_mm / pixelDistance
                localStorage.setItem("mm_per_pixel", mm_per_pixel)
                alert("Scale set: " + mm_per_pixel.toFixed(5) + " mm/pixel")
            } else {
                alert("Invalid input for scale")
            }
            scalePoints = []
        }
    })
})

/* =========================================================
   SAVE PATIENT
========================================================= */
function savePatientData() {
    let demographics = {
        name:
            document.getElementById("patientName")?.value || "",
        age:
            document.getElementById("age")?.value || "",
        gender:
            document.getElementById("gender")?.value || "",
        patientId:
            document.getElementById("patientId")?.value || "",
        medicalHistory:
            document.getElementById("medicalHistory")?.value || "",
        medication:
            document.getElementById("medication")?.value || ""
    }

    let findings = []
    let container =
        document.getElementById("findings")
    if(container){
        container.querySelectorAll("li").forEach(li => {
            findings.push(li.innerText)
        })
    }

    let diagnosisText =
        document.getElementById("diagnosis")?.innerText || ""

    let bopPercent =
        totalSites > 0
        ? ((bopSites / totalSites) * 100).toFixed(1)
        : 0

    let patient = {
        demographics: demographics,
        clinical: {
            calValues: calValues,
            bopSites: bopSites,
            totalSites: totalSites,
            bopPercent: bopPercent,
            toothChartData: toothChartData,
            teethLostPerio: teethLostPerio,
            teethLostOther: teethLostOther
        },
        radiographic: {
            boneLoss:
                document.getElementById("boneLoss")?.innerText || "",
            efpStage:
                document.getElementById("efpStage")?.innerText || ""
        },
        aiFindings: findings,
        diagnosis: diagnosisText,
        intraoralImage:
            document.getElementById("resultImage")?.src || "",
        radiographicImage:
            document.getElementById("rxResultImage")?.src || "",
        date: new Date().toLocaleString()
    }

    fetch("/save_patient", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(patient)
    })
    .then(res => res.json())
    .then(data => {
        console.log("Saved:", data)
        alert("Saved successfully ✅")
        loadPatients()
    })
    .catch(err => {
        console.error("Save Error:", err)
        alert("Save failed ❌")
    })
}

/* =========================================================
   LOAD PATIENTS
========================================================= */
function loadPatients(){
    fetch("/patients")
    .then(res => res.json())
    .then(patients => {
        let container =
            document.getElementById("patientList")
        container.innerHTML = ""
        if(patients.length === 0){
            container.innerHTML =
                "<p>No records found</p>"
            return
        }
        patients.forEach((p, index) => {
            let div = document.createElement("div")
            div.style.border = "1px solid #ccc"
            div.style.padding = "15px"
            div.style.marginBottom = "15px"
            div.style.borderRadius = "10px"
            div.style.background = "#f9f9f9"
            div.innerHTML = `
                <h3>
                    ${p.demographics?.name || "Unnamed"}
                </h3>
                <p>
                    <b>Date:</b>
                    ${p.date || ""}
                </p>
                <p>
                    <b>Diagnosis:</b>
                    ${p.diagnosis || ""}
                </p>
                <button onclick="viewPatient(${index})">
                    View Report
                </button>
                <button onclick="exportPDF(${index})">
                    PDF
                </button>
            `
            container.appendChild(div)
        })
    })
    .catch(err => {
        console.error(err)
        alert("Failed to load patients")
    })
}

/* =========================================================
   VIEW PATIENT
========================================================= */
function viewPatient(index){
    window.open(`/report/${index}`, "_blank")
}

/* =========================================================
   EXPORT PDF
========================================================= */
function exportPDF(index){
    window.open(`/report/${index}`, "_blank")
}

/* =========================================================
   AUTO LOAD PATIENTS
========================================================= */
window.onload = function(){
    loadPatients()
}
