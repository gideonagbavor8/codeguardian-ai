# IBM Bob — Task Session Summaries

> **Status: no session summary exports have been added to this repository yet.**
>
> This directory is an empty placeholder. It does **not** contain evidence, and
> its presence should not be read as the Bob submission requirement being met.

## What belongs here

The IBM submission requires exported **IBM Bob task session summary** screenshots
or reports. Export them from IBM Bob and place the image files in this directory.

Suggested naming, so the sequence is readable in order:

```
docs/bob-session-summaries/
├── 01-<short-task-description>.png
├── 02-<short-task-description>.png
└── ...
```

## How to add them

1. Open the task session in IBM Bob and export or screenshot the session summary.
2. Save the files into this directory using the naming pattern above.
3. Commit them:

   ```bash
   git add docs/bob-session-summaries
   git commit -m "add IBM Bob task session summaries"
   git push origin main
   ```

4. Delete the status warning at the top of this file once real exports are present.
