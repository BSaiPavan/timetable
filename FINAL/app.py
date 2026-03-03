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
        incoming_payload = request.get_json()
        if not incoming_payload:
            return jsonify({"status": "error", "message": "No data received"}), 400

        web_data = incoming_payload.get('table_data', [])
        config = incoming_payload.get('config', {})
        
        # Pulling dynamic days/periods from the Setup UI
        days = int(config.get('days', 6))
        periods = int(config.get('periods', 6))

        organized_classes = {}

        for row in web_data:
            c_name = row['class'].replace("Class ", "").strip()
            if c_name not in organized_classes:
                organized_classes[c_name] = []

            organized_classes[c_name].append({
                "teacher": row.get('teacher', 'Unknown'),
                "subject": row.get('subject', 'General'),
                "hours": int(row.get('periods', 0)),
                "type": row.get('type', 'theory').lower(),
                "continuous": int(row.get('continuous', 1)),
                "lab_no": int(row.get('lab_no', 0))
            })

        # 3. Use the updated adapter
        (No_of_classes, teacher_list, class_teacher_periods, 
         lab_teacher_periods, subject_map) = build_solver_inputs_from_classes(
             {"classes": organized_classes}, days, periods
         )

        # 4. Trigger Solver
        final_timetable = generate_timetable(
            No_of_classes, days, periods, teacher_list, 
            class_teacher_periods, lab_teacher_periods, subject_map
        )

        if final_timetable:
            # VITAL: Store the dimensions used so the Success UI knows how to render
            session_meta = {"days": days, "periods": periods, "num_classes": No_of_classes}
            with open("generated_metadata.json", "w") as f:
                json.dump(session_meta, f)
                
            with open("generated_timetable.json", "w") as f:
                json.dump(final_timetable, f)
            
            with open("final_schedule.json", "w") as f:
                json.dump(web_data, f)
                
            return jsonify({"status": "success", "redirect": url_for('success_summary')})
        
        return jsonify({
            "status": "error", 
            "message": "The solver could not find a valid schedule. Check for teacher overloads."
        }), 400

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": f"Server Error: {str(e)}"}), 500

# CLEANED: Only one version of success_summary using dynamic metadata
@app.route("/success-summary")
def success_summary():
    if not os.path.exists("generated_timetable.json") or not os.path.exists("generated_metadata.json"):
        return redirect(url_for('home'))
        
    with open("generated_timetable.json", "r") as f:
        timetable = json.load(f)
    with open("generated_metadata.json", "r") as f:
        meta = json.load(f)
    with open("final_schedule.json", "r") as f:
        final_data = json.load(f)
    
    # Get unique class names from the final data verified by the user
    class_names = list(dict.fromkeys([row['class'] for row in final_data]))
    
    return render_template("success.html", 
                           timetable=timetable, 
                           num_classes=meta['num_classes'],
                           class_names=class_names,
                           num_days=meta['days'], 
                           periods_per_day=meta['periods'])




# --- ADD THIS NEW ROUTE ---
@app.route("/setup-fixed")
def setup_fixed():
    # Load the data the user just verified in allot.html
    if not os.path.exists("temp_web_data.json"):
        return redirect(url_for('home'))
        
    with open("temp_web_data.json", "r") as f:
        stored = json.load(f)
    
    # We need the teacher list to show in the dropdowns on the fixed grid
    (no_classes, t_list, c_theory, l_periods, subj_map) = build_solver_inputs_from_classes(
        {"classes": stored['organized']}, stored['days'], stored['periods']
    )
    
    return render_template("fixed_setup.html", 
                           days=stored['days'], 
                           periods=stored['periods'], 
                           teachers=t_list)

# --- MODIFY YOUR EXISTING update_data ROUTE ---
@app.route("/update-data", methods=["POST"])
def update_data():
    try:
        incoming_payload = request.get_json()
        web_data = incoming_payload.get('table_data', [])
        config = incoming_payload.get('config', {})
        days = int(config.get('days', 6))
        periods = int(config.get('periods', 6))

        # Organize data exactly like before
        organized_classes = {}
        for row in web_data:
            c_name = row['class'].replace("Class ", "").strip()
            if c_name not in organized_classes: organized_classes[c_name] = []
            organized_classes[c_name].append({
                "teacher": row.get('teacher', 'Unknown'),
                "subject": row.get('subject', 'General'),
                "hours": int(row.get('periods', 0)),
                "type": row.get('type', 'theory').lower(),
                "continuous": int(row.get('continuous', 1)),
                "lab_no": int(row.get('lab_no', 0))
            })

        # INSTEAD OF SOLVING: Save to a temp file and redirect to Fixed Setup
        session_data = {
            "organized": organized_classes,
            "raw_table": web_data,
            "days": days,
            "periods": periods
        }
        with open("temp_web_data.json", "w") as f:
            json.dump(session_data, f)

        # Tell the JS to go to the Fixed Setup page
        return jsonify({"status": "success", "redirect": url_for('setup_fixed')})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/run-final-solver", methods=["POST"])
def run_final_solver():
    fixed_data = request.get_json().get('fixed_slots', {})
    
    with open("temp_web_data.json", "r") as f:
        stored = json.load(f)

    # Use the new subtraction logic
    (No_of_classes, t_list, c_theory, l_periods, subj_map) = build_final_inputs(
        stored['organized'], stored['days'], stored['periods'], fixed_data
    )

    # Run Solver
    final_timetable = generate_timetable(
        No_of_classes, stored['days'], stored['periods'], t_list, 
        c_theory, l_periods, subj_map, fixed_slots=fixed_data
    )

    if final_timetable:
        # Save results (same as your current success logic)
        with open("generated_metadata.json", "w") as f:
            json.dump({"days": stored['days'], "periods": stored['periods'], "num_classes": No_of_classes}, f)
        with open("generated_timetable.json", "w") as f:
            json.dump(final_timetable, f)
        return jsonify({"status": "success", "redirect": url_for('success_summary')})
    
    return jsonify({"status": "error", "message": "Constraint Conflict!"})


    
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)