import random  # Import random for shuffling and non-deterministic slot picking
import copy    # Import copy to create deep copies of nested teacher dictionaries
import csv     # Import csv (though not used in this specific snippet)
import logging # Import logging for debugging the backtracking process
import os      # Import os for file path handling

# Configure logging to overwrite the file each time you run the solver
# This sets the path to 'solver_debug.log' in the same directory as the script
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solver_debug.log')
logging.basicConfig(
    filename=log_path,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w' # 'w' ensures the log is refreshed every run
)

def generate_timetable(
    No_of_classes,          # Number of unique classes/divisions
    No_of_days_in_week,     # Working days (e.g., 5 or 6)
    No_of_periods,          # Periods per day
    teacher_list,           # Dictionary of teacher metadata and base availability
    class_teacher_periods,  # Map of (class, teacher) to number of theory periods
    lab_teacher_periods,    # Map of (class, teacher) to lab session requirements
    subject_map,            # Map of (class, teacher) to the specific Subject Name
    fixed_periods=None      # Optional: Hardcoded slots like Lunch or Library
):
   
    # ---------------- BASIC CONFIG ----------------
    # Calculate the total number of slots available in the week (e.g., 5 days * 8 periods = 40)
    total_periods = No_of_days_in_week * No_of_periods

    # ---------------- TIMETABLE MATRIX ----------------
    Timetable = [] # Initialize the main 2D grid
    arr = [0] * No_of_classes # Create a row representing one period across all classes
    for _ in range(total_periods):
        Timetable.append(arr.copy()) # Fill timetable with zeros (0 indicates an empty slot)

    # ---------------- TEACHER STATE ----------------
    # Create a unique availability state for every teacher for every single time slot
    main_teacher_list = [
        copy.deepcopy(teacher_list)
        for _ in range(total_periods)
    ]

    # ---------------- 1 & 4. COORDINATE MAPPING & PRE-FILLING ----------------
    # Track periods already taught by teachers in fixed slots to avoid double-counting workload
    teacher_fixed_workload = {c: {t: 0 for t in teacher_list} for c in range(No_of_classes)}
    # Track total fixed slots per class to calculate remaining "Free" periods correctly
    class_fixed_total = [0] * No_of_classes

    if fixed_periods:
        # fixed_periods format: { "ClassIdx": { "Day-Period": {"label": "Lunch", "teacher_id": "0"} } }
        for cls_idx_str, slots in fixed_periods.items():
            try:
                cls_idx = int(cls_idx_str) # Convert class index key to integer
            except ValueError:
                continue # Skip if class index is invalid
            
            for slot_str, info in slots.items():
                # Ignore fixed slots that don't have a label (e.g., empty placeholders)
                if not info.get('label') or info.get('label').strip() == "":
                    continue
                
                try:
                    # Convert "Day-Period" string (e.g., "0-4") to a flat index in the Timetable
                    d, p = map(int, slot_str.split('-'))
                    flat_slot = d * No_of_periods + p
                except (ValueError, IndexError):
                    continue

                # 1. Pre-fill the Timetable matrix with the label (e.g., "LUNCH")
                Timetable[flat_slot][cls_idx] = info['label']
                class_fixed_total[cls_idx] += 1
                
                # 2. Handle Teacher Blocking (prevent teachers in fixed slots from being used elsewhere)
                t_id_raw = info.get('teacher_id', "None")
                
                # Check if a valid teacher ID is associated with this fixed slot
                if t_id_raw is not None and str(t_id_raw).isdigit():
                    t_id = int(t_id_raw)
                    
                    # Ensure the teacher exists in the master list
                    if t_id in main_teacher_list[flat_slot]:
                        # Set teacher as unavailable for this specific time slot globally
                        main_teacher_list[flat_slot][t_id]["available"] = False
                        
                        # Increment workload so the solver knows this teacher already fulfilled a period
                        teacher_fixed_workload[cls_idx][t_id] += 1

    No_of_teachers = len(teacher_list)

    # ---------------- LAB HELPERS ----------------
    # Track which physical labs are occupied at which time slots
    labs = {}
    for cls, labs_info in lab_teacher_periods.items():
        for _, (_, _, lab_no) in labs_info.items():
            labs.setdefault(lab_no, []) # Initialize empty list for each lab number

    # Track which class is using which lab on a specific day (to avoid 2 labs for 1 class in 1 day)
    lab_used_by_class_per_day = {
        class_idx: {}
        for class_idx in range(No_of_classes)
    }

    # Helper function to clear daily usage tracking (used during initialization)
    def reset_lab_day_usage():
        for cls in lab_used_by_class_per_day:
            lab_used_by_class_per_day[cls].clear()

    # ---------------- LAB ASSIGNMENT ----------------
    def assign_lab_periods_randomly():
        # Iterate through classes that have lab requirements
        for class_idx, teacher_periods in lab_teacher_periods.items():
            # Get teacher ID and lab requirements (sessions, length, lab room number)
            for teacher_id, (total_sessions, consecutive_periods, lab_number) in teacher_periods.items():
                # Find slots where both the class and teacher are currently free
                available_slots = [
                    i for i in range(total_periods)
                    if Timetable[i][class_idx] == 0
                    and main_teacher_list[i][teacher_id]["available"]
                ]
                random.shuffle(available_slots) # Randomize start slots for variety
                sessions_assigned = 0
                for slot in available_slots:
                    # Check if the consecutive block fits within the week's limit
                    if slot + consecutive_periods > total_periods:
                        continue
                    can_assign = True
                    # Check constraints for every period in the consecutive block
                    for i in range(consecutive_periods):
                        day = (slot + i) // No_of_periods
                        if (
                            Timetable[slot + i][class_idx] != 0 or # Class must be free
                            not main_teacher_list[slot + i][teacher_id]["available"] or # Teacher must be free
                            (slot // No_of_periods) != ((slot + i) // No_of_periods) or # Must stay within the same day
                            (slot + i) in labs[lab_number] or # Lab room must be empty
                            lab_number in lab_used_by_class_per_day[class_idx].get(day, set()) # Class already had this lab today
                        ):
                            can_assign = False
                            break
                    # If all periods in block are valid, assign them
                    if can_assign:
                        for i in range(consecutive_periods):
                            subject_name = subject_map.get((class_idx, teacher_id), "Lab")
                            Timetable[slot + i][class_idx] = f"{subject_name} (Lab {lab_number})"
                            main_teacher_list[slot + i][teacher_id]["available"] = False
                            class_to_teacher[class_idx][teacher_id] -= 1 # Deduct from remaining workload
                            labs[lab_number].append(slot + i) # Mark lab room as occupied
                            day = (slot + i) // No_of_periods
                            lab_used_by_class_per_day.setdefault(class_idx, {}).setdefault(day, set()).add(lab_number)
                        sessions_assigned += 1
                    # Stop once we've assigned all required sessions for this lab
                    if sessions_assigned == total_sessions:
                        break

    # ---------------- 3. CREDIT MATRIX (DYNAMIC FREE CALC) ----------------
    # Identify "Free" teachers (placeholders) used to fill empty gaps in the schedule
    FREE_TEACHERS = [
        t_id for t_id, info in teacher_list.items()
        if info["Name"].startswith("f")
    ]

    class_to_teacher = [] # Represents the "Workload Matrix"
    for class_idx in range(No_of_classes):
        teacher_part = [0] * No_of_teachers # Workload for each teacher for this class
        assigned_workload = 0
        for t_idx, periods in class_teacher_periods.get(class_idx, {}).items():
            # Calculate remaining theory periods by subtracting those already in fixed slots
            fixed_already = teacher_fixed_workload[class_idx].get(t_idx, 0)
            net_needed = max(0, periods - fixed_already)
            teacher_part[t_idx] = net_needed
            assigned_workload += net_needed

        # Factor in Lab periods into the total assigned workload
        assigned_labs = 0
        if class_idx in lab_teacher_periods:
            for t_id, info in lab_teacher_periods[class_idx].items():
                teacher_part[t_id] += info[0]
                assigned_labs += info[0]

        # Calculate how many "Free Periods" remain after Theory, Labs, and Fixed slots
        free_count = total_periods - assigned_workload - assigned_labs - class_fixed_total[class_idx]
        if free_count < 0:
            free_count = 0 # Safety floor

        # Assign remaining free slots to a designated "Free Teacher"
        free_teacher_index = FREE_TEACHERS[class_idx % len(FREE_TEACHERS)]
        teacher_part[free_teacher_index] = free_count

        # Create a priority list for the solver and append it to the workload row
        priority_list = list(range(No_of_teachers))
        row = teacher_part.copy()
        row.append(priority_list)
        class_to_teacher.append(row)

    # ---------------- MRV & BACKTRACKING ----------------
    def find_empty():
        # Minimum Remaining Values (MRV) heuristic: find the cell most difficult to fill
        best_cell = (-1, -1)
        min_teachers = float("inf")
        rows = list(range(len(Timetable)))
        random.shuffle(rows) # Randomize row selection to prevent repetitive patterns
        for x in rows:
            for y in range(No_of_classes):
                if Timetable[x][y] != 0: # Skip if already filled
                    continue
                count = 0
                # Count how many teachers are available for this specific slot and class
                for i in range(No_of_teachers):
                    if class_to_teacher[y][i] > 0 and main_teacher_list[x][i]["available"]:
                        count += 1
                if count == 0: # Constraint violation: no teachers can fill this slot
                    return x, y
                if count < min_teachers: # Track the slot with the fewest options
                    min_teachers = count
                    best_cell = (x, y)
        return best_cell

    def solve():
        # Recursive backtracking function to fill the timetable
        x, y = find_empty()
        if x == -1: # Base case: No empty slots left, timetable is complete
            logging.info("Solution found! All slots filled.")
            return True
        
        # Get the priority list of teachers and shuffle for variation
        priority = class_to_teacher[y][-1][:]
        random.shuffle(priority)
        
        for i in priority:
            # Check if teacher has remaining workload and is available at this time
            if class_to_teacher[y][i] > 0 and main_teacher_list[x][i]["available"]:
                t_name = teacher_list[i]["Name"]
                logging.debug(f"Slot({x}) Class({y}): Trying Teacher {t_name}") 
                
                # RECURSIVE STEP: Try assigning this teacher
                class_to_teacher[y][i] -= 1
                main_teacher_list[x][i]["available"] = False
                Timetable[x][y] = subject_map.get((y, i), teacher_list[i]["Name"])
                
                if solve(): # Move to next empty slot
                    return True
                
                # BACKTRACK: If assigning this teacher led to no solution, undo the assignment
                logging.warning(f"Slot({x}) Class({y}): Backtracking from {t_name}")
                Timetable[x][y] = 0
                class_to_teacher[y][i] += 1
                main_teacher_list[x][i]["available"] = True
        return False # Trigger backtracking in the caller

    # Initialize lab constraints and run the randomized lab assigner
    reset_lab_day_usage()
    assign_lab_periods_randomly()

    # Start the backtracking solver for the remaining theory/free slots
    if solve():
        return Timetable # Return the successful 2D array

    return None # Return None if no valid timetable could be generated