import { AlertTriangle, BookOpen, Database, MapPin, Scale } from "lucide-react";

/**
 * Metodología, fuentes y límites.
 *
 * Existe porque el proyecto hace afirmaciones que necesitan una nota al pie y no tenían
 * dónde ponerla: el ADR 0005 exige que el MAE de la ablación se publique siempre junto al
 * aviso de que no es comparable con el del modelo titular, y hasta ahora no había ninguna
 * pantalla donde decirlo. Un mapa que predice el vaciamiento de un pueblo sin enseñar su
 * incertidumbre es peor que no tener mapa.
 *
 * Las cifras están escritas a mano a partir de `docs/evaluacion/informe.md`, que sí se
 * regenera con `make evaluar`. Si cambian allí, hay que cambiarlas aquí.
 */

const ERROR_POR_TAMANO = [
  { tramo: "menos de 500 hab", n: 4001, mae: "8,53", persistencia: "9,83" },
  { tramo: "500 – 2.000", n: 1871, mae: "4,24", persistencia: "5,88" },
  { tramo: "2.000 – 10.000", n: 1500, mae: "3,07", persistencia: "5,47" },
  { tramo: "más de 10.000", n: 759, mae: "2,36", persistencia: "4,63" },
];

const FUENTES = [
  ["Límites municipales", "IGN / CNIG", "CC BY 4.0"],
  ["Padrón y pirámide de población", "INE", "libre con atribución"],
  ["Estadística de nacimientos y defunciones", "INE", "libre con atribución"],
  ["Renta neta por persona", "INE / AEAT", "libre con atribución"],
  ["Paro registrado", "SEPE", "libre con atribución"],
  ["Alquiler de referencia", "MIVAU (SERPAVI)", "libre con atribución"],
  ["Clima", "AEMET OpenData", "condiciones de AEMET"],
  ["Población extranjera", "INE", "libre con atribución"],
  ["Cobertura de banda ancha", "SETELECO", "libre con atribución"],
  ["Calidad del aire", "EEA", "política de reutilización de la EEA"],
  ["Puntos de interés", "OpenStreetMap", "ODbL — obliga a compartir igual"],
  ["Datos municipales", "Wikidata", "CC0"],
  ["Descripciones e imágenes", "Wikipedia (ES)", "CC BY-SA — obliga a compartir igual"],
  ["Prensa local", "GDELT DOC 2.0", "condiciones de GDELT"],
];

/** Separador de miles español sin depender de `toLocaleString`: el ICU del navegador
 *  puede venir recortado y devolver "4001" en vez de "4.001". */
const miles = (n: number) => n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");

function Seccion({
  icono: Icono,
  titulo,
  children,
}: {
  icono: typeof BookOpen;
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <section className="panel" style={{ padding: 18, marginBottom: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <Icono size={16} strokeWidth={1.75} style={{ color: "var(--accent)" }} />
        <strong style={{ fontSize: 14 }}>{titulo}</strong>
      </div>
      <div style={{ fontSize: 13, lineHeight: 1.65, color: "var(--text)" }}>{children}</div>
    </section>
  );
}

function Aviso({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        padding: "10px 12px",
        margin: "10px 0",
        borderLeft: "3px solid var(--accent)",
        background: "var(--panel-2, rgba(0,80,203,.05))",
        fontSize: 12.5,
        lineHeight: 1.6,
      }}
    >
      <AlertTriangle size={15} strokeWidth={1.75} style={{ flexShrink: 0, marginTop: 2 }} />
      <div>{children}</div>
    </div>
  );
}

