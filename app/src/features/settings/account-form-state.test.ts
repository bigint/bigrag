import { describe, expect, it } from "vitest";
import {
  defaultPasswordFormValues,
  passwordBodyFromValues,
  validatePasswordFormValues,
} from "./account-form-state";

describe("account form state", () => {
  it("builds default password form values", () => {
    expect(defaultPasswordFormValues()).toEqual({
      confirm: "",
      current: "",
      next: "",
    });
  });

  it("validates password change submissions", () => {
    expect(validatePasswordFormValues(defaultPasswordFormValues())).toBe(
      "Current password is required",
    );
    expect(
      validatePasswordFormValues({
        confirm: "",
        current: "current-password",
        next: "",
      }),
    ).toBe("New password is required");
    expect(
      validatePasswordFormValues({
        confirm: "new-password",
        current: "current-password",
        next: "different-password",
      }),
    ).toBe("Passwords do not match");
  });

  it("preserves the password payload shape", () => {
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
