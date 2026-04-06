let currentTooth = null
let calValues = []
let bopSites = 0
let totalSites = 0

let uploadedImage = null

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
}

function closePopup(){
    document.getElementById("popup").style.display = "none"
}

/* =========================
   CALCULATE CAL
========================= */
function updateCAL(){
    let pds = [
        parseFloat(document.getElementById("pd1").value) || 0,
        parseFloat(document.getElementById("pd2").value) || 0,
        parseFloat(document.getElementById("pd3").value) || 0,
        parseFloat(document.getElementById("pd4").value) || 0,
        parseFloat(document.getElementById("pd5").value) || 0,
        parseFloat(document.getElementById("pd6").value) || 0
    ]

    let pd = Math.max(...pds)
    let rec = parseFloat(document.getElementById("rec").value) || 0
    let enl = parseFloat(document.getElementById("enl").value) || 0

    let cal = pd + rec - enl

    document.getElementById("calDisplay").innerText =
        "CAL: " + cal.toFixed(1) + " mm"
}

/* =========================
   SAVE TOOTH DATA
========================= */
function saveTooth(){

    let pds = [
        parseFloat(document.getElementById("pd1").value) || 0,
        parseFloat(document.getElementById("pd2").value) || 0,
        parseFloat(document.getElementById("pd3").value) || 0,
        parseFloat(document.getElementById("pd4").value) || 0,
        parseFloat(document.getElementById("pd5").value) || 0,
        parseFloat(document.getElementById("pd6").value) || 0
    ]

    let pd = Math.max(...pds)
    let rec = parseFloat(document.getElementById("rec").value) || 0
    let enl = parseFloat(document.getElementById("enl").value) || 0
    let bop = parseInt(document.getElementById("bop").value) || 0

    let cal = pd + rec - enl

    calValues.push(cal)
    totalSites += 6
    if(bop > 0) bopSites++

    let tooth = document.getElementById("t"+currentTooth)

    if(pd >= 6) tooth.style.background = "red"
    else if(pd >= 4) tooth.style.background = "orange"
    else tooth.style.background = "green"

    closePopup()
}

/* =========================
   DIAGNOSIS
========================= */
function generateDiagnosis(){

    if (calValues.length === 0) {
        document.getElementById("diagnosis").innerText = "No data entered"
        return
    }

    let maxCAL = Math.max(...calValues)

    let stage = ""
    let management = ""

    if(maxCAL <= 2){
        stage = "Stage I"
        management = "General Dentist"
    }
    else if(maxCAL <= 4){
        stage = "Stage II"
        management = "General Dentist"
    }
    else{
        stage = "Stage III"
        management = "Refer to Periodontist"
    }

    document.getElementById("diagnosis").innerText =
        "EFP Classification: " + stage + " | " + management
}

/* =========================
   AI ANALYSIS
========================= */
function runAI(){

    let fileInput = document.getElementById("imageUpload")

    if(fileInput.files.length === 0){
        alert("Please upload an image first")
        return
    }

    let file = fileInput.files[0]
    uploadedImage = file

    let formData = new FormData()
    formData.append("image", file)

    fetch("/analyze", {
        method: "POST",
        body: formData
    })
    .then(res => res.json())
    .then(data => {

        let findingsList = document.getElementById("findings")
        findingsList.innerHTML = ""

        data.findings.forEach(item => {
            let li = document.createElement("li")
            li.innerText = item
            findingsList.appendChild(li)
        })

        let img = document.getElementById("resultImage")
        img.src = data.output_image
        img.style.display = "block"
    })
    .catch(err => {
        console.log(err)
        alert("AI failed")
    })
}

/* =========================
   SAVE PATIENT
========================= */
function savePatientData(){

    let demographics = {
        name: document.getElementById("patientName")?.value || "",
        age: document.getElementById("age")?.value || "",
        gender: document.getElementById("gender")?.value || "",
        patientId: document.getElementById("patientId")?.value || "",
        medicalHistory: document.getElementById("medicalHistory")?.value || "",
        medication: document.getElementById("medication")?.value || ""
    }

    let findings = []
    let container = document.getElementById("findings")

    if(container){
        container.querySelectorAll("li").forEach(li => findings.push(li.innerText))
    }

    let diagnosisText = document.getElementById("diagnosis")?.innerText || ""

    function finalize(imageData){

        let patient = {
            demographics: demographics,
            clinical: {
                calValues: calValues,
                bopSites: bopSites,
                totalSites: totalSites
            },
            aiFindings: findings,
            diagnosis: diagnosisText,
            image: imageData,
            date: new Date().toLocaleString()
        }

        let patients = JSON.parse(localStorage.getItem("patients")) || []
        patients.push(patient)
        localStorage.setItem("patients", JSON.stringify(patients))

        alert("Saved successfully ✅")
    }

    if(uploadedImage){
        let reader = new FileReader()
        reader.onload = function(){
            finalize(reader.result)
        }
        reader.readAsDataURL(uploadedImage)
    } else {
        finalize(null)
    }
}

/* =========================
   LOAD PATIENTS
========================= */
function loadPatients(){

    let patients = JSON.parse(localStorage.getItem("patients")) || []
    let container = document.getElementById("patientList")

    container.innerHTML = ""

    if(patients.length === 0){
        container.innerHTML = "<p>No records found</p>"
        return
    }

    patients.forEach((p, index) => {

        let div = document.createElement("div")

        div.innerHTML = `
            <h3>${p.demographics?.name || "Unnamed"}</h3>
            <p>${p.date}</p>
            <p>${p.diagnosis}</p>
            <button onclick="viewPatient(${index})">View</button>
            <button onclick="exportPDF(${index})">PDF</button>
            <hr>
        `

        container.appendChild(div)
    })
}

/* =========================
   VIEW PATIENT
========================= */
function viewPatient(index){

    let patients = JSON.parse(localStorage.getItem("patients")) || []
    let p = patients[index]

    alert(
        "Name: " + (p.demographics?.name || "") +
        "\nDate: " + p.date +
        "\nDiagnosis: " + p.diagnosis +
        "\nFindings: " + (p.aiFindings?.join(", ") || "No findings")
    )
}

/* =========================
   EXPORT PDF
========================= */
function exportPDF(index){

    let patients = JSON.parse(localStorage.getItem("patients")) || []
    let p = patients[index]

    let reportData = {
        name: p.demographics.name,
        age: p.demographics.age,
        gender: p.demographics.gender,
        id: p.demographics.patientId,
        history: p.demographics.medicalHistory,
        medication: p.demographics.medication,

        diagnosis: p.diagnosis,
        management: p.diagnosis.includes("Refer") ? 
                    "Refer to Periodontist" : 
                    "Managed by General Dentist",

        findings: p.aiFindings || [],
        image: p.image || "",

        teeth: p.clinical.calValues.map((cal, i) => ({
            tooth: i+1,
            pd: "-",       // (you didn’t store PD separately)
            cal: cal.toFixed(1),
            bop: "-", 
            rec: "-", 
            furcation: "-", 
            enl: "-"
        }))
    }

    localStorage.setItem("reportData", JSON.stringify(reportData))

    window.open("/report", "_blank")
}