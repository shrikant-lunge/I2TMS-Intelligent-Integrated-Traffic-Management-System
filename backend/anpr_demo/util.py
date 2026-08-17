import re
import string
import easyocr

# Initialize the OCR reader
reader = easyocr.Reader(['en'], gpu=False)

# Indian license plate format: SS DD LLL DDDD
#   SS   = 2 letters (state code), e.g. KA, MH, DL
#   DD   = 1-2 digits (RTO code)
#   LLL  = 1-3 letters (series)
#   DDDD = 4 digits (unique number)
INDIAN_PLATE_REGEX = re.compile(r'^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$')

# Minimum OCR confidence to even consider a reading. EasyOCR scores on
# small/blurry CCTV crops are noisy, so this is intentionally lax -
# most filtering happens via the regex format check instead.
MIN_TEXT_SCORE = 0.10


def write_csv(results, output_path):
    """
    Write the results to a CSV file.

    Args:
        results (dict): Dictionary containing the results.
        output_path (str): Path to the output CSV file.
    """
    with open(output_path, 'w') as f:
        f.write('{},{},{},{},{},{},{}\n'.format('frame_nmr', 'car_id', 'car_bbox',
                                                'license_plate_bbox', 'license_plate_bbox_score', 'license_number',
                                                'license_number_score'))

        for frame_nmr in results.keys():
            for car_id in results[frame_nmr].keys():
                if 'car' in results[frame_nmr][car_id].keys() and \
                   'license_plate' in results[frame_nmr][car_id].keys() and \
                   'text' in results[frame_nmr][car_id]['license_plate'].keys():
                    f.write('{},{},{},{},{},{},{}\n'.format(frame_nmr,
                                                            car_id,
                                                            '[{} {} {} {}]'.format(
                                                                results[frame_nmr][car_id]['car']['bbox'][0],
                                                                results[frame_nmr][car_id]['car']['bbox'][1],
                                                                results[frame_nmr][car_id]['car']['bbox'][2],
                                                                results[frame_nmr][car_id]['car']['bbox'][3]),
                                                            '[{} {} {} {}]'.format(
                                                                results[frame_nmr][car_id]['license_plate']['bbox'][0],
                                                                results[frame_nmr][car_id]['license_plate']['bbox'][1],
                                                                results[frame_nmr][car_id]['license_plate']['bbox'][2],
                                                                results[frame_nmr][car_id]['license_plate']['bbox'][3]),
                                                            results[frame_nmr][car_id]['license_plate']['bbox_score'],
                                                            results[frame_nmr][car_id]['license_plate']['text'],
                                                            results[frame_nmr][car_id]['license_plate']['text_score'])
                            )
        f.close()


def get_best_per_car(results):
    """
    Collapse the frame-by-frame results dict down to a single best
    reading per car_id (the one with the highest license_number_score).

    Args:
        results (dict): {frame_nmr: {car_id: {...}}}

    Returns:
        dict: {frame_nmr: {car_id: {...}}} containing only the single
              best frame for each car_id.
    """
    best_per_car = {}  # car_id -> (frame_nmr, entry, score)

    for frame_nmr, cars in results.items():
        for car_id, entry in cars.items():
            if 'license_plate' not in entry or 'text' not in entry['license_plate']:
                continue
            score = entry['license_plate']['text_score']
            if car_id not in best_per_car or score > best_per_car[car_id][2]:
                best_per_car[car_id] = (frame_nmr, entry, score)

    filtered = {}
    for car_id, (frame_nmr, entry, score) in best_per_car.items():
        filtered.setdefault(frame_nmr, {})[car_id] = entry

    return filtered


def license_complies_format(text):
    """
    Check if the license plate text matches the Indian plate format:
    2 letters, 1-2 digits, 1-3 letters, 4 digits.

    Args:
        text (str): License plate text (already uppercased, no spaces).

    Returns:
        bool: True if the text matches the expected format.
    """
    return bool(INDIAN_PLATE_REGEX.match(text))


def format_license(text):
    """
    Indian plates don't need character remapping the way the original
    7-character format did, so just return the text as-is (already
    validated and uppercased by the caller).
    """
    return text


def read_license_plate(license_plate_crop):
    """
    Read the license plate text from the given cropped image. STRICT mode:
    only returns a result if it exactly matches the Indian plate format
    (2 letters, 1-2 digits, 1-3 letters, 4 digits). Anything else -
    partial reads, wrong length, garbled text - is discarded rather than
    guessed at, so every value written to the CSV is a trustworthy plate.

    Args:
        license_plate_crop (numpy.ndarray): Cropped (thresholded) plate image.

    Returns:
        tuple: (text, score) or (None, None) if no exact match was found.
    """
    detections = reader.readtext(license_plate_crop)

    best_text, best_score = None, None

    for detection in detections:
        bbox, text, score = detection

        # Clean up: uppercase, strip spaces and any non-alphanumeric junk
        # (OCR often picks up stray characters like { } | # " etc.)
        cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())

        if score < MIN_TEXT_SCORE:
            continue

        if not license_complies_format(cleaned):
            continue  # reject anything that isn't an exact format match

        if best_score is None or score > best_score:
            best_text, best_score = format_license(cleaned), score

    return best_text, best_score


def get_car(license_plate, vehicle_track_ids):
    """
    Retrieve the vehicle coordinates and ID based on the license plate coordinates.

    Args:
        license_plate (tuple): Tuple containing the coordinates of the license plate (x1, y1, x2, y2, score, class_id).
        vehicle_track_ids (list): List of vehicle track IDs and their corresponding coordinates.

    Returns:
        tuple: Tuple containing the vehicle coordinates (x1, y1, x2, y2) and ID.
    """
    x1, y1, x2, y2, score, class_id = license_plate

    foundIt = False
    for j in range(len(vehicle_track_ids)):
        xcar1, ycar1, xcar2, ycar2, car_id = vehicle_track_ids[j]

        if x1 > xcar1 and y1 > ycar1 and x2 < xcar2 and y2 < ycar2:
            car_indx = j
            foundIt = True
            break

    if foundIt:
        return vehicle_track_ids[car_indx]

    return -1, -1, -1, -1, -1