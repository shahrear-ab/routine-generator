import io
import os
import tempfile
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from data_manager import DataManager
from models import Classroom, Course, CourseAssignment, Routine, Section, Teacher, TimeSlot
from pdf_generator import PDFGenerator
from routine_generator import RoutineGenerator


st.set_page_config(page_title="University Routine Generator", page_icon="📅", layout="wide")


RANK_LOADS = {
	"Professor": (16, 4),
	"Associate Prof": (18, 4),
	"Assistant Prof": (20, 5),
	"Lecturer": (22, 5),
}

ROOM_TYPES = ["General Classroom", "Theory Lab", "Computer Lab"]

ASSIGN_DAY_OPTIONS = ["No Preference", "Sa", "Sun", "Mo", "Tu", "We", "Th", "Fr"]
ASSIGN_DAY_TO_FULL = {
	"Sa": "Saturday",
	"Sun": "Sunday",
	"Mo": "Monday",
	"Tu": "Tuesday",
	"We": "Wednesday",
	"Th": "Thursday",
	"Fr": "Friday",
}
ASSIGN_DAY_FROM_FULL = {v: k for k, v in ASSIGN_DAY_TO_FULL.items()}
PREFERRED_START_TIMES = ["No Preference", "08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00"]

PAGES = [
	"Dashboard",
	"Classrooms",
	"Teachers",
	"Courses",
	"Sections",
	"Assign Courses",
	"Generate Routine",
	"View Timetables",
]

APP_STYLE = """
<style>
	:root {
		--bg-light: #ffffff;
		--bg-base: #ffffff;
		--bg-accent: #eff8f3;
		--panel: #ffffff;
		--panel-light: #f9fcfb;
		--ink-dark: #111111;
		--ink-main: #111111;
		--ink-muted: #666666;
		--accent-primary: #22a055;
		--accent-secondary: #1e8e47;
		--accent-light: #a8e6c0;
		--success: #22a055;
		--border: #d8ebe3;
		--shadow-sm: 0 2px 8px rgba(13, 40, 24, 0.08);
		--shadow-md: 0 4px 16px rgba(13, 40, 24, 0.12);
		--shadow-lg: 0 8px 24px rgba(13, 40, 24, 0.15);
	}

	.stApp {
		background: #ffffff;
		color: var(--ink-main);
	}

	.stAppHeader, .stAppToolbar {
		background: transparent !important;
	}

	.nav-container {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		padding: 1.2rem 1rem;
		border-bottom: 3px solid var(--accent-primary);
		margin-bottom: 2rem;
		background: linear-gradient(90deg, rgba(34, 160, 85, 0.02) 0%, transparent 100%);
		margin-left: -1rem;
		margin-right: -1rem;
	}

	.nav-button {
		padding: 0.65rem 1.4rem;
		border-radius: 12px;
		border: none;
		font-weight: 700;
		cursor: pointer;
		background: var(--bg-accent);
		color: var(--ink-main);
		font-size: 0.95rem;
		transition: all 0.25s ease;
	}

	.nav-button.active {
		background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%);
		color: #ffffff;
		box-shadow: var(--shadow-md);
	}

	h1, h2, h3, h4, h5, h6 {
		letter-spacing: -0.01em;
		color: var(--ink-dark);
		font-weight: 700;
	}

	.block-container {
		padding-top: 0.5rem;
		padding-bottom: 2rem;
	}

	.stMetric {
		background: var(--panel);
		border: 2px solid var(--border);
		border-radius: 16px;
		padding: 1.2rem;
		box-shadow: var(--shadow-sm);
		transition: all 0.3s ease;
	}

	.stMetric:hover {
		border-color: var(--accent-primary);
		box-shadow: var(--shadow-md);
	}

	div[data-testid="stDataFrame"] {
		background: var(--panel);
		border: 2px solid var(--border);
		border-radius: 16px;
		padding: 1rem;
		box-shadow: var(--shadow-sm);
	}

	.timetable-grid {
		width: 100%;
		table-layout: fixed;
		border-collapse: collapse;
		margin: 1.5rem 0;
		font-size: 0.95rem;
		background: var(--panel);
		border: 2px solid var(--border);
		border-radius: 12px;
		overflow: hidden;
		box-shadow: var(--shadow-md);
	}

	.timetable-grid th {
		background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%);
		color: #ffffff;
		font-weight: 700;
		padding: 0.8rem 0.35rem;
		text-align: center;
		border: 1px solid var(--accent-secondary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.timetable-grid td {
		padding: 0.6rem;
		border: 1px solid var(--border);
		height: 78px;
		min-height: 78px;
		vertical-align: top;
		font-size: 0.85rem;
		overflow: hidden;
	}

	.timetable-grid tr:nth-child(even) {
		background: rgba(34, 160, 85, 0.03);
	}

	.timetable-grid .time-slot-col {
		background: var(--bg-accent);
		font-weight: 700;
		color: var(--accent-primary);
		width: 76px;
		max-width: 76px;
		min-width: 76px;
		white-space: nowrap;
		text-align: center;
		vertical-align: middle;
		padding: 0.3rem 0.35rem;
		font-size: 0.82rem;
	}

	.timetable-grid .slot-col {
		width: auto;
	}

	.slot-cell {
		height: 64px;
		max-height: 64px;
		overflow-y: auto;
		overflow-x: hidden;
		padding-right: 2px;
	}

	.class-entry {
		background: linear-gradient(135deg, rgba(34, 160, 85, 0.15) 0%, rgba(32, 206, 111, 0.08) 100%);
		border-left: 4px solid var(--accent-primary);
		padding: 0.5rem;
		border-radius: 6px;
		margin: 0.25rem 0;
		font-size: 0.8rem;
		color: #1a1a1a;
		font-weight: 600;
		box-shadow: 0 2px 6px rgba(34, 160, 85, 0.1);
		line-height: 1.2;
		word-wrap: break-word;
		display: inline-block;
		width: 98%;
	}

	.stButton > button {
		border-radius: 10px;
		padding: 0.6rem 1.2rem;
		font-weight: 700;
		transition: all 0.25s ease;
	}

	.stButton > button[kind="secondary"] {
		background-color: var(--bg-accent);
		color: var(--ink-main);
		border: 2px solid var(--border);
	}

	.stButton > button[kind="primary"] {
		background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%);
		color: #ffffff;
	}

	.stSelectbox, .stTextInput, .stNumberInput {
		padding: 0.5rem;
	}

	.stAlert {
		border-radius: 12px;
		border-left: 5px solid var(--accent-primary);
	}

</style>
"""


def apply_app_styles() -> None:
	st.markdown(APP_STYLE, unsafe_allow_html=True)


