import { describe, expect, it } from "vitest";
import {
  defaultLoginFormValues,
  defaultSetupFormValues,
  loginBodyFromValues,
  setupBodyFromValues,
  validateEmail,
  validateLoginFormValues,
  validatePassword,
  validateSetupFormValues,
} from "./auth-form-state";

describe("auth form state", () => {
  it("creates login and setup defaults", () => {
    expect(defaultLoginFormValues()).toEqual({ email: "", password: "" });
    expect(defaultSetupFormValues()).toEqual({
      confirm: "",
      displayName: "",
      email: "",
      password: "",
    });
  });

  it("validates auth credentials", () => {
    expect(validateEmail("")).toBe("Email is required");
    expect(validateEmail("bad")).toBe("Enter a valid email");
    expect(validateEmail("user@example")).toBeUndefined();
    expect(validatePassword("short")).toBe("Password must be at least 8 characters");
    expect(
      validateLoginFormValues({ email: "user@example", password: "password" }),
    ).toBeUndefined();
  });

  it("validates setup confirmation and builds payloads", () => {
    expect(
      validateSetupFormValues({
        confirm: "password2",
        displayName: "Ada",
        email: "ada@example",
        password: "password1",
      }),
    ).toBe("Passwords do not match");
    expect(
      setupBodyFromValues({
        confirm: "password1",
        displayName: "Ada",
        email: "ada@example",
        password: "password1",
      }),
    ).toEqual({ display_name: "Ada", email: "ada@example", password: "password1" });
    expect(loginBodyFromValues({ email: "ada@example", password: "password1" })).toEqual({
      email: "ada@example",
      password: "password1",
    });
  });
});
