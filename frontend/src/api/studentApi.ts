import { apiClient } from "./client";

export interface ExamSectionInfo {
  id: number;
  subject_name: string;
  kind: "asosiy" | "majburiy";
  question_count: number;
  points_per_question: number;
}

export interface ExamListItem {
  id: number;
  title: string;
  subject_name: string;
  start_at: string | null;
  end_at: string | null;
  duration_minutes: number;
  window_state: "upcoming" | "active" | "closed";
  my_attempt_status: string | null;
  exam_type: "nazorat" | "chorak";
  question_count: number;
  total_points: number | null;
  my_deadline_at: string | null;
  sections: ExamSectionInfo[];
}

export interface AttemptOption {
  id: number;
  order_index: number;
  option_text: string;
  option_image_key: string | null;
}

export interface AttemptQuestion {
  id: number;
  section_id: number | null;
  order_index: number;
  question_type: string;
  prompt_text: string;
  prompt_image_key: string | null;
  points: number;
  options: AttemptOption[];
  selected_option_id: number | null;
  answer_text: string | null;
}

export interface AttemptState {
  attempt_id: number;
  exam_id: number;
  exam_title: string;
  deadline_at: string;
  duration_minutes: number;
  exam_type: "nazorat" | "chorak";
  sections: ExamSectionInfo[];
  questions: AttemptQuestion[];
}

export interface SubmitResult {
  score: number;
  max_score: number;
  submitted_at: string;
}

export interface ResultSection {
  section_id: number;
  subject_name: string;
  kind: "asosiy" | "majburiy";
  score: number;
  max_score: number;
  correct_count: number;
  question_count: number;
}

export interface ResultQuestion {
  question_id: number;
  section_id: number | null;
  question_type: string;
  prompt_text: string;
  points: number;
  selected_option_id: number | null;
  selected_option_text: string | null;
  correct_option_id: number | null;
  correct_option_text: string | null;
  answer_text: string | null;
  ai_feedback: string | null;
  is_correct: boolean | null;
  points_awarded: number | null;
  // a written answer nobody has graded yet: the 0 shown is not a verdict
  pending_review: boolean;
}

export interface ExamResult {
  exam_id: number;
  exam_title: string;
  score: number;
  max_score: number;
  percent: number;
  answers_revealed: boolean;
  reveal_at: string | null;
  exam_type: "nazorat" | "chorak";
  sections: ResultSection[];
  questions: ResultQuestion[];
}

export interface RankingEntry {
  rank_in_class: number;
  student_id: number;
  full_name: string;
  score: number;
  is_me: boolean;
}

export interface SubjectHistoryPoint {
  exam_id: number;
  exam_title: string;
  exam_type: "nazorat" | "chorak";
  score: number;
  max_score: number;
  date: string;
}

export interface SubjectHistory {
  subject_id: number;
  subject_name: string;
  exams_taken_count: number;
  average_percent: number | null;
  trend: "improving" | "declining" | "stable" | null;
  timeline: SubjectHistoryPoint[];
}

export interface Subject {
  id: number;
  name: string;
  code: string | null;
}

export async function listSubjects(): Promise<Subject[]> {
  const { data } = await apiClient.get<Subject[]>("/student/subjects");
  return data;
}

// By default the server returns what is running, upcoming or recent (last 30
// days); includeOld asks for the whole history.
export async function listMyExams(includeOld = false): Promise<ExamListItem[]> {
  const { data } = await apiClient.get<ExamListItem[]>("/student/me/exams", {
    params: includeOld ? { include_old: true } : undefined,
  });
  return data;
}

/** What the "before you start" screen shows. Reading it never starts the clock. */
export async function getExamInfo(examId: number): Promise<ExamListItem> {
  const { data } = await apiClient.get<ExamListItem>(`/student/exams/${examId}/info`);
  return data;
}

export async function startExam(examId: number): Promise<AttemptState> {
  const { data } = await apiClient.post<AttemptState>(`/student/exams/${examId}/start`);
  return data;
}

export async function getMyAttempt(examId: number): Promise<AttemptState> {
  const { data } = await apiClient.get<AttemptState>(`/student/exams/${examId}/attempt`);
  return data;
}

export async function submitAnswer(
  examId: number,
  questionId: number,
  body: { selected_option_id?: number | null; answer_text?: string | null }
): Promise<void> {
  await apiClient.put(`/student/exams/${examId}/answers/${questionId}`, body);
}

export async function submitExam(examId: number): Promise<SubmitResult> {
  const { data } = await apiClient.post<SubmitResult>(`/student/exams/${examId}/submit`);
  return data;
}

export async function getResult(examId: number): Promise<ExamResult> {
  const { data } = await apiClient.get<ExamResult>(`/student/exams/${examId}/result`);
  return data;
}

export async function getExamRanking(examId: number): Promise<RankingEntry[]> {
  const { data } = await apiClient.get<RankingEntry[]>(`/student/exams/${examId}/ranking`);
  return data;
}

export async function getSubjectHistory(subjectId: number): Promise<SubjectHistory> {
  const { data } = await apiClient.get<SubjectHistory>(`/student/me/subjects/${subjectId}/history`);
  return data;
}