def _render_horizontal_navigation() -> str:
	current_page = st.session_state.page if st.session_state.page in PAGES else PAGES[0]
	cols = st.columns(len(PAGES))
	for idx, page_name in enumerate(PAGES):
		with cols[idx]:
			button_style = "primary" if page_name == current_page else "secondary"
			if st.button(page_name, key=f"nav_{page_name}", type=button_style, use_container_width=True):
				st.session_state.page = page_name
				st.rerun()
	return current_page


def _time_to_minutes(value: str) -> int:
	h, m = map(int, value.split(":"))
	return h * 60 + m


def _slot_label_and_minutes() -> List[Tuple[str, int, int]]:
	return [
		("1st (08:00-08:50)", _time_to_minutes("08:00"), _time_to_minutes("08:50")),
		("2nd (09:00-09:50)", _time_to_minutes("09:00"), _time_to_minutes("09:50")),
		("3rd (10:00-10:50)", _time_to_minutes("10:00"), _time_to_minutes("10:50")),
		("4th (11:00-11:50)", _time_to_minutes("11:00"), _time_to_minutes("11:50")),
		("5th (12:00-12:50)", _time_to_minutes("12:00"), _time_to_minutes("12:50")),
		("6th (13:00-13:30)", _time_to_minutes("13:00"), _time_to_minutes("13:30")),
		("7th (14:00-14:50)", _time_to_minutes("14:00"), _time_to_minutes("14:50")),
		("8th (15:00-15:50)", _time_to_minutes("15:00"), _time_to_minutes("15:50")),
		("9th (16:00-16:50)", _time_to_minutes("16:00"), _time_to_minutes("16:50")),
	]


def _entry_overlaps_slot(start_time: str, end_time: str, slot_start: int, slot_end: int) -> bool:
	start = _time_to_minutes(start_time)
	end = _time_to_minutes(end_time)
	return start < slot_end and slot_start < end


def _normalize_dept_name(dept_name: str) -> str:
	return (dept_name or "").strip().lower()


def _minutes_to_time(total_minutes: int) -> str:
	h = total_minutes // 60
	m = total_minutes % 60
	return f"{h:02d}:{m:02d}"


def _build_preferred_scheduled_slots(
	preferred_day_abbr: str,
	preferred_start_time: str,
	course_duration_hours: int,
) -> Tuple[List[Tuple[str, TimeSlot]], Optional[str]]:
	if preferred_day_abbr == "No Preference" and preferred_start_time == "No Preference":
		return [], None
	if preferred_day_abbr == "No Preference" or preferred_start_time == "No Preference":
		return [], "Select both Preferred Day and Preferred Time Slot, or keep both as No Preference."

	day_full = ASSIGN_DAY_TO_FULL.get(preferred_day_abbr)
	if not day_full:
		return [], "Invalid preferred day selected."

	start_minutes = _time_to_minutes(preferred_start_time)
	end_minutes = start_minutes + (int(course_duration_hours) * 60)
	break_start = _time_to_minutes("13:30")
	break_end = _time_to_minutes("14:00")
	if start_minutes < break_end and end_minutes > break_start:
		return [], (
			f"Preferred slot {preferred_start_time}-{_minutes_to_time(end_minutes)} crosses break (13:30-14:00). "
			"Choose a slot that ends before break or starts after break."
		)
	if end_minutes > _time_to_minutes("17:00"):
		return [], (
			f"Preferred start time {preferred_start_time} is too late for a {int(course_duration_hours)} hour course. "
			"Choose an earlier slot."
		)

	slot = TimeSlot(preferred_start_time, _minutes_to_time(end_minutes))
	return [(day_full, slot)], None


def ensure_state() -> None:
	if "data_manager" not in st.session_state:
		try:
			st.session_state.data_manager = DataManager("data")
		except Exception as exc:
			st.error(f"Failed to initialize data manager: {exc}")
			st.stop()

	if "page" not in st.session_state:
		st.session_state.page = "Dashboard"

	if "routine" not in st.session_state:
		try:
			st.session_state.routine = st.session_state.data_manager.load_routine()
		except Exception:
			st.session_state.routine = Routine()

	if "pdf_bytes" not in st.session_state:
		st.session_state.pdf_bytes = None


def load_data() -> Dict[str, List]:
	dm: DataManager = st.session_state.data_manager
	try:
		return {
			"classrooms": dm.load_classrooms(),
			"teachers": dm.load_teachers(),
			"courses": dm.load_courses(),
			"sections": dm.load_sections(),
			"assignments": dm.load_course_assignments(),
		}
	except Exception as exc:
		st.error(f"Could not load JSON data files: {exc}")
		return {
			"classrooms": [],
			"teachers": [],
			"courses": [],
			"sections": [],
			"assignments": [],
		}


def show_missing_file_notice() -> None:
	dm: DataManager = st.session_state.data_manager
	expected = [
		dm.classrooms_file,
		dm.teachers_file,
		dm.courses_file,
		dm.sections_file,
		dm.assignments_file,
		dm.routine_file,
	]
	missing = [path for path in expected if not os.path.exists(path)]
	if missing:
		names = ", ".join(os.path.basename(path) for path in missing)
		st.info(f"Missing JSON files were treated as empty datasets: {names}")


def build_pdf_bytes(routine: Routine, data: Dict[str, List]) -> Optional[bytes]:
	if not routine.entries:
		return None

	try:
		with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
			tmp_path = tmp.name

		try:
			pdf_gen = PDFGenerator(
				routine,
				data["courses"],
				data["teachers"],
				data["classrooms"],
				data["sections"],
			)
			pdf_gen.generate_pdf(tmp_path)
			with open(tmp_path, "rb") as file_obj:
				return file_obj.read()
		finally:
			if os.path.exists(tmp_path):
				os.remove(tmp_path)
	except Exception as exc:
		st.error(f"Failed to generate PDF: {exc}")
		return None


def build_filtered_pdf_bytes(
	routine: Routine,
	data: Dict[str, List],
	export_type: str,
	selected_item: str,
) -> Optional[bytes]:
	if not routine.entries:
		return None

	try:
		with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
			tmp_path = tmp.name

		try:
			pdf_gen = PDFGenerator(
				routine,
				data["courses"],
				data["teachers"],
				data["classrooms"],
				data["sections"],
			)

			if export_type == "All":
				pdf_gen.generate_pdf(tmp_path)
			elif export_type == "Section":
				section_code = _parse_section_code(selected_item)
				pdf_gen.generate_section_pdf(tmp_path, section_code, selected_item)
			elif export_type == "Teacher":
				short_name = selected_item.split("(")[-1].rstrip(")")
				pdf_gen.generate_teacher_pdf(tmp_path, short_name, selected_item)
			elif export_type == "Classroom":
				short_code = selected_item.split("(")[-1].rstrip(")")
				pdf_gen.generate_classroom_pdf(tmp_path, short_code, selected_item)
			elif export_type == "Course":
				course_code = selected_item.split("(")[-1].rstrip(")")
				pdf_gen.generate_course_pdf(tmp_path, course_code, selected_item)
			else:
				st.error("Unsupported export type selected.")
				return None

			with open(tmp_path, "rb") as file_obj:
				return file_obj.read()
		finally:
			if os.path.exists(tmp_path):
				os.remove(tmp_path)
	except Exception as exc:
		st.error(f"Failed to generate PDF: {exc}")
		return None


