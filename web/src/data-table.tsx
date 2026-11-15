import { useMemo, useState } from "react";
import {
  ColumnDef,
  OnChangeFn,
  PaginationState,
  SortingState,
  VisibilityState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { Menu } from "@base-ui/react/menu";
export function DataTable<T>({
  data,
  columns,
  label,
  initialSorting = [],
  getRowId,
  server,
}: {
  data: T[];
  columns: ColumnDef<T>[];
  label: string;
  initialSorting?: SortingState;
  getRowId?: (row: T) => string;
  server?: {
    rowCount: number;
    pagination: PaginationState;
    sorting: SortingState;
    onPaginationChange: OnChangeFn<PaginationState>;
    onSortingChange: OnChangeFn<SortingState>;
  };
}) {
  const [filter, setFilter] = useState(""),
    [sorting, setSorting] = useState<SortingState>(initialSorting),
    [visibility, setVisibility] = useState<VisibilityState>({});
  const rows = useMemo(() => data, [data]);
  const table = useReactTable({
    data: rows,
    getRowId,
    columns,
    state: {
      globalFilter: filter,
      sorting: server?.sorting ?? sorting,
      columnVisibility: visibility,
      ...(server ? { pagination: server.pagination } : {}),
    },
    onGlobalFilterChange: setFilter,
    onSortingChange: server?.onSortingChange ?? setSorting,
    onPaginationChange: server?.onPaginationChange,
    manualPagination: !!server,
    manualSorting: !!server,
    rowCount: server?.rowCount,
    onColumnVisibilityChange: setVisibility,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 25 } },
  });
  return (
    <div className="managed-table">
      <div className="managed-table-controls">
        {!server && (
          <label>
            Search {label}
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              maxLength={100}
            />
          </label>
        )}
        <Menu.Root>
          <Menu.Trigger>Columns</Menu.Trigger>
          <Menu.Portal>
            <Menu.Positioner sideOffset={6}>
              <Menu.Popup className="table-menu">
                {table
                  .getAllLeafColumns()
                  .filter((c) => c.getCanHide())
                  .map((column) => (
                    <Menu.CheckboxItem
                      key={column.id}
                      checked={column.getIsVisible()}
                      onCheckedChange={(value) =>
                        column.toggleVisibility(value)
                      }
                    >
                      {typeof column.columnDef.header === "string"
                        ? column.columnDef.header
                        : column.id}
                      <Menu.CheckboxItemIndicator>
                        {" "}
                        ✓
                      </Menu.CheckboxItemIndicator>
                    </Menu.CheckboxItem>
                  ))}
              </Menu.Popup>
            </Menu.Positioner>
          </Menu.Portal>
        </Menu.Root>
      </div>
      <div
        className="table-scroll"
        role="region"
        aria-label={label}
        tabIndex={0}
      >
        <table aria-label={label}>
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => (
                  <th
                    key={header.id}
                    scope="col"
                    className={
                      (header.column.columnDef.meta as { numeric?: boolean })
                        ?.numeric
                        ? "numeric"
                        : undefined
                    }
                    aria-sort={
                      header.column.getIsSorted() === "asc"
                        ? "ascending"
                        : header.column.getIsSorted() === "desc"
                          ? "descending"
                          : "none"
                    }
                  >
                    {header.column.getCanSort() ? (
                      <button
                        className="table-sort"
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                        {header.column.getIsSorted() === "asc"
                          ? " ↑"
                          : header.column.getIsSorted() === "desc"
                            ? " ↓"
                            : " ↕"}
                      </button>
                    ) : (
                      flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className={
                      (cell.column.columnDef.meta as { numeric?: boolean })
                        ?.numeric
                        ? "numeric"
                        : undefined
                    }
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!table.getFilteredRowModel().rows.length && (
        <p className="empty">No matching records.</p>
      )}
      <div className="table-pagination">
        <span>
          {server?.rowCount ?? table.getFilteredRowModel().rows.length} records
          · Page {table.getState().pagination.pageIndex + 1} of{" "}
          {Math.max(1, table.getPageCount())}
        </span>
        <button
          disabled={!table.getCanPreviousPage()}
          onClick={() => table.previousPage()}
        >
          Previous {label}
        </button>
        <button
          disabled={!table.getCanNextPage()}
          onClick={() => table.nextPage()}
        >
          Next {label}
        </button>
      </div>
    </div>
  );
}
