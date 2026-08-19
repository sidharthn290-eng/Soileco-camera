# Training and storage contract

## Capture lifecycle

1. The Pi writes a local event record first.
2. A selected frame is tagged with camera, timestamp, model version, labels,
   confidence, reason for capture, and review status.
3. Only approved candidates enter the training dataset.
4. Roboflow hosts annotation, dataset versions, review, and YOLO training.
5. An approved model is evaluated on a held-out field set before Pi staging.

## S3 boundary

AWS is optional for the first public dashboard. When enabled, S3 stores only
selected media, LiDAR artifacts, evaluation reports, and approved model
releases. The bucket stays private, Block Public Access remains enabled, and
the Pi uses a device-specific least-privilege upload path with short-lived
credentials or presigned URLs.

The dashboard must never contain an AWS secret or a public S3 object URL.

## Required decisions before collection

- Dataset owner and Roboflow project owner
- Initial class list and annotation definitions
- Retention period for person-related imagery
- Reviewer responsible for approving training candidates
- Monthly S3 budget and data-volume limit
- Model acceptance metrics and rollback owner
