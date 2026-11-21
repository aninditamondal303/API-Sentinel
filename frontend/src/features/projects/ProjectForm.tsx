import { useState, type FormEvent } from "react";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { InlineError } from "@/components/ui/States";

export interface ProjectValues { name: string; description: string }

export function ProjectForm({ initial, submitLabel, onSubmit, onCancel }: {
  initial?: ProjectValues;
  submitLabel: string;
  onSubmit: (values: ProjectValues) => Promise<void>;
  onCancel?: () => void;
}) {
  const [values, setValues] = useState<ProjectValues>(initial ?? { name: "", description: "" });
  const [errors, setErrors] = useState<Partial<ProjectValues>>({});
  const [serverError, setServerError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const name = values.name.trim();
    const found: Partial<ProjectValues> = {};
    if (name.length < 3 || name.length > 100) found.name = "Use 3 to 100 characters.";
    if (values.description.length > 1000) found.description = "Use at most 1000 characters.";
    setErrors(found);
    setServerError(null);
    if (Object.keys(found).length) return;
    setSubmitting(true);
    try {
      await onSubmit({ name, description: values.description.trim() });
    } catch (error) {
      if (error instanceof ApiError && error.code === "PROJECT_NAME_TAKEN") setErrors({ name: "You already have a project with this name." });
      else setServerError(error);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <Field label="Project name" error={errors.name}>
        {(props) => <Input {...props} autoFocus placeholder="e.g. Orders API" value={values.name}
          onChange={(e) => setValues((v) => ({ ...v, name: e.target.value }))} />}
      </Field>
      <Field label="Description (optional)" error={errors.description}>
        {(props) => <Textarea {...props} placeholder="What does this API do?" value={values.description}
          onChange={(e) => setValues((v) => ({ ...v, description: e.target.value }))} />}
      </Field>
      <InlineError error={serverError} />
      <div className="flex justify-end gap-2 pt-1">
        {onCancel ? <Button variant="ghost" onClick={onCancel}>Cancel</Button> : null}
        <Button type="submit" loading={submitting}>{submitLabel}</Button>
      </div>
    </form>
  );
}
