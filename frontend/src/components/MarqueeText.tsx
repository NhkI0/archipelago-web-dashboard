import { useLayoutEffect, useRef, useState, type CSSProperties } from "react";

type Props = {
  children: string;
  className?: string;
  speedPxPerSec?: number;
  pausePerEndMs?: number;
};

export default function MarqueeText({
  children,
  className,
  speedPxPerSec = 40,
  pausePerEndMs = 1200,
}: Props) {
  const wrapRef = useRef<HTMLSpanElement | null>(null);
  const innerRef = useRef<HTMLSpanElement | null>(null);
  const [shift, setShift] = useState(0);

  useLayoutEffect(() => {
    const wrap = wrapRef.current;
    const inner = innerRef.current;
    if (!wrap || !inner) return;

    const measure = () => {
      const overflow = inner.scrollWidth - wrap.clientWidth;
      setShift(overflow > 1 ? overflow : 0);
    };

    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(wrap);
    ro.observe(inner);
    return () => ro.disconnect();
  }, [children]);

  const animating = shift > 0;
  const travelSec = animating ? shift / speedPxPerSec : 0;
  const pauseSec = (pausePerEndMs / 1000) * 2;
  const duration = animating ? travelSec * 2 + pauseSec : 0;

  const style: CSSProperties = animating
    ? ({
        ["--mq-shift" as never]: `-${shift}px`,
        ["--mq-duration" as never]: `${duration}s`,
      } as CSSProperties)
    : {};

  return (
    <span
      ref={wrapRef}
      className={`inline-block max-w-full overflow-hidden align-bottom ${className ?? ""}`}
    >
      <span
        ref={innerRef}
        className={`inline-block whitespace-nowrap ${animating ? "mq-anim" : ""}`}
        style={style}
      >
        {children}
      </span>
    </span>
  );
}
