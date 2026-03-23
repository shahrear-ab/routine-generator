"""
PDF Generator for exporting routines using ReportLab
Creates professional timetables in PDF format
"""

from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from typing import Dict, List, Optional, Tuple
from models import Routine, Course, Teacher, Classroom, Section, RoutineEntry, TimeSlot


class PDFGenerator:
    """Generates PDF documents from routine data"""

    DAYS_ORDER = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    DAY_SHORT = {
        "Saturday": "Sa",
        "Sunday": "Su",
        "Monday": "Mo",
        "Tuesday": "Tu",
        "Wednesday": "We",
        "Thursday": "Th",
        "Friday": "Fr",
    }
    
    def __init__(self, routine: Routine, courses: List[Course], 
                 teachers: List[Teacher], classrooms: List[Classroom], 
                 sections: List[Section]):
        self.routine = routine
        self.courses = courses
        self.teachers = teachers
        self.classrooms = classrooms
        self.sections = sections

    def _get_section_by_code(self, section_code: str):
        """Find a section by its code, including subsection-derived codes."""
        for section in self.sections:
            if section.short_code == section_code:
                return section

        if "-S" in section_code:
            base_code = section_code.rsplit("-S", 1)[0]
            for section in self.sections:
                if section.short_code == base_code:
                    return section
        return None

    @staticmethod
    def _section_part_from_full_name(full_name: str) -> str:
        """Return section part from full_name (last token), e.g., 'Civil Engineering B' -> 'B'."""
        tokens = full_name.strip().split()
        return tokens[-1] if tokens else ""

    def _section_part(self, section: Section) -> str:
        """Return section part for a section, preferring full_name and falling back to short_code."""
        from_name = self._section_part_from_full_name(section.full_name)
        if from_name:
            return from_name
        if "-" in section.short_code:
            return section.short_code.rsplit("-", 1)[-1]
        return section.short_code

    def _get_section_display_name(self, section_code: str) -> str:
        """Format a readable section label using full name and code."""
        section = self._get_section_by_code(section_code)
        if not section:
            return section_code

        if section.short_code == section_code:
            return section.display_name

        suffix = section_code[len(section.short_code):]
        if suffix.startswith("-S"):
            subsection_number = suffix[2:]
            section_part = self._section_part(section)
            return f"{section.full_name} {section_part}{subsection_number} ({section_code})"

        return f"{section.full_name} ({section_code})"

    @staticmethod
    def _time_to_minutes(value: str) -> int:
        hour, minute = map(int, value.split(":"))
        return hour * 60 + minute

    def _entry_interval(self, entry: RoutineEntry) -> Tuple[int, int]:
        return (self._time_to_minutes(entry.time_slot.start_time), self._time_to_minutes(entry.time_slot.end_time))

    def _slot_definitions(self):
        # Teaching columns (1st..9th) with a dedicated visual break column added separately.
        return [
            ("1st", "8:00 - 8:50", 1, "08:00", "08:50"),
            ("2nd", "9:00 - 9:50", 2, "09:00", "09:50"),
            ("3rd", "10:00 - 10:50", 3, "10:00", "10:50"),
            ("4th", "11:00 - 11:50", 4, "11:00", "11:50"),
            ("5th", "12:00 - 12:50", 5, "12:00", "12:50"),
            ("6th", "13:00 - 13:30", 6, "13:00", "13:30"),
            ("7th", "2:00 - 2:50", 8, "14:00", "14:50"),
            ("8th", "3:00 - 3:50", 9, "15:00", "15:50"),
            ("9th", "4:00 - 4:50", 10, "16:00", "16:50"),
        ]

    def _occupied_teaching_columns(self, entry: RoutineEntry) -> List[int]:
        start_min, end_min = self._entry_interval(entry)
        columns = []
        for _, _, col_idx, slot_start, slot_end in self._slot_definitions():
            slot_start_min = self._time_to_minutes(slot_start)
            slot_end_min = self._time_to_minutes(slot_end)
            if start_min < slot_end_min and slot_start_min < end_min:
                columns.append(col_idx)
        return sorted(columns)

    def _split_contiguous_segments(self, columns: List[int]) -> List[List[int]]:
        if not columns:
            return []
        segments = [[columns[0]]]
        for col in columns[1:]:
            prev = segments[-1][-1]
            # Keep break column (7) as a hard separator between 6th and 7th periods.
            if col == prev + 1 and not (prev == 6 and col == 8):
                segments[-1].append(col)
            else:
                segments.append([col])
        return segments

    @staticmethod
    def _overlap(interval_a: Tuple[int, int], interval_b: Tuple[int, int]) -> bool:
        return interval_a[0] < interval_b[1] and interval_b[0] < interval_a[1]

    def _build_day_lanes(self, entries: List[RoutineEntry]) -> List[List[RoutineEntry]]:
        lanes: List[List[RoutineEntry]] = []
        sorted_entries = sorted(
            entries,
            key=lambda e: (
                self._time_to_minutes(e.time_slot.start_time),
                -self._time_to_minutes(e.time_slot.end_time),
                e.course_code,
            ),
        )
        for entry in sorted_entries:
            interval = self._entry_interval(entry)
            placed = False
            for lane in lanes:
                if all(not self._overlap(interval, self._entry_interval(existing)) for existing in lane):
                    lane.append(entry)
                    placed = True
                    break
            if not placed:
                lanes.append([entry])
        return lanes or [[]]

    def _extract_group_label(self, section_name: str) -> str:
        label = self._get_subsection_label(section_name)
        return f"Group {label}" if label else ""

    def _get_subsection_label(self, section_name: str) -> str:
        """Return subsection label like 'C1', 'C2', ... based on the parent section name."""
        if "-S" not in section_name:
            return ""
        parent = self._get_section_by_code(section_name)
        suffix = section_name.rsplit("-S", 1)[-1]
        if parent and suffix.isdigit():
            return f"{self._section_part(parent)}{suffix}"
        return ""

    def _entry_text(self, entry: RoutineEntry, filter_type: str) -> str:
        if filter_type == "Section":
            sub = self._get_subsection_label(entry.section_name)
            extra = f"<br/><font size='7'><b>[{sub}]</b></font>" if sub else ""
            return f"<b>{entry.course_code}</b><br/><font size='7'>{entry.classroom_code}</font><br/><font size='7'>{entry.teacher_short_name}</font>{extra}"
        if filter_type == "Teacher":
            group = self._extract_group_label(entry.section_name)
            section_label = self._get_section_display_name(entry.section_name)
            extra = f"<br/><font size='7'>{group}</font>" if group else ""
            return f"<b>{entry.course_code}</b><br/><font size='7'>{section_label}</font><br/><font size='7'>{entry.classroom_code}</font>{extra}"
        if filter_type == "Classroom":
            group = self._extract_group_label(entry.section_name)
            section_label = self._get_section_display_name(entry.section_name)
            extra = f"<br/><font size='7'>{group}</font>" if group else ""
            return f"<b>{entry.course_code}</b><br/><font size='7'>{section_label}</font><br/><font size='7'>{entry.teacher_short_name}</font>{extra}"
        group = self._extract_group_label(entry.section_name)
        section_label = self._get_section_display_name(entry.section_name)
        extra = f"<br/><font size='7'>{group}</font>" if group else ""
        return f"<b>{section_label}</b><br/><font size='7'>{entry.classroom_code}</font><br/><font size='7'>{entry.teacher_short_name}</font>{extra}"

    def _build_reference_grid(self, filtered_entries: List[RoutineEntry], filter_type: str):
        styles = getSampleStyleSheet()
        header_style = ParagraphStyle(
            "GridHeader",
            parent=styles["Normal"],
            alignment=1,
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=10,
            textColor=colors.HexColor("#0f172a"),
        )
        cell_style = ParagraphStyle(
            "GridCell",
            parent=styles["Normal"],
            alignment=1,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#111827"),
        )

        data: List[List[object]] = []
        style_cmds: List[Tuple] = []

        header_row = [""]
        for slot_name, slot_time, col_idx, _, _ in self._slot_definitions():
            while len(header_row) < col_idx:
                header_row.append("")
            header_row.append(Paragraph(f"<b>{slot_name}</b><br/><font size='7'>{slot_time}</font>", header_style))
            if col_idx == 6:
                header_row.append(Paragraph("<b>Break</b><br/><font size='7'>1:30 - 2:00</font>", header_style))

        data.append(header_row)

        for day in self.DAYS_ORDER:
            day_entries = [entry for entry in filtered_entries if entry.day == day]
            lanes = self._build_day_lanes(day_entries)
            day_start_row = len(data)

            for lane_idx, lane_entries in enumerate(lanes):
                row = [self.DAY_SHORT.get(day, day[:2]) if lane_idx == 0 else ""] + [""] * 10
                occupied = [False] * 11

                for entry in lane_entries:
                    columns = self._occupied_teaching_columns(entry)
                    if not columns:
                        continue
                    for segment in self._split_contiguous_segments(columns):
                        start_col = segment[0]
                        end_col = segment[-1]
                        if any(occupied[idx] for idx in range(start_col, end_col + 1)):
                            continue

                        row[start_col] = Paragraph(self._entry_text(entry, filter_type), cell_style)
                        for idx in range(start_col, end_col + 1):
                            occupied[idx] = True
                        if end_col > start_col:
                            style_cmds.append(("SPAN", (start_col, len(data)), (end_col, len(data))))

                row[7] = ""
                data.append(row)

            if len(lanes) > 1:
                style_cmds.append(("SPAN", (0, day_start_row), (0, len(data) - 1)))

        if len(data) > 1:
            style_cmds.append(("SPAN", (7, 1), (7, len(data) - 1)))

        col_widths = [0.7 * inch] + [0.73 * inch] * 6 + [0.62 * inch] + [0.73 * inch] * 3
        row_heights = [0.55 * inch] + [0.85 * inch] * (len(data) - 1)

        table = Table(data, colWidths=col_widths, rowHeights=row_heights, repeatRows=1)
        base_style = [
            ("GRID", (0, 0), (-1, -1), 0.55, colors.HexColor("#1f2937")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 1), (0, -1), 22),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
            ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#f5f5f5")),
            ("BACKGROUND", (7, 1), (7, -1), colors.HexColor("#f5f5f5")),
            ("BACKGROUND", (7, 0), (7, 0), colors.HexColor("#ebedf0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        table.setStyle(TableStyle(base_style + style_cmds))
        return table
    
    def generate_pdf(self, file_path: str):
        """Generate complete PDF with all timetables"""
        doc = SimpleDocTemplate(file_path, pagesize=A4, 
                               rightMargin=0.5*inch, leftMargin=0.5*inch,
                               topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        story = []
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#0f172a"),
            alignment=1,
            spaceAfter=10,
        )

        story.append(Paragraph("AUTOMATED CLASS ROUTINE", title_style))
        story.append(Spacer(1, 0.15 * inch))

        # One timetable per parent section (subsection entries are merged inside).
        for section in self.sections:
            rows = self._generate_grid_timetable("Section", section.short_code, display_name=section.display_name)
            if rows:
                story.extend(rows)
                story.append(PageBreak())

        for teacher in self.teachers:
            rows = self._generate_grid_timetable(
                "Teacher",
                teacher.short_name,
                display_name=f"{teacher.full_name} ({teacher.short_name})",
            )
            if rows:
                story.extend(rows)
                story.append(PageBreak())

        for classroom in self.classrooms:
            rows = self._generate_grid_timetable(
                "Classroom",
                classroom.short_code,
                display_name=f"{classroom.full_name} ({classroom.short_code})",
            )
            if rows:
                story.extend(rows)
                story.append(PageBreak())

        for course in self.courses:
            rows = self._generate_grid_timetable(
                "Course",
                course.short_code,
                display_name=f"{course.title} ({course.short_code})",
            )
            if rows:
                story.extend(rows)
                story.append(PageBreak())

        doc.build(story)
    
    def _generate_section_timetable(self, section: Section, heading_style) -> list:
        """Generate timetable for a section"""
        story = []
        story.append(Paragraph(f"SECTION: {section.display_name}", heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        entries = [e for e in self.routine.entries if e.section_name == section.short_code]
        
        if not entries:
            story.append(Paragraph("No classes assigned.", ParagraphStyle('Normal', fontSize=10)))
            return story
        
        # Group by day
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        for day in days:
            day_entries = [e for e in entries if e.day == day]
            if day_entries:
                story.append(self._create_day_table(day, day_entries))
                story.append(Spacer(1, 0.15*inch))
        
        return story
    
    def _generate_teacher_timetable(self, teacher: Teacher, heading_style) -> list:
        """Generate timetable for a teacher"""
        story = []
        story.append(Paragraph(f"TEACHER: {teacher.full_name} ({teacher.short_name})", heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        entries = [e for e in self.routine.entries if e.teacher_short_name == teacher.short_name]
        
        if not entries:
            story.append(Paragraph("No classes assigned.", ParagraphStyle('Normal', fontSize=10)))
            return story
        
        # Group by day
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        total_hours = sum(e.time_slot.duration_hours() for e in entries)
        story.append(Paragraph(f"Total Hours: {total_hours}", ParagraphStyle('Normal', fontSize=9)))
        story.append(Spacer(1, 0.05*inch))
        
        for day in days:
            day_entries = [e for e in entries if e.day == day]
            if day_entries:
                story.append(self._create_day_table(day, day_entries))
                story.append(Spacer(1, 0.15*inch))
        
        return story
    
    def _generate_classroom_timetable(self, classroom: Classroom, heading_style) -> list:
        """Generate timetable for a classroom"""
        story = []
        story.append(Paragraph(f"CLASSROOM: {classroom.full_name} ({classroom.short_code})", heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        entries = [e for e in self.routine.entries if e.classroom_code == classroom.short_code]
        
        if not entries:
            story.append(Paragraph("No classes assigned.", ParagraphStyle('Normal', fontSize=10)))
            return story
        
        # Group by day
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        for day in days:
            day_entries = [e for e in entries if e.day == day]
            if day_entries:
                story.append(self._create_day_table(day, day_entries))
                story.append(Spacer(1, 0.15*inch))
        
        return story
    
    def _generate_course_timetable(self, course: Course, heading_style) -> list:
        """Generate timetable for a course"""
        story = []
        story.append(Paragraph(f"COURSE: {course.title} ({course.short_code})", heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        entries = [e for e in self.routine.entries if e.course_code == course.short_code]
        
        if not entries:
            story.append(Paragraph("No sections assigned.", ParagraphStyle('Normal', fontSize=10)))
            return story
        
        # Group by day
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        for day in days:
            day_entries = [e for e in entries if e.day == day]
            if day_entries:
                story.append(self._create_day_table(day, day_entries))
                story.append(Spacer(1, 0.15*inch))
        
        return story
    
    def _create_day_table(self, day: str, entries: List[RoutineEntry]) -> Table:
        """Create a table for a specific day"""
        # Sort by time
        entries.sort(key=lambda e: e.time_slot.start_time)
        
        # Header
        table_data = [[f"{day}", "Time", "Section", "Course", "Teacher", "Classroom"]]
        
        # Add entries
        for i, entry in enumerate(entries):
            time_str = f"{entry.time_slot.start_time} - {entry.time_slot.end_time}"
            row = [
                "" if i > 0 else day,
                time_str,
                self._get_section_display_name(entry.section_name),
                entry.course_code,
                entry.teacher_short_name,
                entry.classroom_code
            ]
            table_data.append(row)
        
        # Create table
        table = Table(table_data, colWidths=[0.8*inch, 1*inch, 1*inch, 0.8*inch, 0.8*inch, 0.8*inch])
        
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F0')])
        ]))
        
        return table    
    def _generate_grid_timetable(self, filter_type: str, filter_value: str, display_name: Optional[str] = None) -> list:
        """Generate grid-based timetable for any filter type"""
        story = []

        if filter_type == "Section":
            # Include both whole-section entries (section_name == filter_value) and
            # subsection-specific entries (section_name == filter_value-S1, -S2, …).
            prefix = filter_value + "-S"
            filtered_entries = [
                e for e in self.routine.entries
                if e.section_name == filter_value
                or (e.section_name.startswith(prefix) and e.section_name[len(prefix):].isdigit())
            ]
            main_title = display_name or self._get_section_display_name(filter_value)
        elif filter_type == "Teacher":
            filtered_entries = [e for e in self.routine.entries if e.teacher_short_name == filter_value]
            main_title = display_name or filter_value
        elif filter_type == "Classroom":
            filtered_entries = [e for e in self.routine.entries if e.classroom_code == filter_value]
            main_title = display_name or filter_value
        elif filter_type == "Course":
            filtered_entries = [e for e in self.routine.entries if e.course_code == filter_value]
            main_title = display_name or filter_value
        else:
            return story

        if not filtered_entries:
            return story

        styles = getSampleStyleSheet()
        top_style = ParagraphStyle(
            "TopMeta",
            parent=styles["Normal"],
            alignment=1,
            fontSize=10,
            textColor=colors.HexColor("#111827"),
        )
        main_style = ParagraphStyle(
            "MainTitle",
            parent=styles["Heading1"],
            alignment=1,
            fontSize=24,
            textColor=colors.HexColor("#111827"),
            spaceAfter=8,
        )
        footer_style = ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#374151"),
        )

        story.append(Paragraph("Final Routine (Term: July 2025)", top_style))
        story.append(Paragraph(main_title, main_style))
        story.append(self._build_reference_grid(filtered_entries, filter_type))

        generated_on = datetime.now().strftime("%m/%d/%Y")
        footer = Table(
            [[Paragraph(f"Timetable generated: {generated_on}", footer_style), Paragraph("Automated Routine Generator by Grp-1 ,ME-C2", footer_style)]],
            colWidths=[5.5 * inch, 2.0 * inch],
        )
        footer.setStyle(TableStyle([
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(footer)
        story.append(Spacer(1, 0.1 * inch))
        return story

    def generate_section_pdf(self, file_path: str, section_name: str, display_name: str = None):
        """Generate PDF for a single section's timetable"""
        doc = SimpleDocTemplate(file_path, pagesize=A4, 
                               rightMargin=0.5*inch, leftMargin=0.5*inch,
                               topMargin=0.5*inch, bottomMargin=0.5*inch)

        story = self._generate_grid_timetable("Section", section_name, display_name=display_name)
        if not story:
            styles = getSampleStyleSheet()
            story = [Paragraph("No classes scheduled for this section.", styles["Normal"])]
        doc.build(story)
    
    def generate_teacher_pdf(self, file_path: str, teacher_short_name: str, display_name: str):
        """Generate PDF for a single teacher's timetable"""
        doc = SimpleDocTemplate(file_path, pagesize=A4, 
                               rightMargin=0.5*inch, leftMargin=0.5*inch,
                               topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        story = self._generate_grid_timetable("Teacher", teacher_short_name, display_name=display_name)
        if not story:
            styles = getSampleStyleSheet()
            story = [Paragraph("No classes scheduled for this teacher.", styles["Normal"])]
        doc.build(story)
    
    def generate_classroom_pdf(self, file_path: str, classroom_code: str, display_name: str):
        """Generate PDF for a single classroom's timetable"""
        doc = SimpleDocTemplate(file_path, pagesize=A4, 
                               rightMargin=0.5*inch, leftMargin=0.5*inch,
                               topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        story = self._generate_grid_timetable("Classroom", classroom_code, display_name=display_name)
        if not story:
            styles = getSampleStyleSheet()
            story = [Paragraph("No classes scheduled for this classroom.", styles["Normal"])]
        doc.build(story)

    def generate_course_pdf(self, file_path: str, course_code: str, display_name: str):
        """Generate PDF for a single course's timetable"""
        doc = SimpleDocTemplate(file_path, pagesize=A4,
                               rightMargin=0.5*inch, leftMargin=0.5*inch,
                               topMargin=0.5*inch, bottomMargin=0.5*inch)

        story = self._generate_grid_timetable("Course", course_code, display_name=display_name)
        if not story:
            styles = getSampleStyleSheet()
            story = [Paragraph("No classes scheduled for this course.", styles["Normal"])]
        doc.build(story)
