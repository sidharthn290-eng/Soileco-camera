# Repository verification

Run the no-hardware check locally:

```text
python tools/verify_repository.py
```

GitHub Actions runs the same check for pull requests and pushes to `develop`
or `main`. It verifies tracked-file policy, common secret patterns, Python
syntax, and local Markdown links. It does not claim camera, LiDAR, cloud, or
production-runtime verification.
