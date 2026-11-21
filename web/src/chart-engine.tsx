import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart, BarChart } from "echarts/charts";
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
}: {
  option: EChartsCoreOption;
  label: string;
  onZoom?: (start: number, end: number) => void;
}) {
  const container = useRef<HTMLDivElement>(null),
    chart = useRef<echarts.EChartsType | null>(null),
    zoomCallback = useRef(onZoom);
  zoomCallback.current = onZoom;
  useEffect(() => {
    const instance = echarts.init(container.current!, undefined, {
      renderer: "canvas",
    });
    chart.current = instance;
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
    />
  );
}
