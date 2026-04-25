---
description: Generate and apply an Alembic migration with autogenerate-pitfall review
argument-hint: <description>
---

# /migrate

Generate, review, and apply an Alembic migration. The argument is the migration description used by `alembic revision --autogenerate -m "..."`.

## Steps

1. **Validate input**
   - If no `<description>` argument is provided, ask the user for one and stop.
   - Refuse if it contains shell metacharacters that would break the `-m` flag (`"`, `` ` ``, `$`).

2. **Generate the revision**
   - Run: `docker-compose -f docker-compose.dev.yml exec -T backend alembic revision --autogenerate -m "<description>"`
   - Capture the path of the new migration file from stdout.

3. **Review the generated migration for pitfalls**
   - Read the generated file under `backend/alembic/versions/`.
   - Flag any of:
     - `op.drop_column` or `op.drop_table` (data loss).
     - `op.alter_column` with `nullable=False` and no `server_default` on a column that already has rows.
     - `op.drop_index` without an obvious replacement.
     - Foreign-key drops/recreates without `ondelete=` parity.
     - Renames detected as drop+create (autogenerate cannot infer renames).
   - If anything is flagged, present the concerns and ask the user to confirm before applying.

4. **Apply**
   - Run: `docker-compose -f docker-compose.dev.yml exec -T backend alembic upgrade head`
   - On success, surface the new revision id and `alembic current`.

5. **Rollback offer on failure**
   - If `upgrade head` fails, surface the error and offer: `docker-compose -f docker-compose.dev.yml exec -T backend alembic downgrade -1` (do not run automatically).

## Notes

- Do NOT delete or amend the generated migration file — even if the review flags issues, leave the file in place; the user decides.
- Migrations are committed by the user separately (often via `/precommit`).
