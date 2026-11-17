from datetime import date

from pydantic import BaseModel


class QuarterOut(BaseModel):
    number: int
    start_date: date  # resolved against the current school year, for display
    end_date: date


class QuartersOut(BaseModel):
    school_year_start: int  # 2026 = the 2026/27 school year
    current_number: int  # the quarter today falls in
    is_default: bool  # True until an admin saves their own dates
    quarters: list[QuarterOut]


class QuarterIn(BaseModel):
    number: int
    # Only the month and day are kept: the calendar repeats every school year.
    start_date: date
    end_date: date


class QuartersIn(BaseModel):
    quarters: list[QuarterIn]