def assignment_table_rows(assignments: List[CourseAssignment]) -> List[Dict[str, str]]:
	rows = []
	for idx, assignment in enumerate(assignments):
		preferred_text = "-"
		if assignment.scheduled_slots:
			first_day, first_slot = assignment.scheduled_slots[0]
			abbr = ASSIGN_DAY_FROM_FULL.get(first_day, first_day[:2])
			hh, mm = map(int, first_slot.start_time.split(":"))
			display_h = hh % 12
			if display_h == 0:
				display_h = 12
			preferred_text = f"{abbr}/{display_h}:{mm:02d}"

		slot_text = ", ".join(
			f"{day} {time_slot.start_time}-{time_slot.end_time}" for day, time_slot in assignment.scheduled_slots
		)
		rows.append(
			{
				"#": idx,
				"Section": assignment.section_name,
				"Course": assignment.course_code,
				"Teacher": assignment.teacher_short_name,
				"Room": assignment.classroom_code or "Auto",
				"Sessions/Week": assignment.sessions_per_week,
				"Preferred Time": preferred_text,
				"Manual Slots": slot_text,
			}
		)
	return rows


def _split_assignment_section_target(section_name: str, valid_sections: List[str]) -> Tuple[str, str]:
	"""Split stored section target into (base_section, subsection_marker)."""
	if "-S" in section_name:
		base, suffix = section_name.rsplit("-S", 1)
		if suffix.isdigit() and base in valid_sections:
			return base, f"S{suffix}"
	return section_name, "All"


def render_dashboard(data: Dict[str, List]) -> None:
	st.markdown("#### 📊 System Overview")
	
	st.divider()
	
	c1, c2, c3, c4 = st.columns(4)
	c1.metric("🏛️ Classrooms", len(data["classrooms"]))
	c2.metric("👨\u200d🏫 Teachers", len(data["teachers"]))
	c3.metric("📚 Courses", len(data["courses"]))
	c4.metric("👥 Sections", len(data["sections"]))

	st.divider()
	
	routine: Routine = st.session_state.routine
	st.markdown("#### 📅 Current Routine Status")
	if routine.entries:
		rc1, rc2, rc3 = st.columns(3)
		rc1.metric("✅ Scheduled Classes", len(routine.entries))
		rc2.metric("⚠️ Conflicts", len(routine.conflicts))
		rc3.metric("📋 Assignments", len(routine.course_assignments))
	else:
		st.warning("📭 No generated routine in memory yet. Use the **Generate Routine** page to create one.")

	st.divider()

	st.markdown("#### 🚀 Quick Actions")
	a1, a2, a3, a4 = st.columns(4)
	if a1.button("📍 Classrooms", use_container_width=True):
		st.session_state.page = "Classrooms"
		st.rerun()
	if a2.button("🔗 Assign Courses", use_container_width=True):
		st.session_state.page = "Assign Courses"
		st.rerun()
	if a3.button("⚙️ Generate Routine", use_container_width=True):
		st.session_state.page = "Generate Routine"
		st.rerun()
	if a4.button("📖 View Timetables", use_container_width=True):
		st.session_state.page = "View Timetables"
		st.rerun()

	st.divider()
	
	st.markdown("#### ℹ️ System Information")
	info_cols = st.columns(2)
	with info_cols[0]:
		st.caption("**Data Summary**")
		st.caption(f"Total sections: {len(data['sections'])}")
		st.caption(f"Available classrooms capacity: {sum(c.capacity for c in data['classrooms'])} seats")
	with info_cols[1]:
		st.caption("**Working Schedule**")
		st.caption("📅 Monday – Friday, 8:00 AM – 5:00 PM")
		st.caption("⏱️ Class durations: 1, 2, or 3 hours")


def render_classrooms(data: Dict[str, List]) -> None:
	st.header("Classrooms")
	dm: DataManager = st.session_state.data_manager
	classrooms: List[Classroom] = data["classrooms"]

	left, right = st.columns([1, 1.2])

	with left:
		st.subheader("Add Classroom")
		with st.form("add_classroom_form"):
			full_name = st.text_input("Full Name")
			short_code = st.text_input("Short Code")
			capacity = st.number_input("Capacity", min_value=1, step=1, value=40)
			room_type = st.selectbox("Room Type", ROOM_TYPES)
			submitted = st.form_submit_button("Add Classroom", use_container_width=True)

		if submitted:
			if not full_name.strip() or not short_code.strip():
				st.error("Full Name and Short Code are required.")
			else:
				created = Classroom(full_name.strip(), short_code.strip(), int(capacity), room_type)
				if dm.add_classroom(created, classrooms):
					st.success("Classroom added successfully.")
					st.rerun()
				else:
					st.error("A classroom with this short code already exists.")

		st.subheader("Update Classroom")
		if classrooms:
			edit_code = st.selectbox(
				"Select classroom to update",
				options=[c.short_code for c in classrooms],
				key="update_classroom_select",
			)
			edit_classroom = next((c for c in classrooms if c.short_code == edit_code), None)

			if edit_classroom:
				with st.form("update_classroom_form"):
					updated_full_name = st.text_input(
						"Full Name (Update)",
						value=edit_classroom.full_name,
						key=f"classroom_update_name_{edit_code}",
					)
					updated_capacity = st.number_input(
						"Capacity (Update)",
						min_value=1,
						step=1,
						value=int(edit_classroom.capacity),
						key=f"classroom_update_capacity_{edit_code}",
					)
					updated_room_type = st.selectbox(
						"Room Type (Update)",
						ROOM_TYPES,
						index=ROOM_TYPES.index(edit_classroom.room_type)
						if edit_classroom.room_type in ROOM_TYPES
						else 0,
						key=f"classroom_update_type_{edit_code}",
					)
					updated = st.form_submit_button("Update Classroom", use_container_width=True)

				if updated:
					if not updated_full_name.strip():
						st.error("Full Name is required.")
					else:
						updated_obj = Classroom(
							full_name=updated_full_name.strip(),
							short_code=edit_classroom.short_code,
							capacity=int(updated_capacity),
							room_type=updated_room_type,
						)
						if dm.update_classroom(updated_obj, classrooms):
							st.success("Classroom updated.")
							st.rerun()
						else:
							st.error("Could not update classroom.")

		st.subheader("Delete Classroom")
		if classrooms:
			delete_code = st.selectbox(
				"Select classroom to delete",
				options=[c.short_code for c in classrooms],
				key="delete_classroom_select",
			)
			if st.button("Delete Selected Classroom", type="secondary", use_container_width=True):
				if dm.delete_classroom(delete_code, classrooms):
					st.success("Classroom deleted.")
					st.rerun()
				else:
					st.error("Could not delete classroom.")
		else:
			st.caption("No classrooms available.")

	with right:
		st.subheader("Classroom List")
		rows = [
			{
				"Full Name": c.full_name,
				"Short Code": c.short_code,
				"Capacity": c.capacity,
				"Room Type": c.room_type,
			}
			for c in classrooms
		]
		st.dataframe(rows, use_container_width=True, hide_index=True)


