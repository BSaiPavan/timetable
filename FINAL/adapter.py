def build_solver_inputs_from_classes(CONFIG, days, periods):
    class_names = list(CONFIG["classes"].keys())
    No_of_classes = len(class_names)
    total_slots_per_class = days * periods # e.g., 6 * 6 = 36

    teacher_ids = {}
    teacher_list = {}
    next_tid = 0

    class_teacher_periods = {}
    lab_teacher_periods = {}
    subject_map = {}
    
    # 1. Map Real Teachers from UI
    for cidx, cname in enumerate(class_names):
        class_teacher_periods[cidx] = {}
        total_assigned_hours = 0
        
        # Changed to 0 as requested - filler will take ALL remaining slots
        fixed_count = 0 

        for item in CONFIG["classes"][cname]:
            tname = item["teacher"]
            hours = int(item["hours"])
            total_assigned_hours += hours

            if tname not in teacher_ids:
                teacher_ids[tname] = next_tid
                teacher_list[next_tid] = {"Name": tname, "available": True}
                next_tid += 1

            tid = teacher_ids[tname]
            class_teacher_periods[cidx][tid] = hours
            subject_map[(cidx, tid)] = item["subject"]

            if item["type"] == "lab":
                lab_teacher_periods.setdefault(cidx, {})
                lab_teacher_periods[cidx][tid] = [
                    hours,
                    int(item["continuous"]),
                    int(item["lab_no"])
                ]
        
        # 2. Add the UNIQUE 'f' Filler Teacher for THIS class
        f_name = f"f{cidx + 1}"
        teacher_list[next_tid] = {"Name": f_name, "available": True}
        
        # Calculate remaining credits: (Total Slots - Theory - Labs)
        free_credits = total_slots_per_class - total_assigned_hours - fixed_count
        
        # Safety check: ensure we don't pass negative credits to the solver
        if free_credits > 0:
            class_teacher_periods[cidx][next_tid] = free_credits
            subject_map[(cidx, next_tid)] = "Free"
        elif free_credits < 0:
            # This means the user assigned more hours than the week allows
            print(f"Warning: Class {cname} is over-scheduled by {abs(free_credits)} hours!")
            
        next_tid += 1

    return (
        No_of_classes,
        teacher_list,
        class_teacher_periods,
        lab_teacher_periods,
        subject_map
    )

def build_final_inputs(CONFIG, days, periods, fixed_slots):
    # 1. Get base inputs
    No_of_classes, teacher_list, class_teacher_periods, lab_teacher_periods, subject_map = build_solver_inputs_from_classes(CONFIG, days, periods)

    # 2. Process Fixed Slots
    # fixed_slots looks like: {"0-1": {"label": "Lunch", "teacher_id": "None"}}
    
    # We need to track how many fixed periods are assigned per class
    # Since they apply to the whole school usually, it's a global count
    total_fixed_per_week = len(fixed_slots)

    for slot_id, info in fixed_slots.items():
        t_id_str = info.get('teacher_id')
        
        if t_id_str != "None":
            t_id = int(t_id_str)
            # If this is a teacher's fixed period, remove 1 credit 
            # from their theory load so they don't get over-assigned
            for c_idx in range(No_of_classes):
                if t_id in class_teacher_periods[c_idx]:
                    if class_teacher_periods[c_idx][t_id] > 0:
                        class_teacher_periods[c_idx][t_id] -= 1

    # 3. Recalculate 'f' Fillers
    # The filler 'f' teacher for each class must now account for these fixed slots
    # New filler = Total Slots - Theory - Labs - Total Fixed
    for cidx in range(No_of_classes):
        total_assigned = sum(class_teacher_periods[cidx].values()) + \
                         sum(val[0] for val in lab_teacher_periods.get(cidx, {}).values())
        
        # This is the teacher ID of the filler 'f' teacher (added at the end of the list)
        # In your adapter, it's the last ID added for that class.
        # We need to find the ID where Name starts with 'f'
        for t_id, t_info in teacher_list.items():
            if t_info['Name'] == f"f{cidx + 1}":
                new_free = (days * periods) - total_assigned - total_fixed_per_week
                class_teacher_periods[cidx][t_id] = max(0, new_free)

    return No_of_classes, teacher_list, class_teacher_periods, lab_teacher_periods, subject_map