export default function Metodologia() {
  return (
    <div style={{ height: "100%", overflowY: "auto", padding: "20px 24px", maxWidth: 860 }}>
      <h1 style={{ fontSize: 20, margin: "0 0 4px" }}>Cómo está hecho esto</h1>
      <p style={{ fontSize: 13, color: "var(--text-2)", margin: "0 0 18px", lineHeight: 1.6 }}>
        Un modelo de despoblación que se vende de más es peor que no tener modelo. Aquí está
        lo que mide, lo que no, y dónde se equivoca.
      </p>

      <Seccion icono={BookOpen} titulo="Qué predice el modelo">
        <p style={{ margin: "0 0 8px" }}>
          La <strong>variación porcentual de población a cinco años</strong> de cada
          municipio, a partir de 17 variables de demografía, economía, vivienda, clima,
          conectividad y aislamiento. El algoritmo es un <em>gradient boosting</em>; lo que
          importa no es eso, sino cómo se valida.
        </p>
        <p style={{ margin: "0 0 8px" }}>
          La validación es <strong>temporal, nunca aleatoria</strong>: cada pliegue entrena
          solo con años anteriores al que valida. Un corte al azar mezclaría el futuro con
          el pasado y daría un número mucho más bonito que no significaría nada.
        </p>
        <p style={{ margin: 0 }}>
          Resultado: <strong>5,80 ± 0,23 puntos porcentuales</strong> de error absoluto
          medio, frente a 7,65 de suponer que nada cambia y 10,02 de extrapolar la
          tendencia reciente. Extrapolar la tendencia es <em>peor</em> que no hacer nada:
          es lo que pasa con poblaciones pequeñas y ruidosas.
        </p>
      </Seccion>

      <Seccion icono={MapPin} titulo="Dónde se equivoca">
        <p style={{ margin: "0 0 10px" }}>
          La cifra global esconde lo importante. El error se concentra justo en los
          municipios pequeños, que son el objeto de este proyecto:
        </p>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
          <thead>
            <tr style={{ textAlign: "left", color: "var(--text-2)" }}>
              <th style={{ padding: "4px 0", fontWeight: 500 }}>Tamaño</th>
              <th style={{ padding: "4px 0", fontWeight: 500 }}>Municipios</th>
              <th style={{ padding: "4px 0", fontWeight: 500 }}>Error del modelo</th>
              <th style={{ padding: "4px 0", fontWeight: 500 }}>Si nada cambiara</th>
            </tr>
          </thead>
          <tbody>
            {ERROR_POR_TAMANO.map((f) => (
              <tr key={f.tramo} style={{ borderTop: "1px solid var(--border)" }}>
                <td style={{ padding: "5px 0" }}>{f.tramo}</td>
                <td style={{ padding: "5px 0" }} className="mono">
                  {miles(f.n)}
                </td>
                <td style={{ padding: "5px 0" }} className="mono">
                  {f.mae} pp
                </td>
                <td style={{ padding: "5px 0", color: "var(--text-2)" }} className="mono">
                  {f.persistencia} pp
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Aviso>
          En un pueblo de 150 habitantes, que se mude una familia es un vuelco del 3 %. Por
          eso cada predicción se muestra con su banda de incertidumbre, y por eso la banda
          es tan ancha en los municipios pequeños. <strong>No es un defecto de la
          interfaz: es la respuesta honesta.</strong>
        </Aviso>
        <p style={{ margin: "10px 0 0" }}>
          Además, los errores <strong>están agrupados en el mapa</strong> (I de Moran =
          0,11, p = 0,001): municipios vecinos fallan en el mismo sentido, lo que significa
          que hay geografía que las variables no capturan. La despoblación es un fenómeno
          comarcal, no municipal.
        </p>
      </Seccion>

      <Seccion icono={AlertTriangle} titulo="El semáforo de riesgo ordena, no cuantifica">
        <p style={{ margin: "0 0 8px" }}>
          El semáforo estima la probabilidad de perder más del 10 % de la población en
          cinco años. Separa bien los municipios en riesgo de los que no (AUC 0,84), y por
          eso la interfaz usa <strong>niveles</strong> —verde, ámbar, rojo— y no el
          porcentaje.
        </p>
        <Aviso>
          Medida sobre un año que el calibrador no había visto, la calibración
          <strong> no mejora</strong> la precisión de la probabilidad, y por encima del
          40 % el modelo promete más de lo que ocurre. <strong>No leas el porcentaje como
          una frecuencia literal.</strong> Es un resultado negativo y se publica igual.
        </Aviso>
      </Seccion>

      <Seccion icono={Database} titulo="Alcance de cada capa">
        <p style={{ margin: "0 0 8px" }}>
          La matriz cubre <strong>8.217 municipios</strong> de toda España desde 2015. Pero
          no todas las capas llegan a todos:
        </p>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li style={{ marginBottom: 6 }}>
            <strong>Prensa local: solo Navarra</strong> (272 municipios, desde 2017). Que un
            municipio de Cuenca no tenga noticias no significa que no pasen cosas allí:
            significa que <em>no hay dato</em>.
          </li>
          <li style={{ marginBottom: 6 }}>
            <strong>Natalidad y mortalidad son provinciales</strong>, no municipales: el INE
            no las publica por municipio en esta serie. La descomposición entre crecimiento
            vegetativo y migratorio es una <em>estimación</em>, y el error es mayor
            precisamente en los municipios pequeños.
          </li>
          <li style={{ marginBottom: 6 }}>
            <strong>Clima y fibra no tienen histórico</strong>: son una foto aplicada a
            todos los años. En el caso de la fibra eso es un riesgo declarado, porque llegó
            antes a los municipios que ya crecían.
          </li>
          <li style={{ marginBottom: 6 }}>
            <strong>Los "factores" de cada municipio son correlación, no causa.</strong> Son
            una pista para investigar, no una explicación.
          </li>
          <li>
            <strong>La prensa se filtra antes de usarse.</strong> Solo el 13,5 % de los
            titulares que la fuente atribuye a un municipio hablan de verdad de él: hay
            muchos homónimos, y nombres como Peralta o Legarda aparecen como apellidos. Un
            clasificador decide cuáles cuentan, y su acierto está medido (95,1 % contra una
            muestra de referencia de 193 titulares). Esa referencia la etiquetó un modelo,
            no una persona, y por eso mide acuerdo entre modelos, no verdad.
          </li>
        </ul>
      </Seccion>

      <Seccion icono={Scale} titulo="Fuentes y licencias">
        <p style={{ margin: "0 0 10px" }}>
          El código es Apache-2.0. Los datos son de quien los produce, con sus propias
          licencias — dos de ellas obligan a compartir igual cualquier derivado.
        </p>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
          <tbody>
            {FUENTES.map(([que, quien, licencia]) => (
              <tr key={que} style={{ borderTop: "1px solid var(--border)" }}>
                <td style={{ padding: "5px 8px 5px 0" }}>{que}</td>
                <td style={{ padding: "5px 8px 5px 0", color: "var(--text-2)" }}>{quien}</td>
                <td style={{ padding: "5px 0", color: "var(--text-2)", fontSize: 11.5 }}>
                  {licencia}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p style={{ margin: "12px 0 0", fontSize: 12, color: "var(--text-2)" }}>
          Este proyecto no redistribuye ningún dato: todo se descarga en tiempo de
          ejecución desde su fuente original.
        </p>
      </Seccion>

      <p style={{ fontSize: 12, color: "var(--text-2)", lineHeight: 1.6, margin: "0 0 24px" }}>
        El informe de evaluación completo —backtest por pliegues, análisis de error,
        diagrama de fiabilidad e importancia de variables— se regenera desde la base de
        datos y vive en <span className="mono">docs/evaluacion/informe.md</span>.
      </p>
    </div>
  );
}
