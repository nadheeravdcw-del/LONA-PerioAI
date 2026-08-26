import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO
from tensorflow.keras.models import load_model


# =========================================================
# CONFIGURATION
# =========================================================

IMG_SIZE = 128

# U-Net classes
BACKGROUND = 0
FGM = 1
MGJ = 2

# YOLO
YOLO_CONFIDENCE = 0.50

# ---------------------------------------------------------
# Tooth crop expansion
# ---------------------------------------------------------

CROP_X_MARGIN = 0.20
CROP_Y_MARGIN_TOP = 0.35
CROP_Y_MARGIN_BOTTOM = 0.35

# ---------------------------------------------------------
# Central corridor
#
# Only the central portion of the tooth crop is used for
# FGM/MGJ geometry.
# ---------------------------------------------------------

CORRIDOR_LEFT = 0.25
CORRIDOR_RIGHT = 0.75

# ---------------------------------------------------------
# Minimum segmentation pixels
# ---------------------------------------------------------

MIN_FGM_PIXELS = 5
MIN_MGJ_PIXELS = 5

# ---------------------------------------------------------
# Maximum reasonable WAG
#
# This is a safety filter, not a clinical diagnosis.
# ---------------------------------------------------------

MAX_WAG_MM = 15.0

# ---------------------------------------------------------
# Minimum/maximum geometry distance in U-Net pixels
#
# 128 x 128 model space.
# ---------------------------------------------------------

MIN_BOUNDARY_DISTANCE_PX = 3
MAX_BOUNDARY_DISTANCE_PX = 70

# ---------------------------------------------------------
# Fallback tooth widths
#
# Used ONLY when the user has not calibrated the image.
# ---------------------------------------------------------

UPPER_TOOTH_WIDTH_MM = 8.5
LOWER_TOOTH_WIDTH_MM = 7.5


# =========================================================
# MODEL PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

YOLO_MODEL_PATH = (
    BASE_DIR
    / "yolo_project"
    / "runs"
    / "detect"
    / "train3"
    / "weights"
    / "best.pt"
)

UNET_MODEL_PATH = (
    BASE_DIR
    / "unet_model.h5"
)


# =========================================================
# LOAD MODELS
# =========================================================

print("Loading YOLO model...")
yolo_model = YOLO(str(YOLO_MODEL_PATH))

print("Loading U-Net model...")
unet_model = load_model(
    str(UNET_MODEL_PATH),
    compile=False
)

print("Models loaded successfully.")


# =========================================================
# FDI TOOTH MAP
# =========================================================

QUADRANT_MAP = {

    "UR": [
        18, 17, 16, 15,
        14, 13, 12, 11
    ],

    "UL": [
        21, 22, 23, 24,
        25, 26, 27, 28
    ],

    "LL": [
        31, 32, 33, 34,
        35, 36, 37, 38
    ],

    "LR": [
        48, 47, 46, 45,
        44, 43, 42, 41
    ]
}


# =========================================================
# WAG CLASSIFICATION
# =========================================================

def classify_wag(wag_mm):

    if wag_mm is None:
        return "Not Detected"

    if wag_mm < 2.0:
        return "Inadequate"

    return "Adequate"


# =========================================================
# DETERMINE ARCH + QUADRANT
# =========================================================

def determine_quadrant(
    cx,
    cy,
    image_width,
    image_height
):

    # -----------------------------------------------------
    # Upper arch
    # -----------------------------------------------------

    if cy < image_height / 2:

        arch = "upper"

        if cx >= image_width / 2:
            quadrant = "UR"
        else:
            quadrant = "UL"

    # -----------------------------------------------------
    # Lower arch
    # -----------------------------------------------------

    else:

        arch = "lower"

        if cx >= image_width / 2:
            quadrant = "LR"
        else:
            quadrant = "LL"

    return arch, quadrant


# =========================================================
# CROP TOOTH
# =========================================================

