"""
Per-team Excel template generation, dry-run validation, atomic commit,
and sequential pipeline handoff / rework send-back logic.
"""
import datetime
import io
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill, Protection
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation


TEMPLATE_HEADERS = [
    "Project / Chapter",
    "File Name",
    "Complexity",
    "Points",
    "Time Worked (Hrs)",
    "Artist Name",
    "Status",
    "Notes / Rework Reason",
]

VALID_COMPLEXITIES = ["Low", "Medium", "High", "Very High"]
VALID_STATUSES = ["Open", "In Progress", "Done", "Rework"]


def get_team_stages(db, team_name: str) -> list[dict]:
    """Return ordered pipeline_stages rows owned by team_name."""
    rows = db.execute(
        "SELECT * FROM pipeline_stages WHERE team_name = ? ORDER BY stage_order ASC",
        (team_name,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_team_members(db, team_name: str) -> list[dict]:
    """Return active artists and leads belonging to team_name."""
    rows = db.execute(
        "SELECT id, name, username, role FROM users WHERE team = ? ORDER BY role DESC, name ASC",
        (team_name,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_team_open_queue(db, team_name: str) -> list[dict]:
    """Return all file_pipeline rows in Open, In Progress, or Rework for team_name."""
    rows = db.execute(
        """
        SELECT
            fp.id AS fp_id,
            fp.file_id,
            fp.step_name,
            fp.stage_order,
            fp.status,
            fp.complexity,
            fp.points,
            fp.time_worked,
            fp.rework_reason,
            fp.remarks,
            f.name AS file_name,
            p.name AS project_name,
            c.name AS chapter_name,
            u.name AS artist_name
        FROM file_pipeline fp
        JOIN files f ON fp.file_id = f.id
        JOIN chapters c ON f.chapter_id = c.id
        JOIN projects p ON c.project_id = p.id
        LEFT JOIN users u ON fp.assigned_to = u.id
        WHERE fp.team_name = ?
          AND fp.status IN ('Open', 'In Progress', 'Rework')
        ORDER BY
            CASE fp.status WHEN 'Rework' THEN 0 WHEN 'In Progress' THEN 1 ELSE 2 END,
            p.name ASC, c.name ASC, f.name ASC, fp.stage_order ASC
        """,
        (team_name,),
    ).fetchall()
    return [dict(r) for r in rows]


def generate_team_excel_template(db, team_name: str) -> bytes:
    """
    Generate an .xlsx workbook pre-filled with Open/In Progress/Rework files
    for team_name, plus 25 blank rows for adding new files, with protected headers
    and Excel dropdown validations.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{team_name[:25]} Queue"

    # Hidden sheet for long dropdown lists (project/chapters, artists)
    ref_ws = wb.create_sheet(title="_Lists")
    ref_ws.sheet_state = "hidden"

    members = get_team_members(db, team_name)
    member_names = [m["name"] for m in members] or ["Unassigned"]
    for idx, name in enumerate(member_names, start=1):
        ref_ws.cell(row=idx, column=1, value=name)

    proj_chaps = db.execute(
        """
        SELECT p.name || ' / ' || c.name AS label
        FROM chapters c
        JOIN projects p ON c.project_id = p.id
        WHERE p.status = 'Active' AND c.status = 'Active'
        ORDER BY p.name, c.name
        """
    ).fetchall()
    pc_labels = [r["label"] for r in proj_chaps] or ["Default Project / Main Chapter"]
    for idx, label in enumerate(pc_labels, start=1):
        ref_ws.cell(row=idx, column=2, value=label)

    # Header styling & protection
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    rework_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")

    for col_idx, heading in enumerate(TEMPLATE_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=heading)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.protection = Protection(locked=True)

    ws.row_dimensions[1].height = 26
    ws.freeze_panes = "A2"

    queue = get_team_open_queue(db, team_name)
    row_idx = 2
    for item in queue:
        proj_chap = f"{item['project_name']} / {item['chapter_name']}"
        note = item["rework_reason"] if item["status"] == "Rework" and item["rework_reason"] else (item["remarks"] or "")
        values = [
            proj_chap,
            item["file_name"],
            item["complexity"] or "Medium",
            item["points"] or 0,
            item["time_worked"] or 0.0,
            item["artist_name"] or "",
            item["status"],
            note,
        ]
        for col_idx, val in enumerate(values, start=1):
            c = ws.cell(row=row_idx, column=col_idx, value=val)
            c.protection = Protection(locked=False)
            if item["status"] == "Rework":
                c.fill = rework_fill
        row_idx += 1

    # Add 25 blank rows for new files
    total_rows = max(row_idx + 25, 30)
    for r in range(row_idx, total_rows + 1):
        for col_idx in range(1, len(TEMPLATE_HEADERS) + 1):
            c = ws.cell(row=r, column=col_idx, value="")
            c.protection = Protection(locked=False)

    # Data validations
    dv_pc = DataValidation(
        type="list",
        formula1=f"=_Lists!$B$1:$B${len(pc_labels)}",
        allow_blank=True,
    )
    dv_complexity = DataValidation(
        type="list",
        formula1=f'"{",".join(VALID_COMPLEXITIES)}"',
        allow_blank=True,
    )
    dv_artist = DataValidation(
        type="list",
        formula1=f"=_Lists!$A$1:$A${len(member_names)}",
        allow_blank=True,
    )
    dv_status = DataValidation(
        type="list",
        formula1=f'"{",".join(VALID_STATUSES)}"',
        allow_blank=False,
    )

    ws.add_data_validation(dv_pc)
    ws.add_data_validation(dv_complexity)
    ws.add_data_validation(dv_artist)
    ws.add_data_validation(dv_status)

    dv_pc.add(f"A2:A{total_rows}")
    dv_complexity.add(f"C2:C{total_rows}")
    dv_artist.add(f"F2:F{total_rows}")
    dv_status.add(f"G2:G{total_rows}")

    col_widths = [28, 30, 14, 10, 18, 22, 15, 36]
    for i, w in enumerate(col_widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Protect sheet structure & header row, allow editing data cells
    ws.protection.sheet = True
    ws.protection.enable()

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def parse_and_validate_upload(db, team_name: str, file_bytes: bytes) -> dict[str, Any]:
    """
    Dry-run parse & validate an uploaded .xlsx workbook for team_name.
    Returns summary dict with valid_rows, errors, and counts.
    """
    errors: list[str] = []
    valid_rows: list[dict[str, Any]] = []

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as exc:
        return {
            "ok": False,
            "errors": [f"Could not read Excel file: {exc}"],
            "rows": [],
            "summary": {"to_update": 0, "to_create": 0, "handoffs": 0, "reworks": 0},
        }

    ws = wb.active
    headers = [str(ws.cell(row=1, column=c).value or "").strip() for c in range(1, len(TEMPLATE_HEADERS) + 1)]
    if headers != TEMPLATE_HEADERS:
        return {
            "ok": False,
            "errors": [
                f"Invalid template headers. Expected {TEMPLATE_HEADERS}, got {headers}."
            ],
            "rows": [],
            "summary": {"to_update": 0, "to_create": 0, "handoffs": 0, "reworks": 0},
        }

    members = get_team_members(db, team_name)
    member_by_name = {m["name"].strip().lower(): m for m in members}
    member_by_user = {m["username"].strip().lower(): m for m in members}

    team_stages = get_team_stages(db, team_name)
    if not team_stages:
        return {
            "ok": False,
            "errors": [f"No pipeline stages configured for team '{team_name}'."],
            "rows": [],
            "summary": {"to_update": 0, "to_create": 0, "handoffs": 0, "reworks": 0},
        }

    to_update = 0
    to_create = 0
    handoffs = 0
    reworks = 0

    for row_num in range(2, ws.max_row + 1):
        vals = [ws.cell(row=row_num, column=c).value for c in range(1, len(TEMPLATE_HEADERS) + 1)]
        if all(v is None or str(v).strip() == "" for v in vals):
            continue

        proj_chap = str(vals[0] or "").strip()
        file_name = str(vals[1] or "").strip()
        complexity = str(vals[2] or "Medium").strip() or "Medium"
        points_raw = vals[3]
        hours_raw = vals[4]
        artist_raw = str(vals[5] or "").strip()
        status = str(vals[6] or "Open").strip()
        notes = str(vals[7] or "").strip()

        row_errs = []
        if not file_name:
            row_errs.append("File Name is required")

        if complexity not in VALID_COMPLEXITIES:
            row_errs.append(f"Invalid Complexity '{complexity}' (must be {', '.join(VALID_COMPLEXITIES)})")

        try:
            points = int(float(points_raw)) if points_raw not in (None, "") else 0
            if points < 0:
                raise ValueError
        except (ValueError, TypeError):
            row_errs.append(f"Points must be a non-negative number (got '{points_raw}')")
            points = 0

        try:
            hours = float(hours_raw) if hours_raw not in (None, "") else 0.0
            if hours < 0:
                raise ValueError
        except (ValueError, TypeError):
            row_errs.append(f"Time Worked (Hrs) must be a non-negative number (got '{hours_raw}')")
            hours = 0.0

        if status not in VALID_STATUSES:
            row_errs.append(f"Invalid Status '{status}' (must be {', '.join(VALID_STATUSES)})")

        artist = None
        if artist_raw:
            artist = member_by_name.get(artist_raw.lower()) or member_by_user.get(artist_raw.lower())
            if not artist:
                row_errs.append(f"Artist '{artist_raw}' is not an active member of team '{team_name}'")
        elif status in ("In Progress", "Done"):
            row_errs.append(f"Artist Name is required when Status is '{status}'")

        if status == "Rework" and not notes:
            row_errs.append("Notes / Rework Reason is required when Status is 'Rework'")

        # Check if file exists in DB and has an active stage for this team
        existing_file = None
        if file_name:
            existing_file = db.execute(
                "SELECT id, name FROM files WHERE LOWER(name) = LOWER(?)",
                (file_name,),
            ).fetchone()

        if existing_file:
            to_update += 1
        else:
            to_create += 1

        if status == "Done":
            handoffs += 1
        elif status == "Rework":
            reworks += 1

        if row_errs:
            errors.append(f"Row {row_num} ({file_name or 'blank'}): " + "; ".join(row_errs))
        else:
            valid_rows.append(
                {
                    "row_num": row_num,
                    "proj_chap": proj_chap,
                    "file_name": file_name,
                    "complexity": complexity,
                    "points": points,
                    "hours": hours,
                    "artist_id": artist["id"] if artist else None,
                    "artist_name": artist["name"] if artist else "",
                    "status": status,
                    "notes": notes,
                    "action": "Update" if existing_file else "Create",
                }
            )

    if not valid_rows and not errors:
        errors.append("No data rows found in the uploaded Excel sheet.")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "rows": valid_rows,
        "summary": {
            "to_update": to_update,
            "to_create": to_create,
            "handoffs": handoffs,
            "reworks": reworks,
        },
    }


def _resolve_chapter_id(db, proj_chap: str) -> int:
    """Find or create project/chapter from 'Project / Chapter' string."""
    if "/" in proj_chap:
        p_name, c_name = [part.strip() for part in proj_chap.split("/", 1)]
    elif proj_chap:
        p_name, c_name = proj_chap, "Main Chapter"
    else:
        p_name, c_name = "Default Project", "Main Chapter"

    proj = db.execute("SELECT id FROM projects WHERE LOWER(name) = LOWER(?)", (p_name,)).fetchone()
    if proj:
        pid = proj["id"]
    else:
        cur = db.execute(
            "INSERT INTO projects (name, description, status) VALUES (?, ?, 'Active')",
            (p_name, f"Auto-created from Excel upload ({p_name})"),
        )
        pid = cur.lastrowid

    chap = db.execute(
        "SELECT id FROM chapters WHERE project_id = ? AND LOWER(name) = LOWER(?)",
        (pid, c_name),
    ).fetchone()
    if chap:
        return chap["id"]

    cur = db.execute(
        "INSERT INTO chapters (project_id, name, description, status) VALUES (?, ?, ?, 'Active')",
        (pid, c_name, f"Auto-created from Excel upload ({c_name})"),
    )
    return cur.lastrowid


def _ensure_file_pipeline_stages(db, file_id: int, initial_open_team: str | None = None) -> None:
    """Ensure all ordered pipeline_stages exist in file_pipeline for file_id."""
    stages = db.execute("SELECT * FROM pipeline_stages ORDER BY stage_order ASC").fetchall()
    existing = {
        r["step_name"]
        for r in db.execute("SELECT step_name FROM file_pipeline WHERE file_id = ?", (file_id,)).fetchall()
    }
    first_for_team_opened = False
    for st in stages:
        if st["stage_name"] in existing:
            continue
        status = "Locked"
        if initial_open_team and st["team_name"] == initial_open_team and not first_for_team_opened:
            status = "Open"
            first_for_team_opened = True
        elif not initial_open_team and st["stage_order"] == 1:
            status = "Open"
        db.execute(
            """
            INSERT INTO file_pipeline (file_id, step_name, stage_order, team_name, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (file_id, st["stage_name"], st["stage_order"], st["team_name"], status),
        )


def _notify_team_lead(db, team_name: str, title: str, body: str, ntype: str = "pipeline") -> None:
    team_row = db.execute("SELECT lead_id FROM teams WHERE name = ?", (team_name,)).fetchone()
    lead_id = team_row["lead_id"] if team_row and team_row["lead_id"] else None
    if not lead_id:
        user_row = db.execute(
            "SELECT id FROM users WHERE team = ? AND role = 'Lead' LIMIT 1",
            (team_name,),
        ).fetchone()
        lead_id = user_row["id"] if user_row else None
    if lead_id:
        db.execute(
            "INSERT INTO notifications (user_id, title, body, type, link) VALUES (?, ?, ?, ?, '/dashboard')",
            (lead_id, title, body, ntype),
        )


def commit_team_upload(
    db,
    team_name: str,
    uploaded_by_user_id: int,
    rows: list[dict[str, Any]],
    filename: str = "upload.xlsx",
) -> dict[str, int]:
    """
    Atomically commit validated Excel rows in a BEGIN IMMEDIATE transaction.
    Handles file creation, stage updates, idempotent daily_assignments + points,
    sequential handoff on 'Done', rework send-back on 'Rework', and daily_upload_logs.
    """
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    now_str = datetime.datetime.now().strftime("%H:%M:%S")
    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    team_row = db.execute("SELECT id FROM teams WHERE name = ?", (team_name,)).fetchone()
    if not team_row:
        raise ValueError(f"Team '{team_name}' not found.")
    team_id = team_row["id"]

    files_updated = 0
    files_added = 0
    files_handed_off = 0
    files_rework = 0

    db.execute("BEGIN IMMEDIATE;")
    try:
        for r in rows:
            file_row = db.execute(
                "SELECT id FROM files WHERE LOWER(name) = LOWER(?)",
                (r["file_name"],),
            ).fetchone()

            if file_row:
                file_id = file_row["id"]
                files_updated += 1
            else:
                chapter_id = _resolve_chapter_id(db, r["proj_chap"])
                cur = db.execute(
                    """
                    INSERT INTO files (chapter_id, name, complexity, status, assigned_to, start_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (chapter_id, r["file_name"], r["complexity"], r["status"], r["artist_id"], today_str),
                )
                file_id = cur.lastrowid
                _ensure_file_pipeline_stages(db, file_id, initial_open_team=team_name)
                files_added += 1

            _ensure_file_pipeline_stages(db, file_id, initial_open_team=team_name)

            # Find active stage for this team (prefer Open/In Progress/Rework, else first stage of team)
            stage_row = db.execute(
                """
                SELECT * FROM file_pipeline
                WHERE file_id = ? AND team_name = ?
                ORDER BY
                    CASE status WHEN 'Rework' THEN 0 WHEN 'In Progress' THEN 1 WHEN 'Open' THEN 2 ELSE 3 END,
                    stage_order ASC
                LIMIT 1
                """,
                (file_id, team_name),
            ).fetchone()

            if not stage_row:
                raise ValueError(f"No pipeline stage found for file '{r['file_name']}' in team '{team_name}'.")

            step_name = stage_row["step_name"]
            stage_order = stage_row["stage_order"]
            new_status = r["status"]

            if new_status == "Done":
                db.execute(
                    """
                    UPDATE file_pipeline
                    SET status = 'Done',
                        assigned_to = COALESCE(?, assigned_to),
                        complexity = ?,
                        points = ?,
                        time_worked = ?,
                        start_date = COALESCE(start_date, ?),
                        end_date = ?,
                        submitted_at = ?,
                        remarks = ?
                    WHERE id = ?
                    """,
                    (
                        r["artist_id"],
                        r["complexity"],
                        r["points"],
                        r["hours"],
                        today_str,
                        today_str,
                        now_ts,
                        r["notes"],
                        stage_row["id"],
                    ),
                )
                # Sequential handoff to next stage
                next_stage = db.execute(
                    """
                    SELECT * FROM file_pipeline
                    WHERE file_id = ? AND stage_order > ?
                    ORDER BY stage_order ASC
                    LIMIT 1
                    """,
                    (file_id, stage_order),
                ).fetchone()
                if next_stage:
                    db.execute(
                        "UPDATE file_pipeline SET status = 'Open' WHERE id = ? AND status = 'Locked'",
                        (next_stage["id"],),
                    )
                    _notify_team_lead(
                        db,
                        next_stage["team_name"],
                        "Incoming File Ready",
                        f"{r['file_name']} completed {step_name} and is now Open for {next_stage['team_name']}.",
                    )
                files_handed_off += 1

            elif new_status == "Rework":
                # Lock current stage and send back to previous stage as Rework
                db.execute(
                    """
                    UPDATE file_pipeline
                    SET status = 'Locked',
                        rework_reason = ?,
                        remarks = ?
                    WHERE id = ?
                    """,
                    (r["notes"], r["notes"], stage_row["id"]),
                )
                prev_stage = db.execute(
                    """
                    SELECT * FROM file_pipeline
                    WHERE file_id = ? AND stage_order < ?
                    ORDER BY stage_order DESC
                    LIMIT 1
                    """,
                    (file_id, stage_order),
                ).fetchone()
                if prev_stage:
                    db.execute(
                        """
                        UPDATE file_pipeline
                        SET status = 'Rework',
                            rework_reason = ?,
                            rework_target_team = ?,
                            take_count = COALESCE(take_count, 1) + 1
                        WHERE id = ?
                        """,
                        (r["notes"], team_name, prev_stage["id"]),
                    )
                    _notify_team_lead(
                        db,
                        prev_stage["team_name"],
                        "Rework Requested",
                        f"{r['file_name']} was sent back from {step_name}: {r['notes']}",
                        ntype="rework",
                    )
                else:
                    # First stage cannot go further back; keep as Rework on itself
                    db.execute(
                        "UPDATE file_pipeline SET status = 'Rework', rework_reason = ? WHERE id = ?",
                        (r["notes"], stage_row["id"]),
                    )
                files_rework += 1

            else:
                # Open or In Progress
                db.execute(
                    """
                    UPDATE file_pipeline
                    SET status = ?,
                        assigned_to = COALESCE(?, assigned_to),
                        complexity = ?,
                        points = ?,
                        time_worked = ?,
                        start_date = COALESCE(start_date, ?),
                        remarks = ?
                    WHERE id = ?
                    """,
                    (
                        new_status,
                        r["artist_id"],
                        r["complexity"],
                        r["points"],
                        r["hours"],
                        today_str,
                        r["notes"],
                        stage_row["id"],
                    ),
                )

            # Update parent files summary status
            db.execute(
                "UPDATE files SET complexity = ?, status = ?, assigned_to = COALESCE(?, assigned_to) WHERE id = ?",
                (r["complexity"], new_status, r["artist_id"], file_id),
            )

            # Idempotent daily_assignments + points per (user_id, date, file_id, stage_name)
            if r["artist_id"]:
                existing_da = db.execute(
                    """
                    SELECT id FROM daily_assignments
                    WHERE user_id = ? AND date = ? AND file_id = ? AND stage_name = ?
                    """,
                    (r["artist_id"], today_str, file_id, step_name),
                ).fetchone()
                if existing_da:
                    db.execute(
                        """
                        UPDATE daily_assignments
                        SET points = ?, time_worked = ?, status = ?, remarks = ?, submit_time = ?
                        WHERE id = ?
                        """,
                        (r["points"], r["hours"], new_status, r["notes"], now_str, existing_da["id"]),
                    )
                else:
                    db.execute(
                        """
                        INSERT INTO daily_assignments
                            (user_id, date, file_id, stage_name, task_description, points, time_worked, status, remarks, submit_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            r["artist_id"],
                            today_str,
                            file_id,
                            step_name,
                            f"{r['file_name']} ({step_name})",
                            r["points"],
                            r["hours"],
                            new_status,
                            r["notes"],
                            now_str,
                        ),
                    )

                if r["points"] > 0:
                    existing_pts = db.execute(
                        """
                        SELECT id FROM points
                        WHERE user_id = ? AND date = ? AND file_id = ? AND stage_name = ?
                        """,
                        (r["artist_id"], today_str, file_id, step_name),
                    ).fetchone()
                    reason = f"Excel Upload: {r['file_name']} ({step_name})"
                    if existing_pts:
                        db.execute(
                            "UPDATE points SET points = ?, reason = ?, awarded_by = ? WHERE id = ?",
                            (r["points"], reason, uploaded_by_user_id, existing_pts["id"]),
                        )
                    else:
                        db.execute(
                            """
                            INSERT INTO points (user_id, date, file_id, stage_name, points, reason, awarded_by)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (r["artist_id"], today_str, file_id, step_name, r["points"], reason, uploaded_by_user_id),
                        )

        db.execute(
            """
            INSERT INTO daily_upload_logs
                (team_id, uploaded_by, upload_date, uploaded_at, files_updated, files_added, files_handed_off, files_rework, filename)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                team_id,
                uploaded_by_user_id,
                today_str,
                now_str,
                files_updated,
                files_added,
                files_handed_off,
                files_rework,
                filename,
            ),
        )
        db.execute(
            "INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Team Excel Upload', ?)",
            (
                uploaded_by_user_id,
                f"Team {team_name}: {files_updated} updated, {files_added} added, {files_handed_off} handed off, {files_rework} rework.",
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "files_updated": files_updated,
        "files_added": files_added,
        "files_handed_off": files_handed_off,
        "files_rework": files_rework,
    }
