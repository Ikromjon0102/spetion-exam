import { getMyDynamics } from "../../api/dynamicsApi";
import { AppHeader } from "../../components/ui";
import DynamicsPage from "../shared/DynamicsPage";

/** The student's own page: how they are doing across every exam and subject
 * of the school year (no class rank — that is for teachers). */
export default function ProfilePage() {
  return (
    <DynamicsPage
      load={getMyDynamics}
      wrap={(children) => (
        <>
          <AppHeader />
          {children}
        </>
      )}
    />
  );
}