def crop_tooth(
    img,
    x1,
    y1,
    x2,
    y2
):

    h, w = img.shape[:2]

    tooth_width = max(
        1,
        x2 - x1
    )

    tooth_height = max(
        1,
        y2 - y1
    )

    margin_x = int(
        tooth_width *
        CROP_X_MARGIN
    )

    margin_top = int(
        tooth_height *
        CROP_Y_MARGIN_TOP
    )

    margin_bottom = int(
        tooth_height *
        CROP_Y_MARGIN_BOTTOM
    )

    crop_x1 = max(
        0,
        x1 - margin_x
    )

    crop_x2 = min(
        w,
        x2 + margin_x
    )

    crop_y1 = max(
        0,
        y1 - margin_top
    )

    crop_y2 = min(
        h,
        y2 + margin_bottom
    )

    crop = img[
        crop_y1:crop_y2,
        crop_x1:crop_x2
    ]

    return (
        crop,
        crop_x1,
        crop_y1,
        crop_x2,
        crop_y2
    )


# =========================================================
# U-NET SEGMENTATION
# =========================================================

def segment_tooth(crop):

    if crop is None:
        return None

    if crop.size == 0:
        return None

    # -----------------------------------------------------
    # Resize to U-Net input size
    # -----------------------------------------------------

    resized = cv2.resize(
        crop,
        (IMG_SIZE, IMG_SIZE),
        interpolation=cv2.INTER_AREA
    )

    input_image = (
        resized.astype(np.float32) /
        255.0
    )

    input_image = np.expand_dims(
        input_image,
        axis=0
    )

    prediction = unet_model.predict(
        input_image,
        verbose=0
    )

    # -----------------------------------------------------
    # Convert softmax/probability map to class mask
    # -----------------------------------------------------

    mask = np.argmax(
        prediction[0],
        axis=-1
    ).astype(np.uint8)

    return mask


# =========================================================
# GET CENTRAL CORRIDOR
# =========================================================

def get_central_corridor(mask):

    if mask is None:
        return None

    height, width = mask.shape

    x_start = int(
        width * CORRIDOR_LEFT
    )

    x_end = int(
        width * CORRIDOR_RIGHT
    )

    x_start = max(
        0,
        min(x_start, width - 1)
    )

    x_end = max(
        x_start + 1,
        min(x_end, width)
    )

    corridor = mask[
        :,
        x_start:x_end
    ]

    return corridor


# =========================================================
# GET CLASS PIXEL ROWS
# =========================================================

def get_class_rows(
    corridor,
    class_id
):

    if corridor is None:
        return np.array([])

    rows, cols = np.where(
        corridor == class_id
    )

    return rows


# =========================================================
# FIND BOUNDARY CANDIDATES
# =========================================================

def find_boundary_candidates(
    rows,
    class_name
):

    if rows is None:
        return []

    rows = np.asarray(
        rows,
        dtype=np.float32
    )

    if len(rows) == 0:
        return []

    # -----------------------------------------------------
    # Remove extreme outliers.
    #
    # We do not simply use the mean because segmentation
    # can contain isolated pixels.
    # -----------------------------------------------------

    q10 = np.percentile(
        rows,
        10
    )

    q25 = np.percentile(
        rows,
        25
    )

    q50 = np.percentile(
        rows,
        50
    )

    q75 = np.percentile(
        rows,
        75
    )

    q90 = np.percentile(
        rows,
        90
    )

    candidates = [
        float(q10),
        float(q25),
        float(q50),
        float(q75),
        float(q90)
    ]

    return candidates


# =========================================================
# SELECT FGM + MGJ BOUNDARIES
# =========================================================

