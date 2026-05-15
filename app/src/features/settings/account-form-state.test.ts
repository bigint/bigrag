import { describe, expect, it } from "vitest";
import {
  defaultPasswordFormValues,
  passwordBodyFromValues,
  validatePasswordFormValues,
} from "./account-form-state";

describe("account form state", () => {
  it("creates defaults and validates password fields", () => {
    expect(defaultPasswordFormValues()).toEqual({ confirm: "", current: "", next: "" });
    expect(validatePasswordFormValues(defaultPasswordFormValues())).toBe(
      "Current password is required",
    );
    expect(
      validatePasswordFormValues({
        confirm: "password2",
        current: "current-password",
        next: "password1",
      }),
    ).toBe("Passwords do not match");
  });

  it("builds password update payloads", () => {
    expect(
      passwordBodyFromValues({
        confirm: "new-password",
        current: "current-password",
        next: "new-password",
      }),
    ).toEqual({
      current_password: "current-password",
      new_password: "new-password",
    });
  });
});
