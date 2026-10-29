import { Alert, Button, Group } from "@mantine/core";
import { IconArrowLeft, IconTool } from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";

import { get, setSetupSchool } from "@/api/client";
import { SetupSchoolContext, useAuth } from "@/auth/AuthContext";
import NotFoundPage from "@/pages/NotFoundPage";

import SetupPage from "./SetupPage";

/** The owner console setting up one school: the school's own setup screens, editable here
 *  and read-only for the school. Every request names the school in X-Setup-School. */
export default function PlatformSetupPage() {
  const { me } = useAuth();
  const { id } = useParams();
  const navigate = useNavigate();
  const client = useQueryClient();
  const schoolId = Number(id);
  // Set before the first child query runs, so no request goes out without the school.
  const [ready] = useState(() => {
    setSetupSchool(schoolId);
    client.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
    return true;
  });
  useEffect(() => {
    // Set again on (re)mount: React may mount, unmount and mount again in development.
    setSetupSchool(schoolId);
    return () => {
      setSetupSchool(null);
      client.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
    };
  }, [client, schoolId]);
  const { data: school } = useQuery({ queryKey: ["platform-school", schoolId], queryFn: () => get(`/platform/schools/${schoolId}/`) });
  if (me?.portal !== "platform") return <NotFoundPage />;
  if (!ready || !school) return null;
  return (
    <SetupSchoolContext.Provider value={{ id: schoolId, name: school.name }}>
      <Group mb="sm">
        <Button variant="subtle" leftSection={<IconArrowLeft size={16} />} onClick={() => navigate("/platform")}>
          Owner console
        </Button>
      </Group>
      <Alert icon={<IconTool size={18} />} color="orange" mb="md" title={`Setting up ${school.name} (${school.code})`}>
        Changes here apply to this school straight away. The school's users see this setup but cannot change it, except the
        grade cut-offs, which the head teacher, director and DOS may adjust.
      </Alert>
      <SetupPage />
    </SetupSchoolContext.Provider>
  );
}
