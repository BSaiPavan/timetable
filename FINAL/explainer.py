import random  # Used to shuffle selections to create variety in the generated timetable
import copy    # Used to create deep copies of teacher availability states
import csv     # Imported for data handling (though not used in this specific snippet)
import logging # Used to track the solver's progress and errors for debugging
import os      # Used to handle file paths for the log file

# Set the path for the debug log in the same directory as the script
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solver_debug.log')
# Configure logging to overwrite ('w') the file every time the solver runs
logging.basicConfig(
    filename=log_path,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)

def generate_timetable(
    No_of_classes,          # Total number of class sections
    No_of_days_in_week,     # Working days per week
    No_of_periods,          # Number of periods per day
    teacher_list,           # Dictionary containing all teacher details {id: info}
    class_teacher_periods,  # Mapping of teacher workloads per class
    lab_teacher_periods,    # Mapping of lab sessions and durations
    subject_map,            # Mapping of (class, teacher) pairs to subject names
    fixed_periods=None      # Optional pre-defined slots that cannot be moved
):
    # ---------------- BASIC CONFIG ----------------
    # Calculate the total number of available slots in the week
    total_periods = No_of_days_in_week * No_of_periods
    
    # Find the highest teacher ID to ensure the state list is large enough to avoid IndexErrors
    max_t_id = max(teacher_list.keys()) if teacher_list else 0
    No_of_teachers = max_t_id + 1

    # ---------------- TIMETABLE MATRIX ----------------
    # Initialize the main timetable: Rows are time slots, Columns are classes
    Timetable = [[0 for _ in range(No_of_classes)] for _ in range(total_periods)]

    # ---------------- TEACHER STATE ----------------
    # Create a unique copy of the teacher availability list for every single time slot
    main_teacher_list = [
        copy.deepcopy(teacher_list)
        for _ in range(total_periods)
    ]

    # ---------------- 1 & 4. COORDINATE MAPPING & PRE-FILLING ----------------
    # Track how many periods for a teacher are already occupied by 'Fixed' slots
    teacher_fixed_workload = {c: {t: 0 for t in teacher_list} for c in range(No_of_classes)}
    class_fixed_total = [0] * No_of_classes

    # Process manually fixed slots (e.g., Assembly, Lunch, or specific teacher requests)
    if fixed_periods:
        for cls_idx_str, slots in fixed_periods.items():
            try:
                cls_idx = int(cls_idx_str) # Ensure the class index is an integer
            except ValueError:
                continue
            
            for slot_str, info in slots.items():
                # Skip slots that don't have a label assigned
                if not info.get('label') or info.get('label').strip() == "":
                    continue
                
                try:
                    # Parse slot index: handles "Day-Period" format or a flat integer index
                    if '-' in slot_str:
                        d, p = map(int, slot_str.split('-'))
                        flat_slot = d * No_of_periods + p
                    else:
                        flat_slot = int(slot_str)
                except (ValueError, IndexError):
                    continue

                # Place the fixed label into the timetable and update teacher availability
                if flat_slot < total_periods and cls_idx < No_of_classes:
                    Timetable[flat_slot][cls_idx] = info['label']
                    class_fixed_total[cls_idx] += 1
                    
                    t_id_raw = info.get('teacher_id')
                    if t_id_raw is not None and str(t_id_raw).isdigit():
                        t_id = int(t_id_raw)
                        # Mark the specific teacher as 'unavailable' for this specific time slot
                        if t_id in main_teacher_list[flat_slot]:
                            main_teacher_list[flat_slot][t_id]["available"] = False
                            # Log that one required period for this teacher/class is already satisfied
                            teacher_fixed_workload[cls_idx][t_id] = teacher_fixed_workload[cls_idx].get(t_id, 0) + 1

    # ---------------- CREDIT MATRIX (WORKLOAD MAPPING) ----------------
    class_to_teacher = []
    for class_idx in range(No_of_classes):
        # Create a list where index corresponds to teacher ID and value is periods remaining
        teacher_part = [0] * No_of_teachers
        active_teacher_ids = list(teacher_list.keys())
        
        # Calculate theory workload by subtracting fixed periods from the total requested
        for t_idx, periods in class_teacher_periods.get(class_idx, {}).items():
            fixed_already = teacher_fixed_workload[class_idx].get(t_idx, 0)
            teacher_part[t_idx] = max(0, periods - fixed_already)

        # Store the remaining workload and a helper list of active IDs for faster iteration
        row = teacher_part.copy()
        row.append(active_teacher_ids) 
        class_to_teacher.append(row)

    # ---------------- LAB HELPERS ----------------
    labs = {} # Tracks which lab rooms are occupied at what times
    lab_used_by_class_per_day = {idx: {} for idx in range(No_of_classes)} # Prevents multiple labs for a class on one day

    def assign_lab_periods_randomly():
        """Attempts to place multi-period lab sessions before general theory classes."""
        for class_idx, teacher_periods in lab_teacher_periods.items():
            for teacher_id, (total_sessions, consecutive_periods, lab_number) in teacher_periods.items():
                labs.setdefault(lab_number, [])
                # Find slots where both the class and the teacher are currently free
                available_slots = [
                    i for i in range(total_periods)
                    if Timetable[i][class_idx] == 0
                    and main_teacher_list[i][teacher_id]["available"]
                ]
                random.shuffle(available_slots)
                sessions_assigned = 0
                for slot in available_slots:
                    # Check if the block of periods fits within the same day
                    if slot + consecutive_periods > total_periods: continue
                    can_assign = True
                    for i in range(consecutive_periods):
                        day = (slot + i) // No_of_periods
                        # Constraints: slot must be empty, teacher free, same day, lab room free, class doesn't have lab yet
                        if (Timetable[slot + i][class_idx] != 0 or
                            not main_teacher_list[slot + i][teacher_id]["available"] or
                            (slot // No_of_periods) != day or
                            (slot + i) in labs[lab_number] or
                            lab_number in lab_used_by_class_per_day[class_idx].get(day, set())):
                            can_assign = False
                            break
                    # If all conditions are met, assign the lab block
                    if can_assign:
                        for i in range(consecutive_periods):
                            subject_name = subject_map.get((class_idx, teacher_id), "Lab")
                            Timetable[slot + i][class_idx] = f"{subject_name} (Lab {lab_number})"
                            main_teacher_list[slot + i][teacher_id]["available"] = False
                            class_to_teacher[class_idx][teacher_id] -= 1
                            labs[lab_number].append(slot + i)
                            day = (slot + i) // No_of_periods
                            lab_used_by_class_per_day[class_idx].setdefault(day, set()).add(lab_number)
                        #sessions_assigned += 1
                    #if sessions_assigned == total_sessions: break
                    sessions_assigned += consecutive_periods
                    if sessions_assigned >= total_sessions: break

    # ---------------- SOLVER CORE ----------------
    def find_empty():
        """Heuristic to find the next empty slot with the fewest possible teacher options (MRV)."""
        best_cell = (-1, -1)
        min_teachers = float("inf")
        rows = list(range(total_periods))
        random.shuffle(rows) # Randomize order to avoid identical timetables
        for x in rows:
            for y in range(No_of_classes):
                if Timetable[x][y] == 0:
                    count = 0
                    active_ids = class_to_teacher[y][-1]
                    # Check how many teachers are available for this specific empty slot
                    for i in active_ids:
                        if class_to_teacher[y][i] > 0 and main_teacher_list[x][i]["available"]:
                            count += 1
                    # If a slot has zero possibilities, we must backtrack immediately
                    if count == 0: return x, y
                    # Prioritize slots with the fewest remaining teacher choices
                    if count < min_teachers:
                        min_teachers = count
                        best_cell = (x, y)
        return best_cell

    def solve():
        """Recursive backtracking function to fill the remaining slots."""
        x, y = find_empty()
        if x == -1: return True # Base Case: All slots are filled successfully
        
        priority = class_to_teacher[y][-1][:] # Copy the list of potential teachers
        random.shuffle(priority) # Shuffling ensures a unique result each time
        for i in priority:
            # Check if teacher still owes periods to this class and is free at this time
            if class_to_teacher[y][i] > 0 and main_teacher_list[x][i]["available"]:
                t_name = teacher_list[i]["Name"]
                # Place teacher (Forward move)
                class_to_teacher[y][i] -= 1
                main_teacher_list[x][i]["available"] = False
                Timetable[x][y] = subject_map.get((y, i), t_name)
                
                # Recursive call: Try to solve the next slot
                if solve(): return True
                
                # If subsequent moves failed, undo the current placement (Backtrack)
                Timetable[x][y] = 0
                class_to_teacher[y][i] += 1
                main_teacher_list[x][i]["available"] = True
        return False # No valid teacher could fit in this slot

    # Start the process: Place labs first, then use backtracking to fill theory classes
    assign_lab_periods_randomly()
    # This sends the data to your solver_debug.log file
    logging.debug("--- Timetable State After Labs ---")
    for row in Timetable:
        logging.debug(row)
    if solve():
        return Timetable # Return the completed 2D list
    return None # Return None if no valid solution is mathematically possible