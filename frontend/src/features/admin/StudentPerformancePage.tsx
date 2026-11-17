import { useCallback } from "react";
import { useParams } from "react-router-dom";
import { getStudentDynamics } from "../../api/dynamicsApi";
import { AdminLayout } from "../../components/ui";
import DynamicsPage from "../shared/DynamicsPage";

/** A student's dynamics for a teacher/admin: the same page the student sees,
 * plus the place in the class. */
export default function StudentPerformancePage() {
  const { studentId } = useParams();
  const id = Number(studentId);
  const load = useCallback((year?: number) => getStudentDynamics(id, year), [id]);
  return <DynamicsPage load={load} wrap={(children) => <AdminLayout>{children}</AdminLayout>} />;
}
