import { useState, type ChangeEvent, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { ApiError } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { InlineError } from "@/components/ui/States";
import { AuthLayout } from "./AuthLayout";
import { validateRegister, type Errors } from "./validation";

type Key = "email" | "password" | "displayName" | "confirm";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [values, setValues] = useState({ displayName: "", email: "", password: "", confirm: "" });
  const [errors, setErrors] = useState<Errors<Key>>({});
  const [serverError, setServerError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);
  const set = (key: Key) => (event: ChangeEvent<HTMLInputElement>) => setValues((v) => ({ ...v, [key]: event.target.value }));

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const found = validateRegister(values);
    setErrors(found);
    setServerError(null);
    if (Object.keys(found).length > 0) return;
    setSubmitting(true);
    try {
      await register(values.email.trim(), values.password, values.displayName.trim());
      navigate("/app", { replace: true });
    } catch (error) {
      if (error instanceof ApiError && error.code === "EMAIL_TAKEN") {
        setErrors({ email: "An account with this email already exists." });
      } else if (error instanceof ApiError && error.errors.length > 0) {
        const mapped: Errors<Key> = {};
        for (const issue of error.errors) {
          if (issue.field === "email" || issue.field === "password" || issue.field === "displayName") mapped[issue.field] = issue.message;
        }
        setErrors(mapped);
        if (Object.keys(mapped).length === 0) setServerError(error);
      } else {
        setServerError(error);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Create your account" subtitle="Start catching breaking API changes in minutes."
      footer={<>Already have an account? <Link to="/login" className="font-medium text-accent-300 hover:text-accent-200">Sign in</Link></>}>
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <Field label="Name" error={errors.displayName}>
          {(props) => <Input {...props} autoComplete="name" value={values.displayName} onChange={set("displayName")} />}
        </Field>
        <Field label="Work email" error={errors.email}>
          {(props) => <Input {...props} type="email" autoComplete="email" value={values.email} onChange={set("email")} />}
        </Field>
        <Field label="Password" error={errors.password} hint="At least 8 characters, with a letter and a digit.">
          {(props) => <Input {...props} type="password" autoComplete="new-password" value={values.password} onChange={set("password")} />}
        </Field>
        <Field label="Confirm password" error={errors.confirm}>
          {(props) => <Input {...props} type="password" autoComplete="new-password" value={values.confirm} onChange={set("confirm")} />}
        </Field>
        <InlineError error={serverError} />
        <Button type="submit" className="w-full" size="lg" loading={submitting}>Create account</Button>
      </form>
    </AuthLayout>
  );
}