def render_teachers(data: Dict[str, List]) -> None:
	st.header("Teachers")
	dm: DataManager = st.session_state.data_manager
	teachers: List[Teacher] = data["teachers"]

	left, right = st.columns([1, 1.2])
	with left:
		st.subheader("Add Teacher")
		add_teacher_rank = st.selectbox("Rank", list(RANK_LOADS.keys()), key="add_teacher_rank")
		weekly_default, daily_default = RANK_LOADS[add_teacher_rank]
		st.caption(f"Max Hours / Week (Fixed by Rank): {int(weekly_default)}")
		with st.form("add_teacher_form"):
			full_name = st.text_input("Full Name")
			short_name = st.text_input("Short Name")
			dept_name = st.text_input("Department")
			seniority = st.number_input("Seniority Level (for same dept.)", min_value=1, step=1, value=1)
			max_hours_day = st.number_input("Max Hours / Day", min_value=1, step=1, value=daily_default)
			preferred_raw = st.text_input("Preferred Slots (comma-separated: 1st,2nd,3rd)")
			submitted = st.form_submit_button("Add Teacher", use_container_width=True)

		if submitted:
			if not full_name.strip() or not short_name.strip():
				st.error("Full Name and Short Name are required.")
			elif any(
				t.rank == add_teacher_rank
				and int(t.seniority_level) == int(seniority)
				and _normalize_dept_name(t.dept_name) == _normalize_dept_name(dept_name)
				for t in teachers
			):
				st.error(
					f"Seniority {int(seniority)} is already used for rank {add_teacher_rank} "
					f"in department '{dept_name.strip() or '(empty dept)'}'. Choose a unique seniority level for that department."
				)
			else:
				preferred_slots = []
				for token in [part.strip() for part in preferred_raw.split(",") if part.strip()]:
					slot = TimeSlot.from_slot_name(token)
					if slot:
						preferred_slots.append(slot)

				teacher = Teacher(
					full_name=full_name.strip(),
					short_name=short_name.strip(),
					seniority_level=int(seniority),
					rank=add_teacher_rank,
					max_hours_per_week=int(weekly_default),
					max_hours_per_day=int(max_hours_day),
					dept_name=dept_name.strip(),
					preferred_time_slots=preferred_slots,
				)
				if dm.add_teacher(teacher, teachers):
					st.success("Teacher added successfully.")
					st.rerun()
				else:
					st.error("A teacher with this short name already exists.")

		st.subheader("Update Teacher")
		if teachers:
			edit_teacher_code = st.selectbox(
				"Select teacher to update",
				options=[t.short_name for t in teachers],
				key="update_teacher_select",
			)
			edit_teacher = next((t for t in teachers if t.short_name == edit_teacher_code), None)

			if edit_teacher:
				updated_rank = st.selectbox(
					"Rank (Update)",
					list(RANK_LOADS.keys()),
					index=list(RANK_LOADS.keys()).index(edit_teacher.rank)
					if edit_teacher.rank in RANK_LOADS
					else 0,
					key=f"teacher_update_rank_{edit_teacher_code}",
				)
				updated_weekly_default, updated_daily_default = RANK_LOADS[updated_rank]
				st.caption(f"Max Hours / Week (Update, Fixed by Rank): {int(updated_weekly_default)}")
				with st.form("update_teacher_form"):
					updated_full_name = st.text_input(
						"Full Name (Update)",
						value=edit_teacher.full_name,
						key=f"teacher_update_name_{edit_teacher_code}",
					)
					updated_short_name = st.text_input(
						"Short Name (Update)",
						value=edit_teacher.short_name,
						key=f"teacher_update_short_{edit_teacher_code}",
					)
					updated_dept = st.text_input(
						"Department (Update)",
						value=edit_teacher.dept_name,
						key=f"teacher_update_dept_{edit_teacher_code}",
					)
					updated_seniority = st.number_input(
						"Seniority Level (for same dept.)",
						min_value=1,
						step=1,
						value=int(edit_teacher.seniority_level),
						key=f"teacher_update_seniority_{edit_teacher_code}",
					)
					updated_max_day = st.number_input(
						"Max Hours / Day (Update)",
						min_value=1,
						step=1,
						value=int(updated_daily_default),
						key=f"teacher_update_day_{edit_teacher_code}",
					)
					updated_pref_raw = st.text_input(
						"Preferred Slots (Update)",
						value=",".join(slot.get_slot_name() for slot in edit_teacher.preferred_time_slots),
						key=f"teacher_update_pref_{edit_teacher_code}",
					)
					updated_submit = st.form_submit_button("Update Teacher", use_container_width=True)

				if updated_submit:
					if not updated_full_name.strip() or not updated_short_name.strip():
						st.error("Full Name and Short Name are required.")
					elif any(
						t.short_name != edit_teacher.short_name
						and t.rank == updated_rank
						and int(t.seniority_level) == int(updated_seniority)
						and _normalize_dept_name(t.dept_name) == _normalize_dept_name(updated_dept)
						for t in teachers
					):
						st.error(
							f"Seniority {int(updated_seniority)} is already used for rank {updated_rank} "
							f"in department '{updated_dept.strip() or '(empty dept)'}'. "
							"Choose a unique seniority level for that department."
						)
					else:
						preferred_slots = []
						for token in [part.strip() for part in updated_pref_raw.split(",") if part.strip()]:
							slot = TimeSlot.from_slot_name(token)
							if slot:
								preferred_slots.append(slot)

						updated_teacher = Teacher(
							full_name=updated_full_name.strip(),
							short_name=updated_short_name.strip(),
							seniority_level=int(updated_seniority),
							rank=updated_rank,
							max_hours_per_week=int(updated_weekly_default),
							max_hours_per_day=int(updated_max_day),
							dept_name=updated_dept.strip(),
							preferred_time_slots=preferred_slots,
						)
						if dm.update_teacher(updated_teacher, teachers, original_short_name=edit_teacher.short_name):
							st.success("Teacher updated.")
							st.rerun()
						else:
							st.error("Could not update teacher.")

		st.subheader("Delete Teacher")
		if teachers:
			delete_teacher_code = st.selectbox(
				"Select teacher to delete",
				options=[t.short_name for t in teachers],
				key="delete_teacher_select",
			)
			if st.button("Delete Selected Teacher", type="secondary", use_container_width=True):
				if dm.delete_teacher(delete_teacher_code, teachers):
					st.success("Teacher deleted.")
					st.rerun()
				else:
					st.error("Could not delete teacher.")
		else:
			st.caption("No teachers available.")

	with right:
		st.subheader("Teacher List")
		rows = [
			{
				"Full Name": t.full_name,
				"Short Name": t.short_name,
				"Dept": t.dept_name,
				"Rank": t.rank,
				"Seniority": t.seniority_level,
				"Max Week": t.max_hours_per_week,
				"Max Day": t.max_hours_per_day,
			}
			for t in teachers
		]
		st.dataframe(rows, use_container_width=True, hide_index=True)


