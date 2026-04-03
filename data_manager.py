"""
Data Manager for handling JSON file persistence
Manages saving and loading of classrooms, teachers, courses, sections, and routines
"""

import json
import os
from typing import List, Dict, Optional
from models import Classroom, Teacher, Course, Section, Routine, TimeSlot, CourseAssignment


class DataManager:
    """Manages all data persistence using JSON files"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.ensure_data_dir_exists()
        
        self.classrooms_file = os.path.join(data_dir, "classrooms.json")
        self.teachers_file = os.path.join(data_dir, "teachers.json")
        self.courses_file = os.path.join(data_dir, "courses.json")
        self.sections_file = os.path.join(data_dir, "sections.json")
        self.routine_file = os.path.join(data_dir, "routine.json")
        self.assignments_file = os.path.join(data_dir, "course_assignments.json")
    
    def ensure_data_dir_exists(self):
        """Create data directory if it doesn't exist"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
    
    # ==================== CLASSROOMS ====================
    
    def load_classrooms(self) -> List[Classroom]:
        """Load all classrooms from file"""
        if not os.path.exists(self.classrooms_file):
            return []
        try:
            with open(self.classrooms_file, 'r') as f:
                data = json.load(f)
                return [Classroom.from_dict(item) for item in data]
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def save_classrooms(self, classrooms: List[Classroom]):
        """Save classrooms to file"""
        with open(self.classrooms_file, 'w') as f:
            json.dump([c.to_dict() for c in classrooms], f, indent=2)
    
    def add_classroom(self, classroom: Classroom, classrooms: List[Classroom]) -> bool:
        """Add a classroom if code doesn't already exist"""
        if any(c.short_code == classroom.short_code for c in classrooms):
            return False
        classrooms.append(classroom)
        self.save_classrooms(classrooms)
        return True
    
    def update_classroom(self, updated: Classroom, classrooms: List[Classroom]) -> bool:
        """Update an existing classroom"""
        for i, c in enumerate(classrooms):
            if c.short_code == updated.short_code:
                classrooms[i] = updated
                self.save_classrooms(classrooms)
                return True
        return False
    
    def delete_classroom(self, short_code: str, classrooms: List[Classroom]) -> bool:
        """Delete a classroom"""
        for i, c in enumerate(classrooms):
            if c.short_code == short_code:
                classrooms.pop(i)
                self.save_classrooms(classrooms)
                return True
        return False
    
    # ==================== TEACHERS ====================
    
    def load_teachers(self) -> List[Teacher]:
        """Load all teachers from file"""
        if not os.path.exists(self.teachers_file):
            return []
        try:
            with open(self.teachers_file, 'r') as f:
                data = json.load(f)
                return [Teacher.from_dict(item) for item in data]
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def save_teachers(self, teachers: List[Teacher]):
        """Save teachers to file"""
        with open(self.teachers_file, 'w') as f:
            json.dump([t.to_dict() for t in teachers], f, indent=2)

    @staticmethod
    def _normalize_dept_name(dept_name: Optional[str]) -> str:
        if not dept_name:
            return ""
        return dept_name.strip().lower()
    
    def add_teacher(self, teacher: Teacher, teachers: List[Teacher]) -> bool:
        """Add a teacher if short name doesn't already exist"""
        if any(t.short_name == teacher.short_name for t in teachers):
            return False
        teacher_dept = self._normalize_dept_name(teacher.dept_name)
        if any(
            t.rank == teacher.rank
            and t.seniority_level == teacher.seniority_level
            and self._normalize_dept_name(t.dept_name) == teacher_dept
            for t in teachers
        ):
            return False
        teachers.append(teacher)
        self.save_teachers(teachers)
        return True
    
    def update_teacher(self, updated: Teacher, teachers: List[Teacher], original_short_name: Optional[str] = None) -> bool:
        """Update an existing teacher"""
        updated_dept = self._normalize_dept_name(updated.dept_name)
        if any(
            t.short_name != (original_short_name or updated.short_name)
            and t.rank == updated.rank
            and t.seniority_level == updated.seniority_level
            and self._normalize_dept_name(t.dept_name) == updated_dept
            for t in teachers
        ):
            return False
        lookup_short_name = original_short_name or updated.short_name
        for i, t in enumerate(teachers):
            if t.short_name == lookup_short_name:
                teachers[i] = updated
                self.save_teachers(teachers)
                return True
        return False
    
    def delete_teacher(self, short_name: str, teachers: List[Teacher]) -> bool:
        """Delete a teacher"""
        for i, t in enumerate(teachers):
            if t.short_name == short_name:
                teachers.pop(i)
                self.save_teachers(teachers)
                return True
        return False
    
    # ==================== COURSES ====================
    
    def load_courses(self) -> List[Course]:
        """Load all courses from file"""
        if not os.path.exists(self.courses_file):
            return []
        try:
            with open(self.courses_file, 'r') as f:
                data = json.load(f)
                return [Course.from_dict(item) for item in data]
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def save_courses(self, courses: List[Course]):
        """Save courses to file"""
        with open(self.courses_file, 'w') as f:
            json.dump([c.to_dict() for c in courses], f, indent=2)
    
    def add_course(self, course: Course, courses: List[Course]) -> bool:
        """Add a course if code doesn't already exist"""
        if any(c.short_code == course.short_code for c in courses):
            return False
        courses.append(course)
        self.save_courses(courses)
        return True
    
    def update_course(self, updated: Course, courses: List[Course]) -> bool:
        """Update an existing course"""
        for i, c in enumerate(courses):
            if c.short_code == updated.short_code:
                courses[i] = updated
                self.save_courses(courses)
                return True
        return False
    
    def delete_course(self, short_code: str, courses: List[Course]) -> bool:
        """Delete a course"""
        for i, c in enumerate(courses):
            if c.short_code == short_code:
                courses.pop(i)
                self.save_courses(courses)
                return True
        return False
    
    # ==================== SECTIONS ====================
    
    def load_sections(self) -> List[Section]:
        """Load all sections from file"""
        if not os.path.exists(self.sections_file):
            return []
        try:
            with open(self.sections_file, 'r') as f:
                data = json.load(f)
                return [Section.from_dict(item) for item in data]
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def save_sections(self, sections: List[Section]):
        """Save sections to file"""
        with open(self.sections_file, 'w') as f:
            json.dump([s.to_dict() for s in sections], f, indent=2)
    
    def add_section(self, section: Section, sections: List[Section]) -> bool:
        """Add a section if short code doesn't already exist"""
        if any(s.short_code == section.short_code for s in sections):
            return False
        sections.append(section)
        self.save_sections(sections)
        return True
    
    def update_section(self, updated: Section, sections: List[Section], original_short_code: Optional[str] = None) -> bool:
        """Update an existing section"""
        lookup_short_code = original_short_code or updated.short_code
        for i, s in enumerate(sections):
            if s.short_code == lookup_short_code:
                sections[i] = updated
                self.save_sections(sections)
                return True
        return False
    
    def delete_section(self, short_code: str, sections: List[Section]) -> bool:
        """Delete a section"""
        for i, s in enumerate(sections):
            if s.short_code == short_code:
                sections.pop(i)
                self.save_sections(sections)
                return True
        return False
    
    # ==================== ROUTINES ====================
    
    def load_routine(self) -> Routine:
        """Load routine from file"""
        if not os.path.exists(self.routine_file):
            return Routine()
        try:
            with open(self.routine_file, 'r') as f:
                data = json.load(f)
                return Routine.from_dict(data)
        except (json.JSONDecodeError, FileNotFoundError):
            return Routine()
    
    def save_routine(self, routine: Routine):
        """Save routine to file"""
        with open(self.routine_file, 'w') as f:
            json.dump(routine.to_dict(), f, indent=2)
    
    # ==================== COURSE ASSIGNMENTS ====================
    
    def load_course_assignments(self) -> List[CourseAssignment]:
        """Load all course assignments from file"""
        if not os.path.exists(self.assignments_file):
            return []
        try:
            with open(self.assignments_file, 'r') as f:
                data = json.load(f)
                return [CourseAssignment.from_dict(item) for item in data]
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def save_course_assignments(self, assignments: List[CourseAssignment]):
        """Save course assignments to file"""
        with open(self.assignments_file, 'w') as f:
            json.dump([a.to_dict() for a in assignments], f, indent=2)
    
    def add_course_assignment(self, assignment: CourseAssignment, assignments: List[CourseAssignment]) -> bool:
        """Add a course assignment"""
        # Check if assignment already exists
        for a in assignments:
            if (a.course_code == assignment.course_code and 
                a.section_name == assignment.section_name and 
                a.teacher_short_name == assignment.teacher_short_name):
                return False
        assignments.append(assignment)
        self.save_course_assignments(assignments)
        return True
    
    def delete_course_assignment(self, assignment: CourseAssignment, assignments: List[CourseAssignment]) -> bool:
        """Delete a course assignment"""
        for i, a in enumerate(assignments):
            if (a.course_code == assignment.course_code and 
                a.section_name == assignment.section_name and 
                a.teacher_short_name == assignment.teacher_short_name):
                assignments.pop(i)
                self.save_course_assignments(assignments)
                return True
        return False
