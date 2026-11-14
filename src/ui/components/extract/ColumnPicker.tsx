"use client";

import { BookOpen } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/input";
import { DataPanel } from "@/components/ui/panel-state";
import { Sheet } from "@/components/ui/sheet";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { useDictionary } from "@/lib/api/hooks";
import type { ColumnInfo } from "@/lib/api/types";
import { parseList, useUrlState } from "@/lib/use-url-state";

function DictionaryTable({ columns }: { columns: ColumnInfo[] }) {
  return (
    <Table>
      <thead>
        <tr>
          <Th>Column</Th>
          <Th>Unit</Th>
          <Th>Description</Th>
        </tr>
      </thead>
      <tbody>
        {columns.map((column) => (
          <Tr key={column.name}>
            <Td>
              <span className="font-medium">{column.label}</span>
              <span className="mono text-muted block text-xs">{column.name}</span>
            </Td>
            <Td className="mono">{column.unit ?? "none"}</Td>
            <Td className="text-muted">{column.description}</Td>
          </Tr>
        ))}
      </tbody>
    </Table>
  );
}

export function ColumnPicker() {
  const dictionary = useDictionary();
  const { params, patch } = useUrlState();
  const [isDictionaryOpen, setDictionaryOpen] = useState(false);
  const selected = parseList(params.get("cols"));
  const toggle = (name: string) =>
    patch({
      cols: (selected.includes(name)
        ? selected.filter((item) => item !== name)
        : [...selected, name]
      ).join(","),
    });

  return (
    <Card>
      <CardHeader
        title="Columns"
        description={
          selected.length
            ? `${selected.length} selected`
            : "Default columns are used when none are selected."
        }
        action={
          <Button size="sm" onClick={() => setDictionaryOpen(true)}>
            <BookOpen className="size-3.5" aria-hidden /> Data dictionary
          </Button>
        }
      />
      <DataPanel
        query={dictionary}
        isEmpty={(data) => data.columns.length === 0}
        emptyMessage="No columns are available."
      >
        {(data) => (
          <>
            <div className="grid max-h-64 grid-cols-1 gap-x-4 overflow-y-auto sm:grid-cols-2">
              {data.columns.map((column) => (
                <Checkbox
                  key={column.name}
                  label={column.unit ? `${column.label} (${column.unit})` : column.label}
                  checked={selected.includes(column.name)}
                  onChange={() => toggle(column.name)}
                />
              ))}
            </div>
            <Sheet
              open={isDictionaryOpen}
              onOpenChange={setDictionaryOpen}
              title="Data dictionary"
              description="Every column available for preview and export."
              widthClass="max-w-3xl"
            >
              <DictionaryTable columns={data.columns} />
            </Sheet>
          </>
        )}
      </DataPanel>
    </Card>
  );
}
