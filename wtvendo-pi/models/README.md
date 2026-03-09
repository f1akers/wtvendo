# YOLO Model for WTVendo Bottle Classification

## Model Details

| Field     | Value                                    |
| --------- | ---------------------------------------- |
| Name      | `yolo26n.pt`                             |
| Framework | YOLOv8 Nano (ultralytics)                |
| Mode      | Detection                                |
| Version   | Custom-trained (26 epochs, Nano variant) |
| SHA256    | `<UPDATE_AFTER_TRAINING>`                |
| Download  | `<UPDATE_WITH_DOWNLOAD_URL>`             |

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

1. Download the model file from the URL above.
2. Place it in this directory as `yolo26n.pt`.
3. Verify the SHA256 hash:

   ```bash
   sha256sum models/yolo26n.pt
   # Must match the SHA256 value above
   ```

4. (Optional) Export to NCNN for faster inference on Pi 4B (~4-5× speedup):

   ```bash
   python -c "from ultralytics import YOLO; YOLO('models/yolo26n.pt').export(format='ncnn', imgsz=320)"
   ```

   This creates a `yolo26n_ncnn_model/` directory next to the `.pt` file.

## Notes

- Model files are **git-ignored** — do NOT commit `.pt` or `.bin` files.
- Input resolution: 320×320 pixels.
- Expected inference time on Pi 4B: ~100–160ms per frame (NCNN).
- Confidence threshold: 0.5 (configurable in `wtvendo/config.py`).
