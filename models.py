"""
Data models for the Routine Generator Application
Includes: Classroom, Teacher, Course, Section, TimeSlot, and Routine classes
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Set, Tuple
from datetime import time
import json

@dataclass
class TimeSlot:
    """Represents a time slot (start_time, end_time)"""
    start_time: str  # "HH:MM" format
    end_time: str    # "HH:MM" format
    
    # Predefined time slots (1st through 9th)
    STANDARD_SLOTS = {
        "1st": ("08:00", "08:50"),
        "2nd": ("09:00", "09:50"),
        "3rd": ("10:00", "10:50"),
        "4th": ("11:00", "11:50"),
        "5th": ("12:00", "12:50"),
        "6th": ("13:00", "13:30"),  # Break
        "7th": ("14:00", "14:50"),
        "8th": ("15:00", "15:50"),
        "9th": ("16:00", "16:50")
    }
    
    def to_dict(self):
        return {"start_time": self.start_time, "end_time": self.end_time}
    
    @staticmethod
    def from_dict(data):
        return TimeSlot(data["start_time"], data["end_time"])
    
    @staticmethod
    def from_slot_name(slot_name: str) -> 'TimeSlot':
        """Create TimeSlot from slot name like '1st', '2nd', etc."""
        if slot_name in TimeSlot.STANDARD_SLOTS:
            start, end = TimeSlot.STANDARD_SLOTS[slot_name]
            return TimeSlot(start, end)
        return None
    
    def get_slot_name(self) -> str:
        """Get slot name from time (e.g., '1st' for 08:00-08:50)"""
        for name, (start, end) in TimeSlot.STANDARD_SLOTS.items():
            if self.start_time == start and self.end_time == end:
                return name
        return f"{self.start_time}-{self.end_time}"
    
    def overlaps_with(self, other: 'TimeSlot') -> bool:
        """Check if this slot overlaps with another"""
        start1 = self._time_to_minutes(self.start_time)
        end1 = self._time_to_minutes(self.end_time)
        start2 = self._time_to_minutes(other.start_time)
        end2 = self._time_to_minutes(other.end_time)
        return start1 < end2 and start2 < end1
    
    @staticmethod
    def _time_to_minutes(time_str: str) -> int:
        """Convert HH:MM to minutes"""
        h, m = map(int, time_str.split(":"))
        return h * 60 + m
    
    def duration_minutes(self) -> int:
        """Get duration in minutes"""
        return self._time_to_minutes(self.end_time) - self._time_to_minutes(self.start_time)
    
    def duration_hours(self) -> int:
        """Get duration in hours"""
        return self.duration_minutes() // 60


@dataclass
class Classroom:
    """Represents a classroom"""
    full_name: str
    short_code: str
    capacity: int
    room_type: str  # "General Classroom", "Theory Lab", "Computer Lab"
    
    def to_dict(self):
        return {
            "full_name": self.full_name,
            "short_code": self.short_code,
            "capacity": self.capacity,
            "room_type": self.room_type
        }
    
    @staticmethod
    def from_dict(data):
        return Classroom(
            data["full_name"],
            data["short_code"],
            data["capacity"],
            data["room_type"]
        )


@dataclass
class Teacher:
    """Represents a teacher"""
    full_name: str
    short_name: str
    seniority_level: int  # Numeric priority within rank (lower = more senior, e.g., 1 > 2)
    rank: str  # "Professor", "Associate Prof", "Assistant Prof", "Lecturer"
    max_hours_per_week: int  # Depends on rank
    max_hours_per_day: int = 4
    dept_name: str = ""
    preferred_time_slots: List[TimeSlot] = field(default_factory=list)
    
    def to_dict(self):
        return {
            "full_name": self.full_name,
            "short_name": self.short_name,
            "seniority_level": self.seniority_level,
            "rank": self.rank,
            "max_hours_per_week": self.max_hours_per_week,
            "max_hours_per_day": self.max_hours_per_day,
            "dept_name": self.dept_name,
            "preferred_time_slots": [ts.to_dict() for ts in self.preferred_time_slots]
        }
    
    @staticmethod
    def from_dict(data):
        preferred_slots = []
        for slot in data.get("preferred_time_slots", []):
            if isinstance(slot, dict):
                preferred_slots.append(TimeSlot.from_dict(slot))
            elif isinstance(slot, str):
                ts = TimeSlot.from_slot_name(slot)
                if ts:
                    preferred_slots.append(ts)

        teacher = Teacher(
            full_name=data["full_name"],
            short_name=data["short_name"],
            seniority_level=data["seniority_level"],
            rank=data["rank"],
            max_hours_per_week=data["max_hours_per_week"],
            max_hours_per_day=data.get("max_hours_per_day", 4),
            dept_name=data.get("dept_name", ""),
            preferred_time_slots=preferred_slots
        )
        return teacher


@dataclass
class Course:
    """Represents a course"""
    title: str
    short_code: str
    credit_hours: float
    required_duration: int  # 1, 2, or 3 hours
    required_room_type: Optional[str] = None  # One of classroom room types or None for any
    
    def to_dict(self):
        return {
            "title": self.title,
            "short_code": self.short_code,
            "credit_hours": self.credit_hours,
            "required_duration": self.required_duration,
            "required_room_type": self.required_room_type
        }
    
    @staticmethod
    def from_dict(data):
        return Course(
            data["title"],
            data["short_code"],
            float(data["credit_hours"]),
            data["required_duration"],
            data.get("required_room_type")
        )


@dataclass
class Section:
    """Represents a student section"""
    full_name: str
    short_code: str
    num_students: int
    home_classroom_code: str  # Reference to classroom short_code
    subsections: int = 1  # Number of subsections if divided

    @property
    def name(self) -> str:
        """Backward-compatible alias for the section identifier."""
        return self.short_code

    @property
    def display_name(self) -> str:
        """Readable label using both full name and short code."""
        if self.full_name == self.short_code:
            return self.short_code
        return f"{self.full_name} ({self.short_code})"
    
    def to_dict(self):
        return {
            "full_name": self.full_name,
            "short_code": self.short_code,
            "num_students": self.num_students,
            "home_classroom_code": self.home_classroom_code,
            "subsections": self.subsections
        }
    
    @staticmethod
    def from_dict(data):
        full_name = data.get("full_name") or data.get("name") or data.get("short_code")
        short_code = data.get("short_code") or data.get("name") or full_name
        return Section(
            full_name,
            short_code,
            data["num_students"],
            data["home_classroom_code"],
            data.get("subsections", 1)
        )


@dataclass
class RoutineEntry:
    """Represents a single entry in the routine"""
    day: str  # "Monday", "Tuesday", etc.
    time_slot: TimeSlot
    section_name: str
    course_code: str
    teacher_short_name: str
    classroom_code: str
    
    def to_dict(self):
        return {
            "day": self.day,
            "time_slot": self.time_slot.to_dict(),
            "section_name": self.section_name,
            "course_code": self.course_code,
            "teacher_short_name": self.teacher_short_name,
            "classroom_code": self.classroom_code
        }
    
    @staticmethod
    def from_dict(data):
        return RoutineEntry(
            data["day"],
            TimeSlot.from_dict(data["time_slot"]),
            data["section_name"],
            data["course_code"],
            data["teacher_short_name"],
            data["classroom_code"]
        )


@dataclass
class CourseAssignment:
    """Represents which courses are taught to which sections by which teachers"""
    course_code: str
    section_name: str
    teacher_short_name: str
    classroom_code: str = ""
    # Number of sessions per week (e.g., 2 sessions for a course)
    sessions_per_week: int = 1
    # Multiple specific day/time combinations (optional - for manual scheduling)
    # List of tuples: [(day, time_slot), (day, time_slot), ...]
    scheduled_slots: List[Tuple[str, TimeSlot]] = field(default_factory=list)
    
    def to_dict(self):
        result = {
            "course_code": self.course_code,
            "section_name": self.section_name,
            "teacher_short_name": self.teacher_short_name,
            "classroom_code": self.classroom_code,
            "sessions_per_week": self.sessions_per_week,
            "scheduled_slots": [
                {"day": day, "time_slot": ts.to_dict()} 
                for day, ts in self.scheduled_slots
            ]
        }
        return result
    
    @staticmethod
    def from_dict(data):
        scheduled_slots = []
        if "scheduled_slots" in data:
            for slot_data in data["scheduled_slots"]:
                day = slot_data["day"]
                ts = TimeSlot.from_dict(slot_data["time_slot"])
                scheduled_slots.append((day, ts))
        return CourseAssignment(
            data["course_code"],
            data["section_name"],
            data["teacher_short_name"],
            data.get("classroom_code", ""),
            data.get("sessions_per_week", 1),
            scheduled_slots
        )


@dataclass
class Routine:
    """Represents the complete weekly routine"""
    entries: List[RoutineEntry] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    course_assignments: List[CourseAssignment] = field(default_factory=list)
    
    def to_dict(self):
        return {
            "entries": [entry.to_dict() for entry in self.entries],
            "conflicts": self.conflicts,
            "course_assignments": [ca.to_dict() for ca in self.course_assignments]
        }
    
    @staticmethod
    def from_dict(data):
        return Routine(
            [RoutineEntry.from_dict(e) for e in data["entries"]],
            data.get("conflicts", []),
            [CourseAssignment.from_dict(ca) for ca in data.get("course_assignments", [])]
        )