def render_courses(data: Dict[str, List]) -> None:
	st.header("Courses")
	dm: DataManager = st.session_state.data_manager
	courses: List[Course] = data["courses"]

	left, right = st.columns([1, 1.2])
	with left:
		st.subheader("Add Course")
		with st.form("add_course_form"):
			title = st.text_input("Course Title")
			short_code = st.text_input("Course Code")
			credit_hours = st.number_input("Credit Hours", min_value=0.5, step=0.5, value=3.0)
			required_duration = st.selectbox("Required Duration (hours)", [1, 2, 3])
			room_type = st.selectbox("Required Room Type", ["Any"] + ROOM_TYPES)
			submitted = st.form_submit_button("Add Course", use_container_width=True)

		if submitted:
			if not title.strip() or not short_code.strip():
				st.error("Course title and code are required.")
			else:
				course = Course(
					title=title.strip(),
					short_code=short_code.strip(),
					credit_hours=float(credit_hours),
					required_duration=int(required_duration),
					required_room_type=None if room_type == "Any" else room_type,
				)
				if dm.add_course(course, courses):
					st.success("Course added successfully.")
					st.rerun()
				else:
					st.error("A course with this code already exists.")

		st.subheader("Update Course")
		if courses:
			edit_course_code = st.selectbox(
				"Select course to update",
				options=[c.short_code for c in courses],
				key="update_course_select",
			)
			edit_course = next((c for c in courses if c.short_code == edit_course_code), None)

			if edit_course:
				with st.form("update_course_form"):
					updated_title = st.text_input(
						"Course Title (Update)",
						value=edit_course.title,
						key=f"course_update_title_{edit_course_code}",
					)
					updated_credit = st.number_input(
						"Credit Hours (Update)",
						min_value=0.5,
						step=0.5,
						value=float(edit_course.credit_hours),
						key=f"course_update_credit_{edit_course_code}",
					)
					updated_duration = st.selectbox(
						"Required Duration (Update)",
						[1, 2, 3],
						index=[1, 2, 3].index(edit_course.required_duration)
						if edit_course.required_duration in [1, 2, 3]
						else 0,
						key=f"course_update_duration_{edit_course_code}",
					)
					room_value = edit_course.required_room_type if edit_course.required_room_type else "Any"
					updated_room = st.selectbox(
						"Required Room Type (Update)",
						["Any"] + ROOM_TYPES,
						index=(["Any"] + ROOM_TYPES).index(room_value)
						if room_value in (["Any"] + ROOM_TYPES)
						else 0,
						key=f"course_update_room_{edit_course_code}",
					)
					updated_submit = st.form_submit_button("Update Course", use_container_width=True)

				if updated_submit:
					if not updated_title.strip():
						st.error("Course title is required.")
					else:
						updated_course = Course(
							title=updated_title.strip(),
							short_code=edit_course.short_code,
							credit_hours=float(updated_credit),
							required_duration=int(updated_duration),
							required_room_type=None if updated_room == "Any" else updated_room,
						)
						if dm.update_course(updated_course, courses):
							st.success("Course updated.")
							st.rerun()
						else:
							st.error("Could not update course.")

		st.subheader("Delete Course")
		if courses:
			delete_course_code = st.selectbox(
				"Select course to delete",
				options=[c.short_code for c in courses],
				key="delete_course_select",
			)
			if st.button("Delete Selected Course", type="secondary", use_container_width=True):
				if dm.delete_course(delete_course_code, courses):
					st.success("Course deleted.")
					st.rerun()
				else:
					st.error("Could not delete course.")
		else:
			st.caption("No courses available.")

	with right:
		st.subheader("Course List")
		rows = [
			{
				"Title": c.title,
				"Code": c.short_code,
				"Credit Hours": c.credit_hours,
				"Duration": c.required_duration,
				"Room Type": c.required_room_type or "Any",
			}
			for c in courses
		]
		st.dataframe(rows, use_container_width=True, hide_index=True)


def render_sections(data: Dict[str, List]) -> None:
	st.header("Sections")
	dm: DataManager = st.session_state.data_manager
	sections: List[Section] = data["sections"]
	classroom_codes = [c.short_code for c in data["classrooms"]]

	left, right = st.columns([1, 1.2])
	with left:
		st.subheader("Add Section")
		if not classroom_codes:
			st.warning("Add classrooms first to assign a home classroom.")

		with st.form("add_section_form"):
			full_name = st.text_input("Section Full Name")
			short_code = st.text_input("Section Short Code")
			num_students = st.number_input("Number of Students", min_value=1, step=1, value=40)
			home_room = st.selectbox(
				"Home Classroom",
				options=classroom_codes if classroom_codes else [""],
				disabled=not classroom_codes,
			)
			subsections = st.number_input("Subsections", min_value=1, step=1, value=1)
			submitted = st.form_submit_button("Add Section", use_container_width=True)

		if submitted:
			if not classroom_codes:
				st.error("You must create at least one classroom first.")
			elif not full_name.strip() or not short_code.strip():
				st.error("Section full name and short code are required.")
			else:
				section = Section(
					full_name=full_name.strip(),
					short_code=short_code.strip(),
					num_students=int(num_students),
					home_classroom_code=home_room,
					subsections=int(subsections),
				)
				if dm.add_section(section, sections):
					st.success("Section added successfully.")
					st.rerun()
				else:
					st.error("A section with this short code already exists.")

		st.subheader("Update Section")
		if sections:
			edit_section_code = st.selectbox(
				"Select section to update",
				options=[s.short_code for s in sections],
				key="update_section_select",
			)
			edit_section = next((s for s in sections if s.short_code == edit_section_code), None)

			if edit_section:
				with st.form("update_section_form"):
					updated_full_name = st.text_input(
						"Section Full Name (Update)",
						value=edit_section.full_name,
						key=f"section_update_name_{edit_section_code}",
					)
					updated_short_code = st.text_input(
						"Section Short Code (Update)",
						value=edit_section.short_code,
						key=f"section_update_code_{edit_section_code}",
					)
					updated_students = st.number_input(
						"Number of Students (Update)",
						min_value=1,
						step=1,
						value=int(edit_section.num_students),
						key=f"section_update_students_{edit_section_code}",
					)
					room_index = classroom_codes.index(edit_section.home_classroom_code) if edit_section.home_classroom_code in classroom_codes else 0
					updated_home_room = st.selectbox(
						"Home Classroom (Update)",
						options=classroom_codes if classroom_codes else [""],
						index=room_index,
						disabled=not classroom_codes,
						key=f"section_update_room_{edit_section_code}",
					)
					updated_subsections = st.number_input(
						"Subsections (Update)",
						min_value=1,
						step=1,
						value=int(edit_section.subsections),
						key=f"section_update_sub_{edit_section_code}",
					)
					updated_submit = st.form_submit_button("Update Section", use_container_width=True)

				if updated_submit:
					if not classroom_codes:
						st.error("You must create at least one classroom first.")
					elif not updated_full_name.strip() or not updated_short_code.strip():
						st.error("Section full name and short code are required.")
					else:
						updated_section = Section(
							full_name=updated_full_name.strip(),
							short_code=updated_short_code.strip(),
							num_students=int(updated_students),
							home_classroom_code=updated_home_room,
							subsections=int(updated_subsections),
						)
						if dm.update_section(updated_section, sections, original_short_code=edit_section.short_code):
							st.success("Section updated.")
							st.rerun()
						else:
							st.error("Could not update section.")

		st.subheader("Delete Section")
		if sections:
			delete_section_code = st.selectbox(
				"Select section to delete",
				options=[s.short_code for s in sections],
				key="delete_section_select",
			)
			if st.button("Delete Selected Section", type="secondary", use_container_width=True):
				if dm.delete_section(delete_section_code, sections):
					st.success("Section deleted.")
					st.rerun()
				else:
					st.error("Could not delete section.")
		else:
			st.caption("No sections available.")

	with right:
		st.subheader("Section List")
		rows = [
			{
				"Full Name": s.full_name,
				"Short Code": s.short_code,
				"Students": s.num_students,
				"Home Classroom": s.home_classroom_code,
				"Subsections": s.subsections,
			}
			for s in sections
		]
		st.dataframe(rows, use_container_width=True, hide_index=True)


