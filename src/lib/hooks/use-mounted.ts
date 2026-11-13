import { useSyncExternalStore } from "react";

const emptySubscribe = () => () => {};

/**
 * React 19 compliant hook to determine if component has mounted on the client,
 * avoiding hydration mismatch and cascading render lint errors.
 */
export function useMounted(): boolean {
  return useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false
  );
}
