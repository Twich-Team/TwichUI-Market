import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart, BarChart, PieChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  AriaComponent,
  LegendComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";
echarts.use([
  LineChart,
  BarChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  AriaComponent,
  LegendComponent,
  CanvasRenderer,
]);
export default function ChartEngine({
  option,
  label,
  onZoom,
  onSelect,
  touchInspect = false,
}: {
  option: EChartsCoreOption;
  label: string;
  onZoom?: (start: number, end: number) => void;
  onSelect?: (index: number) => void;
  touchInspect?: boolean;
}) {
  const container = useRef<HTMLDivElement>(null),
    chart = useRef<echarts.EChartsType | null>(null),
    zoomCallback = useRef(onZoom);
  zoomCallback.current = onZoom;
  const touchStart = useRef<{ x: number; y: number } | null>(null);
  const selectCallback = useRef(onSelect);
  selectCallback.current = onSelect;
  useEffect(() => {
    const instance = echarts.init(container.current!, undefined, {
      renderer: "canvas",
    });
    chart.current = instance;
    instance.on("click", (event) => {if(typeof event.dataIndex === "number") selectCallback.current?.(event.dataIndex);});
    instance.on("datazoom", (event) => {
      const zoom = event as {
        start?: number;
        end?: number;
        batch?: { start: number; end: number }[];
      };
      const value = zoom.batch?.[0] || zoom;
      if (value.start !== undefined && value.end !== undefined)
        zoomCallback.current?.(value.start, value.end);
    });
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(container.current!);
    return () => {
      observer.disconnect();
      instance.dispose();
      chart.current = null;
    };
  }, []);
  useEffect(() => {
    chart.current?.setOption(
      {
        ...option,
        aria: { enabled: true, label: { enabled: true, description: label } },
      },
      { replaceMerge: ["series"], silent: true },
    );
  }, [option]);
  return (
    <div
      ref={container}
      className="interactive-chart"
      role="img"
      aria-label={label}
      onPointerDown={touchInspect ? (event) => {
        if (event.pointerType === "touch") touchStart.current = { x: event.clientX, y: event.clientY };
      } : undefined}
      onPointerCancel={touchInspect ? () => { touchStart.current = null; } : undefined}
      onPointerUp={touchInspect ? (event) => {
        const origin = touchStart.current;
        touchStart.current = null;
        if (!origin || Math.hypot(event.clientX - origin.x, event.clientY - origin.y) > 10) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        chart.current?.dispatchAction({ type: "showTip", x: event.clientX - bounds.left, y: event.clientY - bounds.top });
      } : undefined}
    />
  );
}