def render_assign_courses(data: Dict[str, List]) -> None:
	st.header("Assign Courses")
	dm: DataManager = st.session_state.data_manager

	sections: List[Section] = data["sections"]
	courses: List[Course] = data["courses"]
	teachers: List[Teacher] = data["teachers"]
	classrooms: List[Classroom] = data["classrooms"]
	assignments: List[CourseAssignment] = data["assignments"]

	if not sections or not courses or not teachers:
		st.warning("Please add sections, courses, and teachers before assigning courses.")
		return

	left, right = st.columns([1, 1.3])

	with left:
		st.subheader("Create Assignment")
		with st.form("assignment_form"):
			section_choice = st.selectbox("Section", [s.short_code for s in sections])
			section_obj = next((s for s in sections if s.short_code == section_choice), None)

			subsection_mode = "All"
			if section_obj and section_obj.subsections > 1:
				subsection_options = ["All"] + [f"S{i}" for i in range(1, section_obj.subsections + 1)]
				subsection_mode = st.selectbox("Target", subsection_options)

			course_choice = st.selectbox("Course", [c.short_code for c in courses])
			teacher_choice = st.selectbox("Teacher", [t.short_name for t in teachers])

			room_options = ["Auto Select"] + [room.short_code for room in classrooms]
			room_choice = st.selectbox("Preferred Room", room_options)
			preferred_day = st.selectbox("Preferred Day", ASSIGN_DAY_OPTIONS)
			preferred_time = st.selectbox("Preferred Time Slot (start)", PREFERRED_START_TIMES)
			sessions_per_week = st.number_input("Sessions per Week", min_value=1, max_value=7, step=1, value=1)
			submitted = st.form_submit_button("Add Assignment", use_container_width=True)

		if submitted:
			section_name = section_choice
			if subsection_mode != "All":
				section_name = f"{section_choice}-{subsection_mode}"

			selected_course = next((c for c in courses if c.short_code == course_choice), None)
			if not selected_course:
				st.error("Selected course not found.")
				return

			scheduled_slots, slot_error = _build_preferred_scheduled_slots(
				preferred_day,
				preferred_time,
				int(selected_course.required_duration),
			)
			if slot_error:
				st.error(slot_error)
				return

			assignment = CourseAssignment(
				course_code=course_choice,
				section_name=section_name,
				teacher_short_name=teacher_choice,
				classroom_code="" if room_choice == "Auto Select" else room_choice,
				sessions_per_week=int(sessions_per_week),
				scheduled_slots=scheduled_slots,
			)
			if dm.add_course_assignment(assignment, assignments):
				st.success("Assignment added successfully.")
				st.rerun()
			else:
				st.error("This assignment already exists.")

		st.subheader("Update Assignment")
		if assignments:
			edit_idx = st.selectbox(
				"Select assignment to update",
				options=list(range(len(assignments))),
				format_func=lambda i: (
					f"#{i} | {assignments[i].section_name} -> {assignments[i].course_code} ({assignments[i].teacher_short_name})"
				),
				key="assignment_update_index",
			)
			current = assignments[edit_idx]
			section_codes = [s.short_code for s in sections]
			default_base_section, default_sub = _split_assignment_section_target(current.section_name, section_codes)
			default_preferred_day = "No Preference"
			default_preferred_time = "No Preference"
			if current.scheduled_slots:
				first_day, first_slot = current.scheduled_slots[0]
				default_preferred_day = ASSIGN_DAY_FROM_FULL.get(first_day, "No Preference")
				default_preferred_time = first_slot.start_time if first_slot.start_time in PREFERRED_START_TIMES else "No Preference"

			with st.form("assignment_update_form"):
				update_section = st.selectbox(
					"Section (Update)",
					section_codes,
					index=section_codes.index(default_base_section)
					if default_base_section in section_codes
					else 0,
					key=f"assignment_update_section_{edit_idx}",
				)

				update_section_obj = next((s for s in sections if s.short_code == update_section), None)
				update_subsection_mode = "All"
				if update_section_obj and update_section_obj.subsections > 1:
					sub_options = ["All"] + [f"S{i}" for i in range(1, update_section_obj.subsections + 1)]
					default_sub_index = sub_options.index(default_sub) if default_sub in sub_options else 0
					update_subsection_mode = st.selectbox(
						"Target (Update)",
						sub_options,
						index=default_sub_index,
						key=f"assignment_update_sub_{edit_idx}",
					)

				course_codes = [c.short_code for c in courses]
				teacher_codes = [t.short_name for t in teachers]
				room_codes = [room.short_code for room in classrooms]
				room_values = ["Auto Select"] + room_codes

				update_course = st.selectbox(
					"Course (Update)",
					course_codes,
					index=course_codes.index(current.course_code) if current.course_code in course_codes else 0,
					key=f"assignment_update_course_{edit_idx}",
				)
				update_teacher = st.selectbox(
					"Teacher (Update)",
					teacher_codes,
					index=teacher_codes.index(current.teacher_short_name)
					if current.teacher_short_name in teacher_codes
					else 0,
					key=f"assignment_update_teacher_{edit_idx}",
				)

				current_room = current.classroom_code if current.classroom_code else "Auto Select"
				update_room = st.selectbox(
					"Preferred Room (Update)",
					room_values,
					index=room_values.index(current_room) if current_room in room_values else 0,
					key=f"assignment_update_room_{edit_idx}",
				)
				update_sessions = st.number_input(
					"Sessions per Week (Update)",
					min_value=1,
					max_value=7,
					step=1,
					value=int(current.sessions_per_week),
					key=f"assignment_update_sessions_{edit_idx}",
				)
				update_preferred_day = st.selectbox(
					"Preferred Day (Update)",
					ASSIGN_DAY_OPTIONS,
					index=ASSIGN_DAY_OPTIONS.index(default_preferred_day)
					if default_preferred_day in ASSIGN_DAY_OPTIONS
					else 0,
					key=f"assignment_update_day_{edit_idx}",
				)
				update_preferred_time = st.selectbox(
					"Preferred Time Slot (start) (Update)",
					PREFERRED_START_TIMES,
					index=PREFERRED_START_TIMES.index(default_preferred_time)
					if default_preferred_time in PREFERRED_START_TIMES
					else 0,
					key=f"assignment_update_time_{edit_idx}",
				)

				update_submit = st.form_submit_button("Update Assignment", use_container_width=True)

			if update_submit:
				updated_section_name = update_section
				if update_subsection_mode != "All":
					updated_section_name = f"{update_section}-{update_subsection_mode}"

				duplicate_exists = any(
					i != edit_idx
					and a.course_code == update_course
					and a.section_name == updated_section_name
					and a.teacher_short_name == update_teacher
					for i, a in enumerate(assignments)
				)
				if duplicate_exists:
					st.error("Another assignment with the same section, course, and teacher already exists.")
				else:
					updated_course_obj = next((c for c in courses if c.short_code == update_course), None)
					if not updated_course_obj:
						st.error("Selected course not found.")
						return

					updated_slots, slot_error = _build_preferred_scheduled_slots(
						update_preferred_day,
						update_preferred_time,
						int(updated_course_obj.required_duration),
					)
					if slot_error:
						st.error(slot_error)
						return

					assignments[edit_idx] = CourseAssignment(
						course_code=update_course,
						section_name=updated_section_name,
						teacher_short_name=update_teacher,
						classroom_code="" if update_room == "Auto Select" else update_room,
						sessions_per_week=int(update_sessions),
						scheduled_slots=updated_slots,
					)
					dm.save_course_assignments(assignments)
					st.success("Assignment updated.")
					st.rerun()

	with right:
		st.subheader("Existing Assignments")
		rows = assignment_table_rows(assignments)
		st.dataframe(rows, use_container_width=True, hide_index=True)

		if assignments:
			st.markdown("#### Delete Assignment")
			delete_idx = st.selectbox(
				"Choose assignment row (#)",
				options=[row["#"] for row in rows],
				format_func=lambda i: f"#{i} | {rows[i]['Section']} -> {rows[i]['Course']} ({rows[i]['Teacher']})",
			)
			if st.button("Delete Selected Assignment", type="secondary"):
				target = assignments[delete_idx]
				if dm.delete_course_assignment(target, assignments):
					st.success("Assignment deleted.")
					st.rerun()
				else:
					st.error("Failed to delete assignment.")


