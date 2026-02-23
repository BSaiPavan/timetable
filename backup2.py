import random
import copy
# Used for shuffling teacher priority order randomly
import sys

log_file = open("timetable_debug.log", "w", encoding="utf-8")
sys.stdout = log_file


# ---------------- BASIC CONFIG ----------------

No_of_classes = 8
# Number of classes (columns in timetable)

No_of_teachers = 0
# Placeholder; actual value set after teacher_list creation

No_of_days_in_week = 6
# Working days per week

No_of_periods = 6
# Periods per day

total_periods = No_of_days_in_week * No_of_periods
# Total weekly periods per class (36)


# ---------------- TIMETABLE MATRIX ----------------

Timetable = []
# 2D matrix: rows = periods (36), columns = classes (8)

arr = []
# Temporary row template

for i in range(No_of_classes):
    arr.append(0)
# Create one row with 8 empty slots

for j in range(total_periods):
    Timetable.append(arr.copy())
# Create 36 such rows (empty timetable)

for i in range(len(Timetable[0])):
    Timetable[18][i] = "foyer"
    Timetable[31][i] = "iic"
    Timetable[30][i] = "iic"
# ---------------- TEACHER DEFINITIONS ----------------

teacher_list = {
    0:  {"Name": "Aditi",  "available": True},
    1:  {"Name": "Sanjay", "available": True},
    2:  {"Name": "Kavita", "available": True},
    3:  {"Name": "Anil",   "available": True},
    4:  {"Name": "Pooja",  "available": True},
    5:  {"Name": "Manoj",  "available": True},
    6:  {"Name": "Priya",  "available": True},
    7:  {"Name": "Rohit",  "available": True},
    8:  {"Name": "Rahul",  "available": True},
    9:  {"Name": "Rajesh", "available": True},
    10: {"Name": "Ritu",   "available": True},
    11: {"Name": "Nisha",  "available": True},
    12: {"Name": "Meera",  "available": True},
    13: {"Name": "Sameer", "available": True},
    14: {"Name": "Sneha",  "available": True},
    15: {"Name": "Vikram", "available": True},
    16: {"Name": "Richa",  "available": True},

    # Free periods treated as teachers
    17: {"Name": "f1", "available": True},
    18: {"Name": "f2", "available": True},
    19: {"Name": "f3", "available": True},
    20: {"Name": "f4", "available": True},
    21: {"Name": "f5", "available": True},
    22: {"Name": "f6", "available": True},
    23: {"Name": "f7", "available": True},
    24: {"Name": "f8", "available": True}

}
'''
main_teacher_list={}
for day in range(No_of_days_in_week):
    main_teacher_list[day] = {}
    for period in range(No_of_periods):
        main_teacher_list[day][period] = copy.deepcopy(teacher_list)
'''
main_teacher_list = [
    copy.deepcopy(teacher_list)
    for _ in range(total_periods)
]

No_of_teachers = len(teacher_list)
# Total teachers including free placeholders


# ---------------- REQUIRED PERIODS PER CLASS ----------------

class_teacher_periods = {
    0: {0:5, 1:5, 2:5, 3:5, 4:4, 5:4},
    1: {0:5, 1:5, 2:5, 3:5, 4:4, 5:4},
    2: {6:5, 7:5, 15:5, 3:5, 8:5, 9:5},
    3: {6:5, 7:5, 10:5, 3:5, 8:5, 4:5},
    4: {6:5, 1:5, 2:5, 11:5, 14:5, 8:5},
    5: {6:5, 1:5, 2:5, 10:5, 14:5, 8:3, 9:3},
    6: {6:5, 7:5, 15:5, 11:5, 14:5, 8:3, 9:3},
    7: {16:5, 7:5, 15:5, 13:5, 14:5, 8:3, 9:3}
}
# Dict format: class → teacher → weekly periods


    # ---------------- CLASS → TEACHER MATRIX ----------------
class_to_teacher = [] 
# Each row: [remaining_periods_per_teacher..., priority_list]
FREE_TEACHERS = list(range(17, 25))
# One free-teacher per class (f1 for class 0, f2 for class 1, ...)

for class_idx in range(No_of_classes):

    teacher_part = [0] * No_of_teachers
    # Remaining periods for each teacher for this class

    assigned = 0
    # Count assigned real teacher periods

    for t_idx, periods in class_teacher_periods[class_idx].items():
        teacher_part[t_idx] = periods
        assigned += periods
    # Fill real teacher requirements

    free_count = total_periods - assigned
    # Remaining periods are free periods

    free_teacher_index = FREE_TEACHERS[class_idx]
    teacher_part[free_teacher_index] = free_count
    # Assign ALL free periods to ONE free-teacher (diagonal / identity style)


    priority_list = list(range(No_of_teachers))  # base order ONLY

    row = teacher_part.copy()
    row.append(priority_list)

    class_to_teacher.append(row)

