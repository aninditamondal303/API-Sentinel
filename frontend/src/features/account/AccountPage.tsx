import { useState, type ChangeEvent, type FormEvent } from "react";
import { ApiError } from "@/api/client";
import { authApi } from "@/api/endpoints";
import { useAuth } from "@/auth/AuthContext";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { InlineError } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { validateChangePassword, type Errors } from "@/features/auth/validation";

type Key = "currentPassword" | "newPassword" | "confirm";
const EMPTY = { currentPassword: "", newPassword: "", confirm: "" };

function ChangePasswordForm() {
  const toast = useToast();
  const [values, setValues] = useState(EMPTY);
  const [errors, setErrors] = useState<Errors<Key>>({});
  const [serverError, setServerError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);
  const set = (key: Key) => (event: ChangeEvent<HTMLInputElement>) => setValues((v) => ({ ...v, [key]: event.target.value }));

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const found = validateChangePassword(values);
    setErrors(found);
    setServerError(null);
    if (Object.keys(found).length > 0) return;
    setSubmitting(true);
    try {
      await authApi.changePassword({ currentPassword: values.currentPassword, newPassword: values.newPassword });
      setValues(EMPTY);
      toast.success("Password changed. Use the new password next time you sign in.");
    } catch (error) {
      const mapped: Errors<Key> = {};
      if (error instanceof ApiError) {
        for (const issue of error.errors) {
          if (issue.field === "currentPassword") mapped.currentPassword = "This is not your current password.";
          else if (issue.field === "newPassword") mapped.newPassword = issue.message;
        }
      }
      setErrors(mapped);
      if (Object.keys(mapped).length === 0) setServerError(error);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} noValidate className="max-w-md space-y-4">
      <Field label="Current password" error={errors.currentPassword}>
        {(props) => <Input {...props} type="password" autoComplete="current-password" value={values.currentPassword} onChange={set("currentPassword")} />}
      </Field>
      <Field label="New password" error={errors.newPassword} hint="At least 8 characters, with a letter and a digit.">
        {(props) => <Input {...props} type="password" autoComplete="new-password" value={values.newPassword} onChange={set("newPassword")} />}
      </Field>
      <Field label="Confirm new password" error={errors.confirm}>
        {(props) => <Input {...props} type="password" autoComplete="new-password" value={values.confirm} onChange={set("confirm")} />}
      </Field>
      <InlineError error={serverError} />
      <Button type="submit" loading={submitting}>Change password</Button>
    </form>
  );
}

export function AccountPage() {
  const { user } = useAuth();
  return (
    <>
      <PageHeader eyebrow="Settings" title="Account" description="Your sign-in details." />
      <div className="space-y-6">
        <Card className="p-5">
          <dl className="grid gap-3 text-sm sm:grid-cols-[8rem_1fr]">
            <dt className="text-ink-400">Name</dt><dd className="text-ink-100">{user?.displayName}</dd>
            <dt className="text-ink-400">Email</dt><dd className="break-all text-ink-100">{user?.email}</dd>
          </dl>
        </Card>
        <Card className="p-5">
          <h2 className="mb-4 text-base font-semibold text-ink-100">Change password</h2>
          <ChangePasswordForm />
        </Card>
      </div>
    </>
  );
}
