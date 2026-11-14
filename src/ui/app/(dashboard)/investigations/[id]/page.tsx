import { DetailView } from "../../_components/detail-view";

export default async function InvestigationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <DetailView id={decodeURIComponent(id)} />;
}
