import { describe, expect, it } from "vitest";
import { validateLogin, validateRegister } from "./validation";

describe("auth validation (mirrors backend RegisterRequest)", () => {
  it("requires a letter and a digit, 8 to 128 characters", () => {
    const base = { displayName: "Ada", email: "ada@example.com", confirm: "" };
    expect(validateRegister({ ...base, password: "short1", confirm: "short1" }).password).toMatch(/8 to 128/);
    expect(validateRegister({ ...base, password: "allletters", confirm: "allletters" }).password).toMatch(/letter and one digit/);
    expect(validateRegister({ ...base, password: "12345678", confirm: "12345678" }).password).toMatch(/letter and one digit/);
    expect(validateRegister({ ...base, password: "Correct-horse-9", confirm: "Correct-horse-9" })).toEqual({});
  });

  it("checks email, name and confirmation", () => {
    const errors = validateRegister({ displayName: " ", email: "nope", password: "Correct-horse-9", confirm: "other" });
    expect(Object.keys(errors).sort()).toEqual(["confirm", "displayName", "email"]);
    expect(validateLogin({ email: "", password: "" })).toEqual({ email: expect.any(String), password: expect.any(String) });
  });
});
