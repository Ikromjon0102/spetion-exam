import { apiClient } from "./client";

export interface ClassOut {
  id: number;
  grade_level: number;
  label: string;
  display_name: string;
  homeroom_teacher_id: number | null;
  homeroom_teacher_name: string | null;
}

export interface ClassSubjectAssignment {
  subject_id: number;
  subject_name: string;
  teacher_id: number;
  teacher_name: string;
}

export interface ClassDetail extends ClassOut {
  student_count: number;
  can_manage_students: boolean;
  subject_assignments: ClassSubjectAssignment[];
}

export interface SubjectOut {
  id: number;
  name: string;
  code: string | null;
}

export interface TeacherAssignment {
  id: number;
  class_id: number;
  class_name: string;
  subject_id: number;
  subject_name: string;
}

export interface StudentRow {
  id: number;
  user_id: number;
  username: string;
  full_name: string;
  class_id: number;
  class_name: string;
  student_code: string;
  is_active: boolean;
}

export interface TeacherRow {
  id: number;
  user_id: number;
  username: string;
  full_name: string;
  subject_id: number | null;
  is_active: boolean;
}

export interface ExamUpload {
  id: number;
  original_filename: string;
  file_type: string;
  status: "pending" | "parsing" | "parsed" | "parse_failed";
  parse_error: string | null;
  created_at: string;
  exam_id: number | null;
}

export interface ExamSummary {
  id: number;
  title: string;
  subject_id: number;
  subject_name: string;
  class_id: number;
  class_name: string;
  status: string;
  start_at: string | null;
  end_at: string | null;
  duration_minutes: number;
  total_points: number | null;
  question_count: number;
  needs_review_count: number;
  can_edit: boolean;
}

export interface QuestionOption {
  id: number;
  order_index: number;
  option_text: string;
  is_correct: boolean;
}

export interface Question {
  id: number;
  order_index: number;
  question_type: string;
  prompt_text: string;
  prompt_image_key: string | null;
  points: number;
  source: string;
  needs_review: boolean;
  parse_confidence: "high" | "low" | null;
  options: QuestionOption[];
}

export interface ExamDetail extends ExamSummary {
  questions: Question[];
}

export interface AttemptMonitor {
  student_id: number;
  full_name: string;
  status: string;
  started_at: string | null;
  deadline_at: string | null;
  submitted_at: string | null;
  score: number | null;
}

export interface ClassRankingRow {
  rank_in_class: number;
  student_id: number;
  full_name: string;
  score: number;
  percentile: number | null;
}

export interface ClassRanking {
  exam_id: number;
  exam_title: string;
  rankings: ClassRankingRow[];
}

export async function listAdminClasses(): Promise<ClassOut[]> {
  const { data } = await apiClient.get<ClassOut[]>("/admin/classes");
  return data;
}

export async function listAdminSubjects(): Promise<SubjectOut[]> {
  const { data } = await apiClient.get<SubjectOut[]>("/admin/subjects");
  return data;
}

export async function listMyAssignments(): Promise<TeacherAssignment[]> {
  const { data } = await apiClient.get<TeacherAssignment[]>("/admin/teachers/me/assignments");
  return data;
}

export async function createClass(body: {
  grade_level: number;
  label: string;
  display_name: string;
}): Promise<ClassOut> {
  const { data } = await apiClient.post<ClassOut>("/admin/classes", body);
  return data;
}

export async function getClassDetail(classId: number): Promise<ClassDetail> {
  const { data } = await apiClient.get<ClassDetail>(`/admin/classes/${classId}`);
  return data;
}

export async function updateClass(
  classId: number,
  body: Partial<{ grade_level: number; label: string; display_name: string; homeroom_teacher_id: number | null }>
): Promise<ClassOut> {
  const { data } = await apiClient.put<ClassOut>(`/admin/classes/${classId}`, body);
  return data;
}

export async function deleteClass(classId: number): Promise<void> {
  await apiClient.delete(`/admin/classes/${classId}`);
}

export async function createSubject(body: { name: string; code?: string }): Promise<SubjectOut> {
  const { data } = await apiClient.post<SubjectOut>("/admin/subjects", body);
  return data;
}

export async function updateSubject(
  subjectId: number,
  body: Partial<{ name: string; code: string | null }>
): Promise<SubjectOut> {
  const { data } = await apiClient.put<SubjectOut>(`/admin/subjects/${subjectId}`, body);
  return data;
}

export async function deleteSubject(subjectId: number): Promise<void> {
  await apiClient.delete(`/admin/subjects/${subjectId}`);
}

export async function listAdminStudents(classId?: number): Promise<StudentRow[]> {
  const { data } = await apiClient.get<StudentRow[]>("/admin/students", {
    params: classId ? { class_id: classId } : undefined,
  });
  return data;
}

export async function createAdminStudent(body: {
  username: string;
  password: string;
  full_name: string;
  class_id: number;
  student_code: string;
}): Promise<StudentRow> {
  const { data } = await apiClient.post<StudentRow>("/admin/students", body);
  return data;
}

export async function updateAdminStudent(
  studentId: number,
  body: Partial<{ full_name: string; class_id: number; is_active: boolean }>
): Promise<StudentRow> {
  const { data } = await apiClient.put<StudentRow>(`/admin/students/${studentId}`, body);
  return data;
}

export async function deleteAdminStudent(studentId: number): Promise<void> {
  await apiClient.delete(`/admin/students/${studentId}`);
}

export interface BulkImportedStudent {
  full_name: string;
  username: string;
  password: string;
}

