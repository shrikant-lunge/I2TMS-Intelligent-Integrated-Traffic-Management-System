import argparse
import os

import cv2
import numpy as np
from ultralytics import YOLO

from sort.sort import Sort
from util import get_car, read_license_plate, write_csv, get_best_per_car


def parse_args():
    parser = argparse.ArgumentParser(description='Automatic number plate recognition pipeline.')
    parser.add_argument('--video', default='demo.mp4', help='Path to input video file.')
    parser.add_argument('--plate-model', default='models/license_plate_detector.pt', help='Path to license plate model.')
    parser.add_argument('--output-csv', default='test.csv', help='Path for detection CSV output.')
    parser.add_argument('--no-display', action='store_true', help='Disable the live preview window.')
    return parser.parse_args()


def main():
    args = parse_args()

    if not os.path.exists(args.video):
        raise FileNotFoundError(
            f'Input video not found: {args.video}. Provide a valid video with --video.'
        )

    if not os.path.exists(args.plate_model):
        raise FileNotFoundError(
            f'License plate model not found: {args.plate_model}. '
            'Download a model to this path or pass --plate-model.'
        )

    results = {}
    mot_tracker = Sort()

    # Keeps the last known good plate reading per car_id so the label
    # stays visible on screen even on frames where OCR doesn't get a
    # fresh reading that frame. Purely for display - does not affect
    # the CSV output in any way.
    car_id_to_label = {}

    # Load models once to reuse them across all frames.
    coco_model = YOLO('yolov8n.pt')
    license_plate_detector = YOLO(args.plate_model)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError(f'Could not open video: {args.video}')

    vehicles = [2, 3, 5, 7]

    frame_nmr = -1
    ret = True
    while ret:
        frame_nmr += 1
        ret, frame = cap.read()
        if not ret:
            break

        results[frame_nmr] = {}

        detections = coco_model(frame, verbose=False)[0]
        detections_ = []
        for detection in detections.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = detection
            if int(class_id) in vehicles:
                detections_.append([x1, y1, x2, y2, score])

        dets_np = np.asarray(detections_) if detections_ else np.empty((0, 5))
        track_ids = mot_tracker.update(dets_np)

        # Draw a box for every currently tracked vehicle, plus its last
        # known plate reading (if any) above the box. This runs every
        # frame regardless of whether OCR fires this frame, so labels
        # persist smoothly instead of flickering on/off.
        if not args.no_display:
            for xcar1, ycar1, xcar2, ycar2, car_id in track_ids:
                p1 = (int(xcar1), int(ycar1))
                p2 = (int(xcar2), int(ycar2))
                cv2.rectangle(frame, p1, p2, (0, 200, 0), 2)
                label_entry = car_id_to_label.get(car_id)
                if label_entry:
                    label_text, _ = label_entry
                    cv2.putText(frame, label_text, (p1[0], max(p1[1] - 10, 15)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2)

        license_plates = license_plate_detector(frame, verbose=False)[0]
        for license_plate in license_plates.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = license_plate

            xcar1, ycar1, xcar2, ycar2, car_id = get_car(license_plate, track_ids)
            if car_id == -1:
                continue

            license_plate_crop = frame[int(y1):int(y2), int(x1): int(x2), :]
            if license_plate_crop.size == 0:
                continue

            # Upscale small plate crops before OCR - CCTV plates are often tiny
            h, w = license_plate_crop.shape[:2]
            if h < 60:
                scale = 60 / h
                license_plate_crop = cv2.resize(
                    license_plate_crop, (int(w * scale), int(h * scale)),
                    interpolation=cv2.INTER_CUBIC
                )

            license_plate_crop_gray = cv2.cvtColor(license_plate_crop, cv2.COLOR_BGR2GRAY)
            # Otsu's method picks the threshold automatically per-crop,
            # which handles varying outdoor lighting far better than a
            # fixed threshold value.
            _, license_plate_crop_thresh = cv2.threshold(
                license_plate_crop_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            )

            license_plate_text, license_plate_text_score = read_license_plate(license_plate_crop_thresh)
            if license_plate_text is None:
                continue

            # Track the best label seen so far for this car, for display only.
            if car_id not in car_id_to_label or license_plate_text_score > car_id_to_label[car_id][1]:
                car_id_to_label[car_id] = (license_plate_text, license_plate_text_score)

            if not args.no_display:
                pp1 = (int(x1), int(y1))
                pp2 = (int(x2), int(y2))
                cv2.rectangle(frame, pp1, pp2, (0, 0, 255), 2)
                cv2.putText(frame, license_plate_text, (pp1[0], max(pp1[1] - 10, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            results[frame_nmr][car_id] = {
                'car': {'bbox': [xcar1, ycar1, xcar2, ycar2]},
                'license_plate': {
                    'bbox': [x1, y1, x2, y2],
                    'text': license_plate_text,
                    'bbox_score': score,
                    'text_score': license_plate_text_score,
                },
            }

        if not args.no_display:
            cv2.imshow('ANPR - press q to quit', frame)
            # waitKey(1) keeps playback moving; 'q' exits early without
            # losing results gathered so far - they still get written to CSV.
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cap.release()
    if not args.no_display:
        cv2.destroyAllWindows()

    # Collapse per-frame noise down to a single best reading per vehicle.
    best_results = get_best_per_car(results)

    write_csv(best_results, args.output_csv)
    print(f'Results written to {args.output_csv} ({sum(len(v) for v in best_results.values())} vehicles)')


if __name__ == '__main__':
    main()