import { apiClient } from "./client";

export interface ClassScope {
  all_subjects: boolean;
  subject_ids: number[];
}

export interface ClassResultColumn {
  exam_id: number;
  exam_title: string;
  exam_type: "nazorat" | "chorak";
  subject_id: number;
  subject_name: string;
  date: string;
  max_score: number;
  taken: number;
  class_percent: number | null;
}

export interface ClassResultCell {
  score: number;
  max_score: number;
  percent: number;
}

export interface ClassResultRow {
  student_id: number;
  full_name: string;
  cells: (ClassResultCell | null)[]; // index-aligned to `columns`; null = did not take it
  percent: number | null;
  rank: number | null;
}

export interface ClassResults {
  class_id: number;
  class_name: string;
  start_date: string;
  end_date: string;
  scope: ClassScope;
  columns: ClassResultColumn[];
  students: ClassResultRow[];
  class_percent: number | null;
}

export interface ClassDynSubject {
  subject_id: number;
  subject_name: string;
  exams_count: number;
  baseline_percent: number;
  current_percent: number;
  average_percent: number;
  delta: number | null;
}

export interface ClassDynStudent {
  student_id: number;
  full_name: string;
  exams_count: number;
  average_percent: number | null;
  baseline_percent: number | null;
  current_percent: number | null;
  delta: number | null;
  rank: number | null;
}

export interface ClassDynQuarter {
  number: number;
  start_date: string;
  end_date: string;
  exams_count: number;
  percent: number | null;
}

export interface ClassDynamics {
  class_id: number;
  class_name: string;
  school_year_start: number;
  available_school_years: number[];
  scope: ClassScope;
  students_count: number;
  exams_count: number;
  baseline_percent: number | null;
  current_percent: number | null;
  delta: number | null;
  average_percent: number | null;
  bands: { low: number; middle: number; high: number };
  subjects: ClassDynSubject[];
  quarters: ClassDynQuarter[];
  timeline: ClassResultColumn[];
  students: ClassDynStudent[];
}

export async function getClassResults(
  classId: number,
  params: { start?: string; end?: string; school_year?: number }
): Promise<ClassResults> {
  const { data } = await apiClient.get<ClassResults>(`/admin/classes/${classId}/results`, { params });
  return data;
}

export async function getClassDynamics(classId: number, schoolYear?: number): Promise<ClassDynamics> {
  const { data } = await apiClient.get<ClassDynamics>(`/admin/classes/${classId}/dynamics`, {
    params: schoolYear ? { school_year: schoolYear } : undefined,
  });
  return data;
}