def render_generate_routine(data: Dict[str, List]) -> None:
	st.header("Generate Routine")

	classrooms = data["classrooms"]
	teachers = data["teachers"]
	courses = data["courses"]
	sections = data["sections"]
	assignments = data["assignments"]

	c1, c2, c3 = st.columns(3)
	c1.metric("Assignments", len(assignments))
	c2.metric("Available Teachers", len(teachers))
	c3.metric("Available Rooms", len(classrooms))

	if st.button("Generate Routine Now", type="primary", use_container_width=True):
		if not classrooms or not teachers or not courses or not sections:
			st.error("Please add classrooms, teachers, courses, and sections first.")
		elif not assignments:
			st.error("Please add course assignments first.")
		else:
			try:
				generator = RoutineGenerator(
					classrooms,
					teachers,
					courses,
					sections,
					course_assignments=assignments,
				)
				candidate_routine = generator.generate()
				if candidate_routine.conflicts:
					st.error("Routine generation blocked. Resolve all conflicts before generating the routine.")
					for conflict in candidate_routine.conflicts:
						st.error(conflict)
				else:
					st.session_state.routine = candidate_routine
					st.session_state.data_manager.save_routine(candidate_routine)
					st.session_state.pdf_bytes = None
					st.success("Routine generated successfully.")
			except Exception as exc:
				st.error(f"Failed to generate routine: {exc}")

	routine: Routine = st.session_state.routine
	st.markdown("### Generation Summary")
	s1, s2, s3 = st.columns(3)
	s1.metric("Scheduled Entries", len(routine.entries))
	s2.metric("Conflicts", len(routine.conflicts))
	s3.metric("Assignments Snapshot", len(routine.course_assignments))

	if routine.conflicts:
		st.markdown("### Conflicts")
		for conflict in routine.conflicts:
			st.error(conflict)
	elif routine.entries:
		st.success("No conflicts were reported in the current routine.")

	st.markdown("### Export PDF")
	if routine.entries:
		export_col1, export_col2 = st.columns([1, 2])
		with export_col1:
			export_type = st.selectbox(
				"Export Type",
				["All", "Section", "Teacher", "Classroom", "Course"],
				key="pdf_export_type",
			)

		selected_item = ""
		with export_col2:
			if export_type == "Section":
				items = _get_section_items(data["sections"])
			elif export_type == "Teacher":
				items = [f"{t.full_name} ({t.short_name})" for t in data["teachers"]]
			elif export_type == "Classroom":
				items = [f"{c.full_name} ({c.short_code})" for c in data["classrooms"]]
			elif export_type == "Course":
				items = [f"{c.title} ({c.short_code})" for c in data["courses"]]
			else:
				items = []

			if export_type != "All":
				if not items:
					st.warning(f"No {export_type.lower()} records found for export.")
					selected_item = ""
				else:
					selected_item = st.selectbox("Select Item", items, key="pdf_export_item")

		if st.button("Prepare PDF", use_container_width=True):
			if export_type != "All" and not selected_item:
				st.error(f"Please select a {export_type.lower()} for export.")
			else:
				st.session_state.pdf_bytes = build_filtered_pdf_bytes(
					routine,
					data,
					export_type,
					selected_item,
				)

		if st.session_state.pdf_bytes:
			if export_type == "All":
				filename = "routine_all.pdf"
			elif export_type == "Section":
				filename = f"routine_section_{_parse_section_code(selected_item)}.pdf"
			elif export_type == "Teacher":
				filename = f"routine_teacher_{selected_item.split('(')[-1].rstrip(')')}.pdf"
			elif export_type == "Classroom":
				filename = f"routine_classroom_{selected_item.split('(')[-1].rstrip(')')}.pdf"
			else:
				filename = f"routine_course_{selected_item.split('(')[-1].rstrip(')')}.pdf"

			st.download_button(
				label="Download Routine PDF",
				data=st.session_state.pdf_bytes,
				file_name=filename,
				mime="application/pdf",
				use_container_width=True,
			)
	else:
		st.info("Generate a routine first to export PDF.")


