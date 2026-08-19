# Training workflow

## Recommended first platform: Roboflow

Roboflow is the initial training workspace because it supports browser/phone
upload, annotation, review, dataset versioning, and YOLO training. Edge
Impulse remains a later option for small embedded/quantized experiments; it
is not the first dataset source for this Pi dashboard.

## Workflow

1. Pi records selected detection or manually requested training frames.
2. A reviewer approves each candidate and assigns a purpose/tag.
3. Approved frames and labels enter a Roboflow dataset version.
4. The intern annotates classes and performs quality review in Roboflow.
5. Train a candidate YOLO model and record dataset version, metrics,
   confusion matrix, date, and intended use.
6. Evaluate the model against a held-out field set before deployment.
7. Store the approved model as a versioned release artifact; deploy to a
   Pi staging path first, with rollback to the previous known model.

## Initial classes

Start with a limited, measurable class set: `person`, relevant animal types,
`plant`, irrigation/drip state, and explicitly named farm objects. Wind
direction and irrigation decisions need separate measurement and control
validation; detection labels alone must not actuate irrigation.

## Access

The intern uses Roboflow and the protected dashboard. The intern does not
need ShellHub SSH, Pi Linux credentials, Cloudflare administrator access, or
AWS administrator credentials.
