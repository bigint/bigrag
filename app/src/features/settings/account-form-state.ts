import { validateEmail } from "@/features/auth/auth-form-state";
import type { CurrentUser } from "@/hooks/use-auth";

export type ProfileFormValues = {
  displayName: string;
  email: string;
};

export type PasswordFormValues = {
  confirm: string;
  current: string;
  next: string;
};

export const defaultProfileFormValues = (): ProfileFormValues => ({
  displayName: "",
  email: "",
});

export const profileFormValuesFromUser = (user: CurrentUser): ProfileFormValues => ({
  displayName: user.display_name,
  email: user.email,
});

export const defaultPasswordFormValues = (): PasswordFormValues => ({
  confirm: "",
  current: "",
  next: "",
});

export const validateProfileFormValues = ({
  displayName,
  email,
}: ProfileFormValues): string | undefined => {
  if (displayName.length > 120) return "Display name must be 120 characters or fewer";
  return validateProfileEmail(email);
};

export const validateProfileEmail = (email: string): string | undefined =>
  validateEmail(email.trim());

export const profileBodyFromValues = ({ displayName, email }: ProfileFormValues) => ({
  display_name: displayName.trim(),
  email: email.trim(),
});

export const profileFormHasChanges = (
  current: ProfileFormValues,
  next: ProfileFormValues,
): boolean =>
  current.displayName.trim() !== next.displayName.trim() ||
  current.email.trim().toLowerCase() !== next.email.trim().toLowerCase();

export const validatePasswordFormValues = ({
  confirm,
  current,
  next,
}: PasswordFormValues): string | undefined => {
  if (!current) return "Current password is required";
  if (!next) return "New password is required";
  if (next.length < 8) return "New password must be at least 8 characters";
  if (!confirm) return "Confirm new password is required";
  if (confirm.length < 8) return "Confirm new password must be at least 8 characters";
  if (next !== confirm) return "Passwords do not match";
  return undefined;
};

export const passwordBodyFromValues = ({ current, next }: PasswordFormValues) => ({
  current_password: current,
  new_password: next,
});
