"""
Per-team Excel template generation, dry-run validation, atomic commit,
and sequential pipeline handoff / Retake (Take 1, Take 2, Take 3) logic.
"""
import datetime
import io
import re
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
    "Take Version",
    "Notes / Retake Reason",
]

VALID_COMPLEXITIES = ["Easy", "Medium", "Hard", "High Complexity"]
VALID_STATUSES = ["Yet to Start", "Work In Progress", "Review", "Retake", "Approved"]
VALID_TAKES = ["Take 1", "Take 2", "Take 3"]
OPEN_QUEUE_STATUSES = ("Yet to Start", "Work In Progress", "Review", "Retake", "Open", "In Progress", "Rework")


def strip_take_suffix(file_name: str) -> str:
    """Remove any trailing _Take_1 / _Take_2 / _Take_3 suffix from a file name."""
    return re.sub(r"_Take_[123]$", "", file_name.strip(), flags=re.IGNORECASE)


def apply_take_suffix(file_name: str, take_num: int) -> str:
    """Append _Take_<N> cleanly to the base file name."""
    base = strip_take_suffix(file_name)
    return f"{base}_Take_{take_num}"


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
    """Return all file_pipeline rows currently active for team_name."""
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
            COALESCE(fp.take_count, 0) AS take_count,
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
          AND fp.status IN ('Yet to Start', 'Work In Progress', 'Review', 'Retake', 'Open', 'In Progress', 'Rework')
        ORDER BY
            CASE fp.status
                WHEN 'Retake' THEN 0
                WHEN 'Review' THEN 1
                WHEN 'Work In Progress' THEN 2
                ELSE 3
            END,
            p.name ASC, c.name ASC, f.name ASC, fp.stage_order ASC
        """,
        (team_name,),
    ).fetchall()
    return [dict(r) for r in rows]


def generate_team_excel_template(db, team_name: str) -> bytes:
    """
    Generate an .xlsx workbook pre-filled with active queue files for team_name,
    plus 25 blank rows for adding new files, with protected headers and dropdown validations.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{team_name[:25]} Queue"

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
    pc_labels = [r["label"] for r in proj_chaps] or ["Promo Videos / Promo Videos Main Chapter"]
    for idx, label in enumerate(pc_labels, start=1):
        ref_ws.cell(row=idx, column=2, value=label)

    header_fill = PatternFill(start_color="232325", end_color="232325", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    retake_fill = PatternFill(start_color="FBEEEE", end_color="FBEEEE", fill_type="solid")

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
        is_retake = item["status"] in ("Retake", "Rework")
        note = item["rework_reason"] if is_retake and item["rework_reason"] else (item["remarks"] or "")
        take_str = f"Take {item['take_count']}" if (item.get("take_count") or 0) in (1, 2, 3) else ""
        comp = item["complexity"] if item["complexity"] in VALID_COMPLEXITIES else "Medium"
        st_display = "Retake" if is_retake else (
            "Yet to Start" if item["status"] == "Open" else (
                "Work In Progress" if item["status"] == "In Progress" else item["status"]
            )
        )
        values = [
            proj_chap,
            item["file_name"],
            comp,
            item["points"] or 0,
            item["time_worked"] or 0.0,
            item["artist_name"] or "",
            st_display,
            take_str,
            note,
        ]
        for col_idx, val in enumerate(values, start=1):
            c = ws.cell(row=row_idx, column=col_idx, value=val)
            c.protection = Protection(locked=False)
            if is_retake:
                c.fill = retake_fill
        row_idx += 1

    total_rows = max(row_idx + 25, 30)
    for r in range(row_idx, total_rows + 1):
        for col_idx in range(1, len(TEMPLATE_HEADERS) + 1):
            c = ws.cell(row=r, column=col_idx, value="")
            c.protection = Protection(locked=False)

    dv_pc = DataValidation(type="list", formula1=f"=_Lists!$B$1:$B${len(pc_labels)}", allow_blank=True)
    dv_complexity = DataValidation(type="list", formula1=f'"{",".join(VALID_COMPLEXITIES)}"', allow_blank=True)
    dv_artist = DataValidation(type="list", formula1=f"=_Lists!$A$1:$A${len(member_names)}", allow_blank=True)
    dv_status = DataValidation(type="list", formula1=f'"{",".join(VALID_STATUSES)}"', allow_blank=False)
    dv_take = DataValidation(type="list", formula1=f'"{",".join(VALID_TAKES)}"', allow_blank=True)

    for dv in (dv_pc, dv_complexity, dv_artist, dv_status, dv_take):
        ws.add_data_validation(dv)

    dv_pc.add(f"A2:A{total_rows}")
    dv_complexity.add(f"C2:C{total_rows}")
    dv_artist.add(f"F2:F{total_rows}")
    dv_status.add(f"G2:G{total_rows}")
    dv_take.add(f"H2:H{total_rows}")

    col_widths = [28, 32, 18, 10, 18, 22, 18, 15, 36]
    for i, w in enumerate(col_widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.protection.sheet = True
    ws.protection.enable()

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _find_existing_file(db, file_name: str):
    """Find file by exact name or base name (ignoring _Take_N suffix)."""
    row = db.execute("SELECT id, name, COALESCE(take_count, 0) AS take_count FROM files WHERE LOWER(name) = LOWER(?)", (file_name,)).fetchone()
    if row:
        return row
    base = strip_take_suffix(file_name)
    return db.execute(
        "SELECT id, name, COALESCE(take_count, 0) AS take_count FROM files WHERE LOWER(name) = LOWER(?) OR LOWER(name) LIKE LOWER(?)",
        (base, f"{base}_Take_%"),
    ).fetchone()


def parse_and_validate_upload(db, team_name: str, file_bytes: bytes) -> dict[str, Any]:
    """
    Dry-run parse & validate an uploaded .xlsx workbook for team_name.
    Enforces Status, Complexity, compulsory Take Version (1->2->3 progression) on Retake,
    and updates the file name with _Take_N when Retake is selected.
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
            "summary": {"to_update": 0, "to_create": 0, "handoffs": 0, "retakes": 0},
        }

    ws = wb.active
    headers = [str(ws.cell(row=1, column=c).value or "").strip() for c in range(1, len(TEMPLATE_HEADERS) + 1)]
    if headers != TEMPLATE_HEADERS:
        return {
            "ok": False,
            "errors": [f"Invalid template headers. Expected {TEMPLATE_HEADERS}, got {headers}."],
            "rows": [],
            "summary": {"to_update": 0, "to_create": 0, "handoffs": 0, "retakes": 0},
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
            "summary": {"to_update": 0, "to_create": 0, "handoffs": 0, "retakes": 0},
        }

    to_update = 0
    to_create = 0
    handoffs = 0
    retakes = 0

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
        status = str(vals[6] or "Yet to Start").strip()
        take_raw = str(vals[7] or "").strip()
        notes = str(vals[8] or "").strip()

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
        elif status in ("Work In Progress", "Review", "Approved"):
            row_errs.append(f"Artist Name is required when Status is '{status}'")

        existing_file = _find_existing_file(db, file_name) if file_name else None
        current_take = existing_file["take_count"] if existing_file else 0
        final_file_name = file_name
        take_num = current_take

        if status == "Retake":
            if take_raw not in VALID_TAKES:
                row_errs.append("Take Version (Take 1, Take 2, or Take 3) is compulsory when Status is 'Retake'")
            else:
                requested_take = int(take_raw.split()[-1])
                expected_take = min(current_take + 1, 3)
                if current_take >= 3:
                    row_errs.append("File has already reached Take 3 (maximum retake version)")
                elif requested_take != expected_take:
                    row_errs.append(
                        f"Invalid Take progression: current take is {current_take or 'Review/0'}, so next Retake must be 'Take {expected_take}'"
                    )
                else:
                    take_num = requested_take
                    final_file_name = apply_take_suffix(file_name, take_num)
            if not notes:
                row_errs.append("Notes / Retake Reason is required when Status is 'Retake'")

        if existing_file:
            to_update += 1
        else:
            to_create += 1

        if status == "Approved":
            handoffs += 1
        elif status == "Retake":
            retakes += 1

        if row_errs:
            errors.append(f"Row {row_num} ({file_name or 'blank'}): " + "; ".join(row_errs))
        else:
            valid_rows.append(
                {
                    "row_num": row_num,
                    "proj_chap": proj_chap,
                    "file_name": final_file_name,
                    "raw_file_name": file_name,
                    "complexity": complexity,
                    "points": points,
                    "hours": hours,
                    "artist_id": artist["id"] if artist else None,
                    "artist_name": artist["name"] if artist else "",
                    "status": status,
                    "take_version": f"Take {take_num}" if take_num in (1, 2, 3) else "",
                    "take_num": take_num,
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
            "retakes": retakes,
        },
    }


def _resolve_chapter_id(db, proj_chap: str) -> int:
    if "/" in proj_chap:
        p_name, c_name = [part.strip() for part in proj_chap.split("/", 1)]
    elif proj_chap:
        p_name, c_name = proj_chap, "Main Chapter"
    else:
        p_name, c_name = "Promo Videos", "Promo Videos Main Chapter"

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
    proj_row = db.execute(
        """
        SELECT p.project_type FROM files f
        JOIN chapters c ON f.chapter_id = c.id
        JOIN projects p ON c.project_id = p.id
        WHERE f.id = ?
        """,
        (file_id,),
    ).fetchone()
    is_comp_only = bool(proj_row and proj_row["project_type"] == "Comp Only")

    if is_comp_only:
        stages = db.execute(
            "SELECT * FROM pipeline_stages WHERE team_name = '3D Comp & Motion Graphics' ORDER BY stage_order ASC"
        ).fetchall()
    else:
        stages = db.execute("SELECT * FROM pipeline_stages ORDER BY stage_order ASC").fetchall()

    existing = {
        r["step_name"]
        for r in db.execute("SELECT step_name FROM file_pipeline WHERE file_id = ?", (file_id,)).fetchall()
    }
    first_for_team_opened = False
    for idx, st in enumerate(stages):
        if st["stage_name"] in existing:
            continue
        status = "Locked"
        if initial_open_team and st["team_name"] == initial_open_team and not first_for_team_opened:
            status = "Yet to Start"
            first_for_team_opened = True
        elif not initial_open_team and idx == 0:
            status = "Yet to Start"
        db.execute(
            """
            INSERT INTO file_pipeline (file_id, step_name, stage_order, team_name, status, take_count)
            VALUES (?, ?, ?, ?, ?, 0)
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
    - 'Approved': marks current stage Approved & opens next stage as 'Yet to Start'.
    - 'Retake': appends _Take_N to file name, sets take_count = N, and reopens previous
      stage (or keeps current stage if first) as 'Retake' with reason note.
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
    files_retake = 0

    db.execute("BEGIN IMMEDIATE;")
    try:
        for r in rows:
            file_row = _find_existing_file(db, r["raw_file_name"])

            if file_row:
                file_id = file_row["id"]
                files_updated += 1
            else:
                chapter_id = _resolve_chapter_id(db, r["proj_chap"])
                cur = db.execute(
                    """
                    INSERT INTO files (chapter_id, name, complexity, status, assigned_to, take_count, start_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (chapter_id, r["file_name"], r["complexity"], r["status"], r["artist_id"], r["take_num"], today_str),
                )
                file_id = cur.lastrowid
                _ensure_file_pipeline_stages(db, file_id, initial_open_team=team_name)
                files_added += 1

            _ensure_file_pipeline_stages(db, file_id, initial_open_team=team_name)

            stage_row = db.execute(
                """
                SELECT * FROM file_pipeline
                WHERE file_id = ? AND team_name = ?
                ORDER BY
                    CASE status
                        WHEN 'Retake' THEN 0
                        WHEN 'Rework' THEN 0
                        WHEN 'Review' THEN 1
                        WHEN 'Work In Progress' THEN 2
                        WHEN 'In Progress' THEN 2
                        WHEN 'Yet to Start' THEN 3
                        WHEN 'Open' THEN 3
                        ELSE 4
                    END,
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

            if new_status == "Approved":
                db.execute(
                    """
                    UPDATE file_pipeline
                    SET status = 'Approved',
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
                next_stage = db.execute(
                    "SELECT * FROM file_pipeline WHERE file_id = ? AND stage_order > ? ORDER BY stage_order ASC LIMIT 1",
                    (file_id, stage_order),
                ).fetchone()
                if next_stage:
                    db.execute(
                        "UPDATE file_pipeline SET status = 'Yet to Start' WHERE id = ? AND status = 'Locked'",
                        (next_stage["id"],),
                    )
                    _notify_team_lead(
                        db,
                        next_stage["team_name"],
                        "Incoming File Ready",
                        f"{r['file_name']} is Approved in {step_name} and is now Yet to Start for {next_stage['team_name']}.",
                    )
                files_handed_off += 1

            elif new_status == "Retake":
                take_num = r["take_num"]
                prev_stage = db.execute(
                    "SELECT * FROM file_pipeline WHERE file_id = ? AND stage_order < ? ORDER BY stage_order DESC LIMIT 1",
                    (file_id, stage_order),
                ).fetchone()
                if prev_stage:
                    db.execute(
                        "UPDATE file_pipeline SET status = 'Locked', rework_reason = ?, remarks = ? WHERE id = ?",
                        (r["notes"], r["notes"], stage_row["id"]),
                    )
                    db.execute(
                        """
                        UPDATE file_pipeline
                        SET status = 'Retake',
                            rework_reason = ?,
                            rework_target_team = ?,
                            take_count = ?
                        WHERE id = ?
                        """,
                        (r["notes"], team_name, take_num, prev_stage["id"]),
                    )
                    _notify_team_lead(
                        db,
                        prev_stage["team_name"],
                        f"Retake (Take {take_num}) Requested",
                        f"{r['file_name']} sent back from {step_name} as Take {take_num}: {r['notes']}",
                        ntype="rework",
                    )
                else:
                    db.execute(
                        """
                        UPDATE file_pipeline
                        SET status = 'Retake',
                            rework_reason = ?,
                            take_count = ?,
                            remarks = ?
                        WHERE id = ?
                        """,
                        (r["notes"], take_num, r["notes"], stage_row["id"]),
                    )
                files_retake += 1

            else:
                # Yet to Start, Work In Progress, Review
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

            # Update parent files record (including _Take_N rename and take_count)
            db.execute(
                """
                UPDATE files
                SET name = ?,
                    complexity = ?,
                    status = ?,
                    take_count = ?,
                    assigned_to = COALESCE(?, assigned_to),
                    rework_reason = CASE WHEN ? = 'Retake' THEN ? ELSE rework_reason END
                WHERE id = ?
                """,
                (r["file_name"], r["complexity"], new_status, r["take_num"], r["artist_id"], new_status, r["notes"], file_id),
            )

            # Idempotent daily_assignments + points per (user_id, date, file_id, stage_name)
            # (Linked to upload_log_id below for full Excel evidence tracking)
            if r["artist_id"]:
                existing_da = db.execute(
                    "SELECT id FROM daily_assignments WHERE user_id = ? AND date = ? AND file_id = ? AND stage_name = ?",
                    (r["artist_id"], today_str, file_id, step_name),
                ).fetchone()
                if existing_da:
                    db.execute(
                        """
                        UPDATE daily_assignments
                        SET team_name = ?, complexity = ?, points = ?, time_worked = ?, status = ?, remarks = ?, submit_time = ?
                        WHERE id = ?
                        """,
                        (team_name, r["complexity"], r["points"], r["hours"], new_status, r["notes"], now_str, existing_da["id"]),
                    )
                else:
                    db.execute(
                        """
                        INSERT INTO daily_assignments
                            (user_id, date, file_id, stage_name, team_name, complexity, task_description, points, time_worked, status, remarks, submit_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            r["artist_id"],
                            today_str,
                            file_id,
                            step_name,
                            team_name,
                            r["complexity"],
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
                        "SELECT id FROM points WHERE user_id = ? AND date = ? AND file_id = ? AND stage_name = ?",
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
                            "INSERT INTO points (user_id, date, file_id, stage_name, points, reason, awarded_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (r["artist_id"], today_str, file_id, step_name, r["points"], reason, uploaded_by_user_id),
                        )

        cur_log = db.execute(
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
                files_retake,
                filename,
            ),
        )
        upload_log_id = cur_log.lastrowid

        # Attach upload_log_id evidence to today's assignments for the uploaded files
        for r in rows:
            if r["artist_id"]:
                f_row = _find_existing_file(db, r["file_name"])
                if f_row:
                    db.execute(
                        "UPDATE daily_assignments SET upload_log_id = ? WHERE user_id = ? AND date = ? AND file_id = ?",
                        (upload_log_id, r["artist_id"], today_str, f_row["id"]),
                    )
        db.execute(
            "INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Team Excel Upload', ?)",
            (
                uploaded_by_user_id,
                f"Team {team_name}: {files_updated} updated, {files_added} added, {files_handed_off} approved/handed off, {files_retake} retakes.",
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
        "files_rework": files_retake,
    }


ASSET_SCENE_HEADERS = ["Project Name", "Type", "Chapter", "File Name"]


def generate_assets_scenes_template(db) -> bytes:
    """
    Generate the 'Upload Assets & Scene Names' .xlsx template for HR, Content Lead, and Admin.
    Columns: Project Name (dropdown), Type (Asset/Scene dropdown), Chapter (optional), File Name (required).
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Assets & Scenes"

    ref_ws = wb.create_sheet(title="_Projects")
    ref_ws.sheet_state = "hidden"

    projects = db.execute("SELECT name FROM projects WHERE status = 'Active' ORDER BY name ASC").fetchall()
    proj_names = [r["name"] for r in projects] or ["Promo Videos"]
    for idx, p_name in enumerate(proj_names, start=1):
        ref_ws.cell(row=idx, column=1, value=p_name)

    header_fill = PatternFill(start_color="232325", end_color="232325", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    for col_idx, heading in enumerate(ASSET_SCENE_HEADERS, start=1):
        c = ws.cell(row=1, column=col_idx, value=heading)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.protection = Protection(locked=True)

    ws.row_dimensions[1].height = 26
    ws.freeze_panes = "A2"

    for r in range(2, 102):
        for c_idx in range(1, 5):
            cell = ws.cell(row=r, column=c_idx, value="")
            cell.protection = Protection(locked=False)

    dv_proj = DataValidation(type="list", formula1=f"=_Projects!$A$1:$A${len(proj_names)}", allow_blank=False)
    dv_type = DataValidation(type="list", formula1='"Asset,Scene"', allow_blank=False)
    ws.add_data_validation(dv_proj)
    ws.add_data_validation(dv_type)
    dv_proj.add("A2:A101")
    dv_type.add("B2:B101")

    for i, w in enumerate([28, 14, 28, 36], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.protection.sheet = True
    ws.protection.enable()

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def import_assets_scenes_excel(db, file_bytes: bytes, uploaded_by_user_id: int) -> dict[str, Any]:
    """
    Validate and atomically import Assets & Scene Names from the simple 4-column template
    into `files` and `file_pipeline` (initializing first stage as 'Yet to Start' and rest 'Locked').
    """
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as exc:
        return {"ok": False, "errors": [f"Could not read Excel file: {exc}"], "created": 0, "skipped": 0}

    ws = wb.active
    headers = [str(ws.cell(row=1, column=c).value or "").strip() for c in range(1, 5)]
    if headers != ASSET_SCENE_HEADERS:
        return {
            "ok": False,
            "errors": [f"Invalid headers. Expected {ASSET_SCENE_HEADERS}, got {headers}."],
            "created": 0,
            "skipped": 0,
        }

    errors = []
    parsed = []
    for row_num in range(2, ws.max_row + 1):
        vals = [ws.cell(row=row_num, column=c).value for c in range(1, 5)]
        if all(v is None or str(v).strip() == "" for v in vals):
            continue
        p_name = str(vals[0] or "").strip()
        f_type = str(vals[1] or "").strip()
        c_name = str(vals[2] or "").strip() or "Main Chapter"
        f_name = str(vals[3] or "").strip()

        row_errs = []
        if not p_name:
            row_errs.append("Project Name is required")
        if f_type not in ("Asset", "Scene"):
            row_errs.append("Type must be 'Asset' or 'Scene'")
        if not f_name:
            row_errs.append("File Name is required")

        if row_errs:
            errors.append(f"Row {row_num}: " + "; ".join(row_errs))
        else:
            parsed.append({"project_name": p_name, "file_type": f_type, "chapter_name": c_name, "file_name": f_name})

    if errors:
        return {"ok": False, "errors": errors, "created": 0, "skipped": 0}
    if not parsed:
        return {"ok": False, "errors": ["No data rows found in the uploaded Excel sheet."], "created": 0, "skipped": 0}

    created = 0
    skipped = 0
    db.execute("BEGIN IMMEDIATE;")
    try:
        for r in parsed:
            proj = db.execute("SELECT id FROM projects WHERE LOWER(name) = LOWER(?)", (r["project_name"],)).fetchone()
            if proj:
                pid = proj["id"]
            else:
                pid = db.execute(
                    "INSERT INTO projects (name, description, status) VALUES (?, 'Created via Assets & Scenes Upload', 'Active')",
                    (r["project_name"],),
                ).lastrowid

            chap = db.execute(
                "SELECT id FROM chapters WHERE project_id = ? AND LOWER(name) = LOWER(?)",
                (pid, r["chapter_name"]),
            ).fetchone()
            if chap:
                cid = chap["id"]
            else:
                cid = db.execute(
                    "INSERT INTO chapters (project_id, name, description, status) VALUES (?, ?, 'Chapter', 'Active')",
                    (pid, r["chapter_name"]),
                ).lastrowid

            existing = db.execute(
                "SELECT id FROM files WHERE chapter_id = ? AND LOWER(name) = LOWER(?)",
                (cid, r["file_name"]),
            ).fetchone()
            if existing:
                skipped += 1
                continue

            file_id = db.execute(
                """
                INSERT INTO files (chapter_id, name, file_type, complexity, status, take_count)
                VALUES (?, ?, ?, 'Medium', 'Yet to Start', 0)
                """,
                (cid, r["file_name"], r["file_type"]),
            ).lastrowid
            _ensure_file_pipeline_stages(db, file_id)
            created += 1

        db.execute(
            "INSERT INTO activity_log (user_id, action, details) VALUES (?, 'Upload Assets & Scenes', ?)",
            (uploaded_by_user_id, f"Registered {created} new file(s), skipped {skipped} duplicate(s)."),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"ok": True, "errors": [], "created": created, "skipped": skipped}
