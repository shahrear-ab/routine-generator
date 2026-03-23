# Automated Class Routine Generator

A desktop application for building conflict-aware weekly class routines using a Tkinter UI.

This project lets you:
- Manage classrooms, teachers, courses, and sections.
- Assign courses to sections and teachers.
- Add optional manual day/time slots for fixed classes.
- Auto-generate routines with conflict handling and priority rules.
- View routines in a visual timetable grid.
- Export complete or filtered timetables to PDF.

## Table of Contents

- [Project Summary](#project-summary)
- [Core Features](#core-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [How Scheduling Works](#how-scheduling-works)
- [Data Model](#data-model)
- [Setup and Installation](#setup-and-installation)
- [How to Run](#how-to-run)
- [Recommended Workflow](#recommended-workflow)
- [PDF Export](#pdf-export)
- [Data Files and Persistence](#data-files-and-persistence)
- [Troubleshooting](#troubleshooting)
- [Known Notes](#known-notes)
- [Contributors](#contributors)

## Project Summary

The application generates weekly class routines for academic departments with these goals:
- Avoid overlapping classes for sections, teachers, and classrooms.
- Respect teacher workload limits (weekly and daily).
- Respect room capacity and room type requirements.
- Prioritize senior faculty when section-level conflicts occur.
- Support subsection-aware scheduling (for split sections such as A1, A2).

## Core Features

### 1) Entity Management
You can add, update, and delete:
- Classrooms
- Teachers
- Courses
- Sections

### 2) Course Assignment System
The Assign Courses tab supports:
- Linking a course to a section and teacher.
- Selecting subsection targets (or All) for multi-subsection sections.
- Optional preferred room selection (or automatic room selection).
- Sessions per week.
- Optional manual scheduled slots (day + time slot).

### 3) Conflict-Aware Routine Generation
The scheduler:
- Processes manual slots first, then auto-scheduling.
- Uses rank and seniority to resolve section overlap conflicts.
- Enforces teacher load caps (weekly and daily).
- Tries teacher preferred slots first when auto-scheduling.
- Tracks and reports unresolved conflicts.

### 4) Visual Timetable Viewer
The View Timetables tab provides a merged visual grid by:
- Section
- Teacher
- Classroom
- Course

### 5) PDF Export
Export options in UI:
- All Routines
- Section-specific
- Teacher-specific
- Classroom-specific

The PDF layout includes merged cells for multi-period classes and clear day/slot formatting.

## Tech Stack

- Python 3.x
- Streamlit (Web UI)
- ReportLab (PDF generation)
- PyPDF2 (PDF utility dependency)
- JSON files for persistence

## Project Structure

```text
routine_generator/
├─ web_app.py
├─ models.py
├─ data_manager.py
├─ routine_generator.py
├─ pdf_generator.py
├─ requirements.txt
├─ data/
│  ├─ classrooms.json
│  ├─ teachers.json
│  ├─ courses.json
│  ├─ sections.json
│  ├─ course_assignments.json
│  └─ routine.json
└─ README.md
```

### File Responsibilities
- web_app.py: Streamlit web UI, data management pages, routine generation, timetable view, and PDF export UI.
- models.py: Dataclass models such as Classroom, Teacher, Course, Section, Routine.
- data_manager.py: JSON load/save and CRUD-like persistence helpers.
- routine_generator.py: Core scheduling algorithm and conflict logic.
- pdf_generator.py: PDF timetable rendering.
- data/: Persistent JSON datasets.

## How Scheduling Works

High-level process:
1. Load entities and assignments.
2. Expand section assignments for subsections when needed.
3. Validate key constraints (for example theory load vs credit hours).
4. Schedule manually fixed slots first.
5. Schedule remaining sessions automatically.
6. Resolve section overlap conflicts using teacher priority rules.
7. Record unscheduled sessions and conflict messages.

### Teacher Priority and Preemption
Priority order uses:
- Rank priority: Professor > Associate Prof > Assistant Prof > Lecturer.
- Seniority level inside same rank and department.

When two classes conflict for the same section/subsection window:
- Higher-priority teacher can preempt lower-priority assignment.
- Teacher self-overlap and cross-section classroom overlap are still blocked.

### Room Selection Rules
For each placement, the scheduler:
- Tries explicit preferred room (if set in assignment).
- Else tries section home classroom first.
- Else tries alternative compatible rooms.

Checks include:
- Room type compatibility.
- Capacity >= section or subsection student count.
- Occupancy at the target day/time.

## Data Model

The main entities are represented in models.py.

### Classroom
Fields:
- full_name
- short_code
- capacity
- room_type (General Classroom, Theory Lab, Computer Lab)

### Teacher
Fields:
- full_name
- short_name
- rank
- seniority_level
- dept_name
- max_hours_per_week
- max_hours_per_day
- preferred_time_slots

### Course
Fields:
- title
- short_code
- credit_hours
- required_duration (1, 2, or 3 hours)
- required_room_type (optional)

### Section
Fields:
- full_name
- short_code
- num_students
- home_classroom_code
- subsections

### CourseAssignment
Fields:
- course_code
- section_name
- teacher_short_name
- classroom_code (optional preferred room)
- sessions_per_week
- scheduled_slots (optional manual day/time entries)

### Routine
Contains:
- entries (scheduled classes)
- conflicts (messages produced during generation/validation)
- course_assignments snapshot

## Setup and Installation

### 1) Create and activate a virtual environment (recommended)
Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```powershell
pip install -r requirements.txt
```

## How to Run

From the project root:

```powershell
streamlit run web_app.py
```

This opens the Streamlit web app.

## Recommended Workflow

1. Open Classrooms tab and add room inventory.
2. Open Teachers tab and add faculty with rank/seniority/workload.
3. Open Courses tab and add courses with duration and room requirements.
4. Open Sections tab and add sections, home room, and subsection count.
5. Open Assign Courses tab and create course assignments.
6. Optionally add manual time slots for fixed classes.
7. Open Generate Routine tab and click Generate Routine.
8. Review conflicts and possible fixes.
9. Open View Timetables tab for section/teacher/classroom/course grids.
10. Export PDF from Generate Routine tab.

## PDF Export

You can export:
- Full routine package (all sections, teachers, classrooms, courses pages).
- Individual timetable by section, teacher, or classroom.

The PDF renderer supports:
- Day-wise grid layout.
- Multi-slot merged cells for longer classes.
- Subsection labels in timetable cells.

## Data Files and Persistence

All data is stored in the data directory as JSON.

- classrooms.json
- teachers.json
- courses.json
- sections.json
- course_assignments.json
- routine.json

Notes:
- The app reads these files on startup.
- Most operations save immediately after add/update/delete.
- Routine generation writes output to routine.json.

## Troubleshooting

### App does not start
- Ensure Python 3 is installed and available in PATH.
- Ensure dependencies are installed from requirements.txt.

### Import errors for ReportLab
- Re-run dependency install:

```powershell
pip install -r requirements.txt
```

### Routine generation says no assignments
- Add course assignments first in the Assign Courses tab.

### Many unscheduled sessions
- Reduce sessions per week for constrained courses.
- Add more compatible classrooms.
- Increase scheduling flexibility (remove restrictive manual slots).
- Re-check teacher daily/weekly limits.

### Capacity conflicts
- Increase classroom capacity options.
- Split large sections into more subsections.
- Use compatible lab/classroom room types.

### Theory load conflicts
- For theory courses, ensure:

weekly contact hours = sessions_per_week x required_duration <= credit_hours

## Known Notes

- Main auto-scheduling loop currently iterates through Monday-Friday.
- The manual slot picker includes Saturday and Sunday; entries on those days may only come from manual assignments.

## Contributors

About tab credits this project to:
- ME Section C-2, Group-1

Listed contributors:
- Md. Atik Aziz (2410151)
- Abdur Rahman (2410152)
- Shahrear Abedin Bhuiyan (2410153)
- Khan Abrar Maheer (2410154)
- Farhan Tasdik (2410155)
- Ettishum Khaleque Munajir (2410156)

Institution note in app:
- Bangladesh University of Engineering and Technology

---
If you want, I can also generate:
- A shorter one-page quick-start README.
- A separate CONTRIBUTING.md.
- A JSON schema reference for each file inside data/.
