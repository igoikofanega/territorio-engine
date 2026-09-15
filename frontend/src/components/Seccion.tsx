import type { ReactNode } from "react";

/** Un bloque desplegable de la ficha, sobre `<details>/<summary>` nativos.
 *
 * No es un sistema de pestañas a mano: eso costaría ~120 líneas (estado, roles ARIA,
 * gestión de foco) para un resultado peor. `<details>` da teclado, accesibilidad y
 * `Ctrl+F` del navegador gratis, con cero estado en React.
 *
 * El `resumen` se ve aunque el bloque esté cerrado ("Vivir aquí · 62/100"): colapsar una
 * sección no debe ser ocultarla.
 *
 * La animación de apertura llega en un paso posterior (con `motion`); por ahora el salto
 * de altura es seco, que es lo que da CSS puro con `<details>`.
 */
export default function Seccion({
  titulo,
  resumen,
  abierta = false,
  children,
}: {
  titulo: string;
  resumen?: string | null;
  abierta?: boolean;
  children: ReactNode;
}) {
  return (
    <details className="ficha-seccion" open={abierta}>
      <summary>
        <span className="ficha-seccion-flecha" aria-hidden="true">
          ▸
        </span>
        <span className="label-caps">{titulo}</span>
        {resumen && <span className="ficha-seccion-resumen">{resumen}</span>}
      </summary>
      <div className="ficha-seccion-cuerpo">{children}</div>
    </details>
  );
}
