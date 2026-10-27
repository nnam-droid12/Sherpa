import Link from "next/link";

export default async function ThankYou({ searchParams }: { searchParams: Promise<{ order?: string }> }) {
  const { order } = await searchParams;
  return (
    <main className="container">
      <h1>Thank you!</h1>
      <p>
        Your PayPal order <strong>{order}</strong> is confirmed. We will start baking two days before delivery.
      </p>
      <Link href="/" className="button">
        Back to the bakehouse
      </Link>
    </main>
  );
}
