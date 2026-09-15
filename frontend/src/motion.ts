export const motion = { enter: 680, exit: 460, reduced: 120 } as const;
export function motionDuration(kind: "enter" | "exit") {
  const reduced = typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  return reduced ? motion.reduced : motion[kind];
}
export function syncMotionVariables() {
  if (typeof document === "undefined") return;
  const root = document.documentElement.style;
  root.setProperty("--motion-enter", `${motionDuration("enter")}ms`);
  root.setProperty("--motion-exit", `${motionDuration("exit")}ms`);
}