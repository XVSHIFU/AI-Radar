export const motion = {
  enter: 680,
  exit: 460,
  drawerEnter: 380,
  drawerExit: 260,
  reduced: 120,
} as const;

export type MotionKind = "enter" | "exit" | "drawerEnter" | "drawerExit";

export function motionDuration(kind: MotionKind) {
  const reduced = typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  return reduced ? motion.reduced : motion[kind];
}

export function syncMotionVariables() {
  if (typeof document === "undefined") return;
  const root = document.documentElement.style;
  root.setProperty("--motion-enter", `${motionDuration("enter")}ms`);
  root.setProperty("--motion-exit", `${motionDuration("exit")}ms`);
  root.setProperty("--drawer-enter", `${motionDuration("drawerEnter")}ms`);
  root.setProperty("--drawer-exit", `${motionDuration("drawerExit")}ms`);
}
