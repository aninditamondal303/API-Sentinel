import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { projectApi } from "@/api/endpoints";
import { SEVERITIES, type Project, type Severity } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Checkbox, Field, Select } from "@/components/ui/Field";
import { InlineError } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";

export function PolicyEditor({ project }: { project: Project }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [failOn, setFailOn] = useState<Severity | "">(project.policy.failOn ?? "");
  const [manual, setManual] = useState(project.policy.failOnManualReview);
  const dirty = (failOn || null) !== project.policy.failOn || manual !== project.policy.failOnManualReview;
  const save = useMutation({
    mutationFn: () => projectApi.updatePolicy(project.id, { failOn: failOn || null, failOnManualReview: manual }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["project", project.id] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Compatibility policy saved.");
    },
  });
  return (
    <div className="space-y-5">
      <Field label="Fail a scan when a finding is at least" hint="Applied to new scans that use the project policy. Existing scans keep their recorded threshold.">
        {(props) => (
          <Select {...props} value={failOn} onChange={(e) => setFailOn(e.target.value as Severity | "")}>
            {SEVERITIES.map((s) => <option key={s} value={s}>{s.charAt(0) + s.slice(1).toLowerCase()}</option>)}
            <option value="">Never (threshold off)</option>
          </Select>
        )}
      </Field>
      <Checkbox label="Fail when a finding requires manual review" checked={manual} onChange={setManual}
        description="Changes the analyzer cannot classify with certainty block the release until reviewed." />
      <InlineError error={save.error} />
      <div className="flex justify-end">
        <Button disabled={!dirty} loading={save.isPending} onClick={() => save.mutate()}>Save policy</Button>
      </div>
    </div>
  );
}
