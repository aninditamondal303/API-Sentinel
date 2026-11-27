// Mirrors the backend's RegisterRequest constraints so users see problems before submitting.
export type Errors<K extends string> = Partial<Record<K, string>>;

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateLogin(values: { email: string; password: string }): Errors<"email" | "password"> {
  const errors: Errors<"email" | "password"> = {};
  if (!values.email.trim()) errors.email = "Enter your email address.";
  else if (!EMAIL.test(values.email.trim())) errors.email = "Enter a valid email address.";
  if (!values.password) errors.password = "Enter your password.";
  return errors;
}

export function validateRegister(values: { email: string; password: string; displayName: string; confirm: string }):
    Errors<"email" | "password" | "displayName" | "confirm"> {
  const errors: Errors<"email" | "password" | "displayName" | "confirm"> = {};
  const name = values.displayName.trim();
  if (!name) errors.displayName = "Enter your name.";
  else if (name.length > 100) errors.displayName = "Use at most 100 characters.";
  const email = values.email.trim();
  if (!email) errors.email = "Enter your email address.";
  else if (!EMAIL.test(email) || email.length > 254) errors.email = "Enter a valid email address.";
  if (values.password.length < 8 || values.password.length > 128) errors.password = "Use 8 to 128 characters.";
  else if (!/[A-Za-z]/.test(values.password) || !/\d/.test(values.password)) errors.password = "Include at least one letter and one digit.";
  if (values.confirm !== values.password) errors.confirm = "Passwords do not match.";
  return errors;
}

function passwordProblem(password: string): string | undefined {
  if (password.length < 8 || password.length > 128) return "Use 8 to 128 characters.";
  if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) return "Include at least one letter and one digit.";
  return undefined;
}

export function validateChangePassword(values: { currentPassword: string; newPassword: string; confirm: string }):
    Errors<"currentPassword" | "newPassword" | "confirm"> {
  const errors: Errors<"currentPassword" | "newPassword" | "confirm"> = {};
  if (!values.currentPassword) errors.currentPassword = "Enter your current password.";
  const problem = passwordProblem(values.newPassword);
  if (problem) errors.newPassword = problem;
  else if (values.newPassword === values.currentPassword) errors.newPassword = "Choose a password different from the current one.";
  if (values.confirm !== values.newPassword) errors.confirm = "Passwords do not match.";
  return errors;
}
