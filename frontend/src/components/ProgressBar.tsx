type Props = { value: number; total: number };

export default function ProgressBar({ value, total }: Props) {
  const pct = total > 0 ? Math.min(100, (100 * value) / total) : 0;
  return (
    <div className="h-1.5 w-full rounded-pill bg-hairline overflow-hidden">
      <div
        className="h-full rounded-pill bg-primary"
        style={{ width: `${pct}%`, transition: "width 400ms ease" }}
      />
    </div>
  );
}
