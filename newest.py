import random

# ---------------- CONFIG ----------------
No_of_classes = 7
No_of_teachers = 10
No_of_days_in_week = 6
No_of_periods = 6

TOTAL_SLOTS = No_of_days_in_week * No_of_periods

# ---------------- TIMETABLE ----------------
# timetable[period][class]
Timetable = [[0 for _ in range(No_of_classes)] for _ in range(TOTAL_SLOTS)]

# ---------------- TEACHERS ----------------
teacher_list = {
    0: {"Name": "t1",  "hours": 4},
    1: {"Name": "t2",  "hours": 4},
    2: {"Name": "t3",  "hours": 4},
    3: {"Name": "t4",  "hours": 4},
    4: {"Name": "t5",  "hours": 4},
    5: {"Name": "t6",  "hours": 4},
    6: {"Name": "t7",  "hours": 4},
    7: {"Name": "t8",  "hours": 4},
    8: {"Name": "t9",  "hours": 4},
    9: {"Name": "t10", "hours": 4},
}

# ---------------- CLASS → TEACHER HOURS ----------------
# class_to_teacher[class][teacher] = remaining hours
class_to_teacher = []
for _ in range(No_of_classes):
    row = {t: teacher_list[t]["hours"] for t in teacher_list}
    class_to_teacher.append(row)

# ---------------- HELPERS ----------------
def find_empty(tt):
    for p in range(len(tt)):
        for c in range(len(tt[0])):
            if tt[p][c] == 0:
                return p, c
    return -1, -1


def get_available_teachers(class_id, used_today):
    teachers = []
    for t in class_to_teacher[class_id]:
        if class_to_teacher[class_id][t] > 0 and t not in used_today:
            teachers.append(t)
    random.shuffle(teachers)
    return teachers


# ---------------- SOLVER ----------------
def solve(tt):
    p, c = find_empty(tt)
    if p == -1:
        return True

    day = p // No_of_periods

    # teachers already teaching this class today
    used_today = set()
    for i in range(day * No_of_periods, (day + 1) * No_of_periods):
        if tt[i][c] != 0 and tt[i][c] != "free":
            for t in teacher_list:
                if teacher_list[t]["Name"] == tt[i][c]:
                    used_today.add(t)

    for t in get_available_teachers(c, used_today):
        tt[p][c] = teacher_list[t]["Name"]
        class_to_teacher[c][t] -= 1

        if solve(tt):
            return True

        # backtrack
        tt[p][c] = 0
        class_to_teacher[c][t] += 1

    tt[p][c] = "free"
    return solve(tt)


# ---------------- RUN ----------------
solve(Timetable)

# ---------------- PRINT ----------------
for i, row in enumerate(Timetable):
    print(f"Period {i+1}: {row}")
