# automatic-number-plate-recognition-python-yolov8

<p align="center">
<a href="https://www.youtube.com/watch?v=fyJB1t0o0ms">
    <img width="600" src="https://utils-computervisiondeveloper.s3.amazonaws.com/thumbnails/with_play_button/anpr_yolo2.jpg" alt="Watch the video">
    </br>Watch on YouTube: Automatic number plate recognition with Python, Yolov8 and EasyOCR !
</a>
</p>

## data

The video I used in this tutorial can be downloaded [here](https://www.pexels.com/video/traffic-flow-in-the-highway-2103099/).

## models

A Yolov8 pretrained model was used to detect vehicles.

A licensed plate detector was used to detect license plates. The model was trained with Yolov8 using [this dataset](https://universe.roboflow.com/roboflow-universe-projects/license-plate-recognition-rxg4e/dataset/4) and following this [step by step tutorial on how to train an object detector with Yolov8 on your custom data](https://github.com/computervisioneng/train-yolov8-custom-dataset-step-by-step-guide).

The trained model is available in my [Patreon](https://www.patreon.com/ComputerVisionEngineer).

## dependencies

The sort module needs to be downloaded from [this repository](https://github.com/abewley/sort) as mentioned in the [video](https://youtu.be/fyJB1t0o0ms?t=1120).

## quick start (free, windows)

This workspace now includes:

- `setup_and_run.ps1`: sets up a local virtual environment, installs dependencies, downloads free model/video assets, and runs inference.
- `run.bat`: one-click wrapper to run `setup_and_run.ps1`.

### run with one command

From this project folder, run:

```powershell
./run.bat
```

### what is downloaded automatically

- SORT tracker: <https://raw.githubusercontent.com/abewley/sort/master/sort.py>
- Free license-plate detector model: <https://huggingface.co/Koushim/yolov8-license-plate-detection>
- Free sample video: <https://raw.githubusercontent.com/opencv/opencv/master/samples/data/vtest.avi>

### outputs

- `test.csv`: detected plate readings per tracked vehicle.

Demo video: backend/anpr_demo/demo.mp4
