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
  it("builds login and setup defaults", () => {
    expect(defaultLoginFormValues()).toEqual({ email: "", password: "" });
    expect(defaultSetupFormValues()).toEqual({
      confirm: "",
      displayName: "",
      email: "",
      password: "",
    });
  });

  it("validates email and password inputs", () => {
    expect(validateEmail("")).toBe("Email is required");
    expect(validateEmail("admin")).toBe("Enter a valid email");
    expect(validateEmail("admin@example.com")).toBeUndefined();
    expect(validatePassword("")).toBe("Password is required");
    expect(validatePassword("short")).toBe("Password must be at least 8 characters");
    expect(validatePassword("long-enough")).toBeUndefined();
  });

  it("validates submitted login and setup values", () => {
    expect(validateLoginFormValues({ email: "", password: "" })).toBe("Email is required");
    expect(
      validateSetupFormValues({
        confirm: "",
        displayName: "",
        email: "admin@example.com",
        password: "long-enough",
      }),
    ).toBe("Confirm password is required");
    expect(
      validateSetupFormValues({
        confirm: "different",
        displayName: "",
        email: "admin@example.com",
        password: "long-enough",
      }),
    ).toBe("Passwords do not match");
  });

  it("preserves auth payload shapes", () => {
    expect(loginBodyFromValues({ email: "admin@example.com", password: "password123" })).toEqual({
      email: "admin@example.com",
      password: "password123",
    });
    expect(
      setupBodyFromValues({
        confirm: "password123",
        displayName: "Admin",
        email: "admin@example.com",
        password: "password123",
      }),
    ).toEqual({
      display_name: "Admin",
      email: "admin@example.com",
      password: "password123",
    });
  });
});