def select_boundaries(
    fgm_candidates,
    mgj_candidates,
    arch
):

    if not fgm_candidates:
        return None, None, "FGM not detected"

    if not mgj_candidates:
        return None, None, "MGJ not detected"

    possible_pairs = []

    # -----------------------------------------------------
    # IMPORTANT GEOMETRY
    #
    # Image coordinates increase DOWNWARD.
    #
    # UPPER ARCH:
    #
    # MGJ is normally ABOVE FGM
    # therefore:
    #
    #       MGJ y < FGM y
    #
    # LOWER ARCH:
    #
    # FGM is normally ABOVE MGJ
    # therefore:
    #
    #       FGM y < MGJ y
    # -----------------------------------------------------

    for fgm in fgm_candidates:

        for mgj in mgj_candidates:

            distance = abs(
                float(fgm) -
                float(mgj)
            )

            if (
                distance <
                MIN_BOUNDARY_DISTANCE_PX
            ):
                continue

            if (
                distance >
                MAX_BOUNDARY_DISTANCE_PX
            ):
                continue

            if arch == "upper":

                # CORRECT upper geometry
                if mgj < fgm:

                    possible_pairs.append(
                        (
                            fgm,
                            mgj,
                            distance
                        )
                    )

            else:

                # CORRECT lower geometry
                if fgm < mgj:

                    possible_pairs.append(
                        (
                            fgm,
                            mgj,
                            distance
                        )
                    )

    # -----------------------------------------------------
    # No valid geometry
    # -----------------------------------------------------

    if not possible_pairs:

        if arch == "upper":

            return (
                None,
                None,
                "Invalid upper geometry"
            )

        else:

            return (
                None,
                None,
                "Invalid lower geometry"
            )

    # -----------------------------------------------------
    # Choose the pair with the smallest reasonable
    # boundary distance.
    #
    # This prevents distant segmentation regions from
    # being interpreted as attached gingiva.
    # -----------------------------------------------------

    possible_pairs.sort(
        key=lambda x: x[2]
    )

    best = possible_pairs[0]

    fgm_y = float(best[0])
    mgj_y = float(best[1])
    distance = float(best[2])

    return (
        fgm_y,
        mgj_y,
        "Valid"
    )


# =========================================================
# FIND FGM + MGJ
# =========================================================

def find_boundary_positions(
    mask,
    arch
):

    if mask is None:

        return (
            None,
            None,
            "No segmentation"
        )

    corridor = get_central_corridor(
        mask
    )

    if corridor is None:

        return (
            None,
            None,
            "No corridor"
        )

    fgm_rows = get_class_rows(
        corridor,
        FGM
    )

    mgj_rows = get_class_rows(
        corridor,
        MGJ
    )

    fgm_count = len(fgm_rows)
    mgj_count = len(mgj_rows)

    print(
        f"FGM pixels: {fgm_count}"
    )

    print(
        f"MGJ pixels: {mgj_count}"
    )

    # -----------------------------------------------------
    # Minimum pixel validation
    # -----------------------------------------------------

    if fgm_count < MIN_FGM_PIXELS:

        print(
            "Geometry: FGM not detected"
        )

        return (
            None,
            None,
            "FGM not detected"
        )

    if mgj_count < MIN_MGJ_PIXELS:

        print(
            "Geometry: MGJ not detected"
        )

        return (
            None,
            None,
            "MGJ not detected"
        )

    # -----------------------------------------------------
    # Generate boundary candidates
    # -----------------------------------------------------

    fgm_candidates = (
        find_boundary_candidates(
            fgm_rows,
            "FGM"
        )
    )

    mgj_candidates = (
        find_boundary_candidates(
            mgj_rows,
            "MGJ"
        )
    )

    # -----------------------------------------------------
    # Select geometrically valid pair
    # -----------------------------------------------------

    fgm_y, mgj_y, geometry_status = (
        select_boundaries(
            fgm_candidates,
            mgj_candidates,
            arch
        )
    )

    print(
        "Geometry:",
        geometry_status
    )

    if (
        fgm_y is not None and
        mgj_y is not None
    ):

        print(
            f"FGM row: {fgm_y:.2f}"
        )

        print(
            f"MGJ row: {mgj_y:.2f}"
        )

        print(
            f"Boundary distance: "
            f"{abs(fgm_y - mgj_y):.2f}px"
        )

    else:

        print(
            "NO RELIABLE FGM → MGJ GEOMETRY"
        )

    return (
        fgm_y,
        mgj_y,
        geometry_status
    )


# =========================================================
# PIXEL DISTANCE
# =========================================================

def calculate_pixel_distance(
    fgm_y,
    mgj_y
):

    if fgm_y is None:
        return None

    if mgj_y is None:
        return None

    distance = abs(
        float(fgm_y) -
        float(mgj_y)
    )

    if (
        distance <
        MIN_BOUNDARY_DISTANCE_PX
    ):
        return None

    if (
        distance >
        MAX_BOUNDARY_DISTANCE_PX
    ):
        return None

    return float(distance)


# =========================================================
# PIXEL → MM
# =========================================================