export interface BulkImportResult {
  created: BulkImportedStudent[];
  errors: string[];
}

export async function bulkImportStudents(classId: number, fullNames: string[]): Promise<BulkImportResult> {
  const { data } = await apiClient.post<BulkImportResult>("/admin/students/bulk-import", {
    class_id: classId,
    full_names: fullNames,
  });
  return data;
}

export async function resetClassPasswords(classId: number, newPassword: string): Promise<{ updated_count: number }> {
  const { data } = await apiClient.post<{ updated_count: number }>(`/admin/classes/${classId}/reset-password`, {
    new_password: newPassword,
  });
  return data;
}

export async function listAdminTeachers(): Promise<TeacherRow[]> {
  const { data } = await apiClient.get<TeacherRow[]>("/admin/teachers");
  return data;
}

export async function createAdminTeacher(body: {
  username: string;
  password: string;
  full_name: string;
  subject_id?: number;
}): Promise<TeacherRow> {
  const { data } = await apiClient.post<TeacherRow>("/admin/teachers", body);
  return data;
}

export async function updateAdminTeacher(
  teacherId: number,
  body: Partial<{ full_name: string; subject_id: number; is_active: boolean }>
): Promise<TeacherRow> {
  const { data } = await apiClient.put<TeacherRow>(`/admin/teachers/${teacherId}`, body);
  return data;
}

export async function deleteAdminTeacher(teacherId: number): Promise<void> {
  await apiClient.delete(`/admin/teachers/${teacherId}`);
}

export async function listTeacherAssignments(teacherId: number): Promise<TeacherAssignment[]> {
  const { data } = await apiClient.get<TeacherAssignment[]>(`/admin/teachers/${teacherId}/assignments`);
  return data;
}

export async function addTeacherAssignment(
  teacherId: number,
  classId: number,
  subjectId: number
): Promise<TeacherAssignment> {
  const { data } = await apiClient.post<TeacherAssignment>(`/admin/teachers/${teacherId}/class-subjects`, {
    teacher_id: teacherId,
    class_id: classId,
    subject_id: subjectId,
  });
  return data;
}

export async function removeTeacherAssignment(teacherId: number, linkId: number): Promise<void> {
  await apiClient.delete(`/admin/teachers/${teacherId}/class-subjects/${linkId}`);
}

export async function uploadExamFile(
  file: File,
  subjectId: number,
  classId: number,
  title?: string
): Promise<ExamUpload> {
  const form = new FormData();
  form.append("file", file);
  form.append("subject_id", String(subjectId));
  form.append("class_id", String(classId));
  if (title) form.append("title", title);
  const { data } = await apiClient.post<ExamUpload>("/admin/exams/uploads", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getUploadStatus(uploadId: number): Promise<ExamUpload> {
  const { data } = await apiClient.get<ExamUpload>(`/admin/exams/uploads/${uploadId}`);
  return data;
}

export async function listExams(filters?: {
  exam_status?: string;
  class_id?: number;
  subject_id?: number;
}): Promise<ExamSummary[]> {
  const { data } = await apiClient.get<ExamSummary[]>("/admin/exams", { params: filters });
  return data;
}

export async function getExamDetail(examId: number): Promise<ExamDetail> {
  const { data } = await apiClient.get<ExamDetail>(`/admin/exams/${examId}`);
  return data;
}

export async function updateExam(
  examId: number,
  body: Partial<{
    title: string;
    duration_minutes: number;
    start_at: string;
    end_at: string;
    shuffle_questions: boolean;
    shuffle_options: boolean;
  }>
): Promise<ExamSummary> {
  const { data } = await apiClient.put<ExamSummary>(`/admin/exams/${examId}`, body);
  return data;
}

export async function updateQuestion(
  examId: number,
  questionId: number,
  body: Partial<{ prompt_text: string; points: number; needs_review: boolean; order_index: number }>
): Promise<Question> {
  const { data } = await apiClient.put<Question>(`/admin/exams/${examId}/questions/${questionId}`, body);
  return data;
}

export async function updateQuestionOption(
  examId: number,
  questionId: number,
  optionId: number,
  body: Partial<{ option_text: string; is_correct: boolean }>
): Promise<QuestionOption> {
  const { data } = await apiClient.put<QuestionOption>(
    `/admin/exams/${examId}/questions/${questionId}/options/${optionId}`,
    body
  );
  return data;
}

export async function addQuestion(
  examId: number,
  body: {
    question_type?: string;
    prompt_text: string;
    points?: number;
    options: { option_text: string; is_correct: boolean }[];
  }
): Promise<Question> {
  const { data } = await apiClient.post<Question>(`/admin/exams/${examId}/questions`, body);
  return data;
}

export async function deleteQuestion(examId: number, questionId: number): Promise<void> {
  await apiClient.delete(`/admin/exams/${examId}/questions/${questionId}`);
}

export async function publishExam(examId: number): Promise<ExamSummary> {
  const { data } = await apiClient.post<ExamSummary>(`/admin/exams/${examId}/publish`);
  return data;
}

export async function closeExam(examId: number): Promise<ExamSummary> {
  const { data } = await apiClient.post<ExamSummary>(`/admin/exams/${examId}/close`);
  return data;
}

export async function listExamAttempts(examId: number): Promise<AttemptMonitor[]> {
  const { data } = await apiClient.get<AttemptMonitor[]>(`/admin/exams/${examId}/attempts`);
  return data;
}

export async function getClassRanking(examId: number): Promise<ClassRanking> {
  const { data } = await apiClient.get<ClassRanking>(`/admin/exams/${examId}/ranking`);
  return data;
}
