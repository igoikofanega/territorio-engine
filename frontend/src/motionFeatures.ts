/** Las funciones de animación de `domAnimation`, en su PROPIO módulo.
 *
 * Esto no es cosmético: es lo único que hace que `LazyMotion` cumpla lo que promete.
 * Si `Movimiento.tsx` importara `domAnimation` de forma síncrona (`import { domAnimation }
 * from "motion/react"`) y se lo pasara directo a `<LazyMotion features={domAnimation}>`,
 * Vite lo empaquetaría en el chunk principal igual que cualquier otro import — "Lazy" en
 * el nombre no hace nada por sí solo si la importación sigue siendo estática.
 *
 * `LazyMotion` solo carga esto de verdad aparte cuando `features` es una FUNCIÓN que
 * hace un `import()` dinámico a un módulo separado — como este. `Movimiento.tsx` pasa
 * `loadFeatures` (no `domAnimation` directo), y ese `import()` dinámico es lo que le da
 * a Vite la señal para generar un chunk propio.
 */
export { domAnimation as default } from "motion/react";