def _get_section_items(sections: List[Section]) -> List[str]:
	return [section.display_name for section in sections]


def _parse_section_code(display_value: str) -> str:
	if "(" in display_value and display_value.endswith(")"):
		return display_value.split("(")[-1].rstrip(")")
	return display_value


def _filter_entries_for_view(
	routine: Routine,
	filter_type: str,
	selected_value: str,
) -> List:
	if filter_type == "Section":
		code = _parse_section_code(selected_value)
		prefix = f"{code}-S"
		return [
			entry
			for entry in routine.entries
			if entry.section_name == code
			or (entry.section_name.startswith(prefix) and entry.section_name[len(prefix):].isdigit())
		]

	if filter_type == "Teacher":
		code = selected_value.split("(")[-1].rstrip(")")
		return [entry for entry in routine.entries if entry.teacher_short_name == code]

	if filter_type == "Classroom":
		code = selected_value.split("(")[-1].rstrip(")")
		return [entry for entry in routine.entries if entry.classroom_code == code]

	if filter_type == "Course":
		code = selected_value.split("(")[-1].rstrip(")")
		return [entry for entry in routine.entries if entry.course_code == code]

	return []


def _cell_text(filter_type: str, entry) -> str:
	if filter_type == "Section":
		return f"{entry.course_code}\n{entry.teacher_short_name}\n{entry.classroom_code}"
	if filter_type == "Teacher":
		return f"{entry.course_code}\n{entry.section_name}\n{entry.classroom_code}"
	if filter_type == "Classroom":
		return f"{entry.course_code}\n{entry.section_name}\n{entry.teacher_short_name}"
	return f"{entry.section_name}\n{entry.teacher_short_name}\n{entry.classroom_code}"


def _render_timetable_grid(filtered_entries, filter_type: str) -> None:
	"""Render a professional HTML/CSS timetable grid with time slots as columns and weekdays as rows."""
	days_header = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
	slot_defs = _slot_label_and_minutes()
	
	# Build the grid structure - time slots as columns, days as rows
	html_rows = []
	html_rows.append('<thead><tr><th class="timetable-grid time-slot-col">Day</th>')
	for slot_label, _, _ in slot_defs:
		html_rows.append(f'<th class="timetable-grid slot-col">{slot_label}</th>')
	html_rows.append('</tr></thead><tbody>')
	
	# Create a row for each day
	for day in days_header:
		html_rows.append('<tr>')
		html_rows.append(f'<td class="timetable-grid time-slot-col">{day}</td>')
		
		# Create a column for each time slot
		for slot_label, slot_start, slot_end in slot_defs:
			matches = [
				_cell_text(filter_type, entry)
				for entry in filtered_entries
				if entry.day == day
				and _entry_overlaps_slot(entry.time_slot.start_time, entry.time_slot.end_time, slot_start, slot_end)
			]
			
			cell_content = ""
			for match in matches:
				cell_content += f'<div class="class-entry">{match}</div>'
			
			html_rows.append(f'<td class="timetable-grid"><div class="slot-cell">{cell_content}</div></td>')
		
		html_rows.append('</tr>')
	
	html_rows.append('</tbody>')
	html_table = '<table class="timetable-grid">' + ''.join(html_rows) + '</table>'
	st.markdown(html_table, unsafe_allow_html=True)


def render_view_timetables(data: Dict[str, List]) -> None:
	st.header("📅 View Timetables")
	routine: Routine = st.session_state.routine

	if not routine.entries:
		st.warning("📭 No generated routine found. Go to **Generate Routine** page first.")
		return

	filter_col, item_col = st.columns([1, 2])
	with filter_col:
		filter_type = st.selectbox("📊 View By", ["Section", "Teacher", "Classroom", "Course"])

	with item_col:
		if filter_type == "Section":
			items = _get_section_items(data["sections"])
		elif filter_type == "Teacher":
			items = [f"{t.full_name} ({t.short_name})" for t in data["teachers"]]
		elif filter_type == "Classroom":
			items = [f"{c.full_name} ({c.short_code})" for c in data["classrooms"]]
		else:
			items = [f"{c.title} ({c.short_code})" for c in data["courses"]]

		if not items:
			st.warning(f"❌ No {filter_type.lower()} records available.")
			return

		selected_item = st.selectbox("🔍 Select Item", items)

	filtered_entries = _filter_entries_for_view(routine, filter_type, selected_item)
	if not filtered_entries:
		st.warning(f"⏰ No scheduled classes for {selected_item}.")
		return

	st.markdown("### 🕐 Weekly Timetable Grid")
	st.caption("Time slots in columns, weekdays in rows")
	_render_timetable_grid(filtered_entries, filter_type)

	st.markdown("### 📋 Detailed Schedule Entries")
	days = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
	detail_rows = [
		{
			"🗓️ Day": entry.day,
			"⏱️ Time": f"{entry.time_slot.start_time}-{entry.time_slot.end_time}",
			"📚 Section": entry.section_name,
			"📖 Course": entry.course_code,
			"👨‍🏫 Teacher": entry.teacher_short_name,
			"🏛️ Classroom": entry.classroom_code,
		}
		for entry in sorted(
			filtered_entries,
			key=lambda e: (days.index(e.day) if e.day in days else 99, e.time_slot.start_time),
		)
	]
	st.dataframe(detail_rows, use_container_width=True, hide_index=True)


def main() -> None:
	ensure_state()
	apply_app_styles()
	show_missing_file_notice()

	st.title("📅 University Routine Generator")
	st.caption("Automated class scheduling system")

	page = _render_horizontal_navigation()

	data = load_data()

	if page == "Dashboard":
		render_dashboard(data)
	elif page == "Classrooms":
		render_classrooms(data)
	elif page == "Teachers":
		render_teachers(data)
	elif page == "Courses":
		render_courses(data)
	elif page == "Sections":
		render_sections(data)
	elif page == "Assign Courses":
		render_assign_courses(data)
	elif page == "Generate Routine":
		render_generate_routine(data)
	elif page == "View Timetables":
		render_view_timetables(data)


if __name__ == "__main__":
	main()
