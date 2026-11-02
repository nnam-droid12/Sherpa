import Link from "next/link";

export default async function ThankYou({ searchParams }: { searchParams: Promise<{ order?: string }> }) {
  const { order } = await searchParams;
  return (
    <main className="container" style={{ maxWidth: 720, textAlign: "center", paddingTop: 80, paddingBottom: 80 }}>
      <p className="eyebrow">Order confirmed</p>
      <h1>Thank you! Your cake is on the schedule.</h1>
      <p className="muted">
        Your PayPal order <strong>{order}</strong> is confirmed. We&apos;ll start baking the day before delivery and
        text you when your cake is on its way.
      </p>
      <Link href="/" className="button">
        Back to the bakehouse
      </Link>
    </main>
  );
}
