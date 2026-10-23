# History caveats

## Lineage restarts on delete and re-add (D-H15)

Traces follows a file across renames. It does not join a file to an earlier file that was deleted at the same path. When a path is deleted and later added again, the HEAD file's history starts at that re-add. Commits before the delete are not counted for it in churn, hotspot or co-change records. This is the v1 identity rule (contract section 9.2) and it is not changed.

Records now say when this happens:

- `metrics.lineage_breaks` is the number of delete then re-add gaps at the path where the file's current history starts. It counts non-merge deletes of that path earlier in the analysed range.
- On file-level co-change records, `metrics.lineage_breaks_a` and `metrics.lineage_breaks_b` give the count for each side (`from` and `to`), and `metrics.lineage_breaks` is their sum.
- The record has the flag `x-lineage_restart`, a plain sentence in `provenance_raw.caveat`, and the same sentence at the end of `statement`, for example: "History for src/services/user.service.js restarts after 1 delete and re-add gap in the analysed range; commits before the last re-add are not counted for this path."
- The lifecycle stage report lists every affected HEAD path under `lineage_breaks`. The file-level co-change report gives `lineage_break_records`.

Records for paths without a gap have none of these fields and are unchanged. The fields do not change `claim_id`, `status` or `parameters`.

Not covered in v1: component-level co-change and component metrics, and a path that is deleted and then reused by a rename into it (the rename carries the other file's history, which is the intended rule).

`git log --follow` does cross a delete and re-add at the same path, so a hand count with `--follow` can be higher than the Traces count for a flagged path. For example, on hagopj13/node-express-boilerplate at 179ae84, `src/services/user.service.js` and `src/services/auth.service.js` were deleted in ffb47ae and re-added in c6c4206; the 4 co-change pairs that involve them are flagged with `lineage_breaks: 1`.
