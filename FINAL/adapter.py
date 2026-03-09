def build_solver_inputs_from_classes(CONFIG, days, periods):
    class_names = list(CONFIG["classes"].keys())
    No_of_classes = len(class_names)
    total_slots_per_class = days * periods

    teacher_list = {}
    class_teacher_periods = {}
    lab_teacher_periods = {}
    subject_map = {}

    for cidx, cname in enumerate(class_names):
        class_teacher_periods[cidx] = {}
        total_assigned_hours = 0

        for item in CONFIG["classes"][cname]:
            tid   = int(item.get("teacher_id", 99))
            tname = item.get("teacher", "Unknown")
            hours = int(item.get("hours", 0))
            total_assigned_hours += hours

            if tid not in teacher_list:
                teacher_list[tid] = {"Name": tname, "available": True}

            if cidx not in subject_map:
                subject_map[cidx] = {}
            if tid not in subject_map[cidx]:
                subject_map[cidx][tid] = []

            subject_map[cidx][tid].append({
                "name": item.get("subject", "Subject"),
                "hours": hours,
                "type": str(item.get("type")).lower().strip()
            })

            if str(item.get("type")).lower() == "lab":
                lab_teacher_periods.setdefault(cidx, {})
                lab_teacher_periods[cidx][tid] = [
                    hours,
                    int(item.get("continuous", 2)),
                    int(item.get("lab_no", 1))
                ]
                if tid not in class_teacher_periods[cidx]:
                    class_teacher_periods[cidx][tid] = 0
            else:
                class_teacher_periods[cidx][tid] = class_teacher_periods[cidx].get(tid, 0) + hours

        # Free-period filler teacher for this class
        f_id = 1000 + cidx
        teacher_list[f_id] = {"Name": f"f{cidx + 1}", "available": True}
        free_credits = total_slots_per_class - total_assigned_hours
        class_teacher_periods[cidx][f_id] = max(0, free_credits)
        subject_map[cidx][f_id] = [{"name": "Free", "hours": max(0, free_credits), "type": "theory"}]

    return No_of_classes, teacher_list, class_teacher_periods, lab_teacher_periods, subject_map


def build_final_inputs(CONFIG, days, periods, fixed_slots_data):
    """
    Build solver inputs and pre-deduct workload for every fixed slot.

    Fixed slot types:
      • Subject slot  – teacher_id is a real int string, label is the subject name
      • Free slot     – teacher_id == '__free__', label == 'Free'
        → deducted from the filler teacher (id = 1000 + cls_idx)

    The solver will stamp these slots directly into the timetable and mark
    the teacher unavailable for that slot.  It must NOT re-deduct hours.
    The deduction happens here ONLY, once.
    """
    No_of_classes, teacher_list, class_theory, lab_periods, subject_map = \
        build_solver_inputs_from_classes(CONFIG, days, periods)

    print("--- Adapter: Reducing workload for fixed slots ---")

    for cls_idx_str, slots in fixed_slots_data.items():
        try:
            cls_idx = int(cls_idx_str)
        except ValueError:
            continue

        for slot_id, info in slots.items():
            label     = (info.get('label') or '').strip()
            t_id_raw  = info.get('teacher_id', '')
            is_free   = info.get('is_free', False) or str(t_id_raw) == '__free__'
            is_event  = info.get('is_event', False) or str(t_id_raw) == '__event__'

            # Nothing to deduct for un-set slots
            if not label or str(t_id_raw) == '__none__':
                continue

            # ── EVENT: no teacher, no credits touched — just counts as a fixed slot ─
            if is_event:
                print(f"  Event slot '{label}' fixed for Class {cls_idx} at {slot_id} — no credits deducted")
                continue

            # ── FREE PERIOD: deduct from the filler teacher ─────────────────
            if is_free or label.lower() == 'free':
                f_id = 1000 + cls_idx
                if cls_idx in class_theory and f_id in class_theory[cls_idx]:
                    class_theory[cls_idx][f_id] = max(0, class_theory[cls_idx][f_id] - 1)
                if cls_idx in subject_map and f_id in subject_map[cls_idx]:
                    for sub in subject_map[cls_idx][f_id]:
                        if sub["hours"] > 0:
                            sub["hours"] -= 1
                            break
                print(f"  Free slot fixed for Class {cls_idx} at {slot_id}")
                continue

            # ── SUBJECT PERIOD: deduct from the real teacher ────────────────
            if not str(t_id_raw).lstrip('-').isdigit():
                print(f"  WARNING: Skipping slot {slot_id} for Class {cls_idx} — bad teacher_id '{t_id_raw}'")
                continue

            t_id = int(t_id_raw)

            # 1. Reduce subject_map hours (used by solver to pick subject names)
            found = False
            if cls_idx in subject_map and t_id in subject_map[cls_idx]:
                for sub in subject_map[cls_idx][t_id]:
                    if sub["name"].lower().strip() == label.lower().strip() and sub["hours"] > 0:
                        sub["hours"] -= 1
                        found = True
                        print(f"  Reduced '{label}' for Class {cls_idx}, Teacher {t_id}. Remaining: {sub['hours']}")
                        break

            if not found:
                print(f"  WARNING: '{label}' not found in subject_map for Class {cls_idx}, Teacher {t_id}")

            # 2. Reduce theory or lab workload counter
            if "lab" in label.lower():
                if cls_idx in lab_periods and t_id in lab_periods[cls_idx]:
                    lab_periods[cls_idx][t_id][0] = max(0, lab_periods[cls_idx][t_id][0] - 1)
            else:
                if cls_idx in class_theory and t_id in class_theory[cls_idx]:
                    class_theory[cls_idx][t_id] = max(0, class_theory[cls_idx][t_id] - 1)

    # ── RE-BALANCE FREE FILLER after all fixed slots are deducted ───────────
    for cls_idx in range(No_of_classes):
        f_id = 1000 + cls_idx
        if cls_idx not in class_theory or f_id not in class_theory[cls_idx]:
            continue

        total_slots  = days * periods
        rem_theory   = sum(v for k, v in class_theory[cls_idx].items() if k != f_id)
        rem_lab      = sum(v[0] for v in lab_periods.get(cls_idx, {}).values())

        # Count ALL fixed slots (both subject and free)
        cls_fixed_count = 0
        for slot_info in fixed_slots_data.get(str(cls_idx), {}).values():
            t_raw = str(slot_info.get('teacher_id', '__none__'))
            lbl   = (slot_info.get('label') or '').strip()
            if t_raw != '__none__' and lbl:
                cls_fixed_count += 1

        new_free = total_slots - (rem_theory + rem_lab + cls_fixed_count)
        class_theory[cls_idx][f_id] = max(0, new_free)
        if cls_idx in subject_map and f_id in subject_map[cls_idx]:
            subject_map[cls_idx][f_id][0]["hours"] = max(0, new_free)

        print(f"  Class {cls_idx}: rem_theory={rem_theory}, rem_lab={rem_lab}, "
              f"fixed={cls_fixed_count}, new_free={new_free}")

    return No_of_classes, teacher_list, class_theory, lab_periods, subject_map