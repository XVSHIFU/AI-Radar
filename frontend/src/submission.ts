import { secureUuid } from "./browser-ids";

export function idempotentSubmission() {
  let key: string | undefined;
  let pending = false;
  return {
    begin() {
      if (pending) return undefined;
      pending = true;
      key ??= secureUuid();
      return key;
    },
    finish(success: boolean) {
      pending = false;
      if (success) key = undefined;
    },
    get pending() {
      return pending;
    },
  };
}
