# YOLO Model for WTVendo Bottle Classification

## Model Details

| Field     | Value                                    |
| --------- | ---------------------------------------- |
| Name      | `best_ncnn_model`                        |
| Framework | YOLOv8 Nano (ultralytics, NCNN export)   |
| Mode      | Detection                                |
| Version   | Custom-trained (26 epochs, Nano variant) |

## Class Names (10 classes)

| Index | Class Name           |
| ----- | -------------------- |
| 0     | large bottled water  |
| 1     | medium bottled water |
| 2     | medium soda          |
| 3     | medium thick bottle  |
| 4     | pepsi viper          |
| 5     | small bottled water  |
| 6     | small soda           |
| 7     | small thick bottle   |
| 8     | xs soda              |
| 9     | xs thick bottle      |

## Setup

1. Export the trained `.pt` model to NCNN format:

   ```bash
   python -c "from ultralytics import YOLO; YOLO('best.pt').export(format='ncnn', imgsz=224)"
   ```

   This creates a `best_ncnn_model/` directory containing `.param` and `.bin` files.

2. Place the `best_ncnn_model/` directory in this `models/` folder.

## Notes

- Model files are **git-ignored** — do NOT commit `.param`, `.bin`, or model directories.
- Input resolution: 224x224 pixels (configurable in `wtvendo/config.py`).
- Confidence threshold: 0.5 (configurable in `wtvendo/config.py`).
- NCNN provides ~4-5x speedup over PyTorch on Raspberry Pi 4B.