def calculate_wag_mm(
    pixel_distance,
    crop_height_pixels,
    mm_per_pixel
):

    if pixel_distance is None:
        return None

    if mm_per_pixel is None:
        return None

    if crop_height_pixels <= 0:
        return None

    # -----------------------------------------------------
    # U-Net coordinates are 128x128.
    #
    # Convert the measured 128-pixel distance back to the
    # original crop coordinate system.
    # -----------------------------------------------------

    scale = (
        float(crop_height_pixels) /
        float(IMG_SIZE)
    )

    original_pixel_distance = (
        float(pixel_distance) *
        scale
    )

    wag_mm = (
        original_pixel_distance *
        float(mm_per_pixel)
    )

    # -----------------------------------------------------
    # Sanity check
    # -----------------------------------------------------

    if wag_mm < 0:
        return None

    if wag_mm > MAX_WAG_MM:

        print(
            f"Geometry: WAG {wag_mm:.2f} mm "
            f"is excessively large"
        )

        return None

    return float(wag_mm)


# =========================================================
# FALLBACK CALIBRATION
# =========================================================

def estimate_pixel_to_mm(
    teeth
):

    if not teeth:
        return None

    upper_widths = []
    lower_widths = []

    # -----------------------------------------------------
    # Collect YOLO tooth widths
    # -----------------------------------------------------

    for tooth in teeth:

        width = (
            tooth["x2"] -
            tooth["x1"]
        )

        if width <= 0:
            continue

        if tooth["arch"] == "upper":

            upper_widths.append(
                width
            )

        else:

            lower_widths.append(
                width
            )

    conversions = []

    # -----------------------------------------------------
    # Upper arch calibration
    # -----------------------------------------------------

    if upper_widths:

        upper_pixels = np.median(
            upper_widths
        )

        if upper_pixels > 0:

            upper_conversion = (
                UPPER_TOOTH_WIDTH_MM /
                upper_pixels
            )

            conversions.append(
                upper_conversion
            )

    # -----------------------------------------------------
    # Lower arch calibration
    # -----------------------------------------------------

    if lower_widths:

        lower_pixels = np.median(
            lower_widths
        )

        if lower_pixels > 0:

            lower_conversion = (
                LOWER_TOOTH_WIDTH_MM /
                lower_pixels
            )

            conversions.append(
                lower_conversion
            )

    if not conversions:
        return None

    # -----------------------------------------------------
    # Use median rather than mean to reduce influence of
    # unusually sized/misdetected teeth.
    # -----------------------------------------------------

    return float(
        np.median(
            conversions
        )
    )


# =========================================================
# SORT TEETH
# =========================================================

def sort_teeth(
    teeth,
    quadrant
):

    # -----------------------------------------------------
    # Important:
    #
    # FDI numbering progresses:
    #
    # UR: 18 → 11, left-to-right in image
    # UL: 21 → 28, left-to-right in image
    # LL: 31 → 38, left-to-right in image
    # LR: 48 → 41, left-to-right in image
    #
    # The existing QUADRANT_MAP already follows image order,
    # so sorting by X coordinate is correct.
    # -----------------------------------------------------

    return sorted(
        teeth,
        key=lambda t: t["cx"]
    )


# =========================================================
# DRAW SEGMENTATION
# =========================================================

