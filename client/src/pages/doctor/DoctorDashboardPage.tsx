import { useAuth } from "../../hooks/useAuth";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";

export default function DoctorDashboardPage() {
  const { user } = useAuth();

  return (
    <>
      <PageHeader
        title={`Welcome, Dr. ${user?.name ?? ""}`.trim()}
        description="You only see patients who have explicitly authorized you. Records are never shared automatically."
      />

      <div className="grid gap-4 md:grid-cols-2">
        <Card
          title="Authorized patients"
          description="Patients who have granted you access to their records."
        >
          <p className="text-2xl font-semibold text-slate-900">—</p>
          <p className="mt-1 text-sm text-slate-500">Available in Phase 3</p>
        </Card>
        <Card title="How access works" description="CAREVERSE authorization model.">
          <ul className="space-y-2 text-sm text-slate-600">
            <li className="flex gap-2">
              <Badge tone="success">Consent</Badge>
              <span>A patient grants access from their own profile. There is no open patient directory.</span>
            </li>
            <li className="flex gap-2">
              <Badge tone="info">Scoped</Badge>
              <span>Access covers only that one patient, and the patient can revoke it at any time.</span>
            </li>
            <li className="flex gap-2">
              <Badge tone="warning">Verify</Badge>
              <span>
                Summaries are AI-generated. Always confirm values against the original documents.
              </span>
            </li>
          </ul>
        </Card>
      </div>
    </>
  );
}