# ---------------- HELPER FUNCTIONS ----------------
'''
def printmat(Timetable):
    for i in range(len(Timetable)):
        print(f"Row {i}: {Timetable[i]}")

def printmat(Timetable):
    for cls in range(No_of_classes):
        print(f"\n========== Class {cls} ==========")

        for day in range(No_of_days_in_week):
            start = day * No_of_periods
            end = start + No_of_periods

            day_periods = []
            for p in range(start, end):
                day_periods.append(Timetable[p][cls])

            print(f"Day {day + 1}: {day_periods}")
'''
def print_timetable_classwise(Timetable):
    # Day names (we will slice based on No_of_days_in_week)
    all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    days = all_days[:No_of_days_in_week]

    # Period header
    period_header = "        "  # spacing for day label
    for p in range(1, No_of_periods + 1):
        period_header += f"P{p:^6}"
    
    for cls in range(No_of_classes):
        print(f"\n========== Class {cls} ==========")
        print(period_header)

        for day_index, day_name in enumerate(days):
            start = day_index * No_of_periods
            end = start + No_of_periods

            print(f"{day_name:<9}", end="")

            for row in range(start, end):
                teacher = Timetable[row][cls]
                print(f"{teacher:^7}", end="")

            print() 
'''
def find_empty(x):
    # Find first empty timetable slot
    for i in range(len(x)):
        for j in range(len(x[0])):
            if x[i][j] == 0 or x[i][j] == "":
                print(f"returning {i},{j}")
                return i, j

    return -1, -1
'''
def find_empty(Timetable, class_to_teacher, Tl):
    """
    MRV (Minimum Remaining Values):
    Choose the empty (x, y) slot with the fewest legal teachers.
    """

    best_cell = (-1, -1)
    min_domain_size = float("inf")

    for x in range(len(Timetable)):          # period
        for y in range(len(Timetable[0])):   # class
            if Timetable[x][y] == 0 or Timetable[x][y] == "":

                legal_count = 0
                for i in range(No_of_teachers):
                    if class_to_teacher[y][i] > 0 and Tl[x][i]["available"]:
                        legal_count += 1

                # Dead-end: no legal teacher
                if legal_count == 0:
                    return x, y

                # MRV + random tie-break
                if (
                    legal_count < min_domain_size or
                    (legal_count == min_domain_size and random.random() < 0.5)
                ):
                    min_domain_size = legal_count
                    best_cell = (x, y)

    return best_cell
def shuffle_days(Timetable):
    days = []
    for d in range(No_of_days_in_week):
        start = d * No_of_periods
        end = start + No_of_periods
        days.append(Timetable[start:end])

    random.shuffle(days)
    Timetable[:] = [row for day in days for row in day]
'''def reset_available(Tl):
    # Reset teacher availability at new period
    for i in Tl:
        Tl[i]["available"] = True
'''



# ---------------- BACKTRACKING SOLVER ----------------

#prev_x = [-1]
# Tracks last period row to reset availability

def solve(Timetable, class_to_teacher, Tl):

    #x, y = find_empty(Timetable)
    x, y = find_empty(Timetable, class_to_teacher, Tl)
    #print(f"x is {x}, y is {y}")

    if x == -1:   # All slots filled successfully
        return True

    #priority_list = class_to_teacher[y][-1]
    #priority_list = class_to_teacher[y][-1].copy()
    priority_list = class_to_teacher[y][-1].copy()



    random.shuffle(priority_list)

    for i in priority_list:
        if class_to_teacher[y][i] > 0 and Tl[x][i]["available"]:
            class_to_teacher[y][i] -= 1
            Tl[x][i]["available"] = False

            Timetable[x][y] = Tl[x][i]["Name"]
            #print(f"in time table of {x},{y}, placed {Tl[x][i]['Name']}")

            if solve(Timetable, class_to_teacher, Tl):
                return True

            # BACKTRACK
            Timetable[x][y] = 0
            class_to_teacher[y][i] += 1
            Tl[x][i]["available"] = True

            #ptr = class_to_teacher[y][-1][1]
    # Backtrack
    
    return False





if solve(Timetable, class_to_teacher, main_teacher_list):
    #shuffle_days(Timetable)
    print_timetable_classwise(Timetable)
else:
    print("No Solution!")
#printmat(Timetable)

log_file.close()
