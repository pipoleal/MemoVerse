import CheckoutView from "@/components/checkout/CheckoutView";

type PageProps = {
  params: Promise<{ draftId: string }>;
};

export default async function CheckoutPage({ params }: PageProps) {
  const { draftId } = await params;

  return <CheckoutView draftId={draftId} />;
}
