import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { ApiError } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { safeNext } from "@/auth/RequireAuth";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { InlineError } from "@/components/ui/States";
import { AuthLayout } from "./AuthLayout";
import { SlowServerNotice } from "./SlowServerNotice";
import { validateLogin, type Errors } from "./validation";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Errors<"email" | "password">>({});
  const [serverError, setServerError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const found = validateLogin({ email, password });
    setErrors(found);
    setServerError(null);
    if (Object.keys(found).length > 0) return;
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate(safeNext(params.get("next")), { replace: true });
    } catch (error) {
      setServerError(error instanceof ApiError && error.status === 401
        ? new ApiError(401, error.code, "Incorrect email or password.") : error);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to review your API changes."
      footer={<>New to API Sentinel? <Link to="/register" className="font-medium text-accent-300 hover:text-accent-200">Create an account</Link></>}>
      {params.get("expired") ? (
        <p role="status" className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-100">
          Your session ended. Please sign in again.
        </p>
      ) : null}
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <Field label="Email" error={errors.email}>
          {(props) => <Input {...props} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />}
        </Field>
        <Field label="Password" error={errors.password}>
          {(props) => <Input {...props} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <InlineError error={serverError} />
        <SlowServerNotice active={submitting} />
        <Button type="submit" className="w-full" size="lg" loading={submitting}>Sign in</Button>
      </form>
    </AuthLayout>
  );
}
