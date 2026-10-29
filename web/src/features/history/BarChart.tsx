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
  return (
    <figure className="min-w-0 max-w-full overflow-hidden rounded-lg border border-line bg-surface p-3" aria-labelledby={cap} data-testid="bar-chart">
      <figcaption id={cap} className="text-sm font-semibold">
        {title}
      </figcaption>
      {shown.length > 0 && top > 0 ? (
        <ul className="mt-3 flex min-w-0 flex-col gap-2" aria-hidden="true">
          {shown.map((b) => (
            <li key={b.id} className="min-w-0">
              <span className="block max-w-full truncate font-mono text-xs text-ink">{b.label}</span>
              <span className="mt-1 block h-2 overflow-hidden rounded-full bg-white/10">
                <span className="block h-2 rounded-full bg-observed" style={{ width: `${Math.max(4, ((b.value ?? 0) / top) * 100)}%` }} />
              </span>
              <span className="mt-1 block break-words text-xs text-ink-2">{b.display}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="relative h-0 overflow-hidden">
      <table className="sr-only">
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
      </div>
    </figure>
  );
}
