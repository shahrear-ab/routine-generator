"""
Routine Generation Engine
Implements the scheduling algorithm with conflict detection and seniority prioritization
"""

from typing import List, Dict, Tuple, Set, Optional
from models import Classroom, Teacher, Course, Section, Routine, RoutineEntry, TimeSlot, CourseAssignment
import random


class RoutineGenerator:
    """Generates class routines with conflict detection and prioritization"""
    
    DAYS_OF_WEEK = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday"]
    WORKING_HOURS = ("08:00", "17:00")  # 8 AM to 5 PM
    BREAK_START = "13:30"
    BREAK_END = "14:00"
    
    # Teacher load per rank (hours per week)
    TEACHER_LOADS = {
        "Professor": 16,
        "Associate Prof": 18,
        "Assistant Prof": 20,
        "Lecturer": 22
    }

    # Default daily load caps per rank (hours per day)
    TEACHER_DAILY_LOADS = {
        "Professor": 4,
        "Associate Prof": 4,
        "Assistant Prof": 5,
        "Lecturer": 5
    }

    RANK_PRIORITY = {
        "Professor": 4,
        "Associate Prof": 3,
        "Assistant Prof": 2,
        "Lecturer": 1
    }

    ROOM_TYPE_ALIASES = {
        "theory": "General Classroom",
        "general classroom": "General Classroom",
        "lab": "Theory Lab",
        "theory lab": "Theory Lab",
        "sessional": "Theory Lab",
        "computer lab": "Computer Lab"
    }
    
    def __init__(self, classrooms: List[Classroom], teachers: List[Teacher],
                 courses: List[Course], sections: List[Section],
                 course_assignments: List[CourseAssignment] = None):
        self.classrooms = classrooms
        self.teachers = teachers
        self.courses = courses
        self.sections = sections
        self.course_assignments = course_assignments or []
        self.routine = Routine()
        self.classroom_schedule: Dict = {}
        self.teacher_schedule: Dict = {}
        self.section_schedule: Dict = {}
        self.expanded_sections: Dict[str, Section] = {}
    
    def generate_time_slots(self) -> List[TimeSlot]:
        """Generate all possible 1-hour, 2-hour, and 3-hour time slots for the day"""
        slots = []
        start_h, start_m = 8, 0
        end_h, end_m = 17, 0
        
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        
        # Generate slots for 1, 2, and 3 hour durations starting each hour
        for hour in range(8, 17):  # 8 AM to 4 PM (last slot ends at 5 PM)
            for duration in [1, 2, 3]:
                slot_start = hour * 60
                slot_end = slot_start + (duration * 60)
                if slot_end <= end_minutes:
                    start_str = f"{slot_start // 60:02d}:{slot_start % 60:02d}"
                    end_str = f"{slot_end // 60:02d}:{slot_end % 60:02d}"
                    candidate = TimeSlot(start_str, end_str)
                    if not self._crosses_break(candidate):
                        slots.append(candidate)
        
        return slots

    @staticmethod
    def _time_to_minutes(value: str) -> int:
        h, m = map(int, value.split(":"))
        return h * 60 + m

    def _crosses_break(self, time_slot: TimeSlot) -> bool:
        """Return True when a class spans across the break window."""
        start = self._time_to_minutes(time_slot.start_time)
        end = self._time_to_minutes(time_slot.end_time)
        break_start = self._time_to_minutes(self.BREAK_START)
        break_end = self._time_to_minutes(self.BREAK_END)
        return start < break_end and end > break_start
    
    def generate(self) -> Routine:
        """Generate the routine with conflict detection"""
        self.routine = Routine()
        self.routine.course_assignments = self.course_assignments
        self.classroom_schedule = {}
        self.teacher_schedule = {}
        self.section_schedule = {}
        self.expanded_sections = self._build_expanded_sections()
        generation_messages: List[str] = []
        
        # If no course assignments, return early
        if not self.course_assignments:
            self.routine.conflicts.append("ERROR: No course assignments defined. Please assign courses to sections and teachers first.")
            return self.routine
        
        # Ensure seniority is unique within each rank to avoid ambiguity
        self._validate_unique_seniority_levels()
        generation_messages.extend(self._validate_theory_sessions_against_credit_hours())

        # Sort teachers by rank first, then by seniority where 1 is highest priority.
        sorted_teachers = sorted(
            self.teachers,
            key=lambda t: (-self.RANK_PRIORITY.get(t.rank, 0), t.seniority_level)
        )
        
        # Generate available time slots
        time_slots = self.generate_time_slots()
        
        # Track teacher weekly and daily hours
        teacher_hours = {t.short_name: 0 for t in self.teachers}
        teacher_daily_hours = {t.short_name: {} for t in self.teachers}
        
        # First, process assignments with scheduled slots (manual scheduling)
        manual_assignments = [a for a in self.course_assignments if a.scheduled_slots]
        auto_assignments = [a for a in self.course_assignments if not a.scheduled_slots]

        manual_assignments.sort(key=lambda a: self._teacher_priority_value(a.teacher_short_name))
        auto_assignments.sort(key=lambda a: self._teacher_priority_value(a.teacher_short_name))

        expanded_manual = self._expand_assignments_for_subsections(manual_assignments)
        expanded_auto = self._expand_assignments_for_subsections(auto_assignments)
        
        # Process manual assignments first (each scheduled slot)
        for assignment in expanded_manual:
            for day, time_slot in assignment.scheduled_slots:
                if self._crosses_break(time_slot):
                    generation_messages.append(
                        f"Break conflict: {assignment.section_name} - {assignment.course_code} on {day} "
                        f"{time_slot.start_time}-{time_slot.end_time} crosses the break "
                        f"{self.BREAK_START}-{self.BREAK_END}."
                    )
                    continue

                # Find the course
                course = next((c for c in self.courses if c.short_code == assignment.course_code), None)
                if not course:
                    generation_messages.append(f"Course {assignment.course_code} not found")
                    continue
                
                # Find the teacher
                teacher = next((t for t in sorted_teachers if t.short_name == assignment.teacher_short_name), None)
                if not teacher:
                    generation_messages.append(f"Teacher {assignment.teacher_short_name} not found")
                    continue

                duration = time_slot.duration_hours()
                if not self._within_teacher_load_limits(
                    teacher,
                    day,
                    duration,
                    teacher_hours,
                    teacher_daily_hours
                ):
                    generation_messages.append(
                        f"Manual assignment skipped (teacher load exceeded): {assignment.section_name} - {assignment.course_code} "
                        f"for {teacher.short_name} on {day}"
                    )
                    continue
                
                # Find a suitable classroom
                suitable_classroom, classroom_reason = self._find_suitable_classroom_with_reason(
                    assignment.section_name,
                    course,
                    day,
                    time_slot,
                    getattr(assignment, "classroom_code", "")
                )
                
                if suitable_classroom:
                    # Check for conflicts with priority preemption
                    can_schedule, removed_entries = self._resolve_conflicts_with_priority(
                        assignment.section_name,
                        teacher.short_name,
                        suitable_classroom.short_code,
                        day,
                        time_slot
                    )
                    if can_schedule:
                        # Add entry to routine
                        entry = RoutineEntry(
                            day=day,
                            time_slot=time_slot,
                            section_name=assignment.section_name,
                            course_code=course.short_code,
                            teacher_short_name=teacher.short_name,
                            classroom_code=suitable_classroom.short_code
                        )
                        self.routine.entries.append(entry)
                        
                        # Update schedules
                        self._update_schedules(entry)
                        teacher_hours[teacher.short_name] += duration
                        teacher_daily_hours[teacher.short_name][day] = (
                            teacher_daily_hours[teacher.short_name].get(day, 0) + duration
                        )
                        for removed_entry in removed_entries:
                            removed_duration = removed_entry.time_slot.duration_hours()
                            teacher_hours[removed_entry.teacher_short_name] -= removed_duration
                            teacher_daily_hours[removed_entry.teacher_short_name][removed_entry.day] = (
                                teacher_daily_hours[removed_entry.teacher_short_name].get(removed_entry.day, 0) - removed_duration
                            )
                    else:
                        overlap_entries = self._collect_overlap_conflicts(
                            assignment.section_name,
                            teacher.short_name,
                            suitable_classroom.short_code,
                            day,
                            time_slot,
                        )
                        overlap_text = "; ".join(
                            f"{e.section_name} - {e.course_code} ({e.teacher_short_name}) "
                            f"{e.time_slot.start_time}-{e.time_slot.end_time}"
                            for e in overlap_entries
                        )
                        generation_messages.append(
                            f"Time overlap conflict: {assignment.section_name} - {assignment.course_code} "
                            f"({teacher.short_name}) on {day} {time_slot.start_time}-{time_slot.end_time}. "
                            f"Overlaps with: {overlap_text or 'existing scheduled class'}"
                        )
                else:
                    if classroom_reason == "capacity":
                        generation_messages.append(
                            f"Capacity conflict (manual): unable to place {assignment.section_name} - {assignment.course_code} "
                            f"on {day} at {time_slot.start_time}-{time_slot.end_time}; no classroom with enough seats."
                        )
                    else:
                        generation_messages.append(
                            f"No suitable classroom for manual assignment: {assignment.section_name} - {assignment.course_code}"
                        )
        
        # Process automatic assignments (no specific day/time)
        for assignment in expanded_auto:
            course = next((c for c in self.courses if c.short_code == assignment.course_code), None)
            if not course:
                generation_messages.append(f"Course {assignment.course_code} not found")
                continue

            teacher = next((t for t in sorted_teachers if t.short_name == assignment.teacher_short_name), None)
            if not teacher:
                generation_messages.append(f"Teacher {assignment.teacher_short_name} not found")
                continue

            sessions_required = max(1, assignment.sessions_per_week)
            sessions_scheduled = 0
            capacity_shortage_found = False
            days_used_for_section = set()  # Track days already used for this course-section

            for _ in range(sessions_required):
                scheduled_this_round = False

                for day in self.DAYS_OF_WEEK:
                    if day in days_used_for_section:  # Skip days already used for this course-section
                        continue

                    duration = course.required_duration
                    if not self._within_teacher_load_limits(
                        teacher,
                        day,
                        duration,
                        teacher_hours,
                        teacher_daily_hours
                    ):
                        continue

                    suitable_slots = [s for s in time_slots if s.duration_hours() == duration]
                    random.shuffle(suitable_slots)
                    suitable_slots = self._prioritize_slots_by_teacher_preference(teacher, suitable_slots)

                    for time_slot in suitable_slots:
                        suitable_classroom, classroom_reason = self._find_suitable_classroom_with_reason(
                            assignment.section_name,
                            course,
                            day,
                            time_slot,
                            getattr(assignment, "classroom_code", "")
                        )

                        if not suitable_classroom:
                            if classroom_reason == "capacity":
                                capacity_shortage_found = True
                            continue

                        can_schedule, removed_entries = self._resolve_conflicts_with_priority(
                            assignment.section_name,
                            teacher.short_name,
                            suitable_classroom.short_code,
                            day,
                            time_slot
                        )

                        if not can_schedule:
                            continue

                        entry = RoutineEntry(
                            day=day,
                            time_slot=time_slot,
                            section_name=assignment.section_name,
                            course_code=course.short_code,
                            teacher_short_name=teacher.short_name,
                            classroom_code=suitable_classroom.short_code
                        )
                        self.routine.entries.append(entry)
                        self._update_schedules(entry)

                        scheduled_duration = time_slot.duration_hours()
                        teacher_hours[teacher.short_name] += scheduled_duration
                        teacher_daily_hours[teacher.short_name][day] = (
                            teacher_daily_hours[teacher.short_name].get(day, 0) + scheduled_duration
                        )
                        for removed_entry in removed_entries:
                            removed_duration = removed_entry.time_slot.duration_hours()
                            teacher_hours[removed_entry.teacher_short_name] -= removed_duration
                            teacher_daily_hours[removed_entry.teacher_short_name][removed_entry.day] = (
                                teacher_daily_hours[removed_entry.teacher_short_name].get(removed_entry.day, 0) - removed_duration
                            )

                        days_used_for_section.add(day)  # Mark this day as used for this course-section
                        sessions_scheduled += 1
                        scheduled_this_round = True
                        break

                    if scheduled_this_round:
                        break

                if not scheduled_this_round:
                    break

            if sessions_scheduled < sessions_required:
                if capacity_shortage_found:
                    generation_messages.append(
                        f"Capacity conflict: could not fully schedule {assignment.section_name} - {assignment.course_code} "
                        f"({sessions_scheduled}/{sessions_required} sessions)."
                    )
                else:
                    generation_messages.append(
                        f"Unscheduled sessions: {assignment.section_name} - {assignment.course_code} "
                        f"({sessions_scheduled}/{sessions_required} sessions)."
                    )
        
        # Detect remaining conflicts
        self._detect_all_conflicts()
        self.routine.conflicts.extend(generation_messages)
        
        return self.routine
    
    def _validate_unique_seniority_levels(self):
        """Ensure seniority levels are unique within each rank and department."""
        seen_by_rank_and_dept: Dict[Tuple[str, str], Set[int]] = {}
        for teacher in self.teachers:
            dept = self._normalize_dept_name(teacher.dept_name)
            key = (teacher.rank, dept)
            seen = seen_by_rank_and_dept.setdefault(key, set())
            if teacher.seniority_level in seen:
                dept_label = teacher.dept_name.strip() if teacher.dept_name else "(empty dept)"
                self.routine.conflicts.append(
                    f"Duplicate seniority level {teacher.seniority_level} found for rank {teacher.rank} "
                    f"in department {dept_label}. Seniority levels should be unique within the same rank and department."
                )
            else:
                seen.add(teacher.seniority_level)

    @staticmethod
    def _normalize_dept_name(dept_name: Optional[str]) -> str:
        """Normalize department name for comparisons."""
        if not dept_name:
            return ""
        return dept_name.strip().lower()

    def _build_expanded_sections(self) -> Dict[str, Section]:
        """Build subsection-aware section mapping used by the scheduler."""
        expanded: Dict[str, Section] = {}
        for section in self.sections:
            subsection_count = max(1, int(section.subsections))
            if subsection_count == 1:
                expanded[section.short_code] = section
                continue

            # Parent section code is valid for "All" assignments (kept as-is, not expanded).
            expanded[section.short_code] = section

            students_per_subsection = max(1, (section.num_students + subsection_count - 1) // subsection_count)
            for idx in range(1, subsection_count + 1):
                subsection_name = f"{section.short_code}-S{idx}"
                expanded[subsection_name] = Section(
                    full_name=f"{section.full_name} - Subsection {idx}",
                    short_code=subsection_name,
                    num_students=students_per_subsection,
                    home_classroom_code=section.home_classroom_code,
                    subsections=1
                )
        return expanded

    @staticmethod
    def _sections_overlap_conflict(section_a: str, section_b: str) -> bool:
        """Return True when scheduling both would conflict (same section, or one is a subsection of the other)."""
        if section_a == section_b:
            return True
        # a is parent of b  (e.g. "CS-A" vs "CS-A-S1")
        prefix_a = section_a + "-S"
        if section_b.startswith(prefix_a) and section_b[len(prefix_a):].isdigit():
            return True
        # b is parent of a  (e.g. "CS-A-S1" vs "CS-A")
        prefix_b = section_b + "-S"
        if section_a.startswith(prefix_b) and section_a[len(prefix_b):].isdigit():
            return True
        return False

    def _expand_assignments_for_subsections(self, assignments: List[CourseAssignment]) -> List[CourseAssignment]:
        """Expand assignments so each subsection is handled independently."""
        expanded: List[CourseAssignment] = []
        for assignment in assignments:
            target_sections = self._expand_section_name(assignment.section_name)
            for target_section_name in target_sections:
                expanded.append(
                    CourseAssignment(
                        course_code=assignment.course_code,
                        section_name=target_section_name,
                        teacher_short_name=assignment.teacher_short_name,
                        classroom_code=getattr(assignment, "classroom_code", ""),
                        sessions_per_week=assignment.sessions_per_week,
                        scheduled_slots=list(assignment.scheduled_slots)
                    )
                )
        return expanded

    def _expand_section_name(self, section_name: str) -> List[str]:
        """Return subsection names for a section name."""
        if section_name in self.expanded_sections:
            return [section_name]

        source = next((s for s in self.sections if s.short_code == section_name or s.full_name == section_name), None)
        if not source:
            return [section_name]

        subsection_count = max(1, int(source.subsections))
        if subsection_count == 1:
            return [source.short_code]

        return [f"{source.short_code}-S{i}" for i in range(1, subsection_count + 1)]

    def _within_teacher_load_limits(
        self,
        teacher: Teacher,
        day: str,
        duration_hours: int,
        teacher_hours: Dict[str, int],
        teacher_daily_hours: Dict[str, Dict[str, int]]
    ) -> bool:
        """Check if assigning a class would exceed weekly or daily teacher load limits."""
        max_weekly = self.TEACHER_LOADS.get(teacher.rank, teacher.max_hours_per_week)
        max_daily = teacher.max_hours_per_day or self.TEACHER_DAILY_LOADS.get(teacher.rank, 4)
        if teacher_hours[teacher.short_name] + duration_hours > max_weekly:
            return False
        current_daily = teacher_daily_hours[teacher.short_name].get(day, 0)
        if current_daily + duration_hours > max_daily:
            return False
        return True

    def _validate_theory_sessions_against_credit_hours(self) -> List[str]:
        """Return conflicts when theory-course weekly contact hours exceed credit hours."""
        conflicts: List[str] = []
        for assignment in self.course_assignments:
            course = next((c for c in self.courses if c.short_code == assignment.course_code), None)
            if not course:
                continue

            normalized_room_type = self._normalize_room_type(course.required_room_type)
            if normalized_room_type != "General Classroom":
                continue

            weekly_contact_hours = assignment.sessions_per_week * course.required_duration
            if weekly_contact_hours > course.credit_hours:
                conflicts.append(
                    f"Theory load conflict: {assignment.section_name} - {assignment.course_code} has "
                    f"{assignment.sessions_per_week} x {course.required_duration}h = {weekly_contact_hours:g}h/week, "
                    f"which exceeds credit hours ({course.credit_hours:g})."
                )
        return conflicts

    def _prioritize_slots_by_teacher_preference(self, teacher: Teacher, slots: List[TimeSlot]) -> List[TimeSlot]:
        """Sort candidate slots so teacher preferred slots are tried first."""
        preferred_exact = {(ts.start_time, ts.end_time) for ts in teacher.preferred_time_slots}
        preferred_start_times = {ts.start_time for ts in teacher.preferred_time_slots}

        return sorted(
            slots,
            key=lambda s: (
                (s.start_time, s.end_time) in preferred_exact,
                s.start_time in preferred_start_times
            ),
            reverse=True
        )

    def _teacher_priority_value(self, teacher_short_name: str) -> Tuple[int, int, str]:
        """Return priority tuple for ordering (rank first, then lower seniority level)."""
        teacher = next((t for t in self.teachers if t.short_name == teacher_short_name), None)
        if not teacher:
            return (0, 10**9, teacher_short_name)
        return (
            -self.RANK_PRIORITY.get(teacher.rank, 0),
            teacher.seniority_level,
            teacher.short_name
        )

    def _has_higher_priority(self, incoming_teacher_short_name: str, existing_teacher_short_name: str) -> bool:
        """Return True if incoming teacher should preempt existing one."""
        incoming_teacher = next((t for t in self.teachers if t.short_name == incoming_teacher_short_name), None)
        existing_teacher = next((t for t in self.teachers if t.short_name == existing_teacher_short_name), None)
        if not incoming_teacher or not existing_teacher:
            return False

        incoming_rank = self.RANK_PRIORITY.get(incoming_teacher.rank, 0)
        existing_rank = self.RANK_PRIORITY.get(existing_teacher.rank, 0)
        if incoming_rank != existing_rank:
            return incoming_rank > existing_rank

        return incoming_teacher.seniority_level < existing_teacher.seniority_level

    def _remove_entry(self, entry: RoutineEntry):
        """Remove an entry from the routine and internal schedules."""
        if entry in self.routine.entries:
            self.routine.entries.remove(entry)
        if entry.classroom_code in self.classroom_schedule:
            self.classroom_schedule[entry.classroom_code] = [
                e for e in self.classroom_schedule[entry.classroom_code] if e != entry
            ]
        if entry.teacher_short_name in self.teacher_schedule:
            self.teacher_schedule[entry.teacher_short_name] = [
                e for e in self.teacher_schedule[entry.teacher_short_name] if e != entry
            ]
        if entry.section_name in self.section_schedule:
            self.section_schedule[entry.section_name] = [
                e for e in self.section_schedule[entry.section_name] if e != entry
            ]

    def _resolve_conflicts_with_priority(self, section: str, teacher: str, classroom: str,
                                         day: str, time_slot: TimeSlot) -> Tuple[bool, List[RoutineEntry]]:
        """Resolve conflicts by allowing higher-priority teachers to preempt lower-priority ones."""
        removed_entries: List[RoutineEntry] = []

        for entry in list(self.routine.entries):
            if entry.day != day:
                continue
            if not entry.time_slot.overlaps_with(time_slot):
                continue

            # Same teacher conflict: never allow overlapping classes for the same teacher
            if entry.teacher_short_name == teacher:
                return False, []

            # Classroom conflict with different section is not preempted
            if entry.classroom_code == classroom and entry.section_name != section:
                return False, []

            # Section conflict: allow higher-priority teacher to replace lower-priority one
            if self._sections_overlap_conflict(entry.section_name, section):
                if not self._has_higher_priority(teacher, entry.teacher_short_name):
                    return False, []
                removed_entries.append(entry)

        for entry in removed_entries:
            self._remove_entry(entry)

        return True, removed_entries

    def _collect_overlap_conflicts(
        self,
        section: str,
        teacher: str,
        classroom: str,
        day: str,
        time_slot: TimeSlot,
    ) -> List[RoutineEntry]:
        """Collect existing entries that block scheduling at this day/time."""
        overlaps: List[RoutineEntry] = []
        for entry in self.routine.entries:
            if entry.day != day:
                continue
            if not entry.time_slot.overlaps_with(time_slot):
                continue

            teacher_conflict = entry.teacher_short_name == teacher
            classroom_conflict = entry.classroom_code == classroom and entry.section_name != section
            section_conflict = self._sections_overlap_conflict(entry.section_name, section)

            if teacher_conflict or classroom_conflict or section_conflict:
                overlaps.append(entry)

        return overlaps

    def _find_suitable_classroom(self, section_name: str, course: Course,
                                 day: str, time_slot: TimeSlot,
                                 preferred_classroom_code: str = "") -> Optional[Classroom]:
        """Find a suitable classroom for a section and course."""
        classroom, _ = self._find_suitable_classroom_with_reason(
            section_name,
            course,
            day,
            time_slot,
            preferred_classroom_code
        )
        return classroom

    def _find_suitable_classroom_with_reason(
        self,
        section_name: str,
        course: Course,
        day: str,
        time_slot: TimeSlot,
        preferred_classroom_code: str = ""
    ) -> Tuple[Optional[Classroom], str]:
        """Find a suitable classroom and return a reason if not found."""
        section = self.expanded_sections.get(section_name)
        if not section:
            section = next((s for s in self.sections if s.short_code == section_name or s.full_name == section_name), None)
        if not section:
            return None, "section-not-found"

        has_capacity_candidate = False
        required_room_type = self._normalize_room_type(course.required_room_type)

        preferred_code = (preferred_classroom_code or "").strip()
        if preferred_code:
            preferred_classroom = next((c for c in self.classrooms if c.short_code == preferred_code), None)
            if not preferred_classroom:
                return None, "preferred-not-found"

            preferred_room_type = self._normalize_room_type(preferred_classroom.room_type)
            if required_room_type and preferred_room_type != required_room_type:
                return None, "preferred-room-type"

            if preferred_classroom.capacity < section.num_students:
                return None, "preferred-capacity"

            if self._is_classroom_occupied(preferred_classroom.short_code, day, time_slot):
                return None, "preferred-occupied"

            return preferred_classroom, "ok"

        # First, try to use home classroom
        home_classroom = next((c for c in self.classrooms if c.short_code == section.home_classroom_code), None)

        if home_classroom:
            home_room_type = self._normalize_room_type(home_classroom.room_type)
            if required_room_type is None or home_room_type == required_room_type:
                if home_classroom.capacity >= section.num_students:
                    has_capacity_candidate = True
                    if not self._is_classroom_occupied(home_classroom.short_code, day, time_slot):
                        return home_classroom, "ok"

        # Find alternative classroom
        for classroom in self.classrooms:
            classroom_room_type = self._normalize_room_type(classroom.room_type)
            if required_room_type and classroom_room_type != required_room_type:
                continue
            if classroom.capacity >= section.num_students:
                has_capacity_candidate = True
                if not self._is_classroom_occupied(classroom.short_code, day, time_slot):
                    return classroom, "ok"

        if not has_capacity_candidate:
            return None, "capacity"
        return None, "occupied"

    def _normalize_room_type(self, room_type: Optional[str]) -> Optional[str]:
        """Normalize room type values so legacy and current labels match during scheduling."""
        if room_type is None:
            return None
        cleaned = room_type.strip()
        if not cleaned:
            return None
        return self.ROOM_TYPE_ALIASES.get(cleaned.lower(), cleaned)
    
    def _is_classroom_occupied(self, classroom_code: str, day: str, time_slot: TimeSlot) -> bool:
        """Check if a classroom is occupied at a given time"""
        for entry in self.routine.entries:
            if entry.classroom_code == classroom_code and entry.day == day:
                if entry.time_slot.overlaps_with(time_slot):
                    return True
        return False
    
    def _has_conflicts(self, section: str, teacher: str, classroom: str,
                      day: str, time_slot: TimeSlot) -> bool:
        """Check for conflicts before adding an entry"""
        for entry in self.routine.entries:
            if entry.day != day:
                continue
            
            # Section conflict
            if self._sections_overlap_conflict(entry.section_name, section) and entry.time_slot.overlaps_with(time_slot):
                return True
            
            # Teacher conflict
            if entry.teacher_short_name == teacher and entry.time_slot.overlaps_with(time_slot):
                return True
            
            # Classroom conflict
            if entry.classroom_code == classroom and entry.time_slot.overlaps_with(time_slot):
                return True
        
        return False
    
    def _update_schedules(self, entry: RoutineEntry):
        """Update internal schedule tracking"""
        if entry.classroom_code not in self.classroom_schedule:
            self.classroom_schedule[entry.classroom_code] = []
        self.classroom_schedule[entry.classroom_code].append(entry)
        
        if entry.teacher_short_name not in self.teacher_schedule:
            self.teacher_schedule[entry.teacher_short_name] = []
        self.teacher_schedule[entry.teacher_short_name].append(entry)
        
        if entry.section_name not in self.section_schedule:
            self.section_schedule[entry.section_name] = []
        self.section_schedule[entry.section_name].append(entry)
    
    def _detect_all_conflicts(self):
        """Detect and report all conflicts"""
        conflicts = list(self.routine.conflicts)
        
        # Check for overlapping sections in same classroom
        for day in self.DAYS_OF_WEEK:
            day_entries = [e for e in self.routine.entries if e.day == day]
            
            for i, entry1 in enumerate(day_entries):
                for entry2 in day_entries[i+1:]:
                    # Classroom conflict
                    if entry1.classroom_code == entry2.classroom_code:
                        if entry1.time_slot.overlaps_with(entry2.time_slot):
                            conflicts.append(
                                f"Classroom conflict: {entry1.classroom_code} on {day} "
                                f"{entry1.time_slot.start_time}-{entry1.time_slot.end_time} "
                                f"and {entry2.time_slot.start_time}-{entry2.time_slot.end_time}"
                            )
                    
                    # Teacher conflict
                    if entry1.teacher_short_name == entry2.teacher_short_name:
                        if entry1.time_slot.overlaps_with(entry2.time_slot):
                            conflicts.append(
                                f"Teacher conflict: {entry1.teacher_short_name} on {day} "
                                f"{entry1.time_slot.start_time}-{entry1.time_slot.end_time} "
                                f"and {entry2.time_slot.start_time}-{entry2.time_slot.end_time}"
                            )
                    
                    # Section conflict
                    if self._sections_overlap_conflict(entry1.section_name, entry2.section_name):
                        if entry1.time_slot.overlaps_with(entry2.time_slot):
                            conflicts.append(
                                f"Section conflict: {entry1.section_name} on {day} "
                                f"{entry1.time_slot.start_time}-{entry1.time_slot.end_time} "
                                f"and {entry2.time_slot.start_time}-{entry2.time_slot.end_time}"
                            )
        
        self.routine.conflicts = conflicts
    
    def get_section_timetable(self, section_name: str) -> List[RoutineEntry]:
        """Get timetable for a specific section"""
        return [e for e in self.routine.entries if e.section_name == section_name]
    
    def get_teacher_timetable(self, teacher_short_name: str) -> List[RoutineEntry]:
        """Get timetable for a specific teacher"""
        return [e for e in self.routine.entries if e.teacher_short_name == teacher_short_name]
    
    def get_classroom_timetable(self, classroom_code: str) -> List[RoutineEntry]:
        """Get timetable for a specific classroom"""
        return [e for e in self.routine.entries if e.classroom_code == classroom_code]
    
    def get_course_timetable(self, course_code: str) -> List[RoutineEntry]:
        """Get timetable for a specific course"""
        return [e for e in self.routine.entries if e.course_code == course_code]