def draw_segmentation(
    output,
    crop_x1,
    crop_y1,
    crop_x2,
    crop_y2,
    mask
):

    if mask is None:
        return

    crop_width = (
        crop_x2 -
        crop_x1
    )

    crop_height = (
        crop_y2 -
        crop_y1
    )

    if crop_width <= 0:
        return

    if crop_height <= 0:
        return

    # -----------------------------------------------------
    # Resize segmentation mask to original crop
    # -----------------------------------------------------

    full_mask = cv2.resize(
        mask.astype(np.uint8),
        (
            crop_width,
            crop_height
        ),
        interpolation=cv2.INTER_NEAREST
    )

    region = output[
        crop_y1:crop_y2,
        crop_x1:crop_x2
    ]

    # -----------------------------------------------------
    # FGM
    # -----------------------------------------------------

    fgm_binary = (
        full_mask == FGM
    ).astype(np.uint8) * 255

    contours_fgm, _ = cv2.findContours(
        fgm_binary,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    cv2.drawContours(
        region,
        contours_fgm,
        -1,
        (255, 0, 255),
        2
    )

    # -----------------------------------------------------
    # MGJ
    # -----------------------------------------------------

    mgj_binary = (
        full_mask == MGJ
    ).astype(np.uint8) * 255

    contours_mgj, _ = cv2.findContours(
        mgj_binary,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    cv2.drawContours(
        region,
        contours_mgj,
        -1,
        (255, 0, 0),
        2
    )


# =========================================================
# DRAW MEASUREMENT LINE
# =========================================================

def draw_measurement_line(
    output,
    tooth,
    fgm_y,
    mgj_y,
    crop_y1
):

    if fgm_y is None:
        return

    if mgj_y is None:
        return

    crop_height = (
        tooth["crop_height"]
    )

    if crop_height <= 0:
        return

    # -----------------------------------------------------
    # Convert U-Net coordinates to original crop pixels
    # -----------------------------------------------------

    fgm_original_y = (
        float(fgm_y) *
        crop_height /
        IMG_SIZE
    )

    mgj_original_y = (
        float(mgj_y) *
        crop_height /
        IMG_SIZE
    )

    # -----------------------------------------------------
    # Convert to full image coordinates
    # -----------------------------------------------------

    fgm_global_y = int(
        crop_y1 +
        fgm_original_y
    )

    mgj_global_y = int(
        crop_y1 +
        mgj_original_y
    )

    # -----------------------------------------------------
    # Use center of YOLO tooth
    # -----------------------------------------------------

    x = int(
        tooth["cx"]
    )

    # -----------------------------------------------------
    # Measurement line
    # -----------------------------------------------------

    cv2.line(
        output,
        (x, fgm_global_y),
        (x, mgj_global_y),
        (0, 255, 255),
        2
    )

    # FGM point
    cv2.circle(
        output,
        (x, fgm_global_y),
        4,
        (255, 0, 255),
        -1
    )

    # MGJ point
    cv2.circle(
        output,
        (x, mgj_global_y),
        4,
        (255, 0, 0),
        -1
    )


# =========================================================
# DRAW TOOTH LABEL
# =========================================================

def draw_tooth_label(
    output,
    tooth,
    tooth_number,
    wag_mm,
    status
):

    if tooth_number is None:

        label = "Unknown"

    elif wag_mm is not None:

        label = (
            f"T{tooth_number} "
            f"{wag_mm:.2f}mm "
            f"{status}"
        )

    else:

        label = (
            f"T{tooth_number} "
            f"Not Detected"
        )

    label_y = max(
        15,
        tooth["y1"] - 8
    )

    cv2.putText(
        output,
        label,
        (
            tooth["x1"],
            label_y
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (0, 255, 255),
        2,
        cv2.LINE_AA
    )


# =========================================================
# MAIN ANALYSIS
# =========================================================

def analyze(
    image_path,
    mm_per_pixel=None
):

    print(
        "\n======================================"
    )

    print(
        "STARTING PERIODONTAL WAG ANALYSIS"
    )

    print(
        "======================================"
    )

    # =====================================================
    # READ IMAGE
    # =====================================================

    img = cv2.imread(
        str(image_path)
    )

    if img is None:

        print(
            "ERROR: Could not read image."
        )

        return [], None

    image_height, image_width = (
        img.shape[:2]
    )

    print(
        f"Image size: "
        f"{image_width} x "
        f"{image_height}"
    )

    print(
        "mm_per_pixel received:",
        mm_per_pixel
    )

    output = img.copy()

    # =====================================================
    # YOLO
    # =====================================================

    print(
        "\n--------------------------------------"
    )

    print(
        "RUNNING YOLO TOOTH DETECTION"
    )

    print(
        "--------------------------------------"
    )

    yolo_results = yolo_model(
        str(image_path),
        conf=YOLO_CONFIDENCE,
        verbose=False
    )

    teeth = []

    for result in yolo_results:

        if result.boxes is None:
            continue

        for box in result.boxes:

            confidence = float(
                box.conf[0]
            )

            if (
                confidence <
                YOLO_CONFIDENCE
            ):
                continue

            x1, y1, x2, y2 = map(
                int,
                box.xyxy[0]
            )

            # -------------------------------------------------
            # Validate bounding box
            # -------------------------------------------------

            if x2 <= x1:
                continue

            if y2 <= y1:
                continue

            # -------------------------------------------------
            # Clamp to image
            # -------------------------------------------------

            x1 = max(
                0,
                min(x1, image_width - 1)
            )

            y1 = max(
                0,
                min(y1, image_height - 1)
            )

            x2 = max(
                1,
                min(x2, image_width)
            )

            y2 = max(
                1,
                min(y2, image_height)
            )

            cx = (
                x1 + x2
            ) / 2.0

            cy = (
                y1 + y2
            ) / 2.0

            arch, quadrant = (
                determine_quadrant(
                    cx,
                    cy,
                    image_width,
                    image_height
                )
            )

            teeth.append({

                "cx": cx,
                "cy": cy,

                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,

                "arch": arch,
                "quadrant": quadrant,

                "confidence": confidence
            })

    print(
        f"YOLO detected {len(teeth)} teeth."
    )

    if len(teeth) == 0:

        print(
            "No teeth detected."
        )

        return [], output

    # =====================================================
    # CALIBRATION
    # =====================================================

    print(
        "\n--------------------------------------"
    )

    print(
        "CALIBRATION"
    )

    print(
        "--------------------------------------"
    )

    if mm_per_pixel is not None:

        try:

            pixel_to_mm = float(
                mm_per_pixel
            )

            if pixel_to_mm <= 0:

                raise ValueError(
                    "Invalid calibration"
                )

            print(
                "Using USER calibration:",
                pixel_to_mm,
                "mm/pixel"
            )

        except Exception:

            print(
                "Invalid user calibration."
            )

            pixel_to_mm = (
                estimate_pixel_to_mm(
                    teeth
                )
            )

            print(
                "Using fallback calibration:",
                pixel_to_mm,
                "mm/pixel"
            )

    else:

        pixel_to_mm = (
            estimate_pixel_to_mm(
                teeth
            )
        )

        print(
            "No user calibration."
        )

        print(
            "Estimated fallback calibration:",
            pixel_to_mm,
            "mm/pixel"
        )

    # =====================================================
    # GROUP BY QUADRANT
    # =====================================================

    quadrants = {

        "UR": [],
        "UL": [],
        "LL": [],
        "LR": []
    }

    for tooth in teeth:

        quadrants[
            tooth["quadrant"]
        ].append(tooth)

    final_results = []

    # =====================================================
    # PROCESS QUADRANTS
    # =====================================================

    for quadrant in [
        "UR",
        "UL",
        "LL",
        "LR"
    ]:

        quadrant_teeth = sort_teeth(
            quadrants[quadrant],
            quadrant
        )

        fdi_teeth = (
            QUADRANT_MAP[
                quadrant
            ]
        )

        # =================================================
        # PROCESS EACH TOOTH
        # =================================================

        for index, tooth in enumerate(
            quadrant_teeth
        ):

            if index < len(fdi_teeth):

                tooth_number = (
                    fdi_teeth[index]
                )

            else:

                tooth_number = None

            print(
                "\n--------------------------------------"
            )

            print(
                f"PROCESSING TOOTH "
                f"{tooth_number}"
            )

            print(
                "--------------------------------------"
            )

            # =================================================
            # CROP
            # =================================================

            (
                crop,
                crop_x1,
                crop_y1,
                crop_x2,
                crop_y2
            ) = crop_tooth(
                img,
                tooth["x1"],
                tooth["y1"],
                tooth["x2"],
                tooth["y2"]
            )

            if (
                crop is None or
                crop.size == 0
            ):

                print(
                    "Invalid crop"
                )

                final_results.append({

                    "tooth_number":
                        tooth_number,

                    "arch":
                        tooth["arch"],

                    "attached_gingiva_width_mm":
                        None,

                    "status":
                        "Not Detected",

                    "fgm_pixel":
                        None,

                    "mgj_pixel":
                        None,

                    "pixel_distance":
                        None
                })

                continue

            crop_height = (
                crop.shape[0]
            )

            crop_width = (
                crop.shape[1]
            )

            tooth["crop_height"] = (
                crop_height
            )

            tooth["crop_width"] = (
                crop_width
            )

            print(
                f"Crop: "
                f"{crop_height} x "
                f"{crop_width}"
            )

            # =================================================
            # U-NET
            # =================================================

            mask = segment_tooth(
                crop
            )

            if mask is None:

                print(
                    "U-Net segmentation failed."
                )

                final_results.append({

                    "tooth_number":
                        tooth_number,

                    "arch":
                        tooth["arch"],

                    "attached_gingiva_width_mm":
                        None,

                    "status":
                        "Not Detected",

                    "fgm_pixel":
                        None,

                    "mgj_pixel":
                        None,

                    "pixel_distance":
                        None
                })

                continue

            # =================================================
            # BOUNDARY DETECTION
            # =================================================

            (
                fgm_y,
                mgj_y,
                geometry_status
            ) = find_boundary_positions(
                mask,
                tooth["arch"]
            )

            # =================================================
            # PIXEL DISTANCE
            # =================================================

            pixel_distance = (
                calculate_pixel_distance(
                    fgm_y,
                    mgj_y
                )
            )

            # =================================================
            # MM
            # =================================================

            wag_mm = (
                calculate_wag_mm(
                    pixel_distance,
                    crop_height,
                    pixel_to_mm
                )
            )

            # =================================================
            # STATUS
            # =================================================

            status = classify_wag(
                wag_mm
            )

            # =================================================
            # DEBUG
            # =================================================

            if wag_mm is not None:

                print(
                    f"Raw WAG: "
                    f"{wag_mm} mm"
                )

            # =================================================
            # DRAW YOLO BOX
            # =================================================

            cv2.rectangle(
                output,
                (
                    tooth["x1"],
                    tooth["y1"]
                ),
                (
                    tooth["x2"],
                    tooth["y2"]
                ),
                (0, 255, 0),
                2
            )

            # =================================================
            # DRAW SEGMENTATION
            # =================================================

            draw_segmentation(
                output,
                crop_x1,
                crop_y1,
                crop_x2,
                crop_y2,
                mask
            )

            # =================================================
            # DRAW MEASUREMENT
            # =================================================

            if (
                fgm_y is not None and
                mgj_y is not None
            ):

                draw_measurement_line(
                    output,
                    tooth,
                    fgm_y,
                    mgj_y,
                    crop_y1
                )

            # =================================================
            # LABEL
            # =================================================

            draw_tooth_label(
                output,
                tooth,
                tooth_number,
                wag_mm,
                status
            )

            # =================================================
            # CONSOLE RESULT
            # =================================================

            print(
                f"Tooth {tooth_number} | "
                f"Arch={tooth['arch']} | "
                f"FGM={fgm_y} | "
                f"MGJ={mgj_y} | "
                f"Distance={pixel_distance} px | "
                f"WAG={wag_mm} mm | "
                f"{status}"
            )

            # =================================================
            # FINAL RESULT
            # =================================================

            final_results.append({

                "tooth_number":
                    tooth_number,

                "arch":
                    tooth["arch"],

                "attached_gingiva_width_mm":
                    (
                        None
                        if wag_mm is None
                        else round(
                            float(wag_mm),
                            2
                        )
                    ),

                "status":
                    status,

                "fgm_pixel":
                    (
                        None
                        if fgm_y is None
                        else round(
                            float(fgm_y),
                            2
                        )
                    ),

                "mgj_pixel":
                    (
                        None
                        if mgj_y is None
                        else round(
                            float(mgj_y),
                            2
                        )
                    ),

                "pixel_distance":
                    (
                        None
                        if pixel_distance is None
                        else round(
                            float(pixel_distance),
                            2
                        )
                    ),

                "geometry":
                    geometry_status
            })

    # =====================================================
    # FINAL RESULTS
    # =====================================================

    print(
        "\n======================================"
    )

    print(
        "FINAL WAG RESULTS"
    )

    print(
        "======================================"
    )

    for result in final_results:

        print(
            f"Tooth "
            f"{result['tooth_number']} | "
            f"WAG="
            f"{result['attached_gingiva_width_mm']} "
            f"mm | "
            f"{result['status']}"
        )

    print(
        "======================================\n"
    )

    return (
        final_results,
        output
    )


# =========================================================
# FLASK COMPATIBILITY WRAPPER
# =========================================================

def analyze_image(
    image_path,
    mm_per_pixel=None
):

    return analyze(
        image_path,
        mm_per_pixel
    )
