export type PasswordFormValues = {
  confirm: string;
  current: string;
  next: string;
};

export const defaultPasswordFormValues = (): PasswordFormValues => ({
  confirm: "",
  current: "",
  next: "",
});

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
