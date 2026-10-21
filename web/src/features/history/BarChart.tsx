import { useId } from "react";

export interface Bar {
  id: string;
  label: string;
  value: number | null;
  /** Value as text, exactly as shown in the table (for example "18 of 19 commits"). */
  display: string;
}

/**
 * Horizontal bar chart with a text equivalent. The SVG is decorative for assistive tech (aria-hidden) and the
 * table below it carries every value, so nothing is available only as a picture.
 */
export function BarChart({ title, bars, unit, max }: { title: string; bars: readonly Bar[]; unit: string; max?: number }) {
  const cap = useId();
  const top = max ?? Math.max(0, ...bars.map((b) => b.value ?? 0));
  const shown = bars.filter((b) => b.value !== null);
  const row = 22;
  return (
    <figure className="rounded-lg border border-line bg-surface p-3" aria-labelledby={cap} data-testid="bar-chart">
      <figcaption id={cap} className="text-sm font-semibold">
        {title}
      </figcaption>
      {shown.length > 0 && top > 0 ? (
        <svg className="mt-2 w-full" viewBox={`0 0 100 ${shown.length * row}`} preserveAspectRatio="none" height={shown.length * row} aria-hidden="true" focusable="false">
          {shown.map((b, i) => (
            <rect key={b.id} x={0} y={i * row + 4} height={row - 8} width={Math.max(0.5, ((b.value ?? 0) / top) * 100)} className="fill-accent" rx={1} />
          ))}
        </svg>
      ) : null}
      <table className="mt-2 w-full text-left text-sm">
        <caption className="sr-only">{title}, as a table</caption>
        <thead className="text-xs text-muted">
          <tr>
            <th scope="col" className="py-1 pr-2 font-medium">
              Item
            </th>
            <th scope="col" className="py-1 text-right font-medium">
              {unit}
            </th>
          </tr>
        </thead>
        <tbody>
          {bars.map((b) => (
            <tr key={b.id} className="border-t border-line">
              <th scope="row" className="break-all py-1 pr-2 font-mono text-xs font-normal">
                {b.label}
              </th>
              <td className="py-1 text-right tabular-nums">{b.value === null ? "not reported" : b.display}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
