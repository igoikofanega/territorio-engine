import { LazyMotion, MotionConfig } from "motion/react";
import type { ReactNode } from "react";

/** Envoltorio único de `motion` para toda la app, montado una vez en `main.tsx`.
 *
 * `features` es una FUNCIÓN que hace `import()` dinámico a `motionFeatures.ts`, no el
 * objeto `domAnimation` importado a pelo. Esa diferencia es la que separa el chunk: con
 * un import estático, Vite mete `domAnimation` en el bundle principal igual que
 * cualquier otro import y "Lazy" no significa nada por sí solo.
 *
 * Medido con `vite build` contra el mismo commit sin `motion` (114,1 KB comprimidos):
 *
 * - **Con import estático** (el primer intento): 143,2 KB en un único chunk — 29 KB de
 *   golpe, sin separar nada. El nombre "Lazy" no cumplía lo que promete.
 * - **Con el loader dinámico** (esto): 131,2 KB en el chunk principal + un chunk propio
 *   `motionFeatures` de 14,2 KB que el navegador pide aparte, tras el primer pintado.
 *
 * El chunk principal sigue subiendo 17 KB — el runtime base de `m`/`AnimatePresence`/
 * `MotionConfig` no es tan diminuto como sugería la documentación que se consultó antes
 * de escribir esto (~5 KB) — pero esos 17 KB no bloquean nada nuevo: viajan en el mismo
 * chunk que ya se estaba descargando. Lo que SÍ logra el loader dinámico es que las
 * funciones de animación en sí (drag, gestos, exit) no formen parte del camino crítico.
 *
 * `reducedMotion="user"` respeta `prefers-reduced-motion` en TODAS las animaciones que
 * cuelguen de aquí, sin comprobarlo a mano en cada componente.
 *
 * `strict`: si algún componente usara `motion.div` en vez de `m.div`, esto lanza en vez
 * de colar en silencio el paquete completo (~34 KB) por la puerta de atrás.
 */
const loadFeatures = () => import("../motionFeatures").then((mod) => mod.default);

export default function Movimiento({ children }: { children: ReactNode }) {
  return (
    <LazyMotion features={loadFeatures} strict>
      <MotionConfig reducedMotion="user">{children}</MotionConfig>
    </LazyMotion>
  );
}
