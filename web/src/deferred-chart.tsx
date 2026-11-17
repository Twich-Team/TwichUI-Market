import { lazy, Suspense, useRef, useState, useEffect, type ComponentProps } from "react";
const ChartEngine = lazy(() => import("./chart-engine"));
export function DeferredChart(props: ComponentProps<typeof ChartEngine>) {
  const container = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (visible || !container.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "150px" },
    );
    observer.observe(container.current);
    return () => observer.disconnect();
  }, [visible]);
  return (
    <div ref={container} className="chart-viewport">
      {visible ? (
        <Suspense fallback={<p role="status">Opening interactive chart…</p>}>
          <ChartEngine {...props} />
        </Suspense>
      ) : (
        <button className="secondary" onClick={() => setVisible(true)}>
          Load {props.label.toLowerCase()}
        </button>
      )}
    </div>
  );
}
