"use client";

import Link from "next/link";
import { ScoreBar } from "@/components/ranking/ScoreBar";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import type { Lens, RankItem, RankLens, RankResponse } from "@/lib/api/types";
import { LENSES, LENS_COLORS, LENS_LABELS } from "@/lib/constants";
import { formatConfidence, formatScore } from "@/lib/format";

interface RankTableProps {
  data: RankResponse;
  lens: RankLens;
  onSelect: (item: RankItem) => void;
}

function LensScoreCells({ item }: { item: RankItem }) {
  return (
    <>
      {(LENSES as readonly Lens[]).map((lens) => (
        <Td key={lens} className="mono text-muted text-right">
          {formatScore(item.lens_scores[lens])}
        </Td>
      ))}
    </>
  );
}

export function RankTable({ data, lens, onSelect }: RankTableProps) {
  return (
    <Table label="Ranked investigations">
      <thead>
        <tr>
          <Th className="w-12">#</Th>
          <Th>Investigation</Th>
          <Th className="min-w-56">Score (0-100)</Th>
          {LENSES.map((item) => (
            <Th key={item} className="text-right">
              <span
                aria-hidden
                className="mr-1.5 inline-block size-1.5 rounded-full"
                style={{ backgroundColor: LENS_COLORS[item] }}
              />
              {LENS_LABELS[item]}
            </Th>
          ))}
          <Th className="text-right">Confidence</Th>
          <Th>
            <span className="sr-only">Evidence</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {data.items.map((item) => (
          <Tr key={item.acronym} data-testid="rank-row" data-acronym={item.acronym}>
            <Td className="mono text-muted">{item.rank}</Td>
            <Td>
              <Link
                href={`/investigations/${encodeURIComponent(item.acronym)}`}
                className="hover:text-accent font-medium"
              >
                {item.acronym}
              </Link>
              <p className="text-muted max-w-sm truncate text-xs">{item.title}</p>
            </Td>
            <Td>
              <ScoreBar item={item} lens={lens} lensWeights={data.weights_used.lens_weights} />
            </Td>
            <LensScoreCells item={item} />
            <Td className="mono text-right">{formatConfidence(item.confidence)}</Td>
            <Td>
              <button
                type="button"
                onClick={() => onSelect(item)}
                className="text-caption text-cool font-medium hover:underline"
              >
                Evidence
              </button>
            </Td>
          </Tr>
        ))}
      </tbody>
    </Table>
  );
}
