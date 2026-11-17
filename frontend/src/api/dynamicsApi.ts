import { apiClient } from "./client";

export interface DynamicsPoint {
  exam_id: number;
  exam_title: string;
  exam_type: "nazorat" | "chorak";
  subject_id: number;
  subject_name: string;
  date: string; // YYYY-MM-DD
  quarter: number;
  score: number;
  max_score: number;
  percent: number;
  class_percent: number | null; // null when fewer than 3 students sat it
  provisional: boolean; // a written answer still waits for the teacher
}

export interface DynamicsMissed {
  exam_id: number;
  exam_title: string;
  exam_type: "nazorat" | "chorak";
  subject_name: string | null;
  date: string;
}

export interface DynamicsSubject {
  subject_id: number;
  subject_name: string;
  exams_count: number;
  average_percent: number;
  baseline_percent: number;
  current_percent: number;
  delta: number | null;
  class_percent: number | null;
}

export interface DynamicsQuarter {
  number: number;
  start_date: string;
  end_date: string;
  exams_count: number;
  percent: number | null;
  rank: number | null; // staff only
  rank_of: number | null;
}

export interface DynamicsOverall {
  exams_count: number;
  baseline_percent: number | null;
  current_percent: number | null;
  delta: number | null;
  average_percent: number | null;
  class_percent: number | null;
  rank: number | null; // staff only
  rank_of: number | null;
}

export interface DynamicsInsight {
  subject_id: number;
  subject_name: string;
  value: number;
}

export interface Dynamics {
  student_id: number;
  full_name: string;
  class_name: string;
  school_year_start: number;
  available_school_years: number[];
  show_rank: boolean;
  overall: DynamicsOverall;
  subjects: DynamicsSubject[];
  quarters: DynamicsQuarter[];
  points: DynamicsPoint[];
  missed: DynamicsMissed[];
  insights: {
    strongest: DynamicsInsight | null;
    weakest: DynamicsInsight | null;
    most_improved: DynamicsInsight | null;
    most_declined: DynamicsInsight | null;
  };
}

/** A student's own page. */
export async function getMyDynamics(schoolYear?: number): Promise<Dynamics> {
  const { data } = await apiClient.get<Dynamics>("/student/me/dynamics", { params: { school_year: schoolYear } });
  return data;
}

/** Any student, for staff — adds the class rank. */
export async function getStudentDynamics(studentId: number, schoolYear?: number): Promise<Dynamics> {
  const { data } = await apiClient.get<Dynamics>(`/admin/students/${studentId}/dynamics`, {
    params: { school_year: schoolYear },
  });
  return data;
}
