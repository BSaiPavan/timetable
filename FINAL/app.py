import os
import json
import csv
from flask import Flask, render_template, request, redirect, url_for, jsonify

# Custom modules
from config import CONFIG
from solver import generate_timetable
from adapter import build_solver_inputs_from_classes
from extractor import get_solver_data_from_pdf 

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.abspath('uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route("/")
def home():
    return render_template("upload.html")

@app.route("/upload-pdf", methods=["POST"])
def upload_pdf():
    file = request.files.get('file')
    if not file or file.filename == '':
        return "No file selected", 400

    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], "uploaded_schedule.pdf")
    file.save(pdf_path)
    
    try:
        raw_data = get_solver_data_from_pdf(pdf_path) 
        with open("last_extraction.json", "w") as f:
            json.dump(raw_data, f)
        
        CONFIG["raw_extraction"] = raw_data
        return redirect(url_for('generate'))
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return f"AI Extraction Failed: {str(e)}", 500

@app.route("/generate")
def generate():
    data = CONFIG.get("raw_extraction")
    if not data and os.path.exists("last_extraction.json"):
        with open("last_extraction.json", "r") as f:
            data = json.load(f)
    
    if not data:
        return "<h3>No data found. Please upload a PDF first.</h3>"

    try:
        display_data = []
        teacher_map = data.get('teacher_list', {})

        # Process Theory
        for class_id, teachers in data.get('class_teacher_periods', {}).items():
            for t_id, info in teachers.items():
                # Handle dictionary response from AI
                subj = info.get('subject', 'Theory') if isinstance(info, dict) else "Theory"
                p_val = info.get('periods', 0) if isinstance(info, dict) else info

                display_data.append({
                    "class": f"Class {class_id}",
                    "subject": subj,
                    "teacher": teacher_map.get(str(t_id), {}).get('Name', f"S{t_id}"),
                    "type": "Theory",
                    "periods": p_val
                })

        # Process Labs
        for class_id, labs in data.get('lab_teacher_periods', {}).items():
            for t_id, info in labs.items():
                subj = info.get('subject', 'Lab') if isinstance(info, dict) else "Lab"
                
                # SAFE EXTRACTION: Prevent IndexError if periods list is empty
                p_raw = info.get('periods', [0]) if isinstance(info, dict) else [info]
                p_count = p_raw[0] if (isinstance(p_raw, list) and len(p_raw) > 0) else 0

                display_data.append({
                    "class": f"Class {class_id}",
                    "subject": subj,
                    "teacher": teacher_map.get(str(t_id), {}).get('Name', f"S{t_id}"),
                    "type": "Lab",
                    "periods": p_count
                })

        return render_template("view_simple.html", rows=display_data)

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return f"<h3>Data Processing Error: {str(e)}</h3>"

@app.route("/update-data", methods=["POST"])
def update_data():
    try:
        web_data = request.get_json()
        organized_classes = {}
        for row in web_data:
            c_name = row['class']
            organized_classes.setdefault(c_name, []).append({
                "teacher": row['teacher'],
                "subject": row['subject'], # FIXED: Now uses the actual course name
                "hours": int(row['periods']),
                "type": row['type'].lower(),
                "continuous": 2 if row['type'].lower() == "lab" else 1,
                "lab_no": 1
            })

        # Build Solver Inputs
        (No_of_classes, teacher_list, class_teacher_periods, 
         lab_teacher_periods, subject_map) = build_solver_inputs_from_classes({"classes": organized_classes})

        # Create Free Teachers
        next_id = max(teacher_list.keys()) + 1 if teacher_list else 0
        for i in range(No_of_classes):
            teacher_list[next_id + i] = {"Name": f"f{i}", "available": True}

        # Run Solver
        final_timetable = generate_timetable(
            No_of_classes, 5, 7, teacher_list, 
            class_teacher_periods, lab_teacher_periods, subject_map
        )

        if final_timetable:
            with open("generated_timetable.json", "w") as f:
                json.dump(final_timetable, f)
            with open("final_schedule.json", "w") as f:
                json.dump(web_data, f)
            return jsonify({"status": "success", "redirect": url_for('success_summary')})
        
        return jsonify({"status": "error", "message": "Solver could not find a valid schedule."}), 400

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/success-summary")
def success_summary():
    if not os.path.exists("generated_timetable.json"):
        return redirect(url_for('home'))
        
    with open("generated_timetable.json", "r") as f:
        timetable = json.load(f)
    with open("final_schedule.json", "r") as f:
        final_data = json.load(f)
    
    class_names = list(dict.fromkeys([row['class'] for row in final_data]))
    
    return render_template("success.html", 
                           timetable=timetable, 
                           num_classes=len(class_names),
                           class_names=class_names,
                           num_days=5, 
                           periods_per_day=7)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)