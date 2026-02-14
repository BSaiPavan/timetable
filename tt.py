No_of_classes=7
No_of_teachers=10
No_of_days_in_week=6
No_of_periods=6
Timetable=[]
br=[]
crr=0
arr=[]




#making the timetable box with default input 0
for i in range(No_of_classes):
        crr=i
        arr.append(crr)
for j in range(No_of_days_in_week*No_of_periods):
     Timetable.append(arr.copy())

#print(Timetable)

#below - making the class to
crr=0
arr=[]
class_to_teacher=[]
for i in range(No_of_teachers):
       crr=3
       arr.append(crr)
for j in range(No_of_classes):
       class_to_teacher.append(arr)

#print(class_to_teacher)

teacher_list = {
    0: {"Name": "t1",  "no_of_hours": 4, "available": False},
    1: {"Name": "t2",  "no_of_hours": 4, "available": True},
    2: {"Name": "t3",  "no_of_hours": 4, "available": True},
    3: {"Name": "t4",  "no_of_hours": 4, "available": True},
    4: {"Name": "t5",  "no_of_hours": 4, "available": True},
    5: {"Name": "t6",  "no_of_hours": 4, "available": True},
    6: {"Name": "t7",  "no_of_hours": 4, "available": True},
    7: {"Name": "t8",  "no_of_hours": 4, "available": True},
    8: {"Name": "t9",  "no_of_hours": 4, "available": True},
    9: {"Name": "t10", "no_of_hours": 4, "available": True},
}

#print(teacher_lis)
def available_resetter(Tl,i,j):   #np=no. of periods in a week ==no of in a week * no. of periods in a day, i is which period 
    if(j==0):
        for t in Tl:
             Tl["available"]=True                                         #we are in out of (np*no of days in a week)
                                           #i is which period we are in 
                                            #trying to reset every next period
                                
def find_empty(x,Tl):
    for i in range (len(x)):
       # print(f"i now in {i}")
        for j in range (len(x[0])):
            available_resetter(Tl,i,j)
            #print(f"j now in {j}")
            #print(x[i][j])
            if x[i][j] == 0  or  x[i][j] == "":
                print(f"tried {i} and {j}")
                return i, j
    return -1,-1

def reset_available(x):
     for i in range(len(x)):
        x[i]["available"]=True

     
def find_teacher(x,y,Tl):
    for i in range (len(x[0])):
          if x[y][i]>0 and Tl[i]["available"]==True:
                x[y][i]=x[y][i]-1
                Tl[i]["available"]=False
                return i
    return -1

'''
for i in range(No_of_classes):
        crr=0
        arr.append(crr)
for j in range(No_of_days_in_week*No_of_periods):
     Timetable.append(arr)'''

def print_timetable(x):
     for i in range(len(x)):
          print(f'printing row {i}-{x[i]}')

def solve(Timetable , class_to_teacher,Tl):
    x,y=find_empty(Timetable,Tl)
    if x==-1:
        return True
    #if(x>)  # need a way to reset the availability every next day
    e=find_teacher(class_to_teacher,y,Tl)
    print(f'e i {e}')
    #if e==-1: #need to implement
         #use free cases
    if e==-1:
         Timetable[x][y]="free"
    else:
        Timetable[x][y]=Tl[e]["Name"]
        print(f"putting in {Tl[e]['Name']}")
    if(solve(Timetable , class_to_teacher,Tl)):
         return True
    Timetable[x][y]=0
    return False

     
#print_timetable(Timetable)
solve(Timetable,class_to_teacher,teacher_list)
#print(solve==0)
print_timetable(Timetable)