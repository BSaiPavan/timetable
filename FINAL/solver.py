import random
import copy
import logging
import os

log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solver_debug.log')
logging.basicConfig(
    filename=log_path,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)

try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
    logging.info("OR-Tools loaded successfully")
except ImportError:
    ORTOOLS_AVAILABLE = False
    logging.warning("OR-Tools not installed. Falling back to backtracking solver.")


# ═══════════════════════════════════════════════════════════════════════════════
#  OR-TOOLS CP-SAT SOLVER
# ═══════════════════════════════════════════════════════════════════════════════

def generate_timetable_ortools(
    No_of_classes, No_of_days_in_week, No_of_periods,
    teacher_list, class_teacher_periods, lab_teacher_periods,
    subject_map, fixed_periods=None, teacher_unavailability=None,
    time_limit_seconds=60, elective_bundles=None
):
    total_slots = No_of_days_in_week * No_of_periods
    model = cp_model.CpModel()

    # ── STEP 1: Pre-fill fixed slots ─────────────────────────────────────────
    Timetable = [[0] * No_of_classes for _ in range(total_slots)]
    fixed_set = set()
    teacher_busy = {tid: set() for tid in teacher_list}

    # ── Inject teacher unavailability into teacher_busy ─────────────────────
    if teacher_unavailability:
        for tid_str, slots in teacher_unavailability.items():
            try:
                tid = int(tid_str)
            except ValueError:
                continue
            if tid not in teacher_busy:
                teacher_busy[tid] = set()
            for slot_str in slots:
                try:
                    if '-' in str(slot_str):
                        d, p = map(int, str(slot_str).split('-'))
                        flat = d * No_of_periods + p
                    else:
                        flat = int(slot_str)
                    if 0 <= flat < total_slots:
                        teacher_busy[tid].add(flat)
                except Exception:
                    continue

    if fixed_periods:
        for cls_idx_str, slots in fixed_periods.items():
            try:
                cls_idx = int(cls_idx_str)
            except ValueError:
                continue
            for slot_str, info in slots.items():
                label    = (info.get('label') or '').strip()
                t_id_raw = info.get('teacher_id', '')
                is_free  = info.get('is_free', False) or str(t_id_raw) == '__free__'
                is_event = info.get('is_event', False) or str(t_id_raw) == '__event__'

                if not label or str(t_id_raw) == '__none__':
                    continue
                try:
                    if '-' in slot_str:
                        d, p = map(int, slot_str.split('-'))
                        flat_slot = d * No_of_periods + p
                    else:
                        flat_slot = int(slot_str)
                except Exception:
                    continue
                if flat_slot < 0 or flat_slot >= total_slots:
                    continue

                Timetable[flat_slot][cls_idx] = label
                fixed_set.add((flat_slot, cls_idx))

                if not is_event and not is_free and str(t_id_raw).lstrip('-').isdigit():
                    t_id = int(t_id_raw)
                    if t_id in teacher_busy:
                        if flat_slot in teacher_busy[t_id]:
                            logging.error(f"Fixed slot collision: Teacher {t_id} slot {flat_slot}")
                            return None
                        teacher_busy[t_id].add(flat_slot)
                elif is_free:
                    f_id = 1000 + cls_idx
                    teacher_busy.setdefault(f_id, set()).add(flat_slot)

    # ── STEP 2: Place labs greedily (consecutive blocks) ─────────────────────
    labs = {}
    lab_used_by_class_per_day = {idx: {} for idx in range(No_of_classes)}

    for class_idx, teacher_periods in lab_teacher_periods.items():
        for teacher_id, (total_sessions, consecutive_periods, lab_number) in teacher_periods.items():
            labs.setdefault(lab_number, [])
            available_slots = [
                s for s in range(total_slots)
                if Timetable[s][class_idx] == 0
                and s not in teacher_busy.get(teacher_id, set())
            ]
            random.shuffle(available_slots)
            sessions_assigned = 0
            for slot in available_slots:
                if slot + consecutive_periods > total_slots:
                    continue
                can_assign = True
                for i in range(consecutive_periods):
                    day = (slot + i) // No_of_periods
                    if (Timetable[slot + i][class_idx] != 0 or
                            (slot + i) in teacher_busy.get(teacher_id, set()) or
                            (slot // No_of_periods) != day or
                            (slot + i) in labs[lab_number] or
                            lab_number in lab_used_by_class_per_day[class_idx].get(day, set())):
                        can_assign = False
                        break
                if can_assign:
                    subject_name = "Lab"
                    if class_idx in subject_map and teacher_id in subject_map[class_idx]:
                        for sub in subject_map[class_idx][teacher_id]:
                            if sub["type"] == "lab":
                                subject_name = sub["name"]
                                break
                    for i in range(consecutive_periods):
                        s = slot + i
                        Timetable[s][class_idx] = f"{subject_name} (Lab {lab_number})"
                        fixed_set.add((s, class_idx))
                        teacher_busy.setdefault(teacher_id, set()).add(s)
                        labs[lab_number].append(s)
                        day = s // No_of_periods
                        lab_used_by_class_per_day[class_idx].setdefault(day, set()).add(lab_number)
                    sessions_assigned += consecutive_periods
                if sessions_assigned >= total_sessions:
                    break

    # ── STEP 3: Build subject entries per class ───────────────────────────────
    # class_entries[cidx] = list of {teacher_id, name, type, hours}
    class_entries = {}
    for cidx in range(No_of_classes):
        class_entries[cidx] = []
        if cidx in subject_map:
            for tid, subs in subject_map[cidx].items():
                for sub in subs:
                    if sub["type"] == "theory" and sub["hours"] > 0:
                        class_entries[cidx].append({
                            "teacher_id": tid,
                            "name": sub["name"],
                            "hours": sub["hours"]
                        })

    # ── STEP 4: Create boolean decision variables ─────────────────────────────
    # assign_vars[cidx][slot] = list of (entry_idx, BoolVar)
    assign_vars = {}
    for cidx in range(No_of_classes):
        assign_vars[cidx] = {}
        for slot in range(total_slots):
            if (slot, cidx) in fixed_set:
                continue
            slot_vars = []
            for eidx, entry in enumerate(class_entries[cidx]):
                v = model.NewBoolVar(f"c{cidx}_s{slot}_e{eidx}")
                slot_vars.append((eidx, v))
            assign_vars[cidx][slot] = slot_vars
            # Exactly one subject per empty slot
            if slot_vars:
                model.AddExactlyOne([v for _, v in slot_vars])

    # ── STEP 5: Hour budget — each subject assigned exactly its hours ─────────
    for cidx in range(No_of_classes):
        for eidx, entry in enumerate(class_entries[cidx]):
            vars_for_entry = [
                v for slot, slot_vars in assign_vars[cidx].items()
                for ei, v in slot_vars if ei == eidx
            ]
            if vars_for_entry:
                model.Add(sum(vars_for_entry) == entry["hours"])

    # ── STEP 6: Teacher conflict — one class per teacher per slot ─────────────
    slot_teacher_vars = {}
    for cidx in range(No_of_classes):
        for slot, slot_vars in assign_vars[cidx].items():
            for eidx, v in slot_vars:
                tid = class_entries[cidx][eidx]["teacher_id"]
                slot_teacher_vars.setdefault((slot, tid), []).append(v)

    # Block vars for teachers already busy at a slot (from fixed/labs)
    for tid, busy_slots in teacher_busy.items():
        for slot in busy_slots:
            for v in slot_teacher_vars.get((slot, tid), []):
                model.Add(v == 0)

    # At most one class per teacher per slot
    for (slot, tid), var_list in slot_teacher_vars.items():
        if len(var_list) > 1:
            model.AddAtMostOne(var_list)

    # ── STEP 7: No repeat subject on same day ─────────────────────────────────
    for cidx in range(No_of_classes):
        for eidx, entry in enumerate(class_entries[cidx]):
            if entry["name"] == "Free":
                continue
            for day in range(No_of_days_in_week):
                day_vars = [
                    v for p in range(No_of_periods)
                    for slot in [day * No_of_periods + p]
                    if slot in assign_vars[cidx]
                    for ei, v in assign_vars[cidx][slot] if ei == eidx
                ]
                if day_vars:
                    model.Add(sum(day_vars) <= 1)

    # ── STEP 7b: Sync Group constraints ──────────────────────────────────────
    # For each sync group, all member subjects must be placed at the SAME K slots.
    # Works for both:
    #   split  — different subjects/teachers firing simultaneously
    #   merged — same subject shared across classes (same teacher in multiple classes)
    if elective_bundles:
        for bundle in elective_bundles:
            bname    = bundle.get("name", "bundle")
            btype    = bundle.get("type", "split")
            k        = int(bundle.get("periodsPerWeek", bundle.get("periods_per_week", 1)))
            members  = bundle.get("members", [])
            # Fall back to assignments dict if members not provided (backward compat)
            if not members:
                for ci_raw, subj in bundle.get("assignments", {}).items():
                    members.append({"classIdx": int(ci_raw), "subject": subj, "teacherId": None})
            if not members or k < 1:
                continue

            involved_cidxs = list({int(m["classIdx"]) for m in members if int(m.get("classIdx", 999)) < No_of_classes})

            # Slot indicators: True iff this slot is one of K shared bundle slots
            bundle_slot_indicators = {}
            for slot in range(total_slots):
                if any((slot, ci) in fixed_set for ci in involved_cidxs):
                    continue
                bv = model.NewBoolVar(f"sg_{bname}_slot{slot}".replace(" ", "_"))
                bundle_slot_indicators[slot] = bv

            if not bundle_slot_indicators:
                logging.warning(f"Sync group '{bname}': no free slots available")
                continue

            model.Add(sum(bundle_slot_indicators.values()) == k)

            for m in members:
                cidx         = int(m.get("classIdx", -1))
                subj_name    = (m.get("subject") or "").strip()
                if cidx < 0 or cidx >= No_of_classes or not subj_name:
                    continue

                eidx_for_subj = None
                for eidx, entry in enumerate(class_entries[cidx]):
                    if entry["name"].lower().strip() == subj_name.lower().strip():
                        eidx_for_subj = eidx
                        break
                if eidx_for_subj is None:
                    logging.warning(f"Sync group '{bname}': subject '{subj_name}' not found in class {cidx} — skipping member")
                    continue

                for slot, bv in bundle_slot_indicators.items():
                    if slot not in assign_vars[cidx]:
                        model.Add(bv == 0)
                        continue
                    elec_vars = [v for ei, v in assign_vars[cidx][slot] if ei == eidx_for_subj]
                    if not elec_vars:
                        model.Add(bv == 0)
                        continue
                    elec_v = elec_vars[0]
                    model.AddImplication(bv, elec_v)
                    model.AddImplication(elec_v, bv)

            logging.info(f"Sync group '{bname}' ({btype}): {k} shared slots, {len(members)} members constrained")

    # ── STEP 8: Solve ─────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers  = 8
    solver.parameters.log_search_progress = False

    logging.info(f"CP-SAT solving: {No_of_classes} classes, {total_slots} slots, {time_limit_seconds}s limit")
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        logging.error(f"CP-SAT failed: {solver.StatusName(status)}")
        return None

    logging.info(f"CP-SAT done: {solver.StatusName(status)} in {solver.WallTime():.2f}s")

    # ── STEP 9: Extract into Timetable matrix ─────────────────────────────────
    for cidx in range(No_of_classes):
        for slot, slot_vars in assign_vars[cidx].items():
            for eidx, v in slot_vars:
                if solver.Value(v) == 1:
                    Timetable[slot][cidx] = class_entries[cidx][eidx]["name"]
                    break

    return Timetable


# ═══════════════════════════════════════════════════════════════════════════════
#  BACKTRACKING SOLVER (fallback)
# ═══════════════════════════════════════════════════════════════════════════════

import sys
sys.setrecursionlimit(50000)

def generate_timetable_backtrack(
    No_of_classes, No_of_days_in_week, No_of_periods,
    teacher_list, class_teacher_periods, lab_teacher_periods,
    subject_map, fixed_periods=None, teacher_unavailability=None,
    elective_bundles=None
):
    total_periods = No_of_days_in_week * No_of_periods
    Timetable = [[0] * No_of_classes for _ in range(total_periods)]
    main_teacher_list = [copy.deepcopy(teacher_list) for _ in range(total_periods)]

    # ── Inject teacher unavailability — mark teacher as busy at those slots ──
    if teacher_unavailability:
        for tid_str, slots in teacher_unavailability.items():
            try:
                tid = int(tid_str)
            except ValueError:
                continue
            for slot_str in slots:
                try:
                    if '-' in str(slot_str):
                        d, p = map(int, str(slot_str).split('-'))
                        flat = d * No_of_periods + p
                    else:
                        flat = int(slot_str)
                    if 0 <= flat < total_periods and tid in main_teacher_list[flat]:
                        main_teacher_list[flat][tid]['available'] = False
                except Exception:
                    continue

    if fixed_periods:
        for cls_idx_str, slots in fixed_periods.items():
            try:
                cls_idx = int(cls_idx_str)
            except ValueError:
                continue
            for slot_str, info in slots.items():
                label    = (info.get('label') or '').strip()
                t_id_raw = info.get('teacher_id', '')
                is_free  = info.get('is_free', False) or str(t_id_raw) == '__free__'
                is_event = info.get('is_event', False) or str(t_id_raw) == '__event__'
                if not label or str(t_id_raw) == '__none__':
                    continue
                try:
                    if '-' in slot_str:
                        d, p = map(int, slot_str.split('-'))
                        flat_slot = d * No_of_periods + p
                    else:
                        flat_slot = int(slot_str)
                except Exception:
                    continue
                if flat_slot < 0 or flat_slot >= total_periods:
                    continue
                Timetable[flat_slot][cls_idx] = label
                if is_event:
                    pass
                elif is_free:
                    f_id = 1000 + cls_idx
                    if f_id in main_teacher_list[flat_slot]:
                        main_teacher_list[flat_slot][f_id]["available"] = False
                elif str(t_id_raw).lstrip('-').isdigit():
                    t_id = int(t_id_raw)
                    if t_id in main_teacher_list[flat_slot]:
                        if not main_teacher_list[flat_slot][t_id]["available"]:
                            return None
                        main_teacher_list[flat_slot][t_id]["available"] = False

    class_to_teacher = []
    for class_idx in range(No_of_classes):
        credits = {}
        active_teacher_ids = list(teacher_list.keys())
        for t_idx, periods in class_teacher_periods.get(class_idx, {}).items():
            credits[t_idx] = max(0, periods)
        if class_idx in lab_teacher_periods:
            for t_id, info in lab_teacher_periods[class_idx].items():
                credits[t_id] = credits.get(t_id, 0) + info[0]
        credits['__ids__'] = active_teacher_ids
        class_to_teacher.append(credits)

    labs = {}
    lab_used_by_class_per_day = {idx: {} for idx in range(No_of_classes)}

    def assign_lab_periods_randomly():
        for class_idx, teacher_periods in lab_teacher_periods.items():
            for teacher_id, (total_sessions, consecutive_periods, lab_number) in teacher_periods.items():
                labs.setdefault(lab_number, [])
                available_slots = [
                    i for i in range(total_periods)
                    if Timetable[i][class_idx] == 0
                    and teacher_id in main_teacher_list[i]
                    and main_teacher_list[i][teacher_id]["available"]
                ]
                random.shuffle(available_slots)
                sessions_assigned = 0
                for slot in available_slots:
                    if slot + consecutive_periods > total_periods:
                        continue
                    can_assign = True
                    for i in range(consecutive_periods):
                        day = (slot + i) // No_of_periods
                        if (Timetable[slot + i][class_idx] != 0 or
                                not main_teacher_list[slot + i][teacher_id]["available"] or
                                (slot // No_of_periods) != day or
                                (slot + i) in labs[lab_number] or
                                lab_number in lab_used_by_class_per_day[class_idx].get(day, set())):
                            can_assign = False
                            break
                    if can_assign:
                        subject_name = "Lab"
                        if class_idx in subject_map and teacher_id in subject_map[class_idx]:
                            for sub in subject_map[class_idx][teacher_id]:
                                if sub["type"] == "lab":
                                    subject_name = sub["name"]
                                    break
                        for i in range(consecutive_periods):
                            Timetable[slot + i][class_idx] = f"{subject_name} (Lab {lab_number})"
                            main_teacher_list[slot + i][teacher_id]["available"] = False
                            if teacher_id in class_to_teacher[class_idx]:
                                class_to_teacher[class_idx][teacher_id] -= 1
                            labs[lab_number].append(slot + i)
                            day = (slot + i) // No_of_periods
                            lab_used_by_class_per_day[class_idx].setdefault(day, set()).add(lab_number)
                        sessions_assigned += consecutive_periods
                    if sessions_assigned >= total_sessions:
                        break

    def find_empty():
        best_cell = (-1, -1)
        min_count = float("inf")
        rows = list(range(total_periods))
        random.shuffle(rows)
        for x in rows:
            for y in range(No_of_classes):
                if Timetable[x][y] == 0:
                    count = 0
                    active_ids = class_to_teacher[y]['__ids__']
                    for i in active_ids:
                        if class_to_teacher[y].get(i, 0) > 0 and main_teacher_list[x][i]["available"]:
                            count += 1
                    if count < min_count:
                        min_count = count
                        best_cell = (x, y)
                        if count == 0:
                            return best_cell
        return best_cell

    def subject_already_on_day(class_idx, slot, subject_name):
        day = slot // No_of_periods
        for s in range(day * No_of_periods, day * No_of_periods + No_of_periods):
            if Timetable[s][class_idx] == subject_name:
                return True
        return False

    def solve(depth=0):
        x, y = find_empty()
        if x == -1:
            return True
        priority = class_to_teacher[y]['__ids__'][:]
        random.shuffle(priority)
        for i in priority:
            if class_to_teacher[y].get(i, 0) > 0 and main_teacher_list[x][i]["available"]:
                t_name = teacher_list[i]["Name"]
                assigned_name = t_name
                sub_ptr = None
                if y in subject_map and i in subject_map[y]:
                    for sub in subject_map[y][i]:
                        if sub["type"] == "theory" and sub["hours"] > 0:
                            assigned_name = sub["name"]
                            sub_ptr = sub
                            break
                if assigned_name != "Free" and subject_already_on_day(y, x, assigned_name):
                    continue
                class_to_teacher[y][i] -= 1
                main_teacher_list[x][i]["available"] = False
                if sub_ptr:
                    sub_ptr["hours"] -= 1
                Timetable[x][y] = assigned_name
                if solve(depth + 1):
                    return True
                Timetable[x][y] = 0
                class_to_teacher[y][i] += 1
                main_teacher_list[x][i]["available"] = True
                if sub_ptr:
                    sub_ptr["hours"] += 1
        return False

    assign_lab_periods_randomly()

    # ── Pre-place sync groups ─────────────────────────────────────────────────
    # All members of a sync group must share the SAME K slot indices.
    # We pick K free slots where every member's teacher is available, stamp
    # the subject names, mark teachers busy, and deduct subject_map hours.
    if elective_bundles:
        for bundle in elective_bundles:
            bname   = bundle.get("name", "bundle")
            btype   = bundle.get("type", "split")
            k       = int(bundle.get("periodsPerWeek", bundle.get("periods_per_week", 1)))
            members = bundle.get("members", [])
            # Backward compat: build members from assignments dict if needed
            if not members:
                for ci_raw, subj in bundle.get("assignments", {}).items():
                    members.append({"classIdx": int(ci_raw), "subject": subj, "teacherId": None})
            if not members or k < 1:
                continue

            # Resolve teacher ids for each member from subject_map
            resolved = []
            for m in members:
                cidx      = int(m.get("classIdx", -1))
                subj_name = (m.get("subject") or "").strip()
                tid_hint  = m.get("teacherId")
                if cidx < 0 or cidx >= No_of_classes or not subj_name:
                    continue
                # Find teacher id in subject_map
                tid = None
                if cidx in subject_map:
                    for t_id, subs in subject_map[cidx].items():
                        for sub in subs:
                            if sub["name"].lower().strip() == subj_name.lower().strip() and sub["type"] == "theory":
                                tid = t_id
                                break
                        if tid is not None:
                            break
                resolved.append({"cidx": cidx, "subj": subj_name, "tid": tid})

            if not resolved:
                logging.warning(f"Sync group '{bname}': no resolvable members")
                continue

            def slot_ok_for_all(slot):
                for r in resolved:
                    if Timetable[slot][r["cidx"]] != 0:
                        return False
                    tid = r["tid"]
                    if tid is not None:
                        if not main_teacher_list[slot].get(tid, {}).get("available", True):
                            return False
                return True

            candidates = [s for s in range(total_periods) if slot_ok_for_all(s)]
            random.shuffle(candidates)

            # Prefer one slot per day (no-repeat-same-day)
            chosen   = []
            used_days = set()
            for slot in candidates:
                day = slot // No_of_periods
                if day not in used_days:
                    chosen.append(slot); used_days.add(day)
                if len(chosen) == k:
                    break
            if len(chosen) < k:
                chosen = candidates[:k]

            if len(chosen) < k:
                logging.warning(f"Sync group '{bname}': only found {len(chosen)}/{k} slots — skipping")
                continue

            for slot in chosen:
                for r in resolved:
                    Timetable[slot][r["cidx"]] = r["subj"]
                    tid = r["tid"]
                    if tid is not None and tid in main_teacher_list[slot]:
                        main_teacher_list[slot][tid]["available"] = False
                    if tid is not None and tid in class_to_teacher[r["cidx"]]:
                        class_to_teacher[r["cidx"]][tid] = max(0, class_to_teacher[r["cidx"]][tid] - 1)
                    if r["cidx"] in subject_map and tid is not None and tid in subject_map[r["cidx"]]:
                        for sub in subject_map[r["cidx"]][tid]:
                            if sub["name"].lower().strip() == r["subj"].lower().strip() and sub["hours"] > 0:
                                sub["hours"] -= 1
                                break

            logging.info(f"Sync group '{bname}' ({btype}): placed at slots {chosen}")

    if solve():
        return Timetable
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def generate_timetable(
    No_of_classes, No_of_days_in_week, No_of_periods,
    teacher_list, class_teacher_periods, lab_teacher_periods,
    subject_map, fixed_periods=None, teacher_unavailability=None,
    elective_bundles=None
):
    if ORTOOLS_AVAILABLE:
        return generate_timetable_ortools(
            No_of_classes, No_of_days_in_week, No_of_periods,
            teacher_list, class_teacher_periods, lab_teacher_periods,
            subject_map, fixed_periods, teacher_unavailability,
            elective_bundles=elective_bundles
        )
    return generate_timetable_backtrack(
        No_of_classes, No_of_days_in_week, No_of_periods,
        teacher_list, class_teacher_periods, lab_teacher_periods,
        subject_map, fixed_periods, teacher_unavailability,
        elective_bundles=elective_bundles
    )


def generate_timetable_with_retry(
    No_of_classes, No_of_days_in_week, No_of_periods,
    teacher_list, class_teacher_periods, lab_teacher_periods,
    subject_map, fixed_periods=None, teacher_unavailability=None,
    max_attempts=10, elective_bundles=None
):
    if ORTOOLS_AVAILABLE:
        logging.info("OR-Tools active — single attempt with 60s limit")
        return generate_timetable_ortools(
            No_of_classes, No_of_days_in_week, No_of_periods,
            copy.deepcopy(teacher_list),
            copy.deepcopy(class_teacher_periods),
            copy.deepcopy(lab_teacher_periods),
            copy.deepcopy(subject_map),
            fixed_periods, teacher_unavailability,
            time_limit_seconds=60,
            elective_bundles=elective_bundles
        )
    for attempt in range(1, max_attempts + 1):
        logging.info(f"Backtrack attempt {attempt}/{max_attempts}")
        result = generate_timetable_backtrack(
            No_of_classes, No_of_days_in_week, No_of_periods,
            copy.deepcopy(teacher_list),
            copy.deepcopy(class_teacher_periods),
            copy.deepcopy(lab_teacher_periods),
            copy.deepcopy(subject_map),
            fixed_periods, teacher_unavailability,
            elective_bundles=elective_bundles
        )
        if result is not None:
            logging.info(f"Solved on attempt {attempt}")
            return result
        logging.warning(f"Attempt {attempt} failed")
    logging.error("All attempts exhausted")
    return None