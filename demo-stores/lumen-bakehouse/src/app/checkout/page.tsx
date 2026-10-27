import { Checkout } from "@/components/checkout";

export const dynamic = "force-dynamic";

export default function CheckoutPage() {
  return <Checkout clientId={process.env.PAYPAL_CLIENT_ID || "sb"} />;
}
