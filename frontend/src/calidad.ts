import type { SerieRow } from "./types";

/**
 * Qué se puede decir de la última renta de la serie: la nota que la acompaña y si tiene
 * sentido compararla con la del año anterior.
 *
 * Desde 2020 el INE no oculta la renta de los municipios de menos de 100 habitantes: les
 * asigna la media de los de ese tamaño de su provincia (2020 y 2021) o de su comarca
 * agraria (desde 2022). Es uno de cada seis municipios, y la ficha la mostraba como la
 * renta del municipio: 22 pueblos de Tierra Estella con los mismos 18.318 €.
 *
 * La variación tampoco significa nada si uno de los dos años es asignado: comparar la
 * media comarcal con la provincial del año anterior, o con el dato propio de cuando el
 * municipio pasaba de 100 habitantes, no dice nada del municipio.
 */
export function notaRenta(serie: SerieRow[]): { nota: string | undefined; mostrarDelta: boolean } | null {
  const conRenta = serie.filter((r) => r.renta != null);
  if (!conRenta.length) return null;
  const ultima = conRenta[conRenta.length - 1];
  const anterior = conRenta.length > 1 ? conRenta[conRenta.length - 2] : null;
  const mostrarDelta = !ultima.renta_asignada && !anterior?.renta_asignada;

  if (ultima.renta_asignada) {
    const zona = ultima.anio >= 2022 ? "su comarca agraria" : "su provincia";
    return {
      nota: `no es la del municipio: el INE le asigna la media de los de menos de 100 hab. de ${zona}`,
      mostrarDelta,
    };
  }
  if (serie.some((r) => r.renta_secreto)) {
    return { nota: "algún año va sin publicar por secreto estadístico", mostrarDelta };
  }
  return { nota: undefined, mostrarDelta };
}